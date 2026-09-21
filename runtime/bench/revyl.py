"""bench.revyl — thin subprocess wrappers around the revyl CLI (pinned to image/REVYL_CLI_VERSION).

Every function takes the API key EXPLICITLY (`key=`) and sets it as REVYL_API_KEY for that
one subprocess only. Nothing here ever reads a key from the ambient environment: the whole
integrity story is "the grading key exists in exactly one process", and
an implicit env lookup is how a key leaks into the wrong call.

Output parsing: the CLI prints human progress lines ("Searching for workflow...") on some
paths even with --json, and Windows builds emit a UTF-8 BOM. `_json()` therefore takes the
LAST balanced JSON value in stdout rather than json.loads(stdout). Shapes below were
captured live on 2026-08-19 and are asserted where we depend on them.

Project context (measured on CLI 0.1.95/0.1.96, 2026-08-25): `-C <dir>` is only needed
when the command
reads or writes PROJECT state — `test list/push/pull`, every `device *` (the per-project
.revyl/device-sessions.json), every `dev *`. Those commands REFUSE to run if the config
there is in the legacy shape (project.name / build.system / hotreload …); the canonical
shape is project.id + session.idle_timeout_seconds + build.framework/profiles. Org-level
commands (`auth status`, `app *`, `build list/upload/status`, `workflow *`, `test run`,
`test report <task_id>`) need NO project at all and run fine with chdir=None from a dir with
no .revyl/. The runner therefore passes chdir=None for grading: the submission tree's config
is agent-controlled and must never be able to gate (or steer) a grade.

The ONE exception is `revyl build --remote` (build_remote below): it is a project command —
it reads `build.profiles.<profile>.<platform>` from `-C <tree>/.revyl/config.yaml` and there is
no `--app` flag on 0.1.96, so the grading app id can only reach it through that file. The
runner therefore OVERWRITES the submission tree's config with the image-owned recipe
(bench/recipes.py, runner/recipes/expo-preview.yaml.tmpl) immediately before calling it, and
logs the recipe's sha256 — see runner/grade.py step 4.

Version pin: PINNED_VERSION below is read from image/REVYL_CLI_VERSION (the single source of
truth; the Dockerfiles assert it at build time, guards assert it at launch). The server
also enforces a MINIMUM version server-side (an older client is refused with the message
"This Revyl CLI version is no longer compatible"), which is why the guard makes
one authenticated call rather than trusting `--version` alone.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

import shutil as _shutil
# On Windows the npm shim is `eas.cmd` / the CLI may be `revyl.exe`; subprocess needs the
# resolved path (no shell). Inside the Linux containers which() just returns the bare name.
REVYL_BIN = os.environ.get("REVYL_BIN") or _shutil.which("revyl") or "revyl"

# The pin file: runtime/image/REVYL_CLI_VERSION on a checkout, /app/image/REVYL_CLI_VERSION
# inside the runner image (Dockerfile.runner COPYs it there). One line, e.g. "v0.1.96".
PIN_FILE = Path(__file__).resolve().parents[1] / "image" / "REVYL_CLI_VERSION"
PINNED_VERSION = PIN_FILE.read_text(encoding="utf-8").strip() if PIN_FILE.exists() else ""


def version(bin_path: str | None = None) -> str:
    """Installed CLI version as printed by `revyl --version` ("revyl version v0.1.96" -> "v0.1.96").
    No auth, no project needed. Empty string if the binary is missing or prints something else."""
    try:
        p = subprocess.run([bin_path or REVYL_BIN, "--version"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    m = re.search(r"v\d+\.\d+\.\d+", p.stdout + p.stderr)
    return m.group(0) if m else ""


class RevylError(RuntimeError):
    def __init__(self, msg: str, *, stdout: str = "", stderr: str = "", rc: int | None = None):
        super().__init__(msg)
        self.stdout, self.stderr, self.rc = stdout, stderr, rc


def _run(args: list[str], *, key: str, chdir: str | Path | None = None, timeout: int = 300,
         check: bool = True) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["REVYL_API_KEY"] = key
    # The CLI keeps a keyring/config login on some machines; the env key wins ("auth_method":
    # "env" in `auth status --json`), which is exactly the behaviour we rely on.
    cmd = [REVYL_BIN, *args]
    if chdir:
        cmd += ["-C", str(chdir)]
    p = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    if check and p.returncode != 0 and not _has_json(p.stdout):
        raise RevylError(f"revyl {' '.join(args)} failed rc={p.returncode}: {p.stderr.strip()[-800:]}",
                         stdout=p.stdout, stderr=p.stderr, rc=p.returncode)
    return p


def _has_json(s: str) -> bool:
    return "{" in s or "[" in s


def _json(stdout: str) -> Any:
    """Return the last complete JSON value in stdout. Tolerates BOM, progress lines,
    trailing newlines. Raises RevylError if nothing parses."""
    s = stdout.lstrip("﻿")
    # Try whole string first (fast path).
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # Walk candidate start positions from the left; the first that parses to the end wins.
    dec = json.JSONDecoder()
    for i, ch in enumerate(s):
        if ch in "{[":
            try:
                obj, end = dec.raw_decode(s[i:])
                if s[i + end:].strip() == "":
                    return obj
            except json.JSONDecodeError:
                continue
    raise RevylError(f"no JSON in revyl output: {s[:300]!r}")


# ---------------------------------------------------------------------------------------
# auth / org
# ---------------------------------------------------------------------------------------
def auth_status(key: str) -> dict:
    """{'authenticated', 'email', 'org_id', 'org_name', 'auth_method', ...}"""
    return _json(_run(["auth", "status", "--json"], key=key).stdout)


# ---------------------------------------------------------------------------------------
# apps / builds
# ---------------------------------------------------------------------------------------
def app_list(key: str, chdir: str | Path) -> list[dict]:
    """[{'id','name','platform','versions_count'}, ...]"""
    d = _json(_run(["app", "list", "--json"], key=key, chdir=chdir).stdout)
    return d["apps"] if isinstance(d, dict) else d


def app_create(key: str, chdir: str | Path, name: str, platform: str = "ios") -> dict:
    d = _json(_run(["app", "create", "--name", name, "--platform", platform, "--json"],
                   key=key, chdir=chdir).stdout)
    return d


def build_list(key: str, chdir: str | Path, app_id: str) -> list[dict]:
    """[{'id'|'version_id', 'version'|'name', ...}] — shape captured: {'app_id','count','versions':[...]}"""
    d = _json(_run(["build", "list", "--app", app_id, "--json"], key=key, chdir=chdir).stdout)
    return d.get("versions", []) if isinstance(d, dict) else d


def build_upload_url(key: str, chdir: str | Path | None, *, url: str, app_id: str, version: str,
                     platform: str = "ios", set_current: bool = False) -> str:
    """Register a remote artifact (EAS build url) as a build version; returns build_version_id.
    Needs no project (chdir=None ok): --app names the target explicitly. Note: uploading from
    a git checkout stamps branch/commit into the build metadata.

    --no-set-current: the grading app's "current" build must never become a contestant's
    (and, on the agent org, the dev app's current must stay the dev-client). Version names
    are org-unique forever, so a name collision here is a real bug, not a retry."""
    args = ["build", "upload", "--url", url, "--app", app_id, "--platform", platform,
            "--version", version, "--yes", "--json"]
    if not set_current:
        args.append("--no-set-current")
    p = _run(args, key=key, chdir=chdir, timeout=900)
    d = _json(p.stdout)
    vid = _find_version_id(d)
    if not vid:
        raise RevylError(f"build upload returned no version id: {json.dumps(d)[:500]}", stdout=p.stdout)
    return vid


def _find_version_id(d: Any) -> str | None:
    """Tolerate shape drift: look for a version-id-ish key at any depth."""
    if isinstance(d, dict):
        for k in ("version_id", "versionId", "build_version_id", "id"):
            v = d.get(k)
            if isinstance(v, str) and len(v) >= 32:
                return v
        for v in d.values():
            r = _find_version_id(v)
            if r:
                return r
    if isinstance(d, list):
        for v in d:
            r = _find_version_id(v)
            if r:
                return r
    return None


# ---------------------------------------------------------------------------------------
# workflows / tests
# ---------------------------------------------------------------------------------------
# ---------------------------------------------------------------------------------------
# remote builds. Shapes measured on 0.1.96, 2026-08-25:
#   build --remote --detach --json → {"status":"pending","profile","platform","build_job_id","app_id"}
#   build status <job> --json      → {"status":"success","phase":"build","version","version_id",
#                                     "duration_ms","package_id","app_id","timeout_seconds",
#                                     "created_at","started_at","completed_at"}
# Observed statuses (2026-08-25): `pending`, `building`, `success`, `failed`. A failed job
# carries `error: "<command> failed with exit code N"` and `completed_at`; `phase` is "build"
# from the first poll to the last and never says WHERE it failed. Terminal detection is a
# closed set + `completed_at`: an UNKNOWN status keeps polling until the deadline (then the
# job is cancelled) rather than being mistaken for terminal on the first poll — the opposite
# (an allow-list of in-progress words) would let a new "scheduled"/"provisioning" word end
# the wait, record builder_fault, and leave an untracked build to register a version later.
# ---------------------------------------------------------------------------------------
BUILD_TERMINAL = {"success", "failed", "error", "errored", "cancelled", "canceled", "timeout", "timed_out", "refused"}
# A recipe command (setup_commands / build_commands) exited non-zero — the CLI's own wording,
# measured on `xcodebuild … failed with exit code 66`. This is the ONLY evidence that charges
# the contestant (their tree failed inside npm ci / prebuild / pod install / xcodebuild);
# every other failure with a job id is the bench's (builder_fault).
RECIPE_COMMAND_FAILED = re.compile(r"failed with exit code \d+")


def build_remote(key: str, chdir: str | Path, *, profile: str, version: str, timeout_s: int,
                 log=print, platform: str = "ios", poll_s: int = 20) -> dict:
    """`revyl -C <tree> build --remote --detach` → build_job_id, then poll `build status` until a
    terminal status. Returns the FINAL status dict (version_id on success; log_tail on anything
    else). Raises RevylError only when the CLI itself fails (no JSON) — a failed/refused BUILD is
    returned, so grade.py decides between build_failed (agent) and builder_fault (bench).

    Detach + poll rather than `--follow` so the grade deadline stays enforceable from here and a
    runner restart could resume the same job id (grade.py persists it in revyl_build.json).
    --no-set-current: the grading app's current version must never become a contestant's.
    `chdir` MUST be a tree whose .revyl/config.yaml the caller just wrote (see module docstring)."""
    try:
        p = _run(["build", "--remote", "--profile", profile, "--platform", platform, "--version", version,
                  "--no-set-current", "--detach", "--json"], key=key, chdir=chdir, timeout=900, check=False)
    except subprocess.TimeoutExpired as e:
        raise RevylError(f"revyl build --remote --detach hung for 900s (source upload?): {e}") from e
    try:
        d = _json(p.stdout)
    except RevylError:
        raise RevylError(f"revyl build --remote produced no JSON rc={p.returncode}: "
                         f"{(p.stderr or p.stdout).strip()[-800:]}", stdout=p.stdout, stderr=p.stderr, rc=p.returncode)
    if not isinstance(d, dict):
        raise RevylError(f"revyl build --remote JSON is not an object: {str(d)[:200]}", stdout=p.stdout, rc=p.returncode)
    job = d.get("build_job_id")
    if not job:
        # The queue refused the job (bad recipe, org without remote builds, …): terminal, nothing
        # to poll. Never the agent's code — the recipe is bench-rendered — so grade.py maps
        # "no build_job_id" to builder_fault.
        d.setdefault("status", "refused")
        d["error"] = d.get("error") or (p.stderr or "").strip()[-800:] or "queue returned no build_job_id"
        return d
    log(f"[revyl build] queued {profile}/{platform} job {job} version={version}")
    return build_wait(key, job, timeout_s=timeout_s, log=log, poll_s=poll_s)


def build_status(key: str, job: str) -> dict:
    """Org-level (no project needed). Raises RevylError on CLI failure or a non-object payload."""
    d = _json(_run(["build", "status", job, "--json"], key=key, timeout=120).stdout)
    if not isinstance(d, dict):
        raise RevylError(f"build status {job}: JSON is not an object: {str(d)[:200]}")
    return d


_BUILD_ERROR_LINE = re.compile(
    r"error TS\d+|SyntaxError|Unable to resolve|Cannot find module|Module not found|Unexpected token|"
    r"has no exported member|is not defined|\berror:|\bError:|Expected .* but found|Unterminated|"
    # swiftc / xcodebuild on a native tree: `<file>.swift:12:5: error: cannot find 'x' in scope`
    # is caught by `\berror:` above; these are the summary lines that carry no `error:`.
    r"\*\* BUILD FAILED \*\*|Command CompileSwift(Sources)? failed|xcodebuild: error|"
    r"The following build commands failed",
    re.I)
_BUILD_NOISE_LINE = re.compile(r"swift compiler caching|compilation-cache:|phase:compilation_cache", re.I)


def build_error_excerpt(text: str, n: int = 4000, window: int = 40) -> str:
    """The part of a build log the agent can act on. The Xcode failure summary at the end of
    the log names only the phase that failed ("Bundle React Native code and images", exit
    code 65); the bundler's own message — the file, the line, the unclosed tag — is
    earlier and is cut off when only the last 1,500 characters are returned: the agent
    gets the summary, never the error, and has to fix blind. Keep a window of lines starting at
    the first compiler or bundler error line, drop cache-statistics noise, then append the
    tail so the summary is still there. Falls back to the plain tail when no error line
    matches."""
    lines = [l for l in text.splitlines() if not _BUILD_NOISE_LINE.search(l)]
    first = next((i for i, l in enumerate(lines) if _BUILD_ERROR_LINE.search(l)), None)
    tail = "\n".join(lines).strip()[-n // 2:]
    if first is None:
        return "\n".join(lines).strip()[-n:]
    head = "\n".join(lines[first:first + window])
    if head in tail:
        return tail if len(tail) >= len(head) else head
    return (head[:n - n // 2] + "\n…\n" + tail).strip()


def build_log_tail(key: str, job: str, n: int = 4000) -> str:
    """`build status --debug` prints "Recent logs" — the only CLI surface for the runner log.
    The excerpt becomes the agent's feedback for a build_failed verdict (its own compile
    errors); see build_error_excerpt for why it is not a plain tail."""
    try:
        p = _run(["build", "status", job, "--debug"], key=key, check=False, timeout=120)
    except subprocess.TimeoutExpired:
        return "(build status --debug timed out)"
    return build_error_excerpt(((p.stdout or "") + "\n" + (p.stderr or "")).strip(), n)


def build_wait(key: str, job: str, *, timeout_s: int, log=print, poll_s: int = 20) -> dict:
    """Poll until BUILD_TERMINAL / `completed_at`, or the deadline (then `build cancel` so the
    job cannot register a version after we stopped watching). The deadline is measured from
    here, i.e. AFTER the detach call returned — the caller's grade deadline is re-checked
    before the suite starts (grade.py step 6), so a slow source upload cannot push a grade
    past caps.grade_timeout_min unnoticed. Poll errors (CLI hiccup, network, a hung
    `build status`) are logged and retried until the deadline; they never propagate."""
    t0, last = time.time(), ""
    while True:
        try:
            st = build_status(key, job)
            status = str(st.get("status", "")).lower()
        except (RevylError, subprocess.TimeoutExpired) as e:
            st, status = {"status": "poll_error", "error": str(e)[-500:]}, "poll_error"
        if status != last:
            log(f"[revyl build] {job} status={status} phase={st.get('phase')} "
                f"({max(0.0, time.time() - t0):.0f}s)")
            last = status
        st.setdefault("build_job_id", job)
        if status in BUILD_TERMINAL or st.get("completed_at"):
            if status != "success":
                st["log_tail"] = build_log_tail(key, job)
            return st
        if time.time() - t0 > timeout_s:
            try:
                _run(["build", "cancel", job], key=key, check=False, timeout=120)
            except subprocess.TimeoutExpired:
                pass
            return {"status": "timeout", "build_job_id": job, "phase": st.get("phase"), "last_status": status,
                    "error": f"no terminal status after {timeout_s}s (last status {status!r}; cancel requested)",
                    "log_tail": build_log_tail(key, job)}
        time.sleep(poll_s)


def workflow_list(key: str, chdir: str | Path) -> list[dict]:
    d = _json(_run(["workflow", "list", "--json"], key=key, chdir=chdir).stdout)
    return d if isinstance(d, list) else d.get("workflows", d.get("data", []))


def workflow_info(key: str, chdir: str | Path, name: str) -> dict:
    """{'id','name','tests':[{'id','name','platform'}]} (captured live)."""
    return _json(_run(["workflow", "info", name, "--json"], key=key, chdir=chdir).stdout)


def test_run(key: str, chdir: str | Path | None, test_name: str, build_version_id: str,
             *, timeout_s: int = 2400, retries: int = 1) -> dict:
    """Run ONE frozen test pinned to ONE build. Returns the run JSON:
    {'task_id','test_id','success','status','duration','error','report_link','test_name'}.

    chdir=None from the runner (grade.py): `test run` needs no project, and a `-C` pointing
    at the submission tree would let the AGENT's committed .revyl/config.yaml gate the grade
    (a legacy-shape config makes CLI >= 0.1.95 refuse to start the run). Progress lines
    go to stderr, JSON to stdout.
    --no-open: the CLI may otherwise try to open the report in a browser in an interactive tty.

    -b <build_version_id> every time: `test run` without -b resolves "latest uploaded",
    and `test create --from-file` drops pinned_version (CLI v0.1.63–0.1.82 trap) — the
    only loud-failure path is pin-per-run + assert build_version in the report.
    -r 1: retries would let a flaky pass mask an app failure; grading is one attempt.
    A non-zero exit with JSON on stdout is a FAILED test, not a CLI error — returned."""
    p = _run(["test", "run", test_name, "-b", build_version_id, "-r", str(retries),
              "--json", "--no-open", "-t", str(timeout_s)], key=key, chdir=chdir,
             timeout=timeout_s + 300, check=False)
    try:
        d = _json(p.stdout)
    except RevylError:
        raise RevylError(f"test run {test_name}: no JSON (rc={p.returncode}): {p.stderr[-800:]}",
                         stdout=p.stdout, stderr=p.stderr, rc=p.returncode)
    d.setdefault("_stderr_tail", p.stderr[-2000:])
    return d


def test_report(key: str, chdir: str | Path | None, task_id: str, *, attempts: int = 6,
                sleep_s: float = 10.0) -> dict:
    """Full report for a run, bound by task_id (never "latest by name" — a run that never
    started must fail loudly, not inherit a stale report). Retries briefly because the
    report can lag the run's completion by a few seconds. Needs no project (chdir=None ok)."""
    last: Exception | None = None
    for _ in range(attempts):
        try:
            d = _json(_run(["test", "report", task_id, "--json"], key=key, chdir=chdir).stdout)
            if isinstance(d, dict) and "build_version" in d and "steps" in d:
                return d
            last = RevylError(f"report for {task_id} incomplete: keys={list(d)[:10] if isinstance(d, dict) else type(d)}")
        except RevylError as e:
            last = e
        time.sleep(sleep_s)
    raise last or RevylError("test_report: unknown failure")


# ---------------------------------------------------------------------------------------
# devices (agent org hygiene at END)
# ---------------------------------------------------------------------------------------
def device_stop_all(key: str, chdir: str | Path) -> None:
    """Org-wide stop. ONLY safe when no other rollout is live — with parallel rollouts on
    the shared agent org this kills the sibling's dev session mid-exploration.
    down() uses device_stop_session per this rollout's device-sessions.json instead and
    falls back here only when it is provably alone.
    `device *` is a PROJECT command: the -C dir must hold a CANONICAL config.yaml (the staging
    scaffold copy). check=True so a refusal (e.g. a legacy config) raises RevylError instead
    of leaking sessions silently — down() catches and logs it (non-fatal)."""
    _run(["device", "stop", "--all"], key=key, chdir=chdir, check=True)


def device_stop_session(key: str, chdir: str | Path, index: int) -> None:
    """Stop ONE session by its index. `-s` resolves against the .revyl/device-sessions.json
    in the -C project dir (client-side state with explicit `index` fields), so the caller
    must place THIS rollout's sessions file there first — that scoping is what makes the
    stop per-rollout instead of org-wide. Same canonical-config requirement and loud
    failure as device_stop_all (a silent `check=False` would hide a refused stop and leak
    the session)."""
    _run(["device", "stop", "-s", str(index)], key=key, chdir=chdir, check=True)
