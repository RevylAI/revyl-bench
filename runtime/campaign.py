#!/usr/bin/env python3
"""campaign.py — run a benchmark as one campaign folder (docs/campaigns.md).

    campaign.py new    --purpose benchmark --contestant opencode/muse-spark-1.3
                       [--tasks a,b,c] [--seeds 1,2,3] [--label …] [--transport ec2|local]
                       [--cap 5] [--wall-clock-min 480] [--reason "…"] [--by …] [--dry-run]
    campaign.py launch --name <campaign> [--width 12] [--only <task> … [--rerun]] [--dry-run]
    campaign.py status --name <campaign>
    campaign.py list
    campaign.py set    --name <campaign> [--run <rollout_id>] --legitimacy … --reason "…" [--by …]
    campaign.py set    --name <campaign> --run <rollout_id> --lifecycle collect_failed --reason "…"
    campaign.py extend --name <campaign> [--seeds 2,3] [--tasks …] --reason "…"
    campaign.py sync   --name <campaign>            # retry the S3 mirror; push every status.json
    campaign.py fetch  --name <campaign> --run <rollout_id>   # pull a run's heavy artifacts back
    campaign.py promote --name <campaign> --row <row-id> [--reason "…"]   # into results/official.jsonl
    campaign.py render [--check]                    # the results page's leaderboard, from the record

A campaign is one contestant × one purpose × one matrix of tasks × seeds. `new` writes
the manifest; `launch` runs every cell of the matrix that has no collected run yet,
`--width` at a time, each as one `launch_rollout.py --campaign <name>` subprocess — so a
campaign rollout and a hand-launched rollout are the same code path and produce the same
folder. `launch` is resumable: a crashed campaign is relaunched with the same command,
and a `launch.lock` in the folder keeps two launchers off one campaign.

Detached operation is the ops rule for anything longer than a shell session:
    setsid nohup python3 runtime/campaign.py launch --name … < /dev/null &
The launcher's log lands in the campaign folder (launch.log), each rollout's output under
logs/.

`new`, `launch`, `sync` and `fetch` need Python 3.11+ with PyYAML (they go through
bench.config or launch_rollout); `status`, `list`, `set` and `extend` are stdlib-only.

Scoring is not here: `score_v0.py --campaign <name>` reads the folder and writes
scores.json. Publishing is `promote` (a campaign into the committed official record,
results/official.jsonl, one line per published row) and `render` (the results page's
leaderboard block regenerated from that record); neither runs by itself, so an R&D
campaign or a re-run never moves a published number.
"""
from __future__ import annotations

import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

RUNTIME_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(RUNTIME_ROOT))
import campaigns as C  # noqa: E402

# the rollout launcher each cell is handed to; REVYL_BENCH_LAUNCHER lets the tests stand
# in a stub so the launch loop is exercised without a device or a host
LAUNCH_ROLLOUT = Path(os.environ.get("REVYL_BENCH_LAUNCHER") or RUNTIME_ROOT / "launch_rollout.py")


def log(msg: str, logfile: Path | None = None) -> None:
    line = f"[campaign {time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    if logfile is not None:
        with logfile.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def _root(a: argparse.Namespace) -> Path:
    return C.campaigns_root(a.campaigns_dir)


def _cdir(a: argparse.Namespace, name: str | None = None) -> Path:
    name = name or a.name
    # an absolute path names a campaign folder in another store (a row that unites the
    # 17-task campaign of one store with the 18–20 campaign of another)
    d = Path(name) if Path(name).is_absolute() else C.campaign_dir(name, _root(a))
    if not (d / C.MANIFEST).exists():
        raise SystemExit(f"no campaign {name!r} under {_root(a)} (campaign.py list)")
    return d


def _csv(s: str | None) -> list[str]:
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def _ints(s: str | None) -> list[int] | None:
    return [int(x) for x in _csv(s)] if s else None


def _need_bench(what: str) -> None:
    """bench.config needs tomllib (3.11+) and PyYAML. Say so up front instead of failing
    twelve subprocesses deep with an ImportError in each log."""
    try:
        import tomllib  # noqa: F401
        import yaml  # noqa: F401
    except ImportError as e:
        raise SystemExit(f"campaign.py {what} needs Python 3.11+ with PyYAML (bench.config): {e}")


# ---- new ----------------------------------------------------------------------------
def _contestant(slug: str) -> tuple[dict[str, Any], int]:
    """The registry entry (short name, harness, model, harness_version) and the protocol
    version, through bench.config so a campaign names exactly what a rollout resolves."""
    from bench import config as _config
    reg = _config.load_registry()
    if slug not in reg["contestants"]:
        raise SystemExit(f"unknown contestant {slug!r}; known: {sorted(reg['contestants'])}")
    e = dict(reg["contestants"][slug])
    return ({"slug": slug, "short": e.get("short"), "model": e.get("model"), "harness": e.get("harness"),
             "harness_version": e.get("harness_version")}, int(reg["protocol_version"]))


def cmd_new(a: argparse.Namespace) -> int:
    _need_bench("new")
    contestant, protocol = _contestant(a.contestant)
    try:
        tasks = C.resolve_tasks(a.purpose, _csv(a.tasks))
        m = C.new_manifest(purpose=a.purpose, contestant=contestant, protocol_version=protocol, tasks=tasks,
                           seeds=_ints(a.seeds), cap=a.cap, wall_clock_min=a.wall_clock_min,
                           transport=a.transport, mode=a.mode,
                           pipeline=C.current_pipeline(RUNTIME_ROOT, transport=a.transport),
                           created_by=a.by, reason=a.reason, name=a.name, label=a.label,
                           slim=(False if a.keep_artifacts else None), notes=a.notes or "",
                           ssh_ip=a.ssh_ip)
    except ValueError as e:
        raise SystemExit(f"cannot create the campaign: {e}")
    if a.dry_run:
        print(json.dumps(m, indent=2))
        print(f"\ndry run: would create {C.campaign_dir(m['campaign'], _root(a))} "
              f"({len(m['matrix']['tasks'])} tasks × {len(m['matrix']['seeds'])} seeds, legitimacy {m['legitimacy']['status']})")
        return 0
    try:
        cdir = C.create_campaign(m, _root(a))
    except FileExistsError as e:
        raise SystemExit(str(e))
    print(f"created {cdir}")
    print(f"  {len(m['matrix']['tasks'])} tasks × seeds {m['matrix']['seeds']} = {len(C.planned_cells(m))} cells, "
          f"purpose {m['purpose']}, legitimacy {m['legitimacy']['status']} ({m['legitimacy']['reason']})")
    print(f"  pipeline {json.dumps(m['pipeline'])}")
    print(f"next: python3 runtime/campaign.py launch --name {m['campaign']}")
    return 0


# ---- cells ----------------------------------------------------------------------------
def cell_table(cdir: Path, m: dict[str, Any]) -> dict[tuple[str, int], list[dict[str, Any]]]:
    """planned cell → its runs' status records, newest first. Runs outside the matrix (a
    seed-90 check, a task later removed by hand) are not cells: see extra_runs()."""
    table: dict[tuple[str, int], list[dict[str, Any]]] = {c: [] for c in C.planned_cells(m)}
    for e in C.run_index(cdir):
        st = e["status"]
        if st is None:
            continue
        key = (str(st.get("task")), int(st.get("seed") or 0))
        if key in table:
            table[key].append({**st, "_folder": e["folder"]})
    return {k: C.newest_first(v) for k, v in table.items()}


def extra_runs(cdir: Path, m: dict[str, Any]) -> list[dict[str, Any]]:
    """Run folders that are not a planned cell: outside the matrix, or without status.json."""
    planned = set(C.planned_cells(m))
    out = []
    for e in C.run_index(cdir):
        st = e["status"]
        if st is None:
            out.append({"_folder": e["folder"], "rollout_id": None, "lifecycle": "unindexed", "legitimacy": {}})
        elif (str(st.get("task")), int(st.get("seed") or 0)) not in planned:
            out.append({**st, "_folder": e["folder"]})
    return out


def _counts(st: dict[str, Any]) -> bool:
    return (st.get("legitimacy") or {}).get("status") in C.COUNTABLE


def cell_state(runs: list[dict[str, Any]]) -> str:
    """done | live | open. live: a run is still launched/running AND still counts — a
    live run a human set aside (`set --legitimacy void` after a crash) no longer pins the
    cell; done: the newest countable run is collected; open otherwise (never launched, a
    tombstone, or every run set aside)."""
    for st in runs:
        if st.get("lifecycle") in C.LIVE and _counts(st):
            return "live"
    for st in runs:
        if st.get("lifecycle") == "collected" and _counts(st):
            return "done"
    return "open"


def _cell_counts(table: dict) -> tuple[int, int, int]:
    states = [cell_state(r) for r in table.values()]
    return states.count("done"), states.count("live"), states.count("open")


# ---- launch -------------------------------------------------------------------------
def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)      # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            code = ctypes.c_ulong()
            ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
            return bool(ok) and code.value == 259                         # STILL_ACTIVE
        finally:
            ctypes.windll.kernel32.CloseHandle(h)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class LaunchLock:
    """One `launch` per campaign at a time. Two launchers on one campaign would launch the
    same open cell twice inside the window between "no run yet" and the child's
    `launched` status (resolve + seed take seconds), and the scorer would then report a
    duplicate cell. The lock holds the launcher's pid; a lock whose pid is dead (the
    launch host rebooted under nohup) is stale and replaced."""

    def __init__(self, cdir: Path) -> None:
        self.path = cdir / "launch.lock"
        self.held = False

    def acquire(self) -> None:
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    pid = int(self.path.read_text(encoding="utf-8").strip() or 0)
                except (OSError, ValueError):
                    pid = 0
                if _pid_alive(pid):
                    raise SystemExit(f"another launch of this campaign is running (pid {pid}, {self.path}); "
                                     f"wait for it or stop it first")
                self.path.unlink(missing_ok=True)                     # stale: its launcher is gone
                continue
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(f"{os.getpid()}\n")
            self.held = True
            return
        raise SystemExit(f"could not take {self.path}")

    def release(self) -> None:
        if self.held:
            self.path.unlink(missing_ok=True)
            self.held = False


def _unscorable_done(cdir: Path, table: dict) -> list[str]:
    """Done cells whose counted run the scorer would still not score (no_result,
    phantom_fail, adjudicate, mismatch): `launch` will not relaunch them on its own, so
    the operator has to set the run aside and relaunch. Named here so it is not a
    surprise in scores.json."""
    sys.path.insert(0, str(RUNTIME_ROOT / "score"))
    import score_v0                                                   # stdlib-only
    res = score_v0.score_campaign(cdir)
    state_of = {r["rollout_id"]: r["state"] for r in res["records"] if r.get("rollout_id")}
    out = []
    for (task, seed), runs in table.items():
        if cell_state(runs) != "done":
            continue
        st = next(s for s in runs if s.get("lifecycle") == "collected" and _counts(s))
        state = state_of.get(st["rollout_id"])
        if state not in ("scored", None):
            out.append(f"{task} s{seed}: {st['rollout_id']} is {state}")
    return out


def cmd_launch(a: argparse.Namespace) -> int:
    if a.rerun and not a.only:
        raise SystemExit("--rerun needs --only <task> …: it relaunches finished cells of those tasks")
    if not a.dry_run:
        _need_bench("launch")
    cdir = _cdir(a)
    logfile = None if a.dry_run else cdir / "launch.log"     # a dry run writes nothing, not even a log line
    m = C.read_manifest(cdir)
    mx = m["matrix"]

    # the pipeline guard: the manifest recorded what grades this campaign; if the pin moved
    # (rebaked AMI, new CLI) the new cells would be graded by different code than the old
    # ones and the campaign would mix pipelines. Start a new campaign instead.
    cur = C.current_pipeline(RUNTIME_ROOT, transport=mx["transport"])
    diff = C.pipeline_diff(m.get("pipeline") or {}, cur)
    if diff and not a.skip_guards:
        raise SystemExit("pipeline changed since this campaign was created — start a new campaign:\n  "
                         + "\n  ".join(diff) + "\n(--skip-guards overrides knowingly)")
    only = set(a.only or [])
    unknown = only - set(mx["tasks"])
    if unknown:
        raise SystemExit(f"--only names tasks outside the matrix: {sorted(unknown)}")

    lock = LaunchLock(cdir)
    if not a.dry_run:
        lock.acquire()                     # before the cells are read: the window is the race
    try:
        return _launch(a, cdir, m, logfile, only)
    finally:
        lock.release()


def _launch(a: argparse.Namespace, cdir: Path, m: dict[str, Any], logfile: Path, only: set[str]) -> int:
    mx = m["matrix"]
    if (m.get("legitimacy") or {}).get("status") == "void" and m["purpose"] not in ("smoke", "experiment"):
        log(f"note: campaign is void ({m['legitimacy'].get('reason')}); launching anyway", logfile)
    table = cell_table(cdir, m)
    todo: list[tuple[str, int]] = []
    supersede: list[tuple[str, int, dict[str, Any]]] = []
    for (task, seed), runs in table.items():
        if only and task not in only:
            continue
        state = cell_state(runs)
        if state == "live":
            log(f"skip {task} s{seed}: a run is live ({runs[0]['rollout_id']} {runs[0]['lifecycle']})", logfile)
            continue
        if state == "done":
            if not a.rerun:
                continue
            supersede += [(task, seed, st) for st in runs if st.get("lifecycle") == "collected" and _counts(st)]
        todo.append((task, seed))
    done, live, open_ = _cell_counts(table)
    log(f"{m['campaign']}: {len(table)} cells planned, {done} done, {live} live, {len(todo)} to launch, width {a.width}", logfile)
    if a.dry_run:
        for task, seed in todo:
            print(f"  would launch {task} s{seed}")
        for task, seed, st in supersede:
            print(f"  would mark {st['rollout_id']} ({task} s{seed}) superseded")
        return 0
    # an explicit re-run of a finished cell: the old run is set aside NOW, with the reason,
    # so the scorer never sees two counted runs for one cell. Only for real launches — a
    # dry run writes nothing.
    for task, seed, st in supersede:
        C.transition(cdir / "runs" / st["_folder"], legitimacy="superseded",
                     reason="re-run requested by campaign.py launch --rerun", by=a.by or C.who())
        log(f"{task} s{seed}: {st['rollout_id']} marked superseded (re-run)", logfile)
    if not todo:
        C.refresh_manifest_runs(cdir)
        return 0

    (cdir / "logs").mkdir(exist_ok=True)
    pending = list(todo)
    running: dict[tuple[str, int], tuple[subprocess.Popen, Path]] = {}
    failures = 0
    env = dict(os.environ)
    # the children resolve the campaign by name under the same root this launcher used
    env["REVYL_BENCH_CAMPAIGNS"] = str(C.campaigns_root(a.campaigns_dir))
    # and reach the rollout host the way the manifest says (private from a launch host
    # inside the VPC, public from a workstation) — recorded at `new`, so a launch from a
    # shell that never exported REVYL_BENCH_SSH_IP cannot fall back to an address that
    # never connects
    if mx.get("ssh_ip"):
        env["REVYL_BENCH_SSH_IP"] = mx["ssh_ip"]
    while pending or running:
        while pending and len(running) < a.width:
            task, seed = pending.pop(0)
            out = cdir / "logs" / f"{task}_s{seed}_{time.strftime('%Y%m%dT%H%M%S')}.log"
            cmd = [sys.executable, str(LAUNCH_ROLLOUT), "--campaign", m["campaign"], "--task", task,
                   "--contestant", m["contestant"]["slug"], "--seed", str(seed),
                   "--transport", mx["transport"], "--cap", str(mx["cap"]),
                   "--wall-clock-min", str(mx["wall_clock_min"]), "--mode", mx.get("mode", "full")]
            if a.skip_guards:
                cmd.append("--skip-guards")
            with out.open("w", encoding="utf-8") as fh:
                # the child inherits a dup of the handle; closing ours right away is safe
                p = subprocess.Popen(cmd, cwd=str(RUNTIME_ROOT), env=env, stdout=fh, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL)
            running[(task, seed)] = (p, out)
            log(f"launched {task} s{seed} pid {p.pid} → {out.name}", logfile)
            if pending:
                time.sleep(a.stagger)                       # do not hit the EC2 and device APIs in one burst
        time.sleep(a.poll)
        for key, (p, out) in list(running.items()):
            rc = p.poll()
            if rc is None:
                continue
            del running[key]
            task, seed = key
            if rc == 0:
                log(f"finished {task} s{seed} rc=0", logfile)
            else:
                failures += 1
                tail = ""
                try:
                    tail = out.read_text(encoding="utf-8", errors="replace")[-400:].strip().replace("\n", "\n    ")
                except OSError:
                    pass
                log(f"FAILED {task} s{seed} rc={rc} — see {out.name}\n    {tail}", logfile)
    m = C.refresh_manifest_runs(cdir)
    table = cell_table(cdir, m)
    done, live, open_ = _cell_counts(table)
    log(f"{m['campaign']}: {done}/{len(table)} cells done, {live} live, {failures} launch failure(s); "
        f"score with: python3 runtime/score/score_v0.py --campaign {m['campaign']}", logfile)
    for line in _unscorable_done(cdir, table):
        log(f"done but not scorable — set the run aside and relaunch: {line}", logfile)
    return 1 if failures else 0


# ---- status / list ------------------------------------------------------------------
def cmd_status(a: argparse.Namespace) -> int:
    """Read-only: it never touches campaign.json, so it is safe while a launch runs."""
    cdir = _cdir(a)
    m = C.read_manifest(cdir)
    lg = m.get("legitimacy") or {}
    print(f"{m['campaign']}: purpose {m['purpose']}, legitimacy {lg.get('status')} ({lg.get('reason')}), "
          f"contestant {m['contestant']['slug']} ({m['contestant'].get('harness')} {m['contestant'].get('harness_version')}), "
          f"protocol {m['protocol_version']}")
    print(f"  matrix: {len(m['matrix']['tasks'])} tasks × seeds {m['matrix']['seeds']}, transport {m['matrix']['transport']} "
          f"(ssh {m['matrix'].get('ssh_ip', 'public')}), cap {m['matrix']['cap']}, wall {m['matrix']['wall_clock_min']} min; "
          f"pipeline {json.dumps(m.get('pipeline'))}")
    table = cell_table(cdir, m)
    print(f"{'task':<28}{'seed':<6}{'state':<6}{'run':<40}{'lifecycle':<16}{'legitimacy':<15}{'mirror':<8}checks")

    def row(task, seed, state, st):
        ck = st.get("checks")
        # SUITE-FETCH: the transcript names this repository / grading-side (campaigns.suite_fetch_hits);
        # `.get` because status files written before that check existed have no such key
        ck_s = "-" if ck is None else ("PHANTOM " + ",".join(ck.get("phantom_slots") or []) if ck.get("phantom_fail")
                                        else "SUITE-FETCH" if ck.get("suite_fetch")
                                        else f"ok/{ck.get('reports_seen')}")
        mirror = "yes" if (st.get("mirror") or {}).get("synced") else "no"
        print(f"{task:<28}{str(seed):<6}{state:<6}{st['_folder']:<40}{str(st.get('lifecycle')):<16}"
              f"{str((st.get('legitimacy') or {}).get('status')):<15}{mirror:<8}{ck_s}")

    for (task, seed), runs in table.items():
        state = cell_state(runs)
        if not runs:
            print(f"{task:<28}{seed:<6}{state:<6}-")
        for st in runs:
            row(task, seed, state, st)
    extras = extra_runs(cdir, m)
    if extras:
        print(f"outside the matrix ({len(extras)}; listed by the scorer, never aggregated):")
        for st in extras:
            row(str(st.get("task") or "?"), st.get("seed") or "?", "-", st)
    done, live, open_ = _cell_counts(table)
    print(f"cells: {done} done, {live} live, {open_} open of {len(table)} planned")
    return 0


def cmd_list(a: argparse.Namespace) -> int:
    rows = C.iter_campaigns(_root(a))
    if not rows:
        print(f"no campaigns under {_root(a)}")
        return 0
    print(f"{'campaign':<58}{'purpose':<12}{'legit':<12}{'contestant':<30}{'cells':<8}{'done':<6}{'live':<6}faults")
    for name, cdir, m in rows:
        table = cell_table(cdir, m)
        done, live, _ = _cell_counts(table)
        faults = sum(1 for runs in table.values() for st in runs if st.get("lifecycle") in C.TERMINAL_FAULTS)
        print(f"{name:<58}{m['purpose']:<12}{(m.get('legitimacy') or {}).get('status', '?'):<12}"
              f"{m['contestant']['slug']:<30}{len(table):<8}{done:<6}{live:<6}{faults}")
    return 0


# ---- set / extend -------------------------------------------------------------------
def _run_dir_by_id(cdir: Path, rollout_id: str) -> Path:
    for e in C.run_index(cdir):
        st = e["status"]
        if st and st.get("rollout_id") == rollout_id:
            return e["path"]
    raise SystemExit(f"no run {rollout_id} in {cdir.name}")


def cmd_set(a: argparse.Namespace) -> int:
    cdir = _cdir(a)
    if not a.legitimacy and not a.lifecycle:
        raise SystemExit("set needs --legitimacy or --lifecycle")
    if a.lifecycle and not a.run:
        raise SystemExit("--lifecycle applies to a run (--run <rollout_id>)")
    by = a.by or C.who()
    try:
        if a.run:
            d = _run_dir_by_id(cdir, a.run)
            if a.lifecycle:
                # the one human lifecycle write: a run whose launcher died (the launch host
                # rebooted under nohup, ssh dropped) sits at launched/running forever otherwise, and
                # its cell can never be relaunched. Forward-only, terminal faults only.
                cur = (C.read_status(d) or {}).get("lifecycle")
                if cur not in C.LIVE:
                    raise SystemExit(f"{a.run} is {cur}, not live — only a launched/running run can be marked {a.lifecycle}")
                rec = C.transition(d, lifecycle=a.lifecycle, reason=a.reason, by=by)
                print(f"{a.run}: lifecycle {cur} → {rec['lifecycle']} ({a.reason}); its cell is open again")
            if a.legitimacy:
                rec = C.transition(d, legitimacy=a.legitimacy, reason=a.reason, by=by)
                print(f"{a.run}: legitimacy {rec['legitimacy']['status']} ({a.reason})")
        else:
            m = C.set_campaign_legitimacy(cdir, a.legitimacy, reason=a.reason, by=by)
            print(f"{m['campaign']}: legitimacy {m['legitimacy']['status']} ({a.reason})")
    except ValueError as e:
        raise SystemExit(str(e))
    C.refresh_manifest_runs(cdir)
    return 0


def cmd_extend(a: argparse.Namespace) -> int:
    cdir = _cdir(a)
    m = C.read_manifest(cdir)
    cur = C.current_pipeline(RUNTIME_ROOT, transport=m["matrix"]["transport"])
    diff = C.pipeline_diff(m.get("pipeline") or {}, cur)
    if diff:
        raise SystemExit("cannot extend: the pipeline changed since this campaign was created, so the new "
                         "cells would be graded by different code — start a new campaign:\n  " + "\n  ".join(diff))
    try:
        m = C.extend_manifest(cdir, seeds=_ints(a.seeds), tasks=_csv(a.tasks), reason=a.reason, by=a.by or C.who())
    except ValueError as e:
        raise SystemExit(str(e))
    print(f"{m['campaign']}: matrix now {len(m['matrix']['tasks'])} tasks × seeds {m['matrix']['seeds']} "
          f"({len(C.planned_cells(m))} cells); launch fills the new cells")
    return 0


# ---- sync / fetch -------------------------------------------------------------------
def _aws() -> dict[str, Any]:
    """aws binary, profile, region and bucket the way launch_rollout resolves them:
    .env first (AWS_BIN/AWS_PROFILE), then the environment; region and bucket from
    host/ec2/infra.json."""
    from bench import hosts as _hosts           # stdlib-only module
    from launch_rollout import _aws_cli, load_dotenv
    env = load_dotenv()
    aws_bin, profile = _aws_cli(env)
    infra = _hosts.load_infra(RUNTIME_ROOT)
    return {"aws_bin": aws_bin, "profile": profile, "region": infra["region"], "bucket": infra["bucket"]}


def _refuse_local(m: dict[str, Any], what: str) -> None:
    if m["matrix"].get("transport") == "local":
        raise SystemExit(f"{m['campaign']} runs on transport=local: it has no mirror, so there is nothing to {what}")


def runs_to_sync(cdir: Path) -> list[dict[str, Any]]:
    """Every run with a status file whose folder is final: collected runs, and the
    tombstones (guard_abort, launch_failed, collect_failed), which are part of the record
    — a campaign's failed cells must be readable from the store too. Only live runs are
    skipped: their folders are still being written."""
    return [e for e in C.run_index(cdir) if e["status"] and e["status"].get("lifecycle") not in C.LIVE]


def cmd_sync(a: argparse.Namespace) -> int:
    cdir = _cdir(a)
    m = C.read_manifest(cdir)
    if not a.force:
        _refuse_local(m, "sync")           # --force: a backfilled campaign whose runs ran on transport=local
    _need_bench("sync")
    aws = _aws()
    by = a.by or C.who()
    failed = 0
    for e in runs_to_sync(cdir):
        st = e["status"]
        prefix = (st.get("mirror") or {}).get("prefix") or C.mirror_prefix(m["campaign"], e["folder"])
        target = f"s3://{aws['bucket']}/{prefix}/"
        should_slim = bool(getattr(a, "slim", False) or m.get("slim_after_mirror"))
        # Re-upload before pruning even a previously mirrored run: fetch or late
        # collection may have changed its artifacts since the old mirror timestamp.
        if not (st.get("mirror") or {}).get("synced") or (should_slim and C.slim_candidates(e["path"])):
            ok, err = C.s3_sync(str(e["path"]), target, aws_bin=aws["aws_bin"], profile=aws["profile"], region=aws["region"])
            C.transition(e["path"], by=by, mirror={"synced": ok, "at": C.now_iso(), "prefix": prefix, "error": None if ok else err})
            if ok:
                print(f"synced {e['folder']} → {target}")
                if should_slim:
                    try:
                        removed = C.slim(e["path"])
                    except OSError as exc:
                        failed += 1
                        removed = []
                        print(f"FAILED cleanup {e['folder']}: {exc}")
                    if removed:
                        C.transition(e["path"], by=by, slimmed=removed)
                        print(f"  slimmed {removed}")
            else:
                failed += 1
                print(f"FAILED {e['folder']}: {err}")
                continue
        # the status file is always the last thing to change (mirror result, slim,
        # legitimacy set by a human): push it on its own so the store carries the record
        ok, err = C.s3_copy(str(e["path"] / C.STATUS), target + C.STATUS, aws_bin=aws["aws_bin"],
                            profile=aws["profile"], region=aws["region"])
        if not ok:
            failed += 1
            print(f"FAILED status.json of {e['folder']}: {err}")
    C.refresh_manifest_runs(cdir)
    return 1 if failed else 0


def cmd_fetch(a: argparse.Namespace) -> int:
    cdir = _cdir(a)
    m = C.read_manifest(cdir)
    _refuse_local(m, "fetch")
    _need_bench("fetch")
    run_dir = _run_dir_by_id(cdir, a.run)
    st = C.read_status(run_dir) or {}
    prefix = (st.get("mirror") or {}).get("prefix") or C.mirror_prefix(cdir.name, run_dir.name)
    aws = _aws()
    src = f"s3://{aws['bucket']}/{prefix}/"
    # never let the mirror's status.json overwrite the local one: the local file is the
    # newer record whenever a human changed legitimacy after the mirror
    ok, err = C.s3_sync(src, str(run_dir), aws_bin=aws["aws_bin"], profile=aws["profile"], region=aws["region"],
                        extra=["--exclude", C.STATUS])
    if not ok:
        raise SystemExit(f"fetch failed: {err}")
    print(f"fetched {src} → {run_dir}")
    return 0


# ---- promote / render: publishing -----------------------------------------------------
def cmd_promote(a: argparse.Namespace) -> int:
    """Write a campaign into the official record as the campaign behind one published
    row. Refuses — unless --reason is given and recorded — a campaign that is not
    official, not complete, has problems, or whose scores.json predates a status change;
    and a replacement graded by the same pipeline as the row's current campaign."""
    parts: list[tuple[dict, dict]] = []
    for name in a.name:
        cdir = _cdir(a, name)
        m = C.read_manifest(cdir)
        sc = cdir / C.SCORES
        if not sc.exists():
            raise SystemExit(f"{sc} missing — score first: python3 runtime/score/score_v0.py --campaign {m['campaign']}")
        if C.scores_are_stale(cdir):
            raise SystemExit(f"{sc} is older than a status change in the campaign — score again first")
        parts.append((C.read_json(sc), m))
    label = " + ".join(res["campaign"] for res, _ in parts)
    rows = C.read_official(a.record)
    existing = next((r for r in rows if r.get("row") == a.row), None)
    refusals = C.union_refusals(parts) + C.dropped_refusals(existing, [res["campaign"] for res, _ in parts])
    names = [res["campaign"] for res, _ in parts]
    for res, m in parts:
        refusals += [f"{res['campaign']}: {x}" if len(parts) > 1 else x for x in C.promotion_refusals(res, m, existing, names)]
    if refusals and not a.reason:
        raise SystemExit(f"refusing to promote {label} as row {a.row!r}:\n  - " + "\n  - ".join(refusals)
                         + "\n(--reason \"…\" promotes anyway and records the reason in the row)")
    previous = None
    if existing:
        previous = {"campaign": existing.get("campaign"), "macro": existing.get("macro"),
                    "promoted_at": existing.get("promoted_at"), "reason": existing.get("reason")}
    row = C.official_row(parts, row=a.row, reason=a.reason, by=a.by or C.who(), previous=previous)
    m = {"campaign": label}
    if existing:
        rows = [row if r.get("row") == a.row else r for r in rows]
    else:
        rows.append(row)
    C.write_official(rows, a.record)
    path = Path(a.record) if a.record else C.OFFICIAL
    what = f"replaces {previous['campaign']} ({previous['macro']})" if previous else "new row"
    print(f"promoted {m['campaign']} as row {a.row!r} ({what}); macro {row['macro']}, "
          f"seeds {row['seeds_counted']}/{row['seeds_planned']}, {'complete' if row['complete'] else 'INCOMPLETE'}"
          + (f"; reason: {a.reason}" if a.reason else "") + f"\n→ {path}  (commit it)")
    for r in refusals:
        print(f"  overridden: {r}")
    return 0


def cmd_render(a: argparse.Namespace) -> int:
    """Regenerate the results page's leaderboard block from the official record.
    --check exits 1 when the page does not match the record (for CI)."""
    rows = C.read_official(a.record)
    if not rows:
        raise SystemExit(f"nothing promoted yet ({Path(a.record) if a.record else C.OFFICIAL} is empty) — campaign.py promote first")
    page = Path(a.page) if a.page else C.RUNTIME_ROOT.parent / "docs" / "season1-results.md"
    text = page.read_text(encoding="utf-8")
    try:
        new = C.render_page(text, rows)
    except ValueError as e:
        raise SystemExit(str(e))
    if a.check:
        if new == text:
            print(f"{page} matches {len(rows)} row(s) of the record")
            return 0
        print(f"{page} does NOT match the record — run campaign.py render")
        return 1
    if new == text:
        print(f"{page} already matches the record ({len(rows)} row(s))")
        return 0
    page.write_text(new, encoding="utf-8", newline="\n")
    print(f"rendered {len(rows)} row(s) into {page}; review the diff and commit it with the record")
    return 0


# ---- entry --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campaigns-dir", help=f"where campaigns live (default $REVYL_BENCH_CAMPAIGNS or {C.CAMPAIGNS_DIR})")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("new", help="create a campaign folder and manifest")
    p.add_argument("--purpose", required=True, choices=C.PURPOSES)
    p.add_argument("--contestant", required=True, help="registry slug, e.g. opencode/muse-spark-1.3")
    p.add_argument("--tasks", help="comma-separated; default: every package under the purpose's task root")
    p.add_argument("--seeds", help="comma-separated; default: 1,2,3 for benchmark, 1 otherwise")
    p.add_argument("--name", help="full campaign name (default <date>_<contestant>_<purpose>[-label])")
    p.add_argument("--label", help="suffix for the default name (a second campaign on the same day)")
    p.add_argument("--transport", choices=["ec2", "local"], default="ec2")
    p.add_argument("--ssh-ip", choices=["public", "private"],
                   help="how rollout hosts are reached: private from a launch host inside the VPC, public from "
                        "a workstation (default: $REVYL_BENCH_SSH_IP, else public)")
    p.add_argument("--cap", type=int, default=5)
    p.add_argument("--wall-clock-min", type=int, default=480)
    p.add_argument("--mode", choices=["full", "p0"], default="full")
    p.add_argument("--reason", help="required when a benchmark plans fewer than three seeds")
    p.add_argument("--by", help="who creates it (default: login name)")
    p.add_argument("--keep-artifacts", action="store_true",
                   help="keep archived artifacts locally for inspection after the mirror")
    p.add_argument("--notes", help="free text into the manifest")
    p.add_argument("--dry-run", action="store_true", help="print the manifest, create nothing")
    p.set_defaults(fn=cmd_new)

    p = sub.add_parser("launch", help="run every open cell of the matrix, --width at a time")
    p.add_argument("--name", required=True)
    p.add_argument("--width", type=int, default=12, help="concurrent rollouts (device pool ≈ 20, shared)")
    p.add_argument("--only", nargs="*", metavar="TASK", help="restrict to these tasks")
    p.add_argument("--rerun", action="store_true", help="with --only: relaunch finished cells; the old run is marked superseded")
    p.add_argument("--stagger", type=float, default=5.0, help="seconds between launches")
    p.add_argument("--poll", type=float, default=15.0, help="seconds between checks on running rollouts")
    p.add_argument("--skip-guards", action="store_true", help="pass through to launch_rollout.py and skip the pipeline guard")
    p.add_argument("--by")
    p.add_argument("--dry-run", action="store_true", help="print the cells that would launch; writes nothing")
    p.set_defaults(fn=cmd_launch)

    p = sub.add_parser("status", help="one campaign: every planned cell and its runs (read-only)")
    p.add_argument("--name", required=True)
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("list", help="one line per campaign")
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("set", help="change a campaign's or a run's legitimacy, or move a dead live run to a fault (reason required)")
    p.add_argument("--name", required=True)
    p.add_argument("--run", metavar="ROLLOUT_ID", help="a run in the campaign; omit to set the campaign itself")
    p.add_argument("--legitimacy",
                   help=f"campaign: {'|'.join(C.CAMPAIGN_LEGITIMACY)}; run: {'|'.join(C.RUN_LEGITIMACY)}")
    p.add_argument("--lifecycle", choices=["launch_failed", "collect_failed"],
                   help="with --run: a launched/running run whose launcher died; reopens its cell")
    p.add_argument("--reason", required=True)
    p.add_argument("--by")
    p.set_defaults(fn=cmd_set)

    p = sub.add_parser("extend", help="add seeds or tasks to the matrix (same pipeline only)")
    p.add_argument("--name", required=True)
    p.add_argument("--seeds")
    p.add_argument("--tasks")
    p.add_argument("--reason", required=True)
    p.add_argument("--by")
    p.set_defaults(fn=cmd_extend)

    p = sub.add_parser("sync", help="retry the S3 mirror for unmirrored runs and push every collected run's status.json")
    p.add_argument("--name", required=True)
    p.add_argument("--force", action="store_true", help="mirror a local-transport campaign anyway (a backfilled one)")
    p.add_argument("--slim", action="store_true", help="prune archived artifacts even for an older keep-artifacts campaign")
    p.add_argument("--by")
    p.set_defaults(fn=cmd_sync)

    p = sub.add_parser("fetch", help="pull a run's artifacts from S3 into its folder")
    p.add_argument("--name", required=True)
    p.add_argument("--run", required=True, metavar="ROLLOUT_ID")
    p.set_defaults(fn=cmd_fetch)

    p = sub.add_parser("promote", help="write a campaign into results/official.jsonl as the campaign behind a published row")
    p.add_argument("--name", required=True, action="append",
                   help="the campaign; repeat for a row backed by several campaigns with disjoint task sets (the 17-task "
                        "campaign plus the 18–20 one); an absolute path names a campaign folder in another store")
    p.add_argument("--row", required=True, help="the published row's id, e.g. season1-glm-5.2")
    p.add_argument("--reason", help="promote a provisional, incomplete or problem-bearing campaign anyway, on the record")
    p.add_argument("--by")
    p.add_argument("--record", help=f"the official record (default {C.OFFICIAL})")
    p.set_defaults(fn=cmd_promote)

    p = sub.add_parser("render", help="regenerate the results page's leaderboard block from the official record")
    p.add_argument("--page", help="the page (default docs/season1-results.md)")
    p.add_argument("--record", help=f"the official record (default {C.OFFICIAL})")
    p.add_argument("--check", action="store_true", help="exit 1 when the page does not match the record")
    p.set_defaults(fn=cmd_render)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
