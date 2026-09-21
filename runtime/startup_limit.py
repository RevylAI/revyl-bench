"""Optional control-plane startup throttle, shared by rollout CLI processes.

Set RB_MAX_CONCURRENT_STARTUPS=4 on the resource server and use one shared
RB_STARTUP_LOCK_DIR for its children. Every cooperating process must use the same
cap and directory; change them only while startup admission is idle. No files or
locks are used when the cap is unset. This does not reduce the episode ceiling.

The default permit wait is bounded to 600 seconds (RB_STARTUP_WAIT_TIMEOUT_S).
Waiting consumes the existing outer episode timeout, which already includes
provisioning; it does not extend that timeout or the agent's execution budget.
Linux flock releases permits on exceptions, early returns and process death.
"""
from contextlib import contextmanager
import math
import os
from pathlib import Path
import tempfile
import time


@contextmanager
def startup_permit(*, environ=None):
    env = os.environ if environ is None else environ
    value = env.get("RB_MAX_CONCURRENT_STARTUPS")
    if value is None:
        yield
        return
    cap = int(value)
    if cap < 1:
        raise ValueError("RB_MAX_CONCURRENT_STARTUPS must be a positive integer")
    timeout = float(env.get("RB_STARTUP_WAIT_TIMEOUT_S", "600"))
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("RB_STARTUP_WAIT_TIMEOUT_S must be positive and finite")
    import fcntl  # Enabled throttling is a Linux control-plane feature.
    directory = Path(env.get("RB_STARTUP_LOCK_DIR") or
                     Path(tempfile.gettempdir()) / f"revyl-rollout-startups-{os.getuid()}")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    deadline = time.monotonic() + timeout
    acquired = None
    try:
        while acquired is None:
            for slot in range(cap):
                # Non-inheritable descriptors prevent exec'd AWS/SSH children
                # keeping a permit alive after the launcher exits.
                fd = os.open(directory / f"slot-{slot}.lock", os.O_CREAT | os.O_RDWR, 0o600)
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    os.close(fd)
                except BaseException:
                    os.close(fd)
                    raise
                else:
                    acquired = fd
                    break
            if acquired is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"Startup permit wait exceeded {timeout:g}s (cap={cap})")
                time.sleep(min(0.1, remaining))
        yield
    finally:
        if acquired is not None:
            os.close(acquired)
