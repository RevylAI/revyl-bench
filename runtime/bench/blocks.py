"""bench.blocks — the per-block verdict vector, kept in the grading-side record.

Every graded run already computes one verdict per YAML block: ~48 per task across the four
frozen suites. `bench.redact` keeps only the FAILING ones (the
agent must not learn which criteria passed) and `verdicts.json` keeps the AND of each
suite's blocks — so ~48 verdicts are computed on every device run and 4 bits are persisted.

That is fine for a pass/fail leaderboard and useless for anything that needs partial
credit, which needs the vector underneath. This module extracts it from the raw reports the runner already has in
hand, at zero extra device cost: the run already happened.

WHERE THIS MAY AND MAY NOT GO
    attempts.jsonl (log/, collected to runs/)   YES — grading-side, never shown to a solver
    feedback/ (the agent's mailbox)             NO  — redact.py owns that and stays as is

Putting the vector in the feedback bundle would hand the solver the answer key for every
criterion it has not yet failed, which is exactly the leak redact.py exists to close.
"""
from __future__ import annotations

from typing import Any

# Statuses that mean "the judge decided this block did not hold". `warning` is a judged
# partial, so it belongs here; `error`/`errored` do NOT — see ERRORED below.
FAILED = {"failed", "warning"}

# The CLI/device failed to produce a judgement: transport error, timeout, dead session.
# These are DELIBERATELY NOT in FAILED, which is where this module stops mirroring
# redact.FAILED_STATUSES = {"failed","error","errored","warning"}. The two views want
# different answers to "did this block pass":
#
#   redact  → the agent's feedback bundle. Everything that did not pass is disclosed,
#             infra included, because the agent may need to react to it.
#   blocks  → the partial-credit record. An errored block is not evidence about the agent's code,
#             and scoring it `failed` invents a regression the agent did not cause.
#
# So they abstain: `unknown` is excluded from `decided` in summary(), which keeps it out
# of both the numerator and the denominator of `fraction`. An infra failure shrinks the
# sample rather than lowering the score. `total - decided` is the abstention count.
ERRORED = {"error", "errored"}


def _status(step: dict[str, Any]) -> str:
    """Normalise to passed | failed | unknown. `effective_status` wins where present — it
    is what the report itself uses for its pass/fail counts."""
    st = (step.get("effective_status") or step.get("status") or "").lower()
    if step.get("validation_result") is False:
        return "failed"
    if st in ERRORED:
        return "unknown"
    return "failed" if st in FAILED else ("passed" if st else "unknown")


def extract(reports: dict[str, dict[str, Any] | None]) -> list[dict[str, Any]]:
    """reports: slot → raw report json (None when the suite never produced one).

    Returns one row per block, in suite then execution order. A slot with no report
    contributes nothing rather than a row of nulls — "the suite did not run" is already
    carried by verdicts[slot] is None, and inventing per-block rows for it would let a
    consumer mistake a missing run for 48 failures.
    """
    out: list[dict[str, Any]] = []
    for slot, rep in reports.items():
        if not rep:
            continue
        # `test_name` is the frozen suite (s1ht-t_2-habits-detail) — the identifier the
        # rest of the bench joins on. app_name is the GRADING APP and is the same string
        # for all four suites, so every block row would have recorded which app it ran in
        # rather than which test it belongs to. redact.py reads test_name from the same
        # payload; these two views of a report must not disagree.
        test = rep.get("test_name") or rep.get("name") or rep.get("app_name") or ""
        for step in rep.get("steps") or []:
            out.append({
                "slot": slot,
                "test": test,
                # execution_order is what lines up with the frozen YAML block order;
                # node_id is stable across runs and is the join key for stability work
                "index": step.get("execution_order"),
                "node_id": step.get("node_id"),
                "type": step.get("step_type"),
                "status": _status(step),
                "text": step.get("step_description"),
            })
    return out


def summary(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts a consumer can use without re-deriving them. `fraction` is over blocks that
    got a verdict; `unknown` rows abstain rather than counting as failures."""
    decided = [b for b in blocks if b["status"] in ("passed", "failed")]
    passed = sum(b["status"] == "passed" for b in decided)
    return {
        "total": len(blocks),
        "decided": len(decided),
        "passed": passed,
        "failed": len(decided) - passed,
        "fraction": round(passed / len(decided), 4) if decided else None,
        "by_type": {t: sum(b["type"] == t for b in blocks)
                    for t in sorted({b["type"] for b in blocks if b["type"]})},
    }
