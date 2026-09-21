"""bench.eas — build one iOS *simulator* artifact on EAS cloud from a source tree.

Two profiles exist in every scaffold's eas.json:
  * `preview`               developmentClient=false, ios.simulator=true  → BAKED JS. This is
                            the only thing the grader ever runs (a dev-client on the isolated
                            grading simulator would sit at the "searching for development
                            servers" launcher and fail every step).
  * `development-simulator` developmentClient=true                        → dev-client shell for
                            `revyl dev` hot reload; built ONCE per task at provisioning, never
                            by the runner.

Credentials: EXPO_TOKEN is passed explicitly (never read from ambient env here) and only
the runner container / the provisioning machine ever hold it. EAS packages the working tree
via git, so the tree must be a committed git repo — the runner untars `git archive` output
and re-inits a throwaway repo before building (see runner/grade.py).
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import shutil as _shutil
# On Windows the npm shim is `eas.cmd` / the CLI may be `revyl.exe`; subprocess needs the
# resolved path (no shell). Inside the Linux containers which() just returns the bare name.
EAS_BIN = os.environ.get("EAS_BIN") or _shutil.which("eas") or "eas"


class EasError(RuntimeError):
    pass


@dataclass
class EasBuild:
    build_id: str
    status: str            # FINISHED | ERRORED | CANCELED | ...
    artifact_url: str | None
    log_url: str | None
    error_tail: str        # last lines of `eas build:view` message / our stderr, for feedback


def _env(token: str) -> dict:
    env = dict(os.environ)
    if token:
        env["EXPO_TOKEN"] = token
    else:
        # Provisioning on a workstation runs under the interactive `eas login`; only the
        # runner container is REQUIRED to have a token.
        env.pop("EXPO_TOKEN", None)
    # eas-cli treats ANY value of EAS_NO_VCS as "no VCS" (even "0") → unset it: we WANT the
    # git-based file listing (respects .gitignore; the runner commits the untarred tree first).
    env.pop("EAS_NO_VCS", None)
    env["CI"] = "1"             # non-interactive prompts
    return env


def ensure_node_modules(tree: Path, *, log=print, cache_dir: str | None = None) -> None:
    """`eas build` evaluates the app config with the project's own `expo` package and detects
    `expo-dev-client` from node_modules — so a tree without node_modules cannot be built,
    even though the cloud builder installs deps again. Scaffolds are committed WITHOUT
    node_modules and `git archive` submissions never contain them → install here.
    package-lock.json is part of every tree, so `npm ci` is exact. cache_dir (runner:
    /tmp/npm-cache) makes submissions 2..k fast."""
    if (tree / "node_modules" / "expo").exists():
        return
    npm = _shutil.which("npm") or "npm"
    env = dict(os.environ)
    if cache_dir:
        env["npm_config_cache"] = cache_dir
    log(f"[npm] npm ci in {tree} …")
    p = subprocess.run([npm, "ci", "--no-audit", "--no-fund", "--loglevel=error"], cwd=str(tree), env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    if p.returncode != 0:
        raise EasError(f"npm ci failed rc={p.returncode}: {(p.stderr or p.stdout)[-1500:]}")


def _last_json(s: str):
    s = s.lstrip("﻿")
    dec = json.JSONDecoder()
    for i, ch in enumerate(s):
        if ch in "{[":
            try:
                obj, end = dec.raw_decode(s[i:])
                if s[i + end:].strip() == "":
                    return obj
            except json.JSONDecodeError:
                continue
    raise EasError(f"no JSON in eas output: {s[:300]!r}")


def queue_build(tree: Path, *, profile: str, token: str, platform: str = "ios") -> str:
    """`eas build --no-wait --json` → build id. Raises EasError on a rejected queue."""
    cmd = [EAS_BIN, "build", "--platform", platform, "--profile", profile,
           "--non-interactive", "--no-wait", "--json"]
    p = subprocess.run(cmd, cwd=str(tree), env=_env(token), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1200)
    if p.returncode != 0:
        raise EasError(f"eas build queue failed rc={p.returncode}: {(p.stderr or p.stdout)[-1500:]}")
    d = _last_json(p.stdout)
    b = d[0] if isinstance(d, list) else d
    return b["id"]


def view_build(build_id: str, *, token: str, cwd: Path | None = None) -> dict:
    # cwd matters: eas-cli refuses "Run this command inside a project directory" otherwise.
    p = subprocess.run([EAS_BIN, "build:view", build_id, "--json"], env=_env(token),
                       cwd=str(cwd) if cwd else None,
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=120)
    if p.returncode != 0:
        raise EasError(f"eas build:view {build_id} rc={p.returncode}: {p.stderr[-500:]}")
    return _last_json(p.stdout)


def wait_build(build_id: str, *, token: str, poll_s: int = 60, timeout_s: int = 3600,
               log=print, cwd: Path | None = None) -> EasBuild:
    """Poll until FINISHED / ERRORED / CANCELED. Cloud builds take 8–25 min; a poll error
    is transient (network) and just retried on the next tick."""
    t0 = time.time()
    while True:
        try:
            d = view_build(build_id, token=token, cwd=cwd)
            status = d.get("status", "")
        except EasError as e:
            status, d = "POLL_ERR", {"error": str(e)}
        log(f"[eas] {time.strftime('%H:%M:%S')} {build_id} status={status}")
        if status == "FINISHED":
            art = (d.get("artifacts") or {}).get("buildUrl")
            return EasBuild(build_id, status, art, (d.get("logFiles") or [None])[0]
                            if isinstance(d.get("logFiles"), list) else None, "")
        if status in ("ERRORED", "CANCELED"):
            msg = d.get("error") or {}
            tail = json.dumps(msg)[-1500:] if msg else status
            return EasBuild(build_id, status, None, None, tail)
        if time.time() - t0 > timeout_s:
            return EasBuild(build_id, "TIMEOUT", None, None, f"no terminal status after {timeout_s}s")
        time.sleep(poll_s)


def build(tree: Path, *, profile: str, token: str, log=print, timeout_s: int = 3600,
          npm_cache: str | None = None) -> EasBuild:
    """npm ci (if needed) + queue + wait in one call. Never raises on a build failure —
    returns status so the caller can turn it into a `build_failed` verdict (counts against
    the cap; the agent gets the error tail as its feedback)."""
    ensure_node_modules(tree, log=log, cache_dir=npm_cache)
    bid = queue_build(tree, profile=profile, token=token)
    log(f"[eas] queued {profile} build {bid}")
    return wait_build(bid, token=token, log=log, timeout_s=timeout_s, cwd=tree)


def whoami(token: str, *, attempts: int = 3, timeout_s: int = 120) -> str:
    """eas.CMD cold-starts slowly on Windows and CONTENDS on the npm cache lock when two
    launches run it concurrently — two parallel launches both timed out at 60 s (and one
    serial launch hit it as well). Longer timeout + retries: a wrong token still fails fast with rc != 0."""
    last: Exception | None = None
    for _ in range(attempts):
        try:
            p = subprocess.run([EAS_BIN, "whoami"], env=_env(token), capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout_s)
            if p.returncode != 0:
                raise EasError(f"eas whoami failed: {p.stderr[-300:]}")
            return p.stdout.strip().splitlines()[-1]
        except subprocess.TimeoutExpired as e:
            last = e
    raise EasError(f"eas whoami timed out {attempts}x at {timeout_s}s: {last}")
