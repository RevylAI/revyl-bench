"""campaigns — a benchmark run is a folder (docs/campaigns.md).

One CAMPAIGN = one contestant × one purpose × one matrix of tasks × seeds, launched under
one protocol on one image. It is a folder under runtime/campaigns/ with a manifest
(campaign.json), one readable folder per rollout under runs/ (each with its own
status.json), and scores.json written only by the scorer. The layout:

    runtime/campaigns/<date>_<contestant>_<purpose>[-<label>]/
        campaign.json          the manifest: what ran, when, on which code, whether it counts
        scores.json            written by score_v0.py --campaign, never by hand
        launch.log             campaign.py launch's own log
        logs/<task>_s<seed>_<ts>.log     stdout+stderr of each launch_rollout.py it spawned
        runs/<task>_s<seed>_<8hex>/      one rollout; <8hex> is the tail of the rollout id
            status.json        lifecycle (machine), checks, mirror, legitimacy (human), history
            rollout.json  attempts.jsonl    the scoring inputs — always kept on the launch host
            reports/ feedback/ submit/ transcript/   uploaded to S3 at collect, then removed
                                                     from the launch host when the campaign slims

Two facts about a run live in status.json and are deliberately kept apart:

  lifecycle   how far the run got. Machine-written by launch_rollout.py, FORWARD-ONLY:
              launched → running → collected, or a terminal fault (guard_abort,
              launch_failed, collect_failed). A late `--resume` of a dead run can never
              turn a `collected` record back into `running`.
  legitimacy  whether the run is allowed to count: valid | superseded | quarantined |
              void | adjudicated_ok. Changed by launch (a re-run supersedes its
              predecessor) or by a human through `campaign.py set`, always with a reason,
              always appended to `history` with who and when.

The scorer reads these files and never writes them: `score_v0.py --campaign` produces
scores.json and a table, nothing else, so scoring a fetched copy has no side effects
and the launch host never drifts from S3 because someone scored it.

This module is stdlib-only and Python 3.10 compatible on purpose: the scorer imports
it, and some machines that only score still run python3 3.10 (bench.config needs
tomllib, 3.11+). Anything that needs the registry or the bench config lives in campaign.py.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

RUNTIME_ROOT = Path(__file__).resolve().parent
# task packages live beside runtime/ (the bench root); REVYL_BENCH_DIR overrides, exactly
# as bench.config.BENCH_ROOT does, so a campaign discovers the same tasks a rollout resolves
BENCH_ROOT = Path(os.environ.get("REVYL_BENCH_DIR") or RUNTIME_ROOT.parent)
CAMPAIGNS_DIR = RUNTIME_ROOT / "campaigns"

MANIFEST = "campaign.json"
STATUS = "status.json"
SCORES = "scores.json"

# ---- vocabulary --------------------------------------------------------------------
PURPOSES = ("benchmark", "calibration", "seed-check", "smoke", "experiment")
# purpose fixes the initial legitimacy: a benchmark or a calibration run is meant to
# count, a seed check is evidence about seeds rather than a contestant, and a smoke test
# or an experiment must never reach a table however well it scores
INITIAL_LEGITIMACY = {"benchmark": "official", "calibration": "official", "seed-check": "provisional",
                      "smoke": "void", "experiment": "void"}
# the scoring spec's cell is a mean over three seeds (docs/scoring.md); everything else
# is a single-seed check
BENCHMARK_SEEDS = (1, 2, 3)
DEFAULT_SEEDS = {p: ((1, 2, 3) if p == "benchmark" else (1,)) for p in PURPOSES}
# where tasks are discovered from: whole-app packages for a leaderboard row, the step
# tasks (a checkout that carries tasks-step/) for calibration and experiments
TASK_ROOT = {"benchmark": "tasks", "smoke": "tasks", "seed-check": "tasks",
             "calibration": "tasks-step", "experiment": "tasks-step"}
# Archive heavy artifacts for every purpose; fetch them back when a tool needs them.
# Explicit --keep-artifacts remains available for workflows that need local copies.
SLIM_DEFAULT = {purpose: True for purpose in PURPOSES}
SLIM_DIRS = ("reports", "feedback", "submit", "transcript", "final-evaluation")
SLIM_FILES = ("workspace.bundle",)

CAMPAIGN_LEGITIMACY = ("official", "provisional", "void")
RUN_LEGITIMACY = ("valid", "superseded", "quarantined", "void", "adjudicated_ok")
# run legitimacies that let a run count for a cell
COUNTABLE = ("valid", "adjudicated_ok")

LIFECYCLES = ("launched", "running", "collected", "guard_abort", "launch_failed", "collect_failed")
LIVE = ("launched", "running")
TERMINAL_FAULTS = ("guard_abort", "launch_failed", "collect_failed")
# forward-only ordering: a transition may move to a strictly higher rank or sideways
# between the terminal faults (a second failed salvage); it may never go down
_RANK = {"launched": 0, "running": 1, "guard_abort": 2, "launch_failed": 2, "collect_failed": 2, "collected": 3}
# status.json keys transition(**fields) may never overwrite: they are the schema
_RESERVED = frozenset({"rollout_id", "campaign", "task", "seed", "contestant_slug", "protocol_version",
                       "harness_version", "mode", "created_at", "lifecycle", "pipeline", "mirror",
                       "checks", "legitimacy", "history"})

_NAME_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


# ---- small helpers -----------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def who() -> str:
    """Attribution for history rows: the login name, so a quarantine says WHO decided it."""
    return os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic_write_json(path: Path, obj: Any) -> None:
    """write-then-rename: a reader, or an `aws s3 sync` racing us, never sees a half file.
    The temp name is unique per writer, so two processes writing the same file (a
    `sync` and a `collect` on one run) do not rename each other's temp file away."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(obj, indent=2))
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def campaigns_root(root: str | Path | None = None) -> Path:
    """Where campaigns live: an explicit root, else $REVYL_BENCH_CAMPAIGNS (tests and
    wrappers redirect the whole layer with one variable), else runtime/campaigns/."""
    if root:
        return Path(root)
    return Path(os.environ.get("REVYL_BENCH_CAMPAIGNS") or CAMPAIGNS_DIR)


def campaign_dir(name: str, root: str | Path | None = None) -> Path:
    return campaigns_root(root) / name


def campaign_name(purpose: str, contestant_slug: str, *, label: str | None = None,
                  date: str | None = None) -> str:
    """`<date>_<contestant>_<purpose>[-<label>]`, e.g.
    2026-09-03_opencode-muse-spark-1.3_benchmark. The date is the creation day (UTC);
    the slug's `/` becomes `-` so the name is one path segment."""
    if purpose not in PURPOSES:
        raise ValueError(f"purpose {purpose!r} not in {PURPOSES}")
    day = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = _NAME_SAFE.sub("-", contestant_slug.replace("/", "-")).strip("-")
    name = f"{day}_{slug}_{purpose}"
    if label:
        name += "-" + _NAME_SAFE.sub("-", label).strip("-")
    return name


def short_hex(rollout_id: str) -> str:
    """The 8 random hex at the end of `<prefix>-<short>-s<seed>-<8hex>` (bench.config
    mint_rollout_id). It is what makes two runs of one cell distinguishable, so it is the
    only part of the id the folder name keeps."""
    return rollout_id.rsplit("-", 1)[-1]


def run_folder_name(task: str, seed: int, rollout_id: str) -> str:
    """`<task>_s<seed>_<8hex>`: readable (the task and seed are in the path) and unique
    (the hex). The rollout id itself never changes — build version names and the archive
    keys inside rollout.json derive from it — only the folder is named for humans."""
    return f"{task}_s{int(seed)}_{short_hex(rollout_id)}"


def mirror_prefix(campaign: str, run_folder: str) -> str:
    """The S3 key prefix of a run: the campaign tree is mirrored under the identical path,
    so `s3://<bucket>/<prefix>/` holds exactly what the launch host held before the slim."""
    return f"campaigns/{campaign}/runs/{run_folder}"


# ---- tasks -------------------------------------------------------------------------
def discover_tasks(purpose: str, bench_root: str | Path | None = None) -> list[str]:
    """Every package under the purpose's task root that carries a task.toml. Tasks are
    discovered, never listed: a package added to the repository is in the next campaign
    by construction, and a half-provisioned directory without task.toml is invisible."""
    root = Path(bench_root) if bench_root else BENCH_ROOT
    d = root / TASK_ROOT[purpose]
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir() if (p / "task.toml").is_file())


def resolve_tasks(purpose: str, tasks: Iterable[str] | None, bench_root: str | Path | None = None) -> list[str]:
    """The campaign's task list: the discovered set, narrowed by an explicit list. An
    explicit task may come from either root (a smoke campaign on one step task is fine),
    but it must exist — a typo in --tasks would otherwise become an empty cell forever."""
    root = Path(bench_root) if bench_root else BENCH_ROOT
    if not tasks:
        found = discover_tasks(purpose, root)
        if not found:
            raise ValueError(f"no task packages under {root / TASK_ROOT[purpose]}")
        return found
    out: list[str] = []
    for t in tasks:
        t = t.strip()
        if not t:
            continue
        if not any((root / r / t / "task.toml").is_file() for r in ("tasks", "tasks-step")):
            raise ValueError(f"unknown task {t!r}: no task.toml under {root}/tasks or {root}/tasks-step")
        if t not in out:
            out.append(t)
    return out


# ---- manifest ----------------------------------------------------------------------
def new_manifest(*, purpose: str, contestant: dict[str, Any], protocol_version: int, tasks: list[str],
                 seeds: Iterable[int] | None = None, cap: int = 5, wall_clock_min: int = 480,
                 transport: str = "ec2", mode: str = "full", pipeline: dict[str, Any] | None = None,
                 created_by: str | None = None, reason: str | None = None, name: str | None = None,
                 label: str | None = None, slim: bool | None = None, notes: str = "",
                 created_at: str | None = None, ssh_ip: str | None = None) -> dict[str, Any]:
    """The manifest of a campaign that has not launched anything yet.

    The matrix is the PLAN, not the observation: the scorer compares what was collected
    against it and says "2 of 3 seeds" instead of guessing. A benchmark plans seeds
    1, 2, 3 (the scoring spec's cell). Narrowing a benchmark below three seeds needs a
    written reason and makes the campaign `provisional`, so a one-seed benchmark can
    never be `official` by construction."""
    if purpose not in PURPOSES:
        raise ValueError(f"purpose {purpose!r} not in {PURPOSES}")
    if not contestant.get("slug"):
        raise ValueError("contestant needs a slug")
    if not tasks:
        raise ValueError("a campaign needs at least one task")
    if transport not in ("ec2", "local"):
        raise ValueError(f"transport {transport!r} not in ('ec2', 'local')")
    # how the rollout host is reached over ssh: a launch host inside the bench VPC must
    # use the instance's private address (the security group does not admit its public
    # egress); a workstation outside it uses the public one. The launch host's shell
    # profile exports REVYL_BENCH_SSH_IP=private for this; recording it in the manifest means a launch
    # from a non-interactive shell (no .bashrc) cannot silently fall back to public and
    # burn fifteen minutes per host on an ssh that can never connect.
    ssh_ip = ssh_ip or os.environ.get("REVYL_BENCH_SSH_IP") or "public"
    if ssh_ip not in ("public", "private"):
        raise ValueError(f"ssh_ip {ssh_ip!r} not in ('public', 'private')")
    seed_list = sorted({int(s) for s in (seeds if seeds is not None else DEFAULT_SEEDS[purpose])})
    if not seed_list:
        raise ValueError("a campaign needs at least one seed")
    ts = created_at or now_iso()
    legit = INITIAL_LEGITIMACY[purpose]
    legit_reason = f"purpose={purpose}"
    if purpose == "benchmark" and len(seed_list) < len(BENCHMARK_SEEDS):
        if not reason:
            raise ValueError(f"a benchmark plans seeds {list(BENCHMARK_SEEDS)}; narrowing to {seed_list} "
                             f"needs --reason, and the campaign starts provisional")
        legit, legit_reason = "provisional", f"{len(seed_list)} seed(s) of {len(BENCHMARK_SEEDS)}: {reason}"
    by = created_by or who()
    return {
        "campaign": name or campaign_name(purpose, contestant["slug"], label=label, date=ts[:10]),
        "purpose": purpose,
        "created_at": ts,
        "created_by": by,
        "contestant": {"slug": contestant["slug"], "short": contestant.get("short"),
                       "model": contestant.get("model"), "harness": contestant.get("harness"),
                       "harness_version": contestant.get("harness_version")},
        "protocol_version": int(protocol_version),
        "matrix": {"tasks": list(tasks), "seeds": seed_list, "cap": int(cap),
                   "wall_clock_min": int(wall_clock_min), "transport": transport, "mode": mode,
                   "ssh_ip": ssh_ip},
        # `slim_after_mirror` decides whether reports/ feedback/ submit/ transcript/ leave
        # the launch host once they are in S3 (pass slim=False to keep them for tools that
        # read them in place)
        "slim_after_mirror": SLIM_DEFAULT[purpose] if slim is None else bool(slim),
        "pipeline": dict(pipeline or {}),
        "legitimacy": {"status": legit, "reason": legit_reason, "set_by": "campaign.py", "set_at": ts},
        "history": [{"ts": ts, "by": by, "event": "created", "reason": reason}],
        # a cache of the runs' status files, refreshed by campaign.py (single writer);
        # the status.json files are the truth, this list is for `cat campaign.json`
        "runs": [],
        "notes": notes,
    }


def create_campaign(manifest: dict[str, Any], root: str | Path | None = None) -> Path:
    """Materialize the folder. Refuses to overwrite: a campaign is never merged or
    re-created, a second one on the same day gets a --label."""
    cdir = campaign_dir(manifest["campaign"], root)
    if cdir.exists():
        raise FileExistsError(f"{cdir} exists — pick a --label, campaigns are never merged")
    (cdir / "runs").mkdir(parents=True)
    atomic_write_json(cdir / MANIFEST, manifest)
    return cdir


def read_manifest(cdir: Path) -> dict[str, Any]:
    p = Path(cdir) / MANIFEST
    if not p.exists():
        raise FileNotFoundError(f"{p} missing — not a campaign folder")
    return read_json(p)


def write_manifest(cdir: Path, manifest: dict[str, Any]) -> None:
    atomic_write_json(Path(cdir) / MANIFEST, manifest)


def manifest_for_run(run_dir: Path) -> dict[str, Any]:
    """The manifest of the campaign a run folder sits in (`<campaign>/runs/<run>`)."""
    return read_manifest(Path(run_dir).resolve().parent.parent)


def planned_cells(manifest: dict[str, Any]) -> list[tuple[str, int]]:
    m = manifest["matrix"]
    return [(t, int(s)) for t in m["tasks"] for s in m["seeds"]]


def set_campaign_legitimacy(cdir: Path, status: str, *, reason: str, by: str | None = None) -> dict[str, Any]:
    """Human override of a campaign's legitimacy. Reason mandatory: it is the audit trail."""
    if status not in CAMPAIGN_LEGITIMACY:
        raise ValueError(f"legitimacy {status!r} not in {CAMPAIGN_LEGITIMACY}")
    if not reason:
        raise ValueError("a legitimacy change needs a reason")
    m = read_manifest(cdir)
    ts, actor = now_iso(), by or who()
    m["legitimacy"] = {"status": status, "reason": reason, "set_by": actor, "set_at": ts}
    m.setdefault("history", []).append({"ts": ts, "by": actor, "event": "legitimacy", "status": status, "reason": reason})
    write_manifest(cdir, m)
    return m


def extend_manifest(cdir: Path, *, seeds: Iterable[int] | None = None, tasks: Iterable[str] | None = None,
                    reason: str, by: str | None = None, bench_root: str | Path | None = None) -> dict[str, Any]:
    """Grow the matrix (the next `launch` fills the new cells because launch is
    resumable). The pipeline guard — refuse when the current pin no longer matches — is
    campaign.py's, not this function's: the manifest layer does not know what the pin is."""
    if not reason:
        raise ValueError("extend needs a reason")
    m = read_manifest(cdir)
    added_seeds = sorted({int(s) for s in (seeds or ())} - set(m["matrix"]["seeds"]))
    new_tasks = resolve_tasks(m["purpose"], list(tasks), bench_root) if tasks else []
    added_tasks = [t for t in new_tasks if t not in m["matrix"]["tasks"]]
    if not added_seeds and not added_tasks:
        raise ValueError("nothing to add: every seed and task named is already in the matrix")
    m["matrix"]["seeds"] = sorted(set(m["matrix"]["seeds"]) | set(added_seeds))
    m["matrix"]["tasks"] = list(m["matrix"]["tasks"]) + added_tasks
    ts, actor = now_iso(), by or who()
    m.setdefault("history", []).append({"ts": ts, "by": actor, "event": "extended", "seeds": added_seeds,
                                        "tasks": added_tasks, "reason": reason})
    write_manifest(cdir, m)
    return m


# ---- status.json -------------------------------------------------------------------
def status_path(run_dir: Path) -> Path:
    return Path(run_dir) / STATUS


def read_status(run_dir: Path) -> dict[str, Any] | None:
    p = status_path(run_dir)
    return read_json(p) if p.exists() else None


def attempts_sha256(run_dir: Path) -> str | None:
    """Content hash of attempts.jsonl, the scoring input. A re-grade rewrites that file
    in place under the same rollout id and created_at, so this is the only thing that
    tells two versions of a record apart."""
    f = Path(run_dir) / "attempts.jsonl"
    return hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None


def cell_fields(rollout: dict[str, Any]) -> dict[str, Any]:
    """The fields that define a scoring cell, copied out of rollout.json so that
    `cat status.json` shows them — the rollout id never does."""
    cont = rollout.get("contestant") or {}
    return {
        "task": rollout.get("task"),
        "seed": rollout.get("seed"),
        "contestant_slug": rollout.get("contestant_slug"),
        "protocol_version": rollout.get("protocol_version"),
        "harness_version": cont.get("harness_version") if isinstance(cont, dict) else None,
    }


def init_status(run_dir: Path, rollout: dict[str, Any], *, campaign: str, lifecycle: str = "launched",
                by: str = "launch_rollout", pipeline: dict[str, Any] | None = None,
                mirror_prefix_: str | None = None, **note: Any) -> dict[str, Any]:
    """Create status.json from the rollout.json dict. Refuses to overwrite (use
    transition()); the backfill relies on that to be idempotent."""
    if status_path(run_dir).exists():
        raise FileExistsError(f"{status_path(run_dir)} exists — use transition()")
    if lifecycle not in LIFECYCLES:
        raise ValueError(f"lifecycle {lifecycle!r} not in {LIFECYCLES}")
    ts = now_iso()
    rec: dict[str, Any] = {
        "rollout_id": rollout["rollout_id"],
        "campaign": campaign,
        **cell_fields(rollout),
        "mode": rollout.get("mode", "full"),
        "created_at": rollout.get("created_at"),   # launch time: the "newest run of a cell" ordering key
        "lifecycle": lifecycle,
        "pipeline": {"ami_id": None, "runtime_tree_hash": None, "revyl_cli_version": None,
                     "launch_commit": None, "dirty": None, "attempts_sha256": None, **(pipeline or {})},
        "mirror": {"synced": False, "at": None,
                   "prefix": mirror_prefix_ or mirror_prefix(campaign, Path(run_dir).name)},
        # computed once at collect while reports/ and feedback/ are still on the launch
        # host; None until then
        "checks": None,
        "legitimacy": {"status": "valid", "reason": None, "set_by": by, "set_at": ts},
        "history": [{"ts": ts, "by": by, "lifecycle": lifecycle, **note}],
    }
    atomic_write_json(status_path(run_dir), rec)
    return rec


def transition(run_dir: Path, *, lifecycle: str | None = None, legitimacy: str | None = None,
               reason: str | None = None, by: str | None = None, pipeline: dict[str, Any] | None = None,
               checks: dict[str, Any] | None = None, mirror: dict[str, Any] | None = None,
               **fields: Any) -> dict[str, Any]:
    """Apply one change and append it to history. Refuses unknown vocabulary, a backwards
    lifecycle move, and a legitimacy change without a reason. The file is validated on
    every write rather than trusted on read: a typo in a status would be silently wrong
    forever."""
    rec = read_status(run_dir)
    if rec is None:
        raise FileNotFoundError(f"{status_path(run_dir)} missing — init_status() first")
    ts = now_iso()
    row: dict[str, Any] = {"ts": ts, "by": by or who()}
    if lifecycle is not None:
        if lifecycle not in LIFECYCLES:
            raise ValueError(f"lifecycle {lifecycle!r} not in {LIFECYCLES}")
        if _RANK[lifecycle] < _RANK.get(rec["lifecycle"], 0):
            raise ValueError(f"{rec['rollout_id']}: lifecycle {rec['lifecycle']} → {lifecycle} moves backwards")
        rec["lifecycle"] = lifecycle
        row["lifecycle"] = lifecycle
    if legitimacy is not None:
        if legitimacy not in RUN_LEGITIMACY:
            raise ValueError(f"legitimacy {legitimacy!r} not in {RUN_LEGITIMACY}")
        if not reason:
            raise ValueError("a legitimacy change needs a reason — it is the audit trail")
        rec["legitimacy"] = {"status": legitimacy, "reason": reason, "set_by": row["by"], "set_at": ts}
        row["legitimacy"] = legitimacy
    if reason:
        row["reason"] = reason
    if pipeline:
        rec.setdefault("pipeline", {}).update(pipeline)
        row["pipeline"] = pipeline
    if checks is not None:
        rec["checks"] = checks
        row["checks"] = {k: v for k, v in checks.items() if k != "at"}
    if mirror is not None:
        rec["mirror"] = {**(rec.get("mirror") or {}), **mirror}
        row["mirror"] = mirror
    for k, v in fields.items():
        if k in _RESERVED:
            raise ValueError(f"field {k!r} is part of the status schema — not settable via **fields")
        rec[k] = v
        row[k] = v
    rec.setdefault("history", []).append(row)
    atomic_write_json(status_path(run_dir), rec)
    return rec


def mark_fault(run_dir: Path, lifecycle: str, *, by: str = "launch_rollout", **fields: Any) -> bool:
    """Record a terminal fault on a run that is still live. A no-op (False) when the run
    already reached `collected` or a fault, or has no status file. Never raises: it is
    called from exception handlers, where a second failure would mask the first."""
    if lifecycle not in TERMINAL_FAULTS:
        raise ValueError(f"{lifecycle!r} is not a terminal fault")
    try:
        rec = read_status(run_dir)
        if rec is None or rec.get("lifecycle") not in LIVE:
            return False
        transition(run_dir, lifecycle=lifecycle, by=by, **fields)
        return True
    except Exception:  # noqa: BLE001
        return False


# ---- checks: the phantom-FAIL signature ---------------------------------------------
# `s1rb-t_2-search-fare-run1.report.json` → slot "t_2", attempt "1". Slot names are the
# four logical suite slots (bench/config.py SLOTS); the middle part is the free-text test name.
_REPORT_RE = re.compile(r"-(t_\d|final)-.*-run(\d+)\.report\.json$")


def phantom_slots(run_dir: Path) -> list[str]:
    """Every `s<k>/<slot>` of the run carrying the phantom-FAIL signature; empty = clean.

    The bug: the Revyl report API writes the top-level `success` flag asynchronously
    after video-validation judging. An earlier runner fetched the report before the
    flag existed and turned "no key" into a FAIL verdict; the agent then "fixed" a
    non-bug and resubmitted, so k was inflated and the score deflated. score_v0 cannot
    see it: the attempts.jsonl row is well-formed and the run scores as perfectly clean.

    The signature, all five together (verified against every archived report):
      1. `reports/s<k>/<prefix>-<slot>-…-run<n>.report.json` has NO top-level `success`
      2. that report's `session_status == "completed"`
      3. that report's `effective_failed_steps == 0`
      4. the sibling run summary `…-run<n>.json` has `success: true`
      5. `feedback/s<k>.verdict.json["verdicts"][<slot>] == "FAIL"`
    Why all five: the naive form ("all steps green + no success") matches a real failure
    too (session_status failed, effective_failed_steps 1). Tolerant of partial
    dirs: a missing verdict file or summary just means no hit."""
    run_dir = Path(run_dir)
    hits: list[str] = []
    for rep in sorted(run_dir.glob("reports/s*/*.report.json")):
        m = _REPORT_RE.search(rep.name)
        if not m:
            continue
        slot, k_dir = m.group(1), rep.parent.name
        try:
            r = json.loads(rep.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if "success" in r or r.get("session_status") != "completed" or r.get("effective_failed_steps") != 0:
            continue                                                   # (1) (2) (3)
        summary = rep.with_name(rep.name.replace(".report.json", ".json"))
        try:
            s = json.loads(summary.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if s.get("success") is not True:                               # (4)
            continue
        try:
            v = json.loads((run_dir / "feedback" / f"{k_dir}.verdict.json").read_text(encoding="utf-8")).get("verdicts") or {}
        except (OSError, ValueError):
            continue
        if v.get(slot) != "FAIL":                                      # (5)
            continue
        hits.append(f"{k_dir}/{slot}")
    return hits


# ---- checks: did the agent fetch the suites? -----------------------------------------
# The device-test suites are readable in this repository (grading-side/) so that anyone can
# grade in their own organisations. Two things keep them from the agent UNDER TEST: nothing
# mounts or copies grading-side/ into its container, and its Revyl key cannot reach the
# grading organisation. Neither covers the network: the agent container has outbound access
# (npm, Expo, Revyl) and `allowed_hosts` in task.toml is a declaration this runtime does not
# enforce, so an agent can `git clone` this public repository and read the suites. This check
# is the answer to that: it looks for it after the fact and the scorer excludes the run.
#
# Why a plain substring scan is sound: nothing the agent is handed — RUNBOOK, contract,
# scaffold, container scripts — contains any of these strings, so an occurrence in its
# transcript or harness log is text the agent produced or received through its own tool
# calls. It is evidence to review, not proof of intent (a web search result can mention the
# repository), which is why `campaign.py set --legitimacy adjudicated_ok` lifts the exclusion.
_SUITE_FETCH_RE = re.compile(rb"revyl-bench-public|grading-side/|grading-side\\\\|RevylAI/revyl-bench", re.I)
_SUITE_FETCH_MAX_HITS = 5          # enough to review; a looping agent can repeat a URL thousands of times


def suite_fetch_hits(run_dir: Path) -> list[str]:
    """`<file>:<line>: <text around the match>` for the first few places the harness transcript
    or harness.log names this repository or its grading-side/ directory; empty = clean.

    Read as bytes, line by line: a transcript can be hundreds of MB of JSONL and may hold
    invalid UTF-8 from a tool's output. Tolerant of a partial run folder — a missing
    transcript/ (the harness died before the runner copied it) is simply nothing to scan,
    and `transcripts_seen` in run_checks says so."""
    run_dir = Path(run_dir)
    hits: list[str] = []
    files = [p for p in sorted((run_dir / "transcript").rglob("*")) if p.is_file()]
    if (run_dir / "harness.log").is_file():
        files.append(run_dir / "harness.log")
    for f in files:
        try:
            with f.open("rb") as fh:
                for n, line in enumerate(fh, 1):
                    m = _SUITE_FETCH_RE.search(line)
                    if not m:
                        continue
                    # ASCII with \xNN escapes, not UTF-8 with U+FFFD: this string is printed by
                    # launch_rollout.log() and `campaign.py status`, and a cp1252 Windows console
                    # raises UnicodeEncodeError on U+FFFD — a check must never take collect down
                    around = line[max(0, m.start() - 60): m.end() + 60].decode("ascii", errors="backslashreplace").strip()
                    hits.append(f"{f.relative_to(run_dir).as_posix()}:{n}: {around}")
                    if len(hits) >= _SUITE_FETCH_MAX_HITS:
                        return hits
        except OSError:
            continue
    return hits


def run_checks(run_dir: Path, *, by: str = "collect") -> dict[str, Any]:
    """The per-run verdicts that need the heavy artifacts, computed ONCE while reports/,
    feedback/ and transcript/ are still on the launch host and stored in status.json.
    `reports_seen` / `transcripts_seen` say how much each check looked at, so a run with
    nothing to check is distinguishable from a clean one."""
    run_dir = Path(run_dir)
    reports = [p for p in run_dir.glob("reports/s*/*.report.json") if _REPORT_RE.search(p.name)]
    slots = phantom_slots(run_dir)
    fetched = suite_fetch_hits(run_dir)
    transcripts = sum(1 for p in (run_dir / "transcript").rglob("*") if p.is_file())
    return {"phantom_fail": bool(slots), "phantom_slots": slots, "reports_seen": len(reports),
            "suite_fetch": bool(fetched), "suite_fetch_hits": fetched, "transcripts_seen": transcripts,
            "at": now_iso(), "by": by}


def slim_candidates(run_dir: Path) -> list[Path]:
    """Explicit archive-only artifacts; never include receipts or scoring inputs."""
    return [Path(run_dir) / name for name in (*SLIM_DIRS, *SLIM_FILES)
            if (Path(run_dir) / name).exists()]


def slim(run_dir: Path) -> list[str]:
    """Prune only after a successful upload. Preserve scoring metadata and harness.log
    (only SLIM_DIRS and SLIM_FILES are candidates). Surface deletion errors
    so a later sync can retry, rather than falsely recording successful cleanup."""
    removed: list[str] = []
    for path in slim_candidates(run_dir):
        if path.is_symlink():
            raise OSError(f"refusing to prune symlink: {path}")
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        removed.append(path.name)
    return removed


# ---- discovery ---------------------------------------------------------------------
def iter_campaigns(root: str | Path | None = None) -> list[tuple[str, Path, dict[str, Any]]]:
    """(name, dir, manifest) for every campaign folder, oldest name first. A folder
    without campaign.json is not a campaign and is skipped."""
    base = campaigns_root(root)
    if not base.is_dir():
        return []
    out = []
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        if (d / MANIFEST).exists():
            out.append((d.name, d, read_manifest(d)))
    return out


def iter_runs(cdir: Path) -> list[Path]:
    runs = Path(cdir) / "runs"
    if not runs.is_dir():
        return []
    return sorted(p for p in runs.iterdir() if p.is_dir())


def run_index(cdir: Path) -> list[dict[str, Any]]:
    """One entry per run folder: its path, its status.json (None if missing) and its
    rollout.json (None if missing). Everything that reads a campaign starts here."""
    out = []
    for d in iter_runs(cdir):
        rj = d / "rollout.json"
        rollout = None
        if rj.exists():
            try:
                rollout = read_json(rj)
            except ValueError:
                rollout = None
        out.append({"folder": d.name, "path": d, "status": read_status(d), "rollout": rollout})
    return out


def refresh_manifest_runs(cdir: Path) -> dict[str, Any]:
    """Rebuild the manifest's `runs` cache from the status files. campaign.py is the only
    caller (single writer): concurrent launch_rollout.py processes each write their own
    status.json and never touch the manifest, so width-12 launches cannot race on it."""
    m = read_manifest(cdir)
    runs = []
    for e in run_index(cdir):
        st = e["status"]
        if st is None:
            continue
        runs.append({"rollout_id": st["rollout_id"], "path": f"runs/{e['folder']}", "task": st.get("task"),
                     "seed": st.get("seed"), "lifecycle": st.get("lifecycle"),
                     "legitimacy": (st.get("legitimacy") or {}).get("status"), "created_at": st.get("created_at")})
    m["runs"] = sorted(runs, key=lambda r: (str(r["task"]), int(r["seed"] or 0), str(r["created_at"])))
    write_manifest(cdir, m)
    return m


def find_run(rollout_id: str, root: str | Path | None = None) -> tuple[str, Path]:
    """Resolve a rollout id to (campaign name, run dir) by reading status files, never by
    guessing a path. One id in two campaigns is a backfill error and is refused."""
    hits: list[tuple[str, Path]] = []
    for name, cdir, _ in iter_campaigns(root):
        for e in run_index(cdir):
            st = e["status"]
            rid = st["rollout_id"] if st else ((e["rollout"] or {}).get("rollout_id"))
            if rid == rollout_id:
                hits.append((name, e["path"]))
    if not hits:
        raise LookupError(f"rollout {rollout_id} is in no campaign under {campaigns_root(root)}")
    if len(hits) > 1:
        raise ValueError(f"rollout {rollout_id} is in {len(hits)} campaigns: {[h[0] for h in hits]}")
    return hits[0]


def all_run_dirs(root: str | Path | None = None) -> list[Path]:
    """Every run folder of every campaign, campaign by campaign then folder by folder —
    the drop-in for `for d in RUNS.iterdir()` over the legacy flat store."""
    return [d for _, cdir, _ in iter_campaigns(root) for d in iter_runs(cdir)]


def rid_of(run_dir: Path) -> str:
    """The rollout id of a run folder. Folder names are `<task>_s<seed>_<8hex>`, not ids
    any more, so `d.name` is wrong; the status file has it, rollout.json has it, and only
    a folder with neither (a hand-cut seed) falls back to its name."""
    st = read_status(run_dir)
    if st and st.get("rollout_id"):
        return st["rollout_id"]
    rj = Path(run_dir) / "rollout.json"
    if rj.exists():
        try:
            rid = read_json(rj).get("rollout_id")
            if rid:
                return rid
        except ValueError:
            pass
    return Path(run_dir).name


class RunsView:
    """The legacy `RUNS = runtime/runs` root, as a view over the campaign store, so tools
    written against the flat store keep their two idioms: `RUNS / rollout_id / "submit" / …`
    resolves an id to its run folder (a path that does not exist when the id is in no
    campaign, so `.exists()` checks keep working), and `for d in RUNS.iterdir()` walks
    every run of every campaign. The id → folder index is built once and rebuilt on a
    miss, so a loop over hundreds of ids costs one scan, not one per id."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = campaigns_root(root)
        self._index: dict[str, Path] | None = None

    def _build(self) -> dict[str, Path]:
        self._index = {rid_of(d): d for d in all_run_dirs(self.root)}
        return self._index

    def __truediv__(self, rollout_id: str) -> Path:
        rid = str(rollout_id)
        idx = self._index if self._index is not None else self._build()
        if rid not in idx:
            idx = self._build()                       # a run may have been collected since
        return idx.get(rid) or (self.root / "_missing" / rid)

    def iterdir(self):
        return iter(all_run_dirs(self.root))

    def exists(self) -> bool:
        return self.root.is_dir()

    def is_dir(self) -> bool:
        return self.root.is_dir()

    def __fspath__(self) -> str:
        return str(self.root)

    def __str__(self) -> str:
        return str(self.root)


def newest_first(statuses: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order runs of one cell newest first. `created_at` has one-second resolution and
    same-second launches exist, so the rollout id breaks ties:
    arbitrary but deterministic, so every copy of the store orders the same way."""
    return sorted(statuses, key=lambda s: (str(s.get("created_at") or ""), str(s.get("rollout_id") or "")), reverse=True)


# ---- pipeline: the code that grades ------------------------------------------------
def _git(root: Path, *args: str) -> str | None:
    try:
        return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True,
                              text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def current_pipeline(runtime_root: str | Path | None = None, *, transport: str = "ec2") -> dict[str, Any]:
    """What would grade a run launched now. For ec2 the grading code is the AMI's, so the
    tree hash is infra.json's `ami_runtime_tree` (the checkout's own hash differs whenever
    the checkout is ahead of the AMI, and comparing against it would call every fresh run
    "wrong pipeline"). For local the runner image is built from the working tree, so the
    checkout's hash is the honest value, null outside a git repo."""
    root = Path(runtime_root) if runtime_root else RUNTIME_ROOT
    out: dict[str, Any] = {"ami_id": None, "runtime_tree_hash": None, "revyl_cli_version": None,
                           "launch_commit": _git(root, "rev-parse", "--short=12", "HEAD"), "dirty": None}
    pin = root / "image" / "REVYL_CLI_VERSION"
    if pin.exists():
        out["revyl_cli_version"] = pin.read_text(encoding="utf-8").strip()
    porcelain = _git(root, "status", "--porcelain", "--", str(root))
    out["dirty"] = bool(porcelain) if porcelain is not None else None
    if transport == "ec2":
        infra = root / "host" / "ec2" / "infra.json"
        if infra.exists():
            try:
                d = read_json(infra)
                out["ami_id"] = d.get("ami_id")
                out["runtime_tree_hash"] = d.get("ami_runtime_tree")
            except ValueError:
                pass
    else:
        try:
            from bench.hosts import runtime_tree_hash   # stdlib-only module; lazy so this file stays importable anywhere
            out["runtime_tree_hash"] = runtime_tree_hash(root)
        except Exception:  # noqa: BLE001  (outside a git repo, or bench/ absent)
            out["runtime_tree_hash"] = None
    return out


PIPELINE_KEYS = ("ami_id", "runtime_tree_hash", "revyl_cli_version")


def pipeline_diff(recorded: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """The keys on which the recorded pipeline and the current pin disagree. The launch
    commit is informational (a docs commit changes it without changing any grading
    code); the AMI, the tree hash and the CLI pin are what grade."""
    return [f"{k}: campaign has {recorded.get(k)!r}, current pin is {current.get(k)!r}"
            for k in PIPELINE_KEYS if (recorded.get(k) or None) != (current.get(k) or None)]


def pipeline_matches(recorded: dict[str, Any], current: dict[str, Any]) -> bool:
    return not pipeline_diff(recorded, current)


# ---- the official record: publishing is a separate, explicit step ---------------------
# results/official.jsonl names which campaign feeds each published row. It is committed,
# public, and written only by `campaign.py promote`; the results page's leaderboard is
# rendered from it by `campaign.py render`. Neither runs automatically, so an R&D campaign
# or a re-run can never move a published number by itself.
RESULTS_DIR = RUNTIME_ROOT.parent / "results"
OFFICIAL = RESULTS_DIR / "official.jsonl"
LEADERBOARD_BEGIN = "<!-- official:leaderboard"
LEADERBOARD_END = "<!-- /official:leaderboard -->"


def read_official(path: str | Path | None = None) -> list[dict[str, Any]]:
    p = Path(path) if path else OFFICIAL
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_official(rows: list[dict[str, Any]], path: str | Path | None = None) -> None:
    p = Path(path) if path else OFFICIAL
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    os.replace(tmp, p)


def status_digest(cdir: Path) -> str:
    """One hash over every status.json of the campaign, in folder order. scores.json
    records it at scoring time; a later status change (a legitimacy set, a collect)
    changes it, so the record can never quote a scores.json the scorer would disagree
    with now. Content, not mtimes or timestamps: a fetched copy and a same-second write
    both behave."""
    h = hashlib.sha256()
    for e in run_index(cdir):
        p = status_path(e["path"])
        h.update(e["folder"].encode())
        h.update(p.read_bytes() if p.exists() else b"-")
    return h.hexdigest()


def scores_are_stale(cdir: Path) -> bool:
    """True when scores.json is missing or was written against a different set of
    status files than the campaign has now."""
    sc = Path(cdir) / SCORES
    if not sc.exists():
        return True
    try:
        stored = (read_json(sc) or {}).get("status_digest")
    except ValueError:
        return True
    return stored is None or stored != status_digest(cdir)


def row_campaigns(row: dict[str, Any]) -> list[str]:
    """The campaign names behind a record row (one, or the union's parts)."""
    if row.get("campaigns"):
        return [p["campaign"] for p in row["campaigns"]]
    return [row["campaign"]] if row.get("campaign") else []


def row_pipelines(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """campaign name → the pipeline it was graded by, for one campaign or a union."""
    if row.get("campaigns"):
        return {p["campaign"]: p.get("pipeline") or {} for p in row["campaigns"]}
    return {row["campaign"]: row.get("pipeline") or {}} if row.get("campaign") else {}


def promotion_refusals(res: dict[str, Any], manifest: dict[str, Any], existing: dict[str, Any] | None,
                       kept: Iterable[str] = ()) -> list[str]:
    """Why `promote` would not take this campaign without a written reason.
    `kept`: the campaigns of the new row; an existing part that stays is not replaced by
    the newcomer (a union grown by one more disjoint campaign on the same pin)."""
    out = []
    if res.get("legitimacy") != "official":
        out.append(f"legitimacy is {res.get('legitimacy')}, not official")
    agg = res.get("aggregate")
    if not agg:
        out.append("nothing aggregated (a void campaign)")
    elif not agg.get("complete"):
        out.append(f"incomplete: {agg.get('seeds_counted')}/{agg.get('seeds_planned')} seeds counted")
    if res.get("problems"):
        out.append(f"{len(res['problems'])} problem(s) in scores.json")
    if existing and res["campaign"] not in row_campaigns(existing):
        # the audit trail: replacing a row's campaign (any part of a united
        # row) with one graded by the same code is "re-ran until it improved" unless a
        # reason says otherwise
        kept_set = set(kept)
        for name, pipe in row_pipelines(existing).items():
            if name not in kept_set and pipeline_matches(pipe, manifest.get("pipeline") or {}):
                out.append(f"replaces {name} graded by the same pipeline")
    return out


def dropped_refusals(existing: dict[str, Any] | None, names: list[str]) -> list[str]:
    """Re-promoting a joined row (one built from several campaigns) with a part left out narrows the row: on the record only
    with a reason."""
    had = row_campaigns(existing) if existing else []
    if len(had) < 2:
        return []             # replacing a one-campaign row is the pipeline check's business
    return [f"drops {c} from the row" for c in had if c not in names]


def union_refusals(parts: list[tuple[dict[str, Any], dict[str, Any]]]) -> list[str]:
    """Why several campaigns cannot back ONE row without a written reason: a row is one
    contestant at one protocol over a set of tasks each graded in exactly one campaign.
    The 17-task campaigns were closed (and the pin had moved) before tasks 18–20 existed,
    so those ran as separate campaigns; the union is the 20-task row, and every cell still
    names its one manifest."""
    out: list[str] = []
    if len(parts) < 2:
        return out
    first, fm = parts[0]
    c0 = first.get("contestant") or {}
    for res, m in parts[1:]:
        c = res.get("contestant") or {}
        if (c.get("slug"), c.get("harness_version")) != (c0.get("slug"), c0.get("harness_version")):
            out.append(f"{res['campaign']}: contestant {c.get('slug')} {c.get('harness_version')} differs from "
                       f"{first['campaign']}'s {c0.get('slug')} {c0.get('harness_version')}")
        if res.get("protocol_version") != first.get("protocol_version"):
            out.append(f"{res['campaign']}: protocol {res.get('protocol_version')} differs from {first.get('protocol_version')}")
        if set((m.get("matrix") or {}).get("seeds") or []) != set((fm.get("matrix") or {}).get("seeds") or []):
            out.append(f"{res['campaign']}: seeds {(m.get('matrix') or {}).get('seeds')} differ from "
                       f"{first['campaign']}'s {(fm.get('matrix') or {}).get('seeds')}")
    seen: dict[str, str] = {}
    for res, m in parts:
        for task in (m.get("matrix") or {}).get("tasks") or []:
            if task in seen:
                out.append(f"task {task} is in both {seen[task]} and {res['campaign']}: one task, one campaign")
            seen[task] = res["campaign"]
    return out


def official_row(parts: list[tuple[dict[str, Any], dict[str, Any]]], *, row: str, reason: str | None, by: str,
                 previous: dict[str, Any] | None) -> dict[str, Any]:
    """The record's line for a row: one campaign, or the union of several with disjoint
    task sets (union_refusals). The macro is the mean over every counted cell, as
    score_v0 computes it inside one campaign; `campaigns` lists each part with its own
    macro and pipeline, `campaign` names them all."""
    res0, m0 = parts[0]
    planned: dict[str, int] = {}                  # task -> seeds planned (the larger, when split)
    owner: dict[str, list[str]] = {}              # task -> the campaigns that list it
    runs: dict[str, list[dict[str, Any]]] = {}    # task -> every counted run across the parts
    records: list[dict[str, Any]] = []
    tokens_in: list[Any] = []
    tokens_out: list[Any] = []
    campaigns: list[dict[str, Any]] = []
    legit = "official"
    for res, m in parts:
        agg = res.get("aggregate") or {}
        counted = [r for r in res["records"] if r.get("state") == "scored"]
        for t, c in (agg.get("cells") or {}).items():
            planned[t] = max(planned.get(t, 0), c.get("planned") or 0)
            owner.setdefault(t, []).append(res["campaign"])
        for r in counted:
            runs.setdefault(r["task"], []).append(r)
        records += [{"rollout_id": r["rollout_id"], "task": r["task"], "seed": r["seed"], "score_pct": r["score_pct"],
                     "campaign": res["campaign"]} for r in counted]
        tokens_in += [r.get("tokens_in") for r in counted]
        tokens_out += [r.get("tokens_out") for r in counted]
        if res.get("legitimacy") != "official":
            legit = res.get("legitimacy") or legit
        campaigns.append({"campaign": res["campaign"], "tasks": list((m.get("matrix") or {}).get("tasks") or []),
                          "macro": agg.get("macro"), "legitimacy": res.get("legitimacy"), "scored_at": res.get("scored_at"),
                          "pipeline": {k: (m.get("pipeline") or {}).get(k) for k in PIPELINE_KEYS}})
    # every cell from its united runs, the same way score_v0 builds a cell inside one
    # campaign: a task split across campaigns (a relaunched seed in its own campaign, with a
    # reason on the row) is one cell, solved when every counted run resolved it
    cells: dict[str, dict[str, Any]] = {}
    for t in planned:
        rs = runs.get(t, [])
        cells[t] = {"mean": round(sum(r["score_pct"] for r in rs) / len(rs), 1) if rs else None, "n": len(rs),
                    "planned": planned[t], "solved": bool(rs) and all(r.get("resolved") for r in rs),
                    "campaign": " + ".join(owner[t])}
    with_data = [c for c in cells.values() if c.get("n")]
    macro = round(sum(c["mean"] for c in with_data) / len(with_data), 1) if with_data else None
    return {
        "row": row,
        "campaign": " + ".join(p["campaign"] for p in campaigns),
        "campaigns": campaigns,
        "contestant": res0.get("contestant"),
        # mixed on purpose only (a reason was recorded): the row says so rather than hide it
        "protocol_version": (res0.get("protocol_version") if len({r.get("protocol_version") for r, _ in parts}) == 1
                             else " + ".join(str(v) for v in sorted({r.get("protocol_version") for r, _ in parts}, key=str))),
        "purpose": res0.get("purpose"),
        "legitimacy": legit,
        "pipeline": campaigns[0]["pipeline"],
        "scored_at": max(p["scored_at"] or "" for p in campaigns) or None,
        "macro": macro,
        "solved": sum(1 for c in with_data if c.get("solved")),
        "cells_planned": len(cells),
        "cells_counted": len(with_data),
        # seeds: the planned matrix filled, cell by cell; a relaunched cell that now holds two
        # runs fills its one planned seed (the extra run is in runs_counted, and in the mean)
        "seeds_counted": sum(min(c["n"] or 0, c["planned"] or 0) for c in cells.values()),
        "seeds_planned": sum(c["planned"] or 0 for c in cells.values()),
        "runs_counted": len(records),
        "complete": bool(cells) and all((c["n"] or 0) >= (c["planned"] or 0) for c in cells.values()),
        "cells": cells,
        "records": records,
        "tokens_in": sum(tokens_in) if tokens_in and all(isinstance(t, (int, float)) for t in tokens_in) else None,
        "tokens_out": sum(tokens_out) if tokens_out and all(isinstance(t, (int, float)) for t in tokens_out) else None,
        "reason": reason,
        "promoted_at": now_iso(),
        "promoted_by": by,
        "previous": previous,
    }


def _tokens(row: dict[str, Any]) -> str:
    ti, to = row.get("tokens_in"), row.get("tokens_out")
    if ti is None or to is None:
        return ""
    n = len(row.get("records") or [])
    return f"{ti / 1e6:.0f}M in / {to / 1e6:.1f}M out ({n} rollouts)"


def leaderboard_block(rows: list[dict[str, Any]]) -> str:
    """The generated leaderboard: one line per row of the official record, in the
    record's order. Everything a reader needs to re-derive the number is in the row: the
    campaign folder, the seed count, and the reason when the row was promoted with one."""
    lines = [f"{LEADERBOARD_BEGIN} — generated by `campaign.py render` from results/official.jsonl; edit the record, not this table -->",
             "| contestant | protocol | tasks solved | mean score | seeds | tokens | campaign | note |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        c = r.get("contestant") or {}
        who = f"{c.get('slug')} ({c.get('harness')} {c.get('harness_version')})"
        notes = []
        if r.get("legitimacy") != "official":
            notes.append(r.get("legitimacy") or "")
        if not r.get("complete"):
            notes.append("incomplete")
        if r.get("reason"):
            notes.append(str(r["reason"]))
        macro = f"{r['macro']:.1f}%" if isinstance(r.get("macro"), (int, float)) else "—"
        lines.append(f"| {who} | {r.get('protocol_version')} | {r.get('solved')}/{r.get('cells_planned')} | {macro} | "
                     f"{r.get('seeds_counted')}/{r.get('seeds_planned')} | {_tokens(r)} | {' + '.join('`' + c + '`' for c in row_campaigns(r))} | {'; '.join(n for n in notes if n)} |")
    lines.append(LEADERBOARD_END)
    return "\n".join(lines) + "\n"


def render_page(page_text: str, rows: list[dict[str, Any]]) -> str:
    """Replace the marked block of the results page with the generated leaderboard. The
    prose around it is the author's; only the block is the record's."""
    start = page_text.find(LEADERBOARD_BEGIN)
    end = page_text.find(LEADERBOARD_END)
    if start < 0 or end < 0 or end < start:
        raise ValueError(f"the page has no {LEADERBOARD_BEGIN} … {LEADERBOARD_END} block")
    end += len(LEADERBOARD_END)
    if page_text[end:end + 1] == "\n":
        end += 1
    return page_text[:start] + leaderboard_block(rows) + page_text[end:]


# ---- S3 ----------------------------------------------------------------------------
def s3_sync(src: str, dst: str, *, aws_bin: str = "aws", profile: str | None = None,
            region: str | None = None, extra: Iterable[str] = ()) -> tuple[bool, str]:
    """`aws s3 sync src dst`. Returns (ok, tail of stderr). Never raises: the caller
    records the outcome in status.json and `campaign.py sync` retries later."""
    cmd = [aws_bin, *(["--profile", profile] if profile else []), *(["--region", region] if region else []),
           "s3", "sync", src, dst, *extra]
    try:
        p = subprocess.run(cmd, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError as e:
        return False, str(e)
    return p.returncode == 0, (p.stderr or "")[-300:]


def s3_copy(src: str, dst: str, *, aws_bin: str = "aws", profile: str | None = None,
            region: str | None = None) -> tuple[bool, str]:
    """`aws s3 cp src dst` for one file: the status.json push after a mirror, which
    `sync` would otherwise leave one step stale (the mirror result is written after the
    sync ran). Same contract as s3_sync: (ok, tail of stderr), never raises."""
    cmd = [aws_bin, *(["--profile", profile] if profile else []), *(["--region", region] if region else []),
           "s3", "cp", src, dst]
    try:
        p = subprocess.run(cmd, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError as e:
        return False, str(e)
    return p.returncode == 0, (p.stderr or "")[-300:]
