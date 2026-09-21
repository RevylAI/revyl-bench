"""bench.redact — turn the four RAW grading reports into the feedback bundle the agent
may see. "Report-only feedback": the Layer-2 probes stay hidden.

Rule, stated as what is EMITTED (everything else is dropped):
  per FAILED test only:
    failed_criteria.json  [{slot, test, step_index, step_type, criterion_text,
                            judge_reasoning, screenshots:[relative paths]}]
    screenshots/<slot>-step<idx>-{before,after}.png   (downloaded from the report's
                            presigned action screenshot urls)
    launch_errors.txt     app launch / crash text, if the run reported one
  verdicts.json           {slot: PASS|FAIL|null}   (also in verdict.json; duplicated
                            here so the bundle is self-contained)
NEVER emitted: passing steps' descriptions, instruction-block text of passing steps,
step counts, block counts, validation totals, the YAML, the report URI/session id
(a report link would show the whole journey in the Revyl UI).

Failed steps of ANY type are disclosed (a failed *instruction* step — "could not find
'Trip' tab" — carries its description + reason + screenshot too): progressive disclosure
through failure is intended; the submission cap bounds how much of the probe leaks.
Failed-criterion text is verbatim (by decision).

An earlier design's `verifier_detail.json` listed EVERY step's description — that was the
information leak this module exists to close.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

FAILED_STATUSES = {"failed", "error", "errored", "warning"}   # 'warning' = judged partial → treat as disclosed


def _is_failed(step: dict[str, Any]) -> bool:
    st = (step.get("effective_status") or step.get("status") or "").lower()
    return st in FAILED_STATUSES or step.get("validation_result") is False


def _download(url: str, dest: Path, timeout: int = 60) -> bool:
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=timeout) as r, dest.open("wb") as f:
            f.write(r.read())
        return True
    except Exception:
        return False


def redact(reports: dict[str, dict[str, Any] | None], verdicts: dict[str, str | None],
           out_dir: Path, *, launch_errors: dict[str, str] | None = None) -> dict[str, Any]:
    """reports: slot → raw report json (None if the test never produced one).
    Writes the bundle into out_dir and returns the failed_criteria list (for logging)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "verdicts.json").write_text(json.dumps(verdicts, indent=2), encoding="utf-8")

    failed: list[dict[str, Any]] = []
    for slot, rep in reports.items():
        if verdicts.get(slot) == "PASS" or not rep:
            continue                                # passing tests contribute NOTHING
        for step in rep.get("steps", []):
            if not _is_failed(step):
                continue                            # passing steps of a failed test: hidden
            idx = step.get("execution_order")
            shots: list[str] = []
            for a in step.get("actions", []) or []:
                for key, tag in (("screenshot_before_url", "before"), ("screenshot_after_url", "after")):
                    url = a.get(key)
                    if url:
                        rel = f"screenshots/{slot}-step{idx}-{tag}.png"
                        if _download(url, out_dir / rel):
                            shots.append(rel)
            failed.append({
                "slot": slot,
                "test": rep.get("test_name"),
                "step_index": idx,
                "step_type": step.get("step_type"),
                # for validation steps step_description IS the criterion text (captured shape)
                "criterion_text": step.get("step_description"),
                "judge_reasoning": (step.get("validation_reasoning")
                                    or (step.get("type_data") or {}).get("validation_reasoning")
                                    or step.get("effective_status_reason")
                                    or step.get("status_reason")),
                "screenshots": shots,
            })
    # A FAILed test can have ZERO failed steps — e.g. the test driver aborts mid-test on an
    # un-tappable element, and the agent gets an empty bundle. Emit the report-level status
    # text so the feedback is never blank; this reveals nothing about the suite's
    # checkpoints (it is the test-LEVEL outcome only).
    for slot, rep in reports.items():
        if verdicts.get(slot) != "FAIL" or any(f["slot"] == slot for f in failed):
            continue
        detail = None
        if rep:
            # `error_message` first: it is the field the report actually carries for a
            # device launch failure ("Device launch error: DeviceLaunchErrorType.APP_LAUNCH_CRASH
            # - App ... crashed on launch"). Without it a launch crash is reported to the
            # agent as "a target element was not tappable", and the agent cannot recover
            # from a crash it was never shown.
            detail = (rep.get("error_message") or rep.get("error") or rep.get("status_reason")
                      or rep.get("effective_status_reason") or rep.get("status"))
        failed.append({
            "slot": slot,
            "test": (rep or {}).get("test_name"),
            "step_index": None,
            "step_type": "test_level_failure",
            "criterion_text": None,
            "judge_reasoning": f"The test failed without any step-level failed criteria — the test "
                               f"driver most likely aborted mid-run (e.g. a target element was not "
                               f"tappable/reachable when the driver tried to interact with it). "
                               f"Report status: {str(detail)[:400] if detail else 'unavailable'}",
            "screenshots": [],
        })
    (out_dir / "failed_criteria.json").write_text(json.dumps(failed, indent=2, ensure_ascii=False),
                                                  encoding="utf-8")
    if launch_errors:
        txt = "\n\n".join(f"[{slot}] {msg}" for slot, msg in launch_errors.items() if msg)
        if txt.strip():
            (out_dir / "launch_errors.txt").write_text(txt, encoding="utf-8")
    return {"failed_criteria": failed}
