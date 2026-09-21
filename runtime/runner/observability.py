"""Post-suite observability checks: log assertions, perf capture, network silence.

The device platform records more than the screen: os_log (including the app's JS console
channel), hardware metrics, and HTTP traffic, all retrievable per run id after a suite
finishes (`revyl run logs|perf|network`). Three uses, in order of strictness:

  LOG ASSERTIONS (graded when a task declares them; no published task does). A task may declare exact substrings that must appear in the
  app's log output for a given suite — the contract tells the agent to emit them on
  specific actions (`AUDIT|move-card|c3|todo->done`), the suite's instructions cause
  those actions, and the match is a deterministic string comparison. No judge, no
  screenshot: this grades the logic path the screen cannot show. Declared per task in
  [runtime.grading].log_assertions; tasks that declare none are untouched. Matches enter the block
  vector as type "log" rows, so they flow into block fraction like any judged block.

  PERF CAPTURE (recorded, not graded). FPS / CPU / RSS / first-frame per suite, stored
  on the submission row. Grading on it needs a variance baseline first (the same
  verdict-stability caveat applies to hardware numbers too); recording it is free and
  makes that baseline collectible.

  NETWORK SILENCE (integrity warning). Every task's contract is offline-by-construction,
  so captured HTTP traffic on a graded run means an accidental network dependency or an
  app phoning out for answers. Recorded as a count + warning; a policy decision can
  harden it to a failure later.

Everything here is best-effort: an observability fetch that fails must never fail the
grade. A missing CLI, an expired capture, a schema change — all degrade to "not
recorded", logged, never raised.
"""
from __future__ import annotations

import json
import subprocess
from typing import Any, Callable

Log = Callable[[str], None]


def _run_cli(args: list[str], timeout: int = 120) -> tuple[int, str]:
    try:
        p = subprocess.run(["revyl", "run", *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:  # noqa: BLE001 — best-effort by contract (module docstring)
        return -1, f"{type(e).__name__}: {e}"


def log_assertion_rows(assertions: dict[str, list[str]],
                       report_task_ids: dict[str, str | None],
                       suite_names: dict[str, str],
                       log: Log) -> list[dict[str, Any]]:
    """One block row per declared pattern: type "log", status passed/failed/unknown.

    unknown (abstain) when the log fetch itself failed — the pattern was never checked,
    and scoring an unfetched log as failed would invent a regression the policy did not
    cause (same rule as bench.blocks ERRORED).
    """
    rows: list[dict[str, Any]] = []
    for slot, patterns in assertions.items():
        if not patterns:
            continue
        rid = report_task_ids.get(slot)
        text, fetched = "", False
        if rid:
            rc, out = _run_cli(["logs", rid])
            fetched = rc == 0
            text = out if fetched else ""
            if not fetched:
                log(f"[obs] run logs fetch failed for {slot} ({rid}): {out[-160:]}")
        for i, pat in enumerate(patterns):
            status = "unknown" if not fetched else ("passed" if pat in text else "failed")
            rows.append({"slot": slot, "test": suite_names.get(slot, slot), "index": 1000 + i,
                         "node_id": f"log-{slot}-{i}", "type": "log",
                         "status": status, "text": pat})
        if fetched:
            n_ok = sum(1 for r in rows if r["slot"] == slot and r["status"] == "passed")
            log(f"[obs] {slot}: {n_ok}/{len(patterns)} log assertions matched")
    return rows


def perf_summaries(report_task_ids: dict[str, str | None], log: Log) -> dict[str, Any]:
    """slot → the platform's hardware-metrics summary (parsed if JSON, else raw text
    head). Recorded verbatim; interpretation stays downstream."""
    out: dict[str, Any] = {}
    for slot, rid in report_task_ids.items():
        if not rid:
            continue
        rc, text = _run_cli(["perf", rid, "--json"])
        if rc != 0:
            continue
        try:
            out[slot] = json.loads(text[text.index("{"):text.rindex("}") + 1])
        except Exception:  # noqa: BLE001
            out[slot] = {"raw": text[:2000]}
    if out:
        log(f"[obs] perf captured for {sorted(out)}")
    return out


def network_counts(report_task_ids: dict[str, str | None], log: Log) -> dict[str, int]:
    """slot → number of captured HTTP requests. Non-zero is a red flag on an
    offline-by-contract app; recorded and warned, not failed (policy decides later)."""
    out: dict[str, int] = {}
    for slot, rid in report_task_ids.items():
        if not rid:
            continue
        rc, text = _run_cli(["network", rid, "--json"])
        if rc != 0:
            continue
        try:
            payload = json.loads(text[text.index("{"):text.rindex("}") + 1])
            reqs = payload.get("requests") or payload.get("entries") or []
            out[slot] = len(reqs) if isinstance(reqs, list) else int(payload.get("count", 0))
        except Exception:  # noqa: BLE001
            # a list-shaped payload
            try:
                out[slot] = len(json.loads(text[text.index("["):text.rindex("]") + 1]))
            except Exception:  # noqa: BLE001
                continue
    for slot, n in out.items():
        if n > 0:
            log(f"[obs] WARNING {slot}: {n} HTTP request(s) captured on an offline-by-contract app")
    return out
