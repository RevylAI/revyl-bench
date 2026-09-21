"""bench.attempts — the append-only linkage log, one JSON line per submission (+ one END
line per rollout). A superset of what the scorer reads today.

Why a superset and why append-only: scoring is an OPEN decision, so the
rule is "capture everything now, decide the formula later" — every candidate metric
(Resolve@cap, AUP, regression rate, first-submission vector, repair efficiency) must be
computable from these lines alone, retroactively, without re-running anything.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append(path: Path, record: dict[str, Any]) -> None:
    """Atomic enough for one writer: open-append-write-close per line; the runner is the
    only writer of attempts.jsonl for its rollout."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_all(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def submission_record(*, spec: dict[str, Any], k: int, ts_submit: str, ts_build_start: str | None,
                      ts_grade_start: str | None, ts_verdict: str, commit_id: str, tree_sha256: str,
                      eas_build_id: str | None, build_version: str, build_version_id: str | None,
                      verdicts: dict[str, str | None], regressions: list[str], lint_warnings: list[str],
                      failure_kind: str | None, report_task_ids: dict[str, str | None],
                      report_uris: dict[str, str | None], raw_reports_dir: str,
                      wall_clock_s: float, retries: dict[str, int] | None = None,
                      build_job_id: str | None = None,
                      blocks: list[dict[str, Any]] | None = None,
                      blocks_summary: dict[str, Any] | None = None,
                      perf: dict[str, Any] | None = None,
                      network_requests: dict[str, int] | None = None) -> dict[str, Any]:
    """Assemble one attempts-log line. `spec` is the rollout.json dict; the contestant entry is
    embedded whole so a row is self-describing even if the registry changes later."""
    return {
        "type": "submission",
        "rollout_id": spec["rollout_id"], "task": spec["task"], "prefix": spec["prefix"],
        "contestant": spec["contestant"], "seed": spec["seed"],
        "protocol_version": spec["protocol_version"], "split": spec.get("split"), "k": k,
        "ts_submit": ts_submit, "ts_build_start": ts_build_start, "ts_grade_start": ts_grade_start,
        "ts_verdict": ts_verdict, "wall_clock_s": round(wall_clock_s, 1),
        "commit_id": commit_id, "tree_sha256": tree_sha256,
        # which builder produced the graded binary: at most
        # one of eas_build_id / build_job_id is set (both null when the build never got a job:
        # cli_error/refused rows); `builder` is also in the spec via to_dict(), duplicated here
        # so a grep finds it.
        "builder": spec.get("builder", "eas"), "eas_build_id": eas_build_id, "build_job_id": build_job_id,
        "build_version": build_version, "build_version_id": build_version_id,
        # verdicts: slot → "PASS" | "FAIL" | None (None = never ran: build_failed / wrong_build / timeout)
        "verdicts": verdicts, "regressions": regressions, "lint_warnings": lint_warnings,
        # The per-BLOCK vector underneath those four bits (bench.blocks; the dense per-block reward).
        # ~48 verdicts are computed on every graded run and four were persisted; the run
        # already happened, so keeping the rest costs nothing. Grading-side only — the
        # agent's bundle is written by bench.redact and is untouched.
        #
        # Concretely: a submission whose verdicts read {t_1:PASS, t_2:PASS, t_3:FAIL,
        # final:PASS} can have 52 of its 53 blocks passing. The four bits turn a
        # 98%-correct submission into a binary failure; the vector keeps the difference,
        # which is what the block-fraction term of the score is computed from.
        "blocks": blocks or [], "blocks_summary": blocks_summary or {},
        # observability (runner/observability.py): hardware summary per slot, and the
        # count of captured HTTP requests — nonzero is a red flag on offline-by-contract
        # apps. Both best-effort; None = not captured, never a judgement.
        "perf": perf, "network_requests": network_requests,
        # failure_kind != None ⇒ not a plain graded row; build_failed and app_crash are
        # agent-fault (scored 0, consumes k), every other kind is bench-fault (refunded)
        "failure_kind": failure_kind,
        # slot → wrong-build regrade count (empty = no retries fired)
        "retries": retries or {},
        "report_task_ids": report_task_ids, "report_uris": report_uris,
        "raw_reports_dir": raw_reports_dir,
    }


def end_record(*, spec: dict[str, Any], end_reason: str, k_final: int, harness_tokens_in: int | None,
               harness_tokens_out: int | None, harness_turns: int | None, transcript_path: str | None,
               device_sessions: int | None, violations: list[str], wall_clock_s: float,
               device_usage: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "end", "rollout_id": spec["rollout_id"], "task": spec["task"],
        "contestant": spec["contestant"], "seed": spec["seed"],
        "protocol_version": spec["protocol_version"], "split": spec.get("split"),
        "end_reason": end_reason, "k_final": k_final, "wall_clock_s": round(wall_clock_s, 1),
        "harness_tokens_in": harness_tokens_in, "harness_tokens_out": harness_tokens_out,
        "harness_turns": harness_turns, "transcript_path": transcript_path,
        # device_sessions = sessions-file snapshot count: teardown aid, NOT a usage metric
        # (undercounts — agent-stopped sessions vanish from the file). Usage truth is
        # device_usage, derived from the transcript's Bash tool_use records.
        "device_sessions": device_sessions,
        "device_usage": device_usage or {"device_cmds": None, "device_taps": None,
                                         "device_screenshots": None, "device_loop_span_s": None},
        "violations": violations, "ts": now_iso(),
    }
