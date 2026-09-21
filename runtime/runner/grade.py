"""runner.grade — grade_submission(k): one submission, start to finish.

Runs inside the runner container. Holds the grading key (+ EXPO_TOKEN only when
spec.builder == "eas"; passed in by main.py from runner.env); the agent container never sees
either. Transport-agnostic: it
reads `<mailbox>/submit/s<k>.*` and writes `<mailbox>/feedback/s<k>.*` — the same module
works unchanged if the mailbox becomes an S3 prefix in v3.

Sequence (each step's failure mode is a *named* verdict, never a crash that leaves the
agent polling forever):
  1 accept   sha256 of the tarball == request.json                        → else rejected: sha
  2 untar    into a runner-owned temp dir (never the live agent workspace); git init+commit
             so EAS's git-based file listing respects the scaffold's .gitignore
  3 lint     hardening patterns → lint_warnings (warn only in v1)
  4 build    builder=revyl (default): OVERWRITE <tree>/.revyl/config.yaml with the image-owned
             recipe (bench/recipes.py; sha256 logged), then `revyl build --remote --profile
             preview` = native prebuild + xcodebuild Release (BAKED JS) on Revyl's runners;
             the version is registered on the grading app by the build itself.
             "<cmd> failed with exit code N" → build_failed (agent); queue refused / CLI
             error / any other failure → builder_fault (bench, quarantined); deadline → timeout;
             success without version_id → upload_failed. (_classify_remote_build)
             builder=eas (rollback): eas build --profile preview               → build_failed
  5 register eas only: revyl build upload → grading app, version <rollout_id>-s<k>, --no-set-current
  6 grade    4× `revyl test run <name> -b <build_version_id> -r 1` in parallel, then
             `revyl test report <task_id>` each; ASSERT report.build_version == the name
             (retry that one test once on mismatch)                          → wrong_build
             video-validated reports finalize async: backoff-poll (10/20/30s) until the
             report carries `success`, else fall back to the run summary's success bit
  7 verdicts {t_1,t_2,t_3,final} = report.success; regressions vs the last graded k
  8 redact   → feedback/s<k>/ ; then s<k>.verdict.json (LAST — its existence = "done")
  9 record   attempts.jsonl line; RAW reports archived under log/reports/s<k>/
A grade that exceeds caps.grade_timeout_min at any stage becomes failure_kind=timeout.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from bench import attempts as _attempts
from bench import eas as _eas
from bench import recipes as _recipes
from bench import blocks as _blocks
from runner import observability as _obs
from bench import redact as _redact
from bench import revyl as _revyl
from bench.config import SLOTS, RolloutSpec

Log = Callable[[str], None]

# Hardening lint: app values must be computable
# on paper, so live clocks / randomness / persistence are red flags. v1 WARNS (recorded in
# the verdict + attempts.jsonl) — never rejects — because a false positive (e.g. a comment)
# would cost the contestant a submission for nothing.
LINT_PATTERNS = {
    "clock_or_random": re.compile(r"Date\.now\(|new Date\(|Math\.random\("),
    "persistence": re.compile(r"\bpersist\(|AsyncStorage|expo-sqlite|expo-secure-store"),
}
LINT_DIRS = ("app", "src", "components", "lib", "state", "hooks", "constants", "data")
LINT_EXT = {".ts", ".tsx", ".js", ".jsx"}



ADMISSION_REFUSED_RE = re.compile(r"Concurrency limit reached", re.I)
BUILD_CAPACITY_RE = re.compile(r"No build capacity", re.I)
ADMISSION_WAIT_STEP_S = 60
ADMISSION_WAIT_MAX_S = 20 * 60


def _admission_refused(run: dict | None) -> bool:
    """`test run` returned no task id because the organisation's concurrent-run cap was
    hit: the run never started, so nothing about the tree was judged."""
    if not run or run.get("task_id"):
        return False
    return bool(ADMISSION_REFUSED_RE.search(str(run.get("error") or "") + str(run.get("_stderr_tail") or "")))

def _classify_remote_build(st: dict[str, Any]) -> str | None:
    """failure_kind for a `revyl build --remote` terminal status dict (None = usable build).

    Measured on 2026-08-25: a success is {"status":"success","version_id":…};
    a recipe-command failure is {"status":"failed","error":"<cmd> failed with exit code N"}.
    `phase` is "build" throughout and says nothing about where a failure happened, so the
    charge/refund split rests on the error text alone:
      timeout                                    → "timeout"        (bench; deadline hit)
      success but no version_id                  → "upload_failed"  (bench; built, not registered)
      job id + "failed with exit code N"         → "build_failed"   (AGENT: their tree failed
                                                     inside npm ci / prebuild / pod install /
                                                     xcodebuild — the log tail is their feedback)
      anything else (queue refused, CLI error, infra failure, unknown wording) → "builder_fault"
                                                   (bench, quarantined; a wrong refund is
                                                     cheaper than a wrong charge)."""
    status = str(st.get("status", "")).lower()
    if status == "timeout":
        return "timeout"
    if status == "success":
        return None if st.get("version_id") else "upload_failed"
    if st.get("build_job_id") and _revyl.RECIPE_COMMAND_FAILED.search(str(st.get("error", ""))):
        return "build_failed"
    return "builder_fault"


# Device-side launch failures are typed by the Revyl device layer (its
# DeviceLaunchErrorType enum) and the type name rides verbatim in
# `revyl test run`'s `error` and in the report's `error_message`, e.g.
#   "Device launch error: DeviceLaunchErrorType.APP_LAUNCH_CRASH - App com.x crashed on
#    launch: not RUNNING after 3 attempts (last process_state=UNKNOWN)".
# Such a run still returns a task id and a report with `success: false` and `steps: []`, so
# without this classifier it graded as a plain FAIL with an EMPTY block vector — which a
# consumer of the per-block record (bench.blocks) reads as "nothing decided" and drops, while
# the agent's feedback said a target element was not tappable instead of "your app crashed".
#
# Charge by TYPE, never by "did a report exist":
#   APP_LAUNCH_CRASH  → the binary does not stay running. Reproduced deterministically by
#                       re-running the same build ids on idle infrastructure: the crash
#                       follows the build, not the device that ran it.
#                       AGENT fault: failure_kind "app_crash", verdict FAIL, no blocks.
#   anything else     → the device farm, the recipe or the install (DEVICE_CONNECTION_FAILED,
#                       EMULATOR_STARTUP_FAILED, DEVICE_SETUP_TIMEOUT, DEVICE_SESSION_LOST,
#                       APP_INSTALLATION_FAILED, INVALID_APP_FORMAT, ...). Not a verdict on
#                       the tree: the slot is treated like a missing report — re-run once,
#                       then failure_kind "device_fault" (bench, abstain). Open-world on
#                       purpose: a type this code has never seen is a bench fault until a
#                       re-grade on idle infrastructure proves it belongs to the agent.
DEVICE_ERROR_RE = re.compile(r"DeviceLaunchErrorType\.([A-Z_]+)")
AGENT_LAUNCH_ERRORS = {"APP_LAUNCH_CRASH"}
# The same crash WITHOUT the type tag. Newer versions of the device layer report a binary
# that exits on launch as
#   "Launch failure (cause undetermined): App com.x did not stay running after 3 launch
#    attempts (last process_state=UNKNOWN)"
# — the APP_LAUNCH_CRASH condition word for word ("not RUNNING after 3 attempts"), minus
# `DeviceLaunchErrorType.`. DEVICE_ERROR_RE misses it, `session_status: failed` with no
# judged step then types it EMPTY_REPORT, and the submission ABSTAINS (bench fault) instead
# of being charged. It is the tree's property, not the device farm's: the text repeats
# identically on the re-run while other trees of the same app grade normally in the same
# minutes. An abstaining submission is refunded, so without this rule an agent was never
# charged for shipping an app that does not start. Typed as APP_LAUNCH_CRASH so it takes
# the confirm-once-then-charge path below; a launch that succeeds on the re-run still grades.
APP_NOT_RUNNING_RE = re.compile(r"did not stay running after \d+ launch attempts|not RUNNING after \d+ attempts", re.I)
# A second bench-error family that carries no DeviceLaunchErrorType: the device could not
# be prepared, the CLI could not poll the report, a step type the grader could not map. The
# report then has no judged step at all — zero evidence about the tree — yet `success:
# false` would grade it a plain FAIL and charge the submission. Typed here so they take the
# retry-once-then-device_fault path like DeviceLaunchErrorType.
BENCH_REPORT_RE = re.compile(r"Device setup error|polling failed|Step execution failed|Task type \S+ not mapped", re.I)


def _judged_steps(rep: dict[str, Any] | None) -> int:
    if not rep:
        return 0
    if rep.get("total_steps") is not None:
        try:
            return int(rep.get("total_steps") or 0)
        except (TypeError, ValueError):
            return 0
    return len(rep.get("steps") or [])


def _device_error_type(run: dict[str, Any] | None, rep: dict[str, Any] | None) -> str | None:
    """The DeviceLaunchErrorType name carried by a run summary / report pair, or None.
    The report's `error_message` is authoritative (it is what the judge saw); the run's
    `error` is the CLI's copy of the same text and covers reports that omit the field.
    A failed report with no judged step whose error text names a bench condition
    (BENCH_REPORT_RE) is typed EMPTY_REPORT: not a judgement about the tree."""
    for src, key in ((rep, "error_message"), (run, "error"), (rep, "summary_error")):
        if src and src.get(key):
            m = DEVICE_ERROR_RE.search(str(src[key]))
            if m:
                return m.group(1)
    # Untyped launch failure: the crash text without its DeviceLaunchErrorType prefix (see
    # APP_NOT_RUNNING_RE). Checked before the EMPTY_REPORT fallback, which would otherwise
    # swallow it as a bench condition on `session_status: failed` alone.
    for src, key in ((rep, "error_message"), (run, "error"), (rep, "summary_error")):
        if src and src.get(key) and APP_NOT_RUNNING_RE.search(str(src[key])):
            return "APP_LAUNCH_CRASH"
    if rep is not None and rep.get("success") is False and _judged_steps(rep) == 0:
        texts = " ".join(str(src.get(key) or "") for src, key in ((rep, "error_message"), (rep, "summary_error"), (run, "error")) if src)
        if BENCH_REPORT_RE.search(texts) or str(rep.get("session_status", "")).lower() == "failed":
            return "EMPTY_REPORT"
    return None


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _lint(tree: Path) -> list[str]:
    warnings: list[str] = []
    for d in LINT_DIRS:
        base = tree / d
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.suffix not in LINT_EXT or "node_modules" in p.parts:
                continue
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for name, rx in LINT_PATTERNS.items():
                for m in rx.finditer(txt):
                    line = txt.count("\n", 0, m.start()) + 1
                    warnings.append(f"{name}: {p.relative_to(tree).as_posix()}:{line}: {m.group(0)}")
    return warnings[:50]


def _git(tree: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=runner", "-c", "user.email=runner@revyl-bench", *args],
                   cwd=str(tree), check=True, capture_output=True)


class Grader:
    def __init__(self, spec: RolloutSpec, *, mailbox: Path, log_dir: Path, grading_key: str,
                 expo_token: str, work_dir: Path, log: Log = print,
                 final_evaluation: dict[str, Any] | None = None) -> None:
        self.spec, self.mailbox, self.log_dir = spec, mailbox, log_dir
        self.final_evaluation = final_evaluation
        self.grading_key, self.expo_token = grading_key, expo_token
        self.work_dir, self.log = work_dir, log
        self.feedback = mailbox / "feedback"
        self.submit = mailbox / "submit"

    # ---- status plumbing --------------------------------------------------------------
    def _status(self, k: int, s: str) -> None:
        _atomic_write(self.feedback / f"s{k}.status", s)
        self.log(f"[grade s{k}] status={s}")

    def _write_verdict(self, k: int, verdict: dict[str, Any]) -> None:
        _atomic_write(self.feedback / f"s{k}.verdict.json", json.dumps(verdict, indent=2))

    # ---- the whole thing --------------------------------------------------------------
    def grade_submission(self, k: int, *, history: list[dict[str, Any]], rollout_started: float
                         ) -> dict[str, Any]:
        """history: prior submission records (for regressions). Returns the attempts.jsonl
        record (already appended)."""
        spec = self.spec
        t_start = time.time()
        deadline = t_start + spec.caps.grade_timeout_min * 60
        req_path = self.submit / f"s{k}.request.json"
        tar_path = self.submit / f"s{k}.tar.gz"
        req = json.loads(req_path.read_text(encoding="utf-8"))
        ts_submit = req.get("ts") or _attempts.now_iso()
        build_version = spec.build_version(k)
        raw_dir = self.log_dir / "reports" / f"s{k}"
        raw_dir.mkdir(parents=True, exist_ok=True)

        verdicts: dict[str, str | None] = {s: None for s in SLOTS}
        report_task_ids: dict[str, str | None] = {s: None for s in SLOTS}
        report_uris: dict[str, str | None] = {s: None for s in SLOTS}
        reports: dict[str, dict | None] = {s: None for s in SLOTS}
        launch_errors: dict[str, str] = {}
        retries: dict[str, int] = {}     # F3: slot → wrong-build / device-error re-run count (0 = absent)
        device_faults: dict[str, str] = {}   # slot → DeviceLaunchErrorType name (bench-side, abstained)
        device_seen: dict[tuple[str, str], int] = {}   # (slot, error type) → times seen (the re-run gate)
        failure_kind: str | None = None
        eas_build_id: str | None = None
        build_job_id: str | None = None
        build_version_id: str | None = None
        ts_build_start = ts_grade_start = None
        lint_warnings: list[str] = []
        tree_sha = ""

        def finish() -> dict[str, Any]:
            regressions = _regressions(history, verdicts)
            fb_dir = self.feedback / f"s{k}"
            _redact.redact(reports, verdicts, fb_dir, launch_errors=launch_errors)
            verdict = {"k": k, "build_version": build_version, "build_version_id": build_version_id,
                       "verdicts": verdicts, "regressions": regressions, "lint_warnings": lint_warnings,
                       "failure_kind": failure_kind, "ts": _attempts.now_iso()}
            # Only slots that actually produced a verdict. A wrong_build or timed-out slot
            # still has a report on disk while verdicts[slot] is None — "the suite did not
            # run for this submission" — and folding its steps into this submission's
            # vector would attribute another build's results to this tree. That is the
            # exact confusion extract() refuses to create for a MISSING report.
            scored = {s: r for s, r in reports.items() if verdicts.get(s) in ("PASS", "FAIL")}
            blocks = _blocks.extract(scored)
            # observability (runner/observability.py): log assertions join the block
            # vector as graded rows for tasks that declare them; perf and network are
            # recorded alongside. Best-effort by contract — never fails a grade.
            perf = net = None
            if getattr(spec.grading, "log_assertions", None):
                # SCORED slots only — a wrong_build slot still carries a run id, and
                # grading that run's logs folds a wrong binary into the fraction;
                # same slot set extract() uses.
                scored_ids = {sl: rid for sl, rid in report_task_ids.items() if sl in scored}
                blocks += _obs.log_assertion_rows(spec.grading.log_assertions,
                                                  scored_ids, spec.grading.tests, self.log)
            try:
                perf = _obs.perf_summaries(report_task_ids, self.log) or None
                net = _obs.network_counts(report_task_ids, self.log) or None
            except Exception as e:  # noqa: BLE001
                self.log(f"[obs] capture skipped: {e}")
            rec = _attempts.submission_record(
                spec=spec.to_dict(), k=k, ts_submit=ts_submit, ts_build_start=ts_build_start,
                ts_grade_start=ts_grade_start, ts_verdict=verdict["ts"], commit_id=req.get("commit_id", ""),
                tree_sha256=tree_sha, eas_build_id=eas_build_id, build_version=build_version,
                build_version_id=build_version_id, verdicts=verdicts, regressions=regressions,
                lint_warnings=lint_warnings, failure_kind=failure_kind, report_task_ids=report_task_ids,
                report_uris=report_uris, raw_reports_dir=str(raw_dir), wall_clock_s=time.time() - rollout_started,
                retries=retries, build_job_id=build_job_id,
                blocks=blocks, blocks_summary=_blocks.summary(blocks),
                perf=perf, network_requests=net)
            if self.final_evaluation is not None:
                rec.update(self.final_evaluation)
            _attempts.append(self.log_dir / "attempts.jsonl", rec)
            self._write_verdict(k, verdict)          # publish only after durable outcome
            self._status(k, "done")
            bs = rec["blocks_summary"]
            self.log(f"[grade s{k}] blocks {bs.get('passed')}/{bs.get('decided')} passed "
                     f"(fraction={bs.get('fraction')}) of {bs.get('total')}")
            self.log(f"[grade s{k}] DONE verdicts={verdicts} regressions={regressions} failure_kind={failure_kind} "
                     f"({time.time() - t_start:.0f}s)")
            return rec

        # 1. accept ---------------------------------------------------------------------
        self._status(k, "queued")
        tree_sha = _sha256(tar_path)
        if tree_sha != req.get("sha256"):
            failure_kind = "rejected_sha"
            launch_errors["_"] = "submission rejected: tarball sha256 does not match request.json"
            self._status(k, "rejected: sha")
            return finish()

        # 2. untar ----------------------------------------------------------------------
        tree = self.work_dir / f"s{k}" / "tree"
        if tree.exists():
            shutil.rmtree(tree, ignore_errors=True)
        tree.mkdir(parents=True)
        with tarfile.open(tar_path, "r:gz") as tf:
            # 'data' filter forbids absolute-target symlinks etc. Apply it PER MEMBER and
            # drop offenders instead of crashing: the agent's submit.sh symlink (or any
            # hostile member) must cost the agent that file, not wedge the grader.
            for m in tf.getmembers():
                try:
                    safe = tarfile.data_filter(m, str(tree))
                except tarfile.FilterError as e:
                    self.log(f"[grade s{k}] dropping unsafe tar member {m.name!r}: {e}")
                    continue
                tf.extract(safe, tree, set_attrs=False)
        _git(tree, "init", "-q")
        _git(tree, "add", "-A")
        _git(tree, "commit", "-q", "--allow-empty", "-m", f"graded tree s{k} {req.get('commit_id', '')}")
        (self.log_dir / "reports" / f"s{k}" / "request.json").write_text(json.dumps(req, indent=2), encoding="utf-8")

        # 3. lint -----------------------------------------------------------------------
        lint_warnings = _lint(tree)
        if lint_warnings:
            self.log(f"[grade s{k}] lint_warnings={len(lint_warnings)} (warn only)")

        # 4. build ----------------------------------------------------------------------
        self._status(k, "building")
        ts_build_start = _attempts.now_iso()
        if spec.builder == "revyl":
            # 4a. The bench owns the recipe, never the submission: `revyl build`
            # executes whatever build_commands the project config names, so the agent's
            # committed .revyl/config.yaml is REPLACED — it could otherwise `curl` a prebuilt
            # .app. Rendered from the image-owned template with this task's grading app id and
            # Xcode scheme; committed so the source tarball and `git status` agree.
            # technology: "expo" for every rollout.json written before the field existed
            technology = getattr(spec.agent, "technology", "expo")
            recipe = _recipes.build_recipe(spec.task, app_id=spec.grading.app_id,
                                           scheme=spec.agent.ios_scheme, technology=technology)
            # .revyl is recreated from scratch: a tarball that ships `.revyl` as a FILE (or
            # config.yaml as a directory) must not be able to crash the grader.
            rv = tree / ".revyl"
            if rv.is_dir() and not rv.is_symlink():
                shutil.rmtree(rv, ignore_errors=True)
            elif rv.exists() or rv.is_symlink():
                rv.unlink()
            rv.mkdir()
            (rv / "config.yaml").write_text(recipe, encoding="utf-8", newline="\n")
            (raw_dir / "recipe.yaml").write_text(recipe, encoding="utf-8", newline="\n")
            _git(tree, "add", "-A")
            _git(tree, "commit", "-q", "--allow-empty", "-m", "bench: grading recipe")
            self.log(f"[grade s{k}] recipe sha256={hashlib.sha256(recipe.encode()).hexdigest()} "
                     f"(profile=preview app={spec.grading.app_id[:8]}… scheme={spec.agent.ios_scheme} "
                     f"technology={technology})")
            # 4b. build + register in one call; the version name is org-unique (<rollout_id>-s<k>).
            # A builder fault (Revyl's infrastructure, not the tree: "The build could not run
            # on our build infrastructure. Please retry") is
            # retried ONCE under a fresh version name, because the scorer refunds the row but
            # the agent's attempt is spent either way; a build_failed (the tree's own error)
            # is never retried.
            for build_try in (1, 2):
                waited = 0
                while True:
                    try:
                        st = _revyl.build_remote(self.grading_key, tree, profile="preview", version=build_version,
                                                 timeout_s=max(60, int(deadline - time.time())), log=self.log)
                    except (_revyl.RevylError, subprocess.TimeoutExpired) as e:
                        st = {"status": "cli_error", "error": str(e)[-1500:]}
                    # Admission, not a build result: the organisation's build queue was full
                    # ("No build capacity is available for this org.", seen with several
                    # rollouts building at once). Wait for capacity within the grade
                    # budget rather than quarantining the submission as a builder_fault.
                    if not (BUILD_CAPACITY_RE.search(str(st.get("error") or "")) and deadline - time.time() > 900
                            and waited < ADMISSION_WAIT_MAX_S):
                        break
                    delay = min(ADMISSION_WAIT_STEP_S, ADMISSION_WAIT_MAX_S - waited)
                    self.log(f"[grade s{k}] org build capacity full — waiting {delay}s ({waited + delay}s so far)")
                    time.sleep(delay)
                    waited += delay
                build_job_id = st.get("build_job_id")
                (raw_dir / f"revyl_build{'' if build_try == 1 else '.retry'}.json").write_text(
                    json.dumps(st, indent=2, default=str), encoding="utf-8")
                failure_kind = _classify_remote_build(st)
                if failure_kind == "builder_fault" and build_try == 1 and deadline - time.time() > 900:
                    self.log(f"[grade s{k}] remote build {str(st.get('status', '')).lower()} job={build_job_id} "
                             f"error={str(st.get('error'))[:160]!r} → builder fault; retrying the build once")
                    build_version = f"{build_version}-r1"
                    continue
                break
            if failure_kind is not None:
                status = str(st.get("status", "")).lower()
                tail = st.get("log_tail") or st.get("error") or json.dumps(st)[-1500:]
                self.log(f"[grade s{k}] remote build {status} job={build_job_id} error={str(st.get('error'))[:200]!r} → {failure_kind}")
                launch_errors["build"] = f"Revyl remote build {status}: {tail}"
                return finish()
            build_version_id = str(st["version_id"])
            self.log(f"[grade s{k}] built+registered {build_version} → {build_version_id} "
                     f"(job {build_job_id}, {st.get('duration_ms', '?')} ms)")
        else:
            try:
                # npm ci runs inside build() (eas needs node_modules to evaluate the app config);
                # /tmp/npm-cache persists across submissions of this rollout → s2..sk install fast.
                eb = _eas.build(tree, profile="preview", token=self.expo_token, log=self.log,
                                timeout_s=max(60, int(deadline - time.time())), npm_cache="/tmp/npm-cache")
                eas_build_id = eb.build_id
            except _eas.EasError as e:
                eb = _eas.EasBuild("", "ERRORED", None, None, str(e)[-1500:])
            (raw_dir / "eas_build.json").write_text(json.dumps(eb.__dict__, indent=2), encoding="utf-8")
            if eb.status != "FINISHED" or not eb.artifact_url:
                failure_kind = "timeout" if eb.status == "TIMEOUT" else "build_failed"
                # The agent gets the EAS error tail — that IS the feedback for a build failure
                # (it is the agent's code that failed to compile; not a probe leak).
                launch_errors["build"] = f"EAS preview build {eb.status}: {eb.error_tail}"
                return finish()

            # 5. register (eas only — the revyl builder registered the version itself) -------------
            try:
                # chdir=None (no -C): the submission tree is AGENT-controlled; its committed
                # .revyl/config.yaml must never be project context for a grading command (a
                # legacy-shape config makes CLI >= 0.1.95 refuse `test run` outright).
                # None of build upload / test run / test report needs a project.
                build_version_id = _revyl.build_upload_url(
                    self.grading_key, None, url=eb.artifact_url, app_id=spec.grading.app_id,
                    version=build_version, set_current=False)
            except _revyl.RevylError as e:
                failure_kind = "upload_failed"
                launch_errors["upload"] = f"build registration failed (tooling): {str(e)[-500:]}"
                self.log(f"[grade s{k}] upload failed: {e}")
                return finish()
            self.log(f"[grade s{k}] registered {build_version} → {build_version_id}")

        # 6. grade -----------------------------------------------------------------------
        self._status(k, "grading")
        ts_grade_start = _attempts.now_iso()
        remaining = int(deadline - time.time())
        if remaining < 300:
            failure_kind = "timeout"
            launch_errors["grade"] = "grade timeout reached before the suite could start"
            return finish()

        # Video-validated tests finalize their report ASYNCHRONOUSLY: `revyl test report`
        # can return while video validation is still being judged server-side, and that
        # early report is complete EXCEPT for the top-level `success` flag: all steps green,
        # all validations passed, session_status=completed — but no `success` key. Read
        # as falsy, the MISSING key became a FAIL no judge issued (which then also poisoned
        # _regressions and cost the agent a resubmission). Poll with backoff until the flag
        # resolves; what happens if it never does is decided where verdicts are assigned.
        REPORT_SUCCESS_BACKOFF_S = (10, 20, 30)

        def fetch_report(name: str, task_id: str) -> dict:
            rep = _revyl.test_report(self.grading_key, None, task_id)
            for delay in REPORT_SUCCESS_BACKOFF_S:
                if "success" in rep:
                    break
                if time.time() + delay >= deadline:  # never let polling eat the grade timeout
                    break
                self.log(f"[grade s{k}] {name}: report has no `success` yet (video "
                         f"validation still finalizing) — refetching in {delay}s")
                time.sleep(delay)
                rep = _revyl.test_report(self.grading_key, None, task_id)
            return rep

        def run_one(slot: str, attempt: int = 1) -> tuple[str, dict | None, dict | None]:
            name = spec.grading.tests[slot]
            # budget at CALL time, not at the start of the grade: the no-report re-run
            # below starts late in the window and must not be handed the original one
            left = max(60, int(deadline - time.time()))
            try:
                run = _revyl.test_run(self.grading_key, None, name, build_version_id,
                                      timeout_s=min(2400, left), retries=1)
            except _revyl.RevylError as e:
                self.log(f"[grade s{k}] {name}: run error {e}")
                return slot, {"error": str(e)}, None
            # Admission, not a verdict: the grading organisation caps concurrent test
            # runs (observed "Concurrency limit reached for org … (20/20)", 2026-09-08,
            # with 14 rollouts grading at once — the four re-runs the no-report path
            # makes were refused just the same, 23 s later). Wait for a slot with
            # backoff, bounded by the grade budget, instead of scoring the slot None.
            waited = 0
            while _admission_refused(run) and deadline - time.time() > 600 and waited < ADMISSION_WAIT_MAX_S:
                delay = min(ADMISSION_WAIT_STEP_S, ADMISSION_WAIT_MAX_S - waited)
                self.log(f"[grade s{k}] {name}: org concurrency limit — waiting {delay}s for a slot "
                         f"({waited + delay}s so far)")
                time.sleep(delay)
                waited += delay
                left = max(60, int(deadline - time.time()))
                try:
                    run = _revyl.test_run(self.grading_key, None, name, build_version_id,
                                          timeout_s=min(2400, left), retries=1)
                except _revyl.RevylError as e:
                    self.log(f"[grade s{k}] {name}: run error {e}")
                    return slot, {"error": str(e)}, None
            (raw_dir / f"{name}-run{attempt}.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
            task_id = run.get("task_id")
            if not task_id:
                return slot, run, None
            try:
                rep = fetch_report(name, task_id)
            except _revyl.RevylError as e:
                self.log(f"[grade s{k}] {name}: report error {e}")
                return slot, run, None
            (raw_dir / f"{name}-run{attempt}.report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
            if "success" not in rep:
                # Backoff exhausted and the flag still never appeared. Last resort: trust
                # the run summary's own `success` (the CLI's exit-state view of the run) —
                # it read `true` in every observed missing-flag case. The raw report was
                # already archived above UNPATCHED, so the on-disk evidence stays honest;
                # only the in-memory copy that feeds the verdict is filled in.
                self.log(f"[grade s{k}] {name}: report never resolved `success` — "
                         f"falling back to run summary success={run.get('success')!r}")
                rep["success"] = run.get("success")
            # THE binding assertion: the report must name OUR build.
            if rep.get("build_version") != build_version and attempt == 1:
                self.log(f"[grade s{k}] {name}: WRONG BUILD in report ({rep.get('build_version')!r} != "
                         f"{build_version!r}) — retrying once")
                retries[slot] = retries.get(slot, 0) + 1   # retry is otherwise invisible in attempts.jsonl
                return run_one(slot, attempt=2)
            # Device-side launch failure (see DEVICE_ERROR_RE). Both kinds re-run ONCE: a
            # crash that grades on the second try was a flake and that grade stands; a
            # crash that repeats is the tree's (measured deterministic, 2026-09-05). The
            # gate is a per-slot COUNT of device errors, not the attempt number: the
            # no-report path re-enters here with attempt=2, and a crash first seen on that
            # retry still deserves its own confirming run before it is charged.
            err_type = _device_error_type(run, rep)
            if err_type:
                # Counted per (slot, TYPE): a bench-side error followed by one crash is a
                # crash seen once, not twice. At most three runs per slot.
                seen = device_seen.get((slot, err_type), 0) + 1
                device_seen[(slot, err_type)] = seen
                if seen == 1 and attempt < 3:
                    self.log(f"[grade s{k}] {name}: device launch error {err_type} — re-running once")
                    retries[slot] = retries.get(slot, 0) + 1
                    return run_one(slot, attempt=attempt + 1)
                if err_type not in AGENT_LAUNCH_ERRORS or seen < 2:
                    # a bench-side type, or a crash the run budget could not confirm: not a
                    # judgement about the tree. Hand back "no report" so the slot is scored
                    # None; device_faults[] makes the failure_kind say why.
                    device_faults[slot] = err_type
                    return slot, run, None
            return slot, run, rep

        # Grade only the slots this task DECLARES. A whole-app task declares all four; a
        # step task declares a prefix. Iterating SLOTS blindly would KeyError on
        # spec.grading.tests for a step task, and defaulting the missing ones to a verdict
        # would invent results for tests that were never meant to run.
        graded = [s for s in SLOTS if s in spec.grading.tests]
        with ThreadPoolExecutor(max_workers=4) as ex:
            results = list(ex.map(run_one, graded))

        # A slot with no report is not a verdict. Under concurrency (16 rollouts grading
        # at once, 2026-09-03) about one grade in four came back with one slot missing
        # its report while the others were fine — a tooling drop, not a property of the
        # tree. Re-run just those slots once, if the grade budget allows; a second miss
        # stays `no_report` and is recorded as such. The retry is visible in `retries`.
        # device_faults already had their one re-run inside run_one; re-running them a
        # third time would spend grade budget on a slot that is abstaining either way
        missing = [slot for slot, run, rep in results if rep is None and slot not in device_faults]
        if missing and deadline - time.time() > 300:
            self.log(f"[grade s{k}] no report for {missing} — re-running those slots once")
            for slot in missing:
                retries[slot] = retries.get(slot, 0) + 1
            with ThreadPoolExecutor(max_workers=4) as ex:
                redo = {r[0]: r for r in ex.map(lambda s: run_one(s, attempt=2), missing)}
            results = [redo.get(r[0], r) for r in results]

        crashed: list[str] = []
        for slot, run, rep in results:
            report_task_ids[slot] = (run or {}).get("task_id")
            if rep is None:
                verdicts[slot] = None
                err = (run or {}).get("error") or (run or {}).get("_stderr_tail") or "run never produced a report"
                launch_errors[slot] = f"test could not be graded (tooling): {str(err)[-400:]}"
                # the first tooling kind wins: never overwrite a kind already recorded
                # (build kinds returned before this loop; wrong_build / no_report set here)
                failure_kind = failure_kind or ("device_fault" if slot in device_faults else "no_report")
                continue
            reports[slot] = rep
            report_uris[slot] = rep.get("report_url")
            if rep.get("build_version") != build_version:
                verdicts[slot] = None
                failure_kind = "wrong_build"
                launch_errors[slot] = "grading ran against the wrong build (tooling); this test is not scored"
                continue
            if rep.get("success") is None:
                # A verdict is three-valued AT THE SOURCE: PASS, FAIL, or None (unresolved).
                # `success` is still None here when the report never grew the flag (the
                # 10/20/30 s backoff in fetch_report ran out, or the deadline check cut it
                # short) AND the run-summary fallback in run_one had no `success` either.
                # `"PASS" if rep.get("success") else "FAIL"` would read that None as falsy
                # and charge the submission a FAIL the judge never issued: a x0.80
                # submission penalty, a false entry in _regressions, and feedback telling
                # the agent to repair a screen that may be correct. Nothing downstream
                # catches it — the EMPTY_REPORT rule in _device_error_type needs
                # `success is False`. So the slot abstains, exactly like wrong_build above:
                # the report stays in `reports` (archived evidence; the `scored` filter in
                # grade_submission drops slots whose verdict is not PASS/FAIL) and the kind
                # is the bench-fault "no_report", which the scorer refunds.
                verdicts[slot] = None
                failure_kind = failure_kind or "no_report"
                launch_errors[slot] = "test could not be graded (tooling): the report never resolved its success flag"
                continue
            verdicts[slot] = "PASS" if rep["success"] else "FAIL"
            # surface app launch/crash text if the report carries one (shape-tolerant; the
            # report's field is `error_message`, the run summary's is `error`)
            for src, key in ((rep, "error_message"), (rep, "error"), (rep, "launch_error"),
                             (rep, "crash"), (run, "error")):
                if src and src.get(key):
                    launch_errors[slot] = str(src[key])[:1500]
                    break
            if _device_error_type(run, rep) in AGENT_LAUNCH_ERRORS:
                crashed.append(slot)
        if crashed and failure_kind is None:
            # the binary crashed on launch, twice (the re-run in run_one already happened).
            # Agent fault, like build_failed: the verdict rows stay FAIL and a consumer of
            # the record scores the submission 0.0 instead of dropping it — also when
            # another slot produced blocks (key on failure_kind, not on the fraction).
            # The `failure_kind is None` guard is the whole point: a tooling kind recorded
            # on another slot (no_report, device_fault, wrong_build) is never overwritten.
            failure_kind = "app_crash"
        return finish()


def _regressions(history: list[dict[str, Any]], verdicts: dict[str, str | None]) -> list[str]:
    """Tests PASS at the most recent *graded* submission (one with at least one non-None
    verdict) and FAIL now. Only exists because grading is full-suite."""
    prev = None
    for rec in reversed(history):
        v = rec.get("verdicts") or {}
        if any(x is not None for x in v.values()):
            prev = v
            break
    if not prev:
        return []
    return [s for s in SLOTS if prev.get(s) == "PASS" and verdicts.get(s) == "FAIL"]
