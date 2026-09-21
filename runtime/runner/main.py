"""runner.main — the runner container's PID 1.

Loop: watch /mailbox/submit for s<k>.request.json → validate sequence/cap → grade (serial:
one submission in flight per rollout by construction) → write feedback → check termination.
On END: write /mailbox/feedback/END.json, then collect (git bundle of the agent workspace,
harness transcript, device sessions, token accounting, agent-org violations scan) into
/log, append the END record to attempts.jsonl, exit 0. launch_rollout waits on END.json.

Mounts (compose): /rollout.json (ro), /mailbox (submit ro, feedback rw), /log (rw),
/control (ro; launch_rollout writes harness_exit.json / abort), /agent-workspace (ro,
for the git bundle + .revyl/device-sessions.json ONLY — grading never reads it),
/agent-home (ro; harness transcript glob). Env (runner.env): REVYL_API_KEY = GRADING key,
EXPO_TOKEN. Nothing else.

Restart-safe: /log/state.json + attempts.jsonl are re-read at boot, so a runner restart
mid-rollout resumes with the right k and history (an in-flight grade is re-run; the EAS
build for it is re-queued — acceptable, rare).
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from bench import attempts as _attempts
from bench import revyl as _revyl
from bench.config import SLOTS, RolloutSpec
from runner.grade import Grader, _atomic_write

ROLLOUT_JSON = Path(os.environ.get("BENCH_ROLLOUT_JSON", "/rollout.json"))
MAILBOX = Path(os.environ.get("BENCH_MAILBOX", "/mailbox"))
LOG = Path(os.environ.get("BENCH_LOG", "/log"))
CONTROL = Path(os.environ.get("BENCH_CONTROL", "/control"))
AGENT_WS = Path(os.environ.get("BENCH_AGENT_WORKSPACE", "/agent-workspace"))
AGENT_HOME = Path(os.environ.get("BENCH_AGENT_HOME", "/agent-home"))
WORK = Path(os.environ.get("BENCH_WORK", "/tmp/grade"))
POLL_S = 5


def _log_factory(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    f = path.open("a", encoding="utf-8")

    def log(msg: str) -> None:
        line = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}"
        print(line, flush=True)
        f.write(line + "\n")
        f.flush()
    return log


def _pending_requests(submit: Path) -> list[int]:
    ks = []
    for p in submit.glob("s*.request.json"):
        try:
            ks.append(int(p.name[1:].split(".")[0]))
        except ValueError:
            continue
    return sorted(ks)


def _early_stop_reason() -> str | None:
    marker = CONTROL / "final_evaluation.json"
    if not marker.exists():
        return None
    trigger = json.loads(marker.read_text(encoding="utf-8")).get("reason")
    return {"malformed_tool_call": "malformed_tool_call", "policy_stop": "harness_exit"}.get(trigger)


def _all_green(v: dict[str, str | None], declared: tuple[str, ...] | list[str] = SLOTS) -> bool:
    """Every DECLARED slot passed. A step task grades a prefix — t_1, or
    t_1+t_2 — so requiring all four would mean a step-1 task that passes its entire suite
    can never end all_green and runs to cap or wall clock instead."""
    slots = [s for s in declared if s in SLOTS]
    return bool(slots) and all(v.get(s) == "PASS" for s in slots)


# ---------------------------------------------------------------------------------------
# END collection helpers
# ---------------------------------------------------------------------------------------
def _git_bundle(log) -> str | None:
    if not (AGENT_WS / ".git").exists():
        log("[end] no agent workspace .git to bundle")
        return None
    out = LOG / "workspace.bundle"
    frozen = LOG / "final-evaluation" / "workspace.bundle"
    if frozen.exists():
        shutil.copyfile(frozen, out)
        return str(out)
    with tempfile.TemporaryDirectory(prefix="workspace-save-") as scratch:
        p = subprocess.run(["bash", str(Path(__file__).resolve().parents[1] /
                                      "host/final_evaluation_snapshot.sh"), str(AGENT_WS), scratch],
                           capture_output=True, text=True)
        if p.returncode != 0:
            log(f"[end] git bundle failed: {p.stderr[-300:]}")
            return None
        shutil.copyfile(Path(scratch) / "workspace.bundle", out)
    return str(out)


def _copy_transcript(spec: RolloutSpec, log) -> tuple[str | None, int | None, int | None, int | None, dict]:
    """Copy the harness-native transcript files into /log/transcript/ and count tokens,
    turns and dev-loop usage from whichever harness wrote them: Claude Code's jsonl
    (usage blocks on assistant messages), opencode's SQLite store, or Codex's session
    jsonl (`token_usage_record` rows and `exec_command` function calls — without them a
    Codex row's cost columns and device metrics read None).

    Device metrics come from the TRANSCRIPT, not .revyl/device-sessions.json: the sessions
    file's last_activity only tracks the session handshake, and an agent that runs
    `revyl device stop` itself leaves the file empty — observed 2026-08-20: commerce
    issued 34 device commands while its sessions file showed none. The transcript records
    every Bash tool_use verbatim and is the only truthful usage source. Best-effort,
    never fatal."""
    pattern = spec.contestant.get("transcript", "")
    # the registry pattern is rooted at /home/agent; we see that home at /agent-home
    pattern = pattern.replace("/home/agent", str(AGENT_HOME))
    files = sorted(glob.glob(pattern, recursive=True))
    dev = {"device_cmds": 0, "device_taps": 0, "device_screenshots": 0, "device_loop_span_s": None}
    if not files:
        log(f"[end] no transcript files for pattern {pattern}")
        return None, None, None, None, dev
    dest = LOG / "transcript"
    dest.mkdir(exist_ok=True)
    tin = tout = turns = 0
    dev_ts: list[str] = []
    for f in files:
        try:
            shutil.copy2(f, dest / Path(f).name)
        except OSError:
            continue
        if f.endswith(".jsonl"):
            for line in Path(f).read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if d.get("type") == "assistant":
                    turns += 1
                    u = ((d.get("message") or {}).get("usage")) or {}
                    tin += int(u.get("input_tokens", 0) or 0) + int(u.get("cache_read_input_tokens", 0) or 0) \
                        + int(u.get("cache_creation_input_tokens", 0) or 0)
                    tout += int(u.get("output_tokens", 0) or 0)
                    for c in ((d.get("message") or {}).get("content") or []):
                        if not (isinstance(c, dict) and c.get("type") == "tool_use" and c.get("name") == "Bash"):
                            continue
                        cmd = (c.get("input") or {}).get("command", "")
                        if "revyl device" in cmd or "revyl dev " in cmd or cmd.rstrip().endswith("revyl dev"):
                            dev["device_cmds"] += 1
                            dev["device_taps"] += ("device tap" in cmd)
                            dev["device_screenshots"] += ("device screenshot" in cmd)
                            if d.get("timestamp"):
                                dev_ts.append(d["timestamp"])
    if len(dev_ts) >= 2:
        try:
            from datetime import datetime
            t0 = datetime.fromisoformat(dev_ts[0].replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(dev_ts[-1].replace("Z", "+00:00"))
            dev["device_loop_span_s"] = round((t1 - t0).total_seconds(), 1)
        except ValueError:
            pass
    # opencode keeps its session in SQLite (message.data carries per-turn usage, part.data
    # the tool calls). Without this reader an opencode rollout ends with tokens_in/out =
    # None and has no cost figure at all. Read the COPY in
    # /log/transcript (never the live file), read-only, best effort.
    db = dest / "opencode.db"
    if db.exists() and not tin:
        try:
            o_in, o_out, o_turns, o_dev = _opencode_usage(db)
            tin, tout, turns = o_in, o_out, o_turns
            for k_, v_ in o_dev.items():
                dev[k_] = v_ if dev.get(k_) in (None, 0) else dev[k_]
        except Exception as e:  # noqa: BLE001 — accounting must never fail a rollout
            log(f"[end] opencode usage not read: {e!r}")
    # Codex: ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl, one file per session (a
    # `resume --last` appends to the same file). Only when the Claude branch counted
    # nothing, so a Claude transcript is never double-counted.
    codex_files = [f for f in files if Path(f).name.startswith("rollout-") and f.endswith(".jsonl")]
    if codex_files and not tin:
        try:
            c_in, c_out, c_turns, c_dev = _codex_usage([Path(f) for f in codex_files])
            tin, tout, turns = c_in, c_out, c_turns
            for k_, v_ in c_dev.items():
                dev[k_] = v_ if dev.get(k_) in (None, 0) else dev[k_]
        except Exception as e:  # noqa: BLE001
            log(f"[end] codex usage not read: {e!r}")
    return str(dest), (tin or None), (tout or None), (turns or None), dev


def _codex_usage(files: list[Path]) -> tuple[int, int, int, dict]:
    """Tokens, turns and dev-loop usage from Codex session jsonl files.

    Each line is {"type", "timestamp", "payload"}. What is counted, and why it lines up
    with the other two harnesses:
      tokens in  = `token_usage_record` → usage.input_tokens per model response. Codex's
                   input_tokens already INCLUDES the cached share (cached_input_tokens is
                   a subset, not an addend), so this is the same "everything the model
                   read" total that Claude's input + cache_read + cache_creation and
                   opencode's input + cache.read give. Adding cached_input_tokens again
                   would double-count it.
      tokens out = usage.output_tokens, which in the Responses API includes
                   reasoning_output_tokens (same convention as opencode's output+reasoning).
      turns      = one per `token_usage_record` = one per model response, matching
                   "assistant messages" on the other harnesses. `event_msg/token_count`
                   is NOT used: it carries running totals and would be cumulative.
      device     = `response_item` function_call named exec_command whose JSON `cmd`
                   runs `revyl device …` or `revyl dev …`; timestamps bound the dev-loop
                   span exactly as the Claude branch does with Bash tool_use blocks."""
    tin = tout = turns = 0
    dev = {"device_cmds": 0, "device_taps": 0, "device_screenshots": 0, "device_loop_span_s": None}
    dev_ts: list[str] = []
    for f in files:
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            p = d.get("payload") or {}
            if d.get("type") == "token_usage_record":
                u = p.get("usage") or p.get("turn_token_usage") or {}
                turns += 1
                tin += int(u.get("input_tokens", 0) or 0)
                tout += int(u.get("output_tokens", 0) or 0)
            elif d.get("type") == "response_item" and p.get("type") == "function_call" \
                    and p.get("name") in ("exec_command", "shell", "local_shell"):
                try:
                    args = json.loads(p.get("arguments") or "{}")
                except json.JSONDecodeError:
                    continue
                cmd = args.get("cmd") or args.get("command") or ""
                if isinstance(cmd, list):
                    cmd = " ".join(str(x) for x in cmd)
                if "revyl device" in cmd or "revyl dev " in cmd or cmd.rstrip().endswith("revyl dev"):
                    dev["device_cmds"] += 1
                    dev["device_taps"] += ("device tap" in cmd)
                    dev["device_screenshots"] += ("device screenshot" in cmd)
                    if d.get("timestamp"):
                        dev_ts.append(d["timestamp"])
    if len(dev_ts) >= 2:
        try:
            from datetime import datetime
            t0 = datetime.fromisoformat(dev_ts[0].replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(dev_ts[-1].replace("Z", "+00:00"))
            dev["device_loop_span_s"] = round((t1 - t0).total_seconds(), 1)
        except ValueError:
            pass
    return tin, tout, turns, dev


def _opencode_usage(db: Path) -> tuple[int, int, int, dict]:
    """Tokens, turns and dev-loop usage from an opencode session store.

    tokens in  = prompt tokens incl. the cached share (the same total Claude Code's
                 input + cache_read + cache_creation gives, so the two harnesses compare)
    tokens out = output + reasoning tokens
    turns      = assistant messages
    The generic OpenAI-compatible provider reports reasoning as 0 even when the model
    thinks, so `out` is a floor for such routes (the vLLM server's counters are exact).

    The store is copied while the harness may still be running or was just killed, so the
    newest rows often live only in the -wal sidecar. A read-only open cannot replay a WAL
    (it would need to create the -shm), and a copied -shm can make the open fail. The
    remedy: copy db + sidecars to a temp dir and open that
    copy writable, so SQLite replays the WAL into a private scratch file."""
    import sqlite3
    import tempfile
    tin = tout = turns = 0
    dev = {"device_cmds": 0, "device_taps": 0, "device_screenshots": 0}
    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / "opencode.db"
        shutil.copy2(db, work)
        for side in ("-wal", "-shm"):
            s = db.with_name(db.name + side)
            if s.exists():
                shutil.copy2(s, work.with_name(work.name + side))
        con = sqlite3.connect(str(work))
        try:
            tin, tout, turns, dev = _opencode_usage_rows(con)
        finally:
            con.close()
    return tin, tout, turns, dev


def _opencode_usage_rows(con) -> tuple[int, int, int, dict]:
    tin = tout = turns = 0
    for (data,) in con.execute("select data from message"):
        try:
            m = json.loads(data)
        except json.JSONDecodeError:
            continue
        if m.get("role") != "assistant":
            continue
        turns += 1
        tk = m.get("tokens") or {}
        cache = tk.get("cache") or {}
        tin += int(tk.get("input", 0) or 0) + (int(cache.get("read", 0) or 0) if isinstance(cache, dict) else 0)
        tout += int(tk.get("output", 0) or 0) + int(tk.get("reasoning", 0) or 0)
    dev = {"device_cmds": 0, "device_taps": 0, "device_screenshots": 0}
    for (data,) in con.execute("select data from part"):
        try:
            p = json.loads(data)
        except json.JSONDecodeError:
            continue
        if p.get("type") != "tool":
            continue
        cmd = str(((p.get("state") or {}).get("input") or {}).get("command", ""))
        if "revyl device" in cmd or "revyl dev " in cmd or cmd.rstrip().endswith("revyl dev"):
            dev["device_cmds"] += 1
            dev["device_taps"] += ("device tap" in cmd)
            dev["device_screenshots"] += ("device screenshot" in cmd)
    return tin, tout, turns, dev


def _device_sessions(log) -> int | None:
    """Snapshot .revyl/device-sessions.json to /log and count its entries. TEARDOWN AID
    ONLY (launch's down() stops these session ids) — NOT a usage metric: the file is
    client-side lifecycle state, undercounts (agent-stopped sessions vanish from it), and
    its last_activity is handshake-only. Usage metrics = the device_* fields from
    _copy_transcript."""
    src = AGENT_WS / ".revyl" / "device-sessions.json"
    if not src.exists():
        return None
    try:
        shutil.copy2(src, LOG / "device-sessions.json")
        d = json.loads(src.read_text(encoding="utf-8", errors="replace"))
        if isinstance(d, list):
            return len(d)
        if isinstance(d, dict):
            for v in d.values():
                if isinstance(v, list):
                    return len(v)
    except Exception as e:  # noqa: BLE001
        log(f"[end] device-sessions read failed: {e}")
    return None


def _violations(spec: RolloutSpec, agent_key: str | None, log) -> list[str]:
    """Scan the agent org for objects the RUNBOOK forbids creating. The runner is only
    given the AGENT key for this scan if launch_rollout chose to (BENCH_AGENT_KEY in
    runner.env); without it we just record 'not scanned'."""
    if not agent_key:
        return ["not_scanned: no agent key in runner.env"]
    out: list[str] = []
    try:
        # app/build/workflow listing are ORG-level commands: no project context needed, and the
        # agent workspace's config must never be able to gate or steer this scan (same rule as
        # grade.py). chdir=None → the CLI runs from the runner's own cwd.
        proj = None
        apps = _revyl.app_list(agent_key, proj)
        for a in apps:
            if not str(a.get("name", "")).startswith("bench-"):
                out.append(f"app_created: {a.get('name')} ({a.get('id')})")
        builds = _revyl.build_list(agent_key, proj, spec.agent.dev_app_id)
        # a native rollout's own development builds (devbuild.sh names them
        # <rollout_id>-dev<k>) are the loop, not a violation; other rollouts' are theirs
        own_dev = re.compile(r"^[a-z0-9-]+-dev\d+$") if spec.agent.technology == "swift" else None
        for b in builds:
            name = str(b.get("version") or b.get("name") or "")
            # the task's own dev-client, or the one it inherits: a step or repair task pins
            # its PARENT's dev-client (bench-<parent>-devclient-vN) on the parent's dev app,
            # so the name carries the parent, not this task (flagged as foreign on every
            # step-task rollout until 2026-09-20)
            if name.startswith(f"bench-{spec.task}-devclient-") or (spec.agent.devclient_version and name == spec.agent.devclient_version):
                continue
            if own_dev and own_dev.match(name):
                continue
            out.append(f"build_uploaded: {name}")
        wfs = _revyl.workflow_list(agent_key, proj)
        for w in wfs:
            out.append(f"workflow_created: {w.get('name')}")
    except Exception as e:  # noqa: BLE001
        out.append(f"scan_error: {e}")
    return out


# ---------------------------------------------------------------------------------------
def _restore_completed_feedback(history: list[dict], feedback: Path) -> None:
    """Finish publication if a restart followed the durable grade append."""
    for rec in history:
        if rec.get("origin") == "runner_final":
            continue
        k = rec["k"]
        verdict_path = feedback / f"s{k}.verdict.json"
        if not verdict_path.exists():
            verdict = {key: rec.get(key) for key in (
                "k", "build_version", "build_version_id", "verdicts", "regressions",
                "lint_warnings", "failure_kind")}
            verdict["ts"] = rec.get("ts_verdict")
            _atomic_write(verdict_path, json.dumps(verdict))
        _atomic_write(feedback / f"s{k}.status", "done")


def main() -> int:
    log = _log_factory(LOG / "runner.log")
    # CLI pin: the image build already asserted this, but a runner started from a stale image
    # (or with REVYL_BIN overridden) must fail HERE, not at grade step 6 where a wrong CLI
    # version reads as "build_failed/upload_failed" on the agent's record.
    have, want = _revyl.version(), _revyl.PINNED_VERSION
    if not want or have != want:
        log(f"FATAL: revyl CLI {have or 'missing'} != pinned {want or '(no pin file at %s)' % _revyl.PIN_FILE}")
        return 2
    log(f"[runner] revyl CLI {have} == pin")
    spec = RolloutSpec.load(ROLLOUT_JSON)
    grading_key = os.environ.get("REVYL_API_KEY", "")
    expo_token = os.environ.get("EXPO_TOKEN", "")
    agent_key = os.environ.get("BENCH_AGENT_KEY")          # optional, violations scan only
    if not grading_key or (spec.builder == "eas" and not expo_token):
        # EXPO_TOKEN is only a requirement of the EAS rollback builder; the default revyl
        # builder needs nothing beyond the grading key (the remote-build design note).
        log(f"FATAL: runner.env must provide REVYL_API_KEY (grading){' and EXPO_TOKEN (builder=eas)' if spec.builder == 'eas' else ''}")
        return 2
    log(f"[runner] builder={spec.builder}")

    submit, feedback = MAILBOX / "submit", MAILBOX / "feedback"
    feedback.mkdir(parents=True, exist_ok=True)
    state_path = LOG / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {
        "started_at": time.time(), "last_k": 0}
    started = float(state["started_at"])
    _atomic_write(state_path, json.dumps(state))
    history = [r for r in _attempts.read_all(LOG / "attempts.jsonl") if r.get("type") == "submission"]
    _restore_completed_feedback(history, feedback)
    last_k = max([state.get("last_k", 0)] + [r["k"] for r in history])

    grader = Grader(spec, mailbox=MAILBOX, log_dir=LOG, grading_key=grading_key,
                    expo_token=expo_token, work_dir=WORK, log=log)
    log(f"[runner] ready rollout={spec.rollout_id} task={spec.task} contestant={spec.contestant_slug} "
        f"cap={spec.caps.max_submissions} wall_clock_min={spec.caps.wall_clock_min} last_k={last_k}")
    (LOG / "runner.ready").write_text(str(int(time.time())), encoding="utf-8")

    end_reason: str | None = None
    deadline_error = False
    deadline_observed = False
    fallback_only = getattr(spec, "protocol_version", 0) >= 9
    wall_s = spec.caps.wall_clock_min * 60
    while end_reason is None:
        if spec.caps.final_evaluation and not _early_stop_reason() and time.time() - started >= wall_s:
            if fallback_only and not deadline_observed:
                # Read the mailbox only after the host has stopped every agent process;
                # a submission can otherwise arrive between this scan and the freeze.
                from runner.final_evaluation import wait_for_deadline_marker
                try:
                    evidence = wait_for_deadline_marker(CONTROL)
                    if (evidence.get("rollout_id") == spec.rollout_id
                            and evidence.get("reason") in {"malformed_tool_call", "policy_stop"}):
                        # The host may publish an early stop while we wait at the deadline.
                        continue
                    if (evidence.get("status") not in {"ready", "skipped"}
                            or evidence.get("rollout_id") != spec.rollout_id
                            or evidence.get("reason") != "wall_clock"):
                        raise RuntimeError("host did not confirm the deadline stop")
                    deadline_observed = True
                except Exception as exc:
                    log(f"[runner] deadline stop evidence failed: {exc!r}")
                    _attempts.append(LOG / "attempts.jsonl", {
                        "type": "final_evaluation_error", "rollout_id": spec.rollout_id,
                        "failure_kind": "runner_crash", "error": str(exc)[:500]})
                    deadline_error = True
                    end_reason = "wall_clock"
                    break
            # A restarted runner must finish its already-started immutable manual
            # snapshot before allocating the next grade sequence to the final tree.
            pending_status = feedback / f"s{last_k + 1}.status"
            resume_grade = ((fallback_only or (pending_status.exists()
                            and pending_status.read_text().strip() in {"queued", "building", "grading"}))
                            and (submit / f"s{last_k + 1}.request.json").exists()
                            and not (feedback / f"s{last_k + 1}.verdict.json").exists())
            if not resume_grade:
                end_reason = "wall_clock"
                break
        # 1. any pending request? (process in order; only the expected k is accepted)
        # A request is pending if it has no verdict AND is not terminally rejected. A non-
        # terminal status file ("queued"/"building"/"grading") does NOT exclude it: after a
        # runner restart the in-flight grade must be re-run, not skipped (the EAS build it
        # had queued is abandoned — wasteful but correct; rare path).
        def _st(k: int) -> str:
            f = feedback / f"s{k}.status"
            return f.read_text(encoding="utf-8").strip() if f.exists() else ""
        pending = [k for k in _pending_requests(submit) if not (feedback / f"s{k}.verdict.json").exists()
                   and not _st(k).startswith("rejected")]
        for k in pending:
            if k != last_k + 1:
                _atomic_write(feedback / f"s{k}.status", f"rejected: sequence (expected {last_k + 1})")
                log(f"[runner] rejected s{k}: sequence")
                continue
            if k > spec.caps.max_submissions:
                _atomic_write(feedback / f"s{k}.status", "rejected: cap")
                log(f"[runner] rejected s{k}: cap")
                continue
            # wait for the tarball to be fully present (request.json is written last, but be safe)
            for _ in range(30):
                if (submit / f"s{k}.tar.gz").exists():
                    break
                time.sleep(1)
            log(f"[runner] grading s{k}")
            try:
                rec = grader.grade_submission(k, history=history, rollout_started=started)
            except Exception as e:  # noqa: BLE001 — never leave the agent polling forever
                log(f"[runner] grade s{k} CRASHED: {e!r}")
                _atomic_write(feedback / f"s{k}.verdict.json", json.dumps({
                    "k": k, "build_version": spec.build_version(k), "build_version_id": None,
                    "verdicts": {s: None for s in SLOTS}, "regressions": [], "lint_warnings": [],
                    "failure_kind": "runner_crash", "error": repr(e)[:500], "ts": _attempts.now_iso()}))
                _atomic_write(feedback / f"s{k}.status", "done")
                rec = {"k": k, "verdicts": {s: None for s in SLOTS}, "failure_kind": "runner_crash"}
                _attempts.append(LOG / "attempts.jsonl", {"type": "submission", "rollout_id": spec.rollout_id,
                                                          "k": k, "failure_kind": "runner_crash",
                                                          "verdicts": rec["verdicts"], "error": repr(e)[:500]})
            history.append(rec)
            last_k = k
            state["last_k"] = k
            _atomic_write(state_path, json.dumps(state))
            if _all_green(rec.get("verdicts", {}), tuple(spec.grading.tests)):
                end_reason = "all_green"
            elif k >= spec.caps.max_submissions:
                end_reason = "cap"
            break   # re-scan; termination checks below

        if (CONTROL / "abort").exists():
            end_reason = "abort"
        elif (spec.caps.final_evaluation and _early_stop_reason()
                and not _pending_requests_unprocessed(submit, feedback, last_k)):
            end_reason = _early_stop_reason()
        if end_reason:
            break
        # 2. control signals from launch_rollout
        if (CONTROL / "abort").exists():
            end_reason = "abort"
        elif (CONTROL / "harness_exit.json").exists() and not _pending_requests_unprocessed(submit, feedback, last_k):
            end_reason = _harness_end_reason(CONTROL / "harness_exit.json")
        # 3. wall clock
        elif time.time() - started > wall_s:
            if spec.caps.final_evaluation and fallback_only and not deadline_observed:
                continue  # stop confirmation and a stable mailbox scan happen above
            end_reason = "wall_clock"
        if end_reason is None:
            time.sleep(POLL_S)

    # The host freezes the workspace on time even while grade_submission is busy.
    # Complete that grade, then evaluate the frozen tree without more agent feedback.
    submitted = any(r.get("origin") != "runner_final" for r in history) or bool(_pending_requests(submit))
    if (spec.caps.final_evaluation and not deadline_error and end_reason != "abort"
            and (_early_stop_reason() or (
                not (fallback_only and submitted) and time.time() - started >= wall_s
                and end_reason in {"wall_clock", "all_green", "cap", "harness_exit"}))):
        from runner.final_evaluation import grade_final_snapshot
        end_reason = _early_stop_reason() or "wall_clock"
        try:
            rec = grade_final_snapshot(
                spec, control=CONTROL, log_dir=LOG, work_dir=WORK, history=history,
                rollout_started=started, grading_key=grading_key, expo_token=expo_token, log=log,
                agent_mailbox=MAILBOX)
            if not any(r.get("origin") == "runner_final" for r in history):
                history.append(rec)
            last_k = rec["k"]
            state["last_k"] = last_k
            _atomic_write(state_path, json.dumps(state))
        except Exception as exc:
            log(f"[runner] final evaluation failed: {exc!r}")
            _attempts.append(LOG / "attempts.jsonl", {
                "type": "final_evaluation_error", "rollout_id": spec.rollout_id,
                "failure_kind": "runner_crash", "error": str(exc)[:500]})

    # ---- END ---------------------------------------------------------------------------
    log(f"[end] reason={end_reason} k_final={last_k}")
    _atomic_write(feedback / "END.json", json.dumps({"reason": end_reason, "k_final": last_k,
                                                     "ts": _attempts.now_iso()}))
    bundle = _git_bundle(log)
    tpath, tin, tout, turns, dev_usage = _copy_transcript(spec, log)
    nsess = _device_sessions(log)
    viol = _violations(spec, agent_key, log)
    (LOG / "violations.json").write_text(json.dumps(viol, indent=2), encoding="utf-8")
    end = _attempts.end_record(
        spec=spec.to_dict(), end_reason=end_reason, k_final=last_k, harness_tokens_in=tin,
        harness_tokens_out=tout, harness_turns=turns, transcript_path=tpath, device_sessions=nsess,
        violations=viol, wall_clock_s=time.time() - started, device_usage=dev_usage)
    end["agent_submission_count"] = sum(r.get("origin") != "runner_final" for r in history)
    end["final_evaluation_count"] = sum(r.get("origin") == "runner_final" for r in history)
    _attempts.append(LOG / "attempts.jsonl", end)
    log(f"[end] collected bundle={bundle} transcript={tpath} tokens_in={tin} tokens_out={tout} "
        f"turns={turns} device_cmds={dev_usage.get('device_cmds')}")
    return 0


def _harness_end_reason(signal: Path) -> str:
    """`harness_crash` when the agent container stopped because the harness kept failing;
    `harness_exit` otherwise (the model exited without submitting, 8 times in a row).

    launch_rollout forwards the entrypoint's stop marker as `stop`. Without a marker
    (the container died outside the loop) the exit code decides: the entrypoint exits
    with the last harness rc, which is non-zero only on the failure branch. The scorer
    treats harness_crash as a bench fault (NO_RESULT) and collect voids the run so the
    cell is launched again; harness_exit remains a scored outcome."""
    try:
        d = json.loads(signal.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "harness_exit"
    stop = d.get("stop") or {}
    if stop.get("reason") == "malformed_tool_call":
        return "malformed_tool_call"
    if stop.get("reason") == "harness_crash":
        return "harness_crash"
    if stop.get("reason") == "no_progress":
        return "harness_exit"
    return "harness_crash" if str(d.get("rc", "0")) not in ("0", "") else "harness_exit"


def _pending_requests_unprocessed(submit: Path, feedback: Path, last_k: int) -> bool:
    """True if a request for last_k+1 exists that we have not yet processed — the harness may
    have submitted and then exited; that submission must still be graded."""
    nxt = f"s{last_k + 1}"
    return (submit / f"{nxt}.request.json").exists() and \
        not (feedback / f"{nxt}.verdict.json").exists() and \
        not (feedback / f"{nxt}.status").exists()   # a rejected trailing request must not block END


if __name__ == "__main__":
    sys.exit(main())
