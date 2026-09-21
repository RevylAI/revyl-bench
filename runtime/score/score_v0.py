#!/usr/bin/env python3
"""score/score_v0.py — the frozen scoring-v0 implementation (docs/scoring.md).

    python score/score_v0.py --campaign <name>         # one campaign: table + its scores.json
    python score/score_v0.py --all                     # one headline line per campaign

Reads ONLY <run>/{attempts.jsonl, rollout.json} for the formula (the doc's re-derivability
guarantee: a third party with these files must reproduce every published number), plus
<run>/status.json for what counts when scoring a campaign (docs/campaigns.md). The
scorer never writes a status file: --campaign produces scores.json and a table, nothing
else, so scoring a fetched copy has no side effects.

Score% = 100 × O × D_subs × D_time × D_reg          
  O       = 0.2·prefix(t_1..t_3) + 0.4·(final PASS)   on the LAST valid submission
  D_subs  = 0.80^(k_counted − 1)
  D_time  = 1 − 0.40·min(1, ln(T_a/300)/ln(24000/300))
  D_reg   = 0.80^R
Aggregation: cell = mean over seeds; contestant = macro-mean over task cells;
rows aggregate only within identical (protocol_version, harness_version).
"""
from __future__ import annotations

import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

# the campaign layer (runtime/campaigns.py) is stdlib-only and ships with the scorer
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import campaigns as _campaigns  # noqa: E402

# --- constants: frozen in docs/scoring.md; changing ANY of them is a v0.x re-freeze ---
W_STEP = 0.2          # per consecutive step passed (t_1..t_3, in order)
W_FINAL = 0.4         # the end-to-end test
C_SUB = 0.20          # keep 80% per extra counted submission
BETA_T = 0.40         # time penalty cap → floor 0.60 (anti-gaming: 20 pts/submission > 16 pts max time saving)
T_FLOOR_S = 300.0     # below 5 min, time is not penalized (timestamp jitter / startup)
T_BUDGET_S = 24000.0  # 400-min agent budget (480 wall minus ~5×16 min grading reserve)
C_REG = 0.20          # keep 80% per regression event

# failure_kind taxonomy: build_failed is the AGENT's (tree must build — RUNBOOK v2
# says so verbatim), and so is app_crash (the built binary does not stay running on the
# grading simulator; DeviceLaunchErrorType.APP_LAUNCH_CRASH, reproduced on idle
# infrastructure 2026-09-05). Every OTHER non-null kind is bench-fault, refunded.
# Open-world: unknown non-null values are treated bench-fault with a warning.
AGENT_FAULT_KINDS = {"build_failed", "app_crash"}
BENCH_FAULT_KINDS = {"runner_crash", "wrong_build", "upload_failed", "no_report", "device_fault",
                     "rejected_sha", "timeout", "builder_fault"}


def _ts(s: str) -> float:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def score_rollout(run_dir: Path, *, adjudicated: bool = False) -> dict:
    """One rollout → its score record (or a NO_RESULT record with the reason).

    `adjudicated` is the campaign layer's `adjudicated_ok`: the END row carries
    violations, a human reviewed them as benign, so the run is scored instead of
    stopping at ADJUDICATE. The formula is untouched either way."""
    # the rollout id comes from rollout.json: inside a campaign the folder is named
    # <task>_s<seed>_<8hex> for humans, and only the legacy flat store names it by the id
    rid = run_dir.name
    out = {"rollout_id": rid, "status": "scored", "flags": [], "score_pct": None}
    af = run_dir / "attempts.jsonl"
    sf = run_dir / "rollout.json"
    if not af.exists() or not sf.exists():
        out.update(status="NO_RESULT", flags=["missing_artifacts"])
        return out
    try:
        spec = json.loads(sf.read_text(encoding="utf-8"))
        rows = [json.loads(l) for l in af.read_text(encoding="utf-8").splitlines() if l.strip()]
    except ValueError as e:
        out.update(status="NO_RESULT", flags=[f"malformed_artifacts: {e}"])
        return out
    out["rollout_id"] = spec.get("rollout_id") or rid
    subs = [r for r in rows if r.get("type") == "submission" or "verdicts" in r]
    ends = [r for r in rows if r.get("type") == "end" or "end_reason" in r]

    out["task"] = spec.get("task")
    out["seed"] = spec.get("seed")
    cont = spec.get("contestant") or {}
    out["contestant"] = cont.get("model", "?") if isinstance(cont, dict) else str(cont)
    out["slug"] = spec.get("contestant_slug") or (isinstance(cont, dict) and f"{cont.get('harness')}/{cont.get('model')}") or "?"
    out["protocol_version"] = spec.get("protocol_version")
    # 0 == legacy run recorded before rollout.json carried the contract generation
    out["task_version"] = int(spec.get("task_version", 0) or 0)
    out["harness_version"] = (cont or {}).get("harness_version") if isinstance(cont, dict) else None

    # ---- human and p0-mode exclusion: declared mode field wins; the null-tokens
    # heuristic applies ONLY to legacy rows with no mode field (else it would swallow
    # guard_abort tombstones, whose END legitimately has no token counts) ---------------
    if "mode" in spec:
        if spec["mode"] != "full":
            out.update(status="EXCLUDED", flags=[f"mode={spec['mode']}"])
            return out
    elif (ends and ends[-1].get("end_reason") != "guard_abort"
          and ends[-1].get("harness_tokens_in") is None and ends[-1].get("transcript_path") is None):
        out.update(status="EXCLUDED", flags=["suspected_human_run (null tokens+transcript; pre-F1 row)"])
        return out

    # ---- structural validation: one END, last, k gap-free -------------------
    if len(ends) != 1:
        out.update(status="NO_RESULT", flags=[f"end_records={len(ends)} (need exactly 1) — audit"])
        return out
    end = ends[0]
    end_ts = _ts(end["ts"])
    post_end = [r for r in subs if _ts(r["ts_verdict" if r.get("ts_verdict") else "ts_submit"]) > end_ts + 1]
    if post_end:
        out["flags"].append("rows_after_end")   # dropped
        subs = [r for r in subs if r not in post_end]
    ks = [r.get("k") for r in subs]
    if ks != list(range(1, len(ks) + 1)):
        out.update(status="NO_RESULT", flags=out["flags"] + [f"k_sequence={ks} — audit"])
        return out

    # ---- bench-side END: the harness could not run, the model had no turn -----------
    # collect() voids such a run so the campaign layer re-launches the cell; this guard is
    # for a run scored outside a campaign (or before collect learned to void it): a
    # partial vector from before the crash must never become a score.
    if end.get("end_reason") == "harness_crash":
        out.update(status="NO_RESULT", flags=out["flags"] + ["harness_crash — bench fault (harness failed to run), re-run"])
        return out

    # ---- eligibility split ----------------------------------------------
    clean = [r for r in subs if r.get("failure_kind") is None]
    agent_fault = [r for r in subs if r.get("failure_kind") in AGENT_FAULT_KINDS]
    bench_fault = [r for r in subs if r.get("failure_kind") is not None and r.get("failure_kind") not in AGENT_FAULT_KINDS]
    for r in bench_fault:
        if r.get("failure_kind") not in BENCH_FAULT_KINDS:
            out["flags"].append(f"unknown_failure_kind={r.get('failure_kind')} (quarantined)")
    out["tooling_rows"] = len(bench_fault)
    if not subs:
        # zero submissions: the wall clock ran out, or the harness ended on its own (the
        # agent closed its session without submitting) — both are the agent's outcome and
        # score 0 with an audit flag; a crash or an unknown end is NO_RESULT.
        if end.get("end_reason") in ("wall_clock", "harness_exit", "malformed_tool_call"):
            out.update(score_pct=0.0, flags=out["flags"] + [f"zero_submissions_audit end={end.get('end_reason')}"])
        else:
            out.update(status="NO_RESULT", flags=out["flags"] + [f"no_submissions end={end.get('end_reason')}"])
        return out
    if not clean:
        if agent_fault:
            # every graded submission was the agent's own fault (the tree did not build, or
            # the built app crashed on launch): a decided 0, not a drop. Bench-fault rows in
            # the same run are refunded as always; they do not turn the agent's 0 into a drop
            out.update(score_pct=0.0, k_counted=len(agent_fault),
                       flags=out["flags"] + ["all_rows_agent_fault — scored 0"]
                       + ([f"bench_fault_rows={len(bench_fault)} refunded"] if bench_fault else []))
            return out
        out.update(status="NO_RESULT", flags=out["flags"] + ["all_rows_bench_fault — re-run"])
        return out

    # ---- O: last valid vector -------------------------------------------------
    last = max(clean, key=lambda r: r["k"])
    v = last["verdicts"]
    prefix = 0
    for t in ("t_1", "t_2", "t_3"):
        if v.get(t) == "PASS":
            prefix += 1
        else:
            break
    O = W_STEP * prefix + W_FINAL * (v.get("final") == "PASS")
    # incoherence flags → flake adjudication (it has happened: a later stage PASS after an earlier FAIL)
    seen_fail = False
    for t in ("t_1", "t_2", "t_3"):
        if v.get(t) == "FAIL":
            seen_fail = True
        elif v.get(t) == "PASS" and seen_fail:
            out["flags"].append("incoherent_steps")
            break
    if v.get("final") == "PASS" and prefix < 3:
        out["flags"].append("incoherent_final")

    # ---- k_counted, T_a, R ----------------------------------------------------
    counted = sorted(clean + agent_fault, key=lambda r: r["k"])
    k_counted = len(counted)
    start = end_ts - end["wall_clock_s"]
    ta = _ts(counted[0]["ts_submit"]) - start
    for j in range(1, len(counted)):
        prev = counted[j - 1]
        # a bench-fault row between counted rows: its redo time is the bench's, but we
        # only exclude it implicitly via verdict→submit gaps of COUNTED rows
        ta += _ts(counted[j]["ts_submit"]) - _ts(prev.get("ts_verdict") or prev["ts_submit"])
    ta = max(ta, T_FLOOR_S)
    R = 0
    best: dict[str, bool] = {}
    for r in sorted(clean, key=lambda r: r["k"]):
        for t, verdict in (r.get("verdicts") or {}).items():
            if verdict == "FAIL" and best.get(t):
                R += 1
            if verdict == "PASS":
                best[t] = True

    # ---- violations gate ------------------------------------------------------
    if end.get("violations"):
        if not adjudicated:
            out.update(status="ADJUDICATE", flags=out["flags"] + [f"violations={end['violations']}"])
            return out
        out["flags"].append(f"violations_adjudicated={end['violations']}")

    d_subs = (1 - C_SUB) ** (k_counted - 1)
    d_time = 1 - BETA_T * min(1.0, math.log(ta / T_FLOOR_S) / math.log(T_BUDGET_S / T_FLOOR_S))
    d_reg = (1 - C_REG) ** R
    out.update(score_pct=round(100 * O * d_subs * d_time * d_reg, 1),
               O=O, k_counted=k_counted, T_a_s=round(ta, 1), R=R,
               d_subs=round(d_subs, 3), d_time=round(d_time, 3), d_reg=round(d_reg, 3),
               resolved=(O == 1.0), end_reason=end.get("end_reason"),
               turns=end.get("harness_turns"), tokens_in=end.get("harness_tokens_in"),
               tokens_out=end.get("harness_tokens_out"), device_usage=end.get("device_usage"))
    return out


# =======================================================================================
# campaigns — discovery, eligibility, aggregation (docs/campaigns.md, "what counts")
# =======================================================================================
# Every run in a campaign folder ends in exactly one state. Only `scored` runs enter a
# cell; everything else is listed with its reason so "which runs made this number" is
# always answerable from scores.json alone.
STATES = ("scored", "unindexed", "live", "tombstone", "excluded", "superseded", "duplicate",
          "mismatch", "no_result", "adjudicate", "phantom_fail", "suite_fetch", "refused")


def _ids_elsewhere(cdir: Path) -> dict[str, list[str]]:
    """rollout id → the OTHER campaigns under the same root that hold a run with it. One
    id lives in exactly one campaign; a second copy is a backfill error, and it is
    checked here against the sibling folders so that `--campaign` alone sees it."""
    out: dict[str, list[str]] = {}
    for name, other, _ in _campaigns.iter_campaigns(cdir.parent):
        if other.resolve() == cdir.resolve():
            continue
        for e in _campaigns.run_index(other):
            st = e["status"]
            rid = st.get("rollout_id") if st else ((e["rollout"] or {}).get("rollout_id"))
            if rid:
                out.setdefault(rid, []).append(name)
    return out


def _run_state(rec: dict, st: dict | None, rj: dict | None, manifest: dict, run_dir: Path, scorer) -> None:
    """Fill rec["state"] (+ reason, score fields) for one run. The order of the checks is
    the order of the eligibility table in docs/campaigns.md."""
    if st is None or rj is None:
        rec.update(state="unindexed", reason=("missing status.json" if st is None else "missing rollout.json"),
                   rollout_id=((st or rj or {}).get("rollout_id")))
        return
    legit = (st.get("legitimacy") or {}).get("status") or "valid"
    rec.update(rollout_id=st.get("rollout_id"), task=st.get("task"), seed=st.get("seed"),
               created_at=st.get("created_at"), legitimacy=legit)
    lc = st.get("lifecycle")
    if lc in _campaigns.LIVE:
        rec.update(state="live", reason=lc)
        return
    if lc in _campaigns.TERMINAL_FAULTS:
        rec.update(state="tombstone", reason=lc)
        return
    if legit in ("quarantined", "void"):
        rec.update(state="excluded", reason=f"{legit}: {(st.get('legitimacy') or {}).get('reason')}")
        return
    if legit == "superseded":
        rec.update(state="superseded", reason=(st.get("legitimacy") or {}).get("reason"))
        return
    # the run must be what the manifest says the campaign is; a rollout.json that
    # disagrees on contestant, harness or protocol was launched into the wrong folder
    cm = manifest.get("contestant") or {}
    hv = (rj.get("contestant") or {}).get("harness_version") if isinstance(rj.get("contestant"), dict) else None
    mism = []
    if rj.get("contestant_slug") != cm.get("slug"):
        mism.append(f"contestant {rj.get('contestant_slug')!r} != {cm.get('slug')!r}")
    if hv != cm.get("harness_version"):
        mism.append(f"harness_version {hv!r} != {cm.get('harness_version')!r}")
    if rj.get("protocol_version") != manifest.get("protocol_version"):
        mism.append(f"protocol {rj.get('protocol_version')!r} != {manifest.get('protocol_version')!r}")
    if mism:
        rec.update(state="mismatch", reason="; ".join(mism))
        return
    mode = rj.get("mode", st.get("mode", "full"))
    if mode != "full":
        rec.update(state="excluded", reason=f"mode={mode}: not a contestant run")
        return
    s = scorer(run_dir, adjudicated=(legit == "adjudicated_ok"))
    for k, v in s.items():
        if k not in ("rollout_id",):
            rec[k] = v
    rec["flags"] = list(s.get("flags") or [])
    if s["status"] == "NO_RESULT":
        rec.update(state="no_result", reason=",".join(rec["flags"]))
        return
    if s["status"] == "EXCLUDED":
        rec.update(state="excluded", reason=",".join(rec["flags"]))
        return
    if s["status"] == "ADJUDICATE":
        rec.update(state="adjudicate", reason=",".join(rec["flags"]) + " — review, then campaign.py set --legitimacy adjudicated_ok")
        return
    checks = st.get("checks")
    if checks is None:
        # a run whose collect never wrote the checks block (a crash between the fetch and
        # the status write); the artifacts are in S3 if the check has to be run later
        rec["flags"].append("unchecked")
    elif checks.get("phantom_fail") and legit != "adjudicated_ok":
        rec.update(state="phantom_fail", reason=f"phantom-FAIL signature in {checks.get('phantom_slots')}")
        return
    elif checks.get("suite_fetch") and legit != "adjudicated_ok":
        # The agent's transcript names this repository or its grading-side/ directory
        # (campaigns.suite_fetch_hits): it may have read the suites it is graded against. The
        # run is kept out of every mean until a person has read the hits; `.get` because
        # status files written before this check existed have no such key and stay scored.
        rec.update(state="suite_fetch", reason=f"transcript names the suites' repository: {(checks.get('suite_fetch_hits') or ['?'])[0][:160]}"
                                               " — review, then campaign.py set --legitimacy adjudicated_ok")
        return
    if not (st.get("mirror") or {}).get("synced"):
        rec["flags"].append("unmirrored")
    if int(rec.get("task_version", 0) or 0) == 0:
        rec["flags"].append("provisional:no_task_version")
    rec["state"] = "scored"


def score_campaign(cdir: Path, *, scorer=None, write: bool = False) -> dict:
    """One campaign → {campaign, scored_at, records, aggregate, problems}. Reads the
    folder, never writes anything but scores.json (and only when `write`)."""
    scorer = scorer or score_rollout
    cdir = Path(cdir)
    m = _campaigns.read_manifest(cdir)
    mx = m["matrix"]
    planned_tasks, planned_seeds = list(mx["tasks"]), [int(s) for s in mx["seeds"]]
    legit = (m.get("legitimacy") or {}).get("status")
    problems: list[str] = []
    records: list[dict] = []
    for e in _campaigns.run_index(cdir):
        rec: dict = {"folder": e["folder"], "rollout_id": None, "task": None, "seed": None, "state": None,
                     "reason": None, "score_pct": None, "flags": [], "created_at": None, "legitimacy": None}
        _run_state(rec, e["status"], e["rollout"], m, e["path"], scorer)
        records.append(rec)

    elsewhere = _ids_elsewhere(cdir)
    for r in records:
        names = elsewhere.get(r.get("rollout_id") or "")
        if names:
            problems.append(f"rollout {r['rollout_id']} is also in {names}: a backfill error; refused")
            if r["state"] == "scored":
                r.update(state="refused", reason=f"also in {names}: a backfill error")

    # one counted run per cell: newest by (created_at, rollout_id) wins, the rest are
    # listed as `duplicate` problems — the scorer reports, a human resolves with `set`
    by_cell: dict[tuple[str, int], list[dict]] = {}
    for r in records:
        if r["state"] == "scored":
            by_cell.setdefault((str(r["task"]), int(r["seed"] or 0)), []).append(r)
    for (task, seed), rs in by_cell.items():
        if len(rs) > 1:
            ordered = _campaigns.newest_first(rs)
            for old in ordered[1:]:
                old.update(state="duplicate", reason=f"newer run {ordered[0]['rollout_id']} of {task} s{seed} counts")
                problems.append(f"duplicate cell {task} s{seed}: {old['rollout_id']} and {ordered[0]['rollout_id']} both collected; "
                                f"the newer counts — resolve with campaign.py set --run {old['rollout_id']} --legitimacy superseded --reason …")
    counted = [r for r in records if r["state"] == "scored"]
    outside = [r for r in counted if r["task"] not in planned_tasks or int(r["seed"]) not in planned_seeds]
    for r in outside:
        problems.append(f"{r['rollout_id']} ({r['task']} s{r['seed']}) is outside the planned matrix; not aggregated")
    counted = [r for r in counted if r not in outside]
    # a cell is one task at one contract generation: two task_versions in one cell are
    # different tests that share a name, so the cell is refused, not averaged
    refused: set[str] = set()
    for task in planned_tasks:
        vers = sorted({int(r.get("task_version", 0) or 0) for r in counted if r["task"] == task})
        if len(vers) > 1:
            refused.add(task)
            problems.append(f"cell {task} mixes contract versions {vers}; not aggregated")

    aggregate: dict | None = None
    if legit == "void":
        problems.append(f"campaign is void ({(m.get('legitimacy') or {}).get('reason')}); nothing aggregated")
    else:
        cells: dict[str, dict] = {}
        for task in planned_tasks:
            rs = [r for r in counted if r["task"] == task and task not in refused]
            n = len(rs)
            cells[task] = {"mean": round(sum(r["score_pct"] for r in rs) / n, 1) if n else None,
                           "n": n, "planned": len(planned_seeds), "incomplete": n < len(planned_seeds),
                           "refused": task in refused,
                           "solved": bool(rs) and all(r.get("resolved") for r in rs),
                           "runs": [r["rollout_id"] for r in rs]}
        with_data = {t: c for t, c in cells.items() if c["n"]}
        macro = round(sum(c["mean"] for c in with_data.values()) / len(with_data), 1) if with_data else None
        complete = bool(cells) and all(c["n"] == c["planned"] and not c["refused"] for c in cells.values())
        aggregate = {"macro": macro, "cells": cells,
                     "cells_planned": len(cells), "cells_counted": len(with_data),
                     "seeds_planned": len(cells) * len(planned_seeds), "seeds_counted": sum(c["n"] for c in cells.values()),
                     "solved": sum(1 for c in with_data.values() if c["solved"]),
                     "complete": complete,
                     # publishable = may go through `promote` without a written reason
                     "publishable": legit == "official" and complete and not problems}
    result = {"campaign": m["campaign"], "scored_at": _campaigns.now_iso(), "status_digest": _campaigns.status_digest(cdir),
              "purpose": m["purpose"],
              "legitimacy": legit, "contestant": m.get("contestant"), "protocol_version": m.get("protocol_version"),
              "matrix": mx, "records": records, "aggregate": aggregate, "problems": problems}
    if write:
        _campaigns.atomic_write_json(cdir / _campaigns.SCORES, result)
    return result


def print_campaign(res: dict) -> None:
    print(f"== {res['campaign']}  purpose {res['purpose']}  legitimacy {res['legitimacy']}  "
          f"contestant {(res.get('contestant') or {}).get('slug')}  protocol {res.get('protocol_version')}")
    print(f"{'run':<42}{'task':<26}{'seed':<6}{'state':<13}{'k':<4}{'score%':<8}flags / reason")
    for r in sorted(res["records"], key=lambda r: (str(r.get("task")), int(r.get("seed") or 0), str(r.get("created_at")))):
        tail = ",".join(r.get("flags") or []) if r["state"] == "scored" else (r.get("reason") or "")
        k = r.get("k_counted", "-") if r["state"] == "scored" else "-"
        sc = f"{r['score_pct']:<8}" if r.get("score_pct") is not None else f"{'-':<8}"
        print(f"{r['folder']:<42}{str(r.get('task')):<26}{str(r.get('seed')):<6}{r['state']:<13}{str(k):<4}{sc}{tail or '-'}")
    agg = res["aggregate"]
    if agg:
        cells = " ".join(f"{t.split('-')[1] if '-' in t else t}={c['mean'] if c['mean'] is not None else '-'}"
                         f"(n={c['n']}/{c['planned']}){'!' if c['refused'] else ''}" for t, c in sorted(agg["cells"].items()))
        print(f"\nmacro {agg['macro']}%  solved {agg['solved']}/{agg['cells_planned']}  "
              f"seeds {agg['seeds_counted']}/{agg['seeds_planned']}  "
              f"{'complete' if agg['complete'] else 'INCOMPLETE'}  {'publishable' if agg['publishable'] else 'not publishable'}")
        print(f"  {cells}")
    for p in res["problems"]:
        print(f"  !! {p}")


HEADLINE_HEADER = (f"{'campaign':<58}{'purpose':<12}{'legit':<12}{'contestant':<30}{'cells':<8}{'seeds':<10}"
                   f"{'solved':<7}{'macro':<8}{'publ':<6}problems")


def headline(res: dict) -> str:
    """One line per campaign. `publ` says whether `promote` would take it without a
    written reason: official, complete, no problems — a provisional campaign always
    reads `no` here however well it scored."""
    agg = res["aggregate"] or {}
    mx = res.get("matrix") or {}
    planned_cells = len(mx.get("tasks") or [])
    planned_seeds = planned_cells * len(mx.get("seeds") or [])
    return (f"{res['campaign']:<58}{res['purpose']:<12}{str(res['legitimacy']):<12}"
            f"{str((res.get('contestant') or {}).get('slug')):<30}"
            f"{agg.get('cells_counted', 0)}/{agg.get('cells_planned', planned_cells):<6}"
            f"{agg.get('seeds_counted', 0)}/{agg.get('seeds_planned', planned_seeds):<8}"
            f"{str(agg.get('solved', '-')):<7}{str(agg.get('macro', '-')):<8}"
            f"{('yes' if agg.get('publishable') else 'no'):<6}{len(res['problems'])} problem(s)")


def score_all(root: Path | None = None, *, scorer=None) -> list[dict]:
    """Every campaign's result, in name order. The cross-campaign rule (one rollout id in
    exactly one campaign) is applied inside score_campaign against the sibling folders."""
    return [score_campaign(cdir, scorer=scorer) for _, cdir, _ in _campaigns.iter_campaigns(root)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campaign", metavar="NAME", help="score one campaign folder and write its scores.json")
    ap.add_argument("--all", action="store_true", help="one headline line per campaign (the default)")
    ap.add_argument("--campaigns-dir", help=f"where campaigns live (default $REVYL_BENCH_CAMPAIGNS or {_campaigns.CAMPAIGNS_DIR})")
    ap.add_argument("--json", metavar="OUT", help="write the full result (or every result with --all) as JSON")
    a = ap.parse_args()

    root = Path(a.campaigns_dir) if a.campaigns_dir else None
    if a.campaign:
        cdir = _campaigns.campaign_dir(a.campaign, root)
        if not (cdir / _campaigns.MANIFEST).exists():
            print(f"no campaign {a.campaign!r} under {_campaigns.campaigns_root(root)}", file=sys.stderr)
            return 2
        res = score_campaign(cdir, write=True)
        print_campaign(res)
        print(f"\nwrote {cdir / _campaigns.SCORES}")
        if a.json:
            Path(a.json).write_text(json.dumps(res, indent=2), encoding="utf-8")
        return 0
    results = score_all(root)
    if not results:
        print(f"no campaigns under {_campaigns.campaigns_root(root)}")
    else:
        print(HEADLINE_HEADER)
        for res in results:
            print(headline(res))
    if a.json:
        Path(a.json).write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
