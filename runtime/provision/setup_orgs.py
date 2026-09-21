#!/usr/bin/env python3
"""provision/setup_orgs.py — fill a deployment's two Revyl organisations from the repository.

    python3 runtime/provision/setup_orgs.py grading [--all | --task <pkg> ... | --tasks-file F] [--dry-run]
    python3 runtime/provision/setup_orgs.py agent   [--all | --task <pkg> ... | --tasks-file F] [--dry-run]
    python3 runtime/provision/setup_orgs.py check   [--all | --task <pkg> ... | --tasks-file F]

With no selection flag the applications come from runtime/provision/tasks.txt (all 20 as
shipped; delete lines to set up a subset). One line = one application = its whole-app
benchmark task and its three step tasks, which share one grading app, one suite workflow
and one dev client (docs/organizations.md).

WHY TWO COMMANDS AND NOT ONE. The benchmark's security boundary is two organisations: the
agent container holds a key to an organisation that contains only a dev app and a dev
client, and the grading suites live in a second organisation whose key only the runner
holds. A policy can therefore not read its own tests. Setup keeps the same separation:
`grading` needs REVYL_GRADING_API_KEY and never looks for the agent key; `agent` needs
REVYL_AGENT_API_KEY and never looks for the grading key. `check` is the one command that
audits both, and it audits whichever keys are present.

Keys and organisation ids are read from runtime/.env (the documented place, the file every
other provisioning script and the launcher read); a variable missing from the file is
taken from the process environment. If REVYL_GRADING_ORG_ID / REVYL_AGENT_ORG_ID is not
set anywhere, the organisation the key resolves to is used and printed, with the line to
add to runtime/.env — the launcher needs both ids there before the first rollout.

grading   per application, through provision_grading.audit (the same code as
          `provision_grading.py --apply`): the grading app `bench-<pkg>`, the four frozen
          tests from grading-side/<pkg>/, the `<prefix>-suite` workflow. Then the step
          provision_grading only PRINTS is done for you: the grading app id and workflow
          name are written into [runtime.grading] of tasks/<pkg>/task.toml and of every
          task package that names <pkg> as its parent_task. Ends with a read-only
          `--check --content` pass (presence, and that each live test's step text equals
          the committed YAML) and prints one line per application: ok, or what is missing.
agent     per application: the dev app `bench-<pkg>-dev` and its one dev-client build
          (make_devclient.py --builder revyl, ~10 min per application, Revyl builds it),
          then dev_app_id / devclient_version_id / devclient_version written into
          [runtime.agent] of the parent and its step packages. `scaffold` and
          `base_commit` are per-package and are never touched.
check     read-only: provision_grading --check --content for the grading organisation,
          check_devclients.py for the agent organisation, one line per application.

IDEMPOTENT AND RESUMABLE. All 20 applications are about 120 CLI calls on the grading side
and 20 dev-client builds on the agent side. The state is the organisations themselves: a
re-run first asks what is already there and creates only what is missing, so an
interrupted run is resumed by typing the same command again. There is no state file.

--dry-run prints every command that would write and runs none of them (reads still happen:
it needs to see the organisation to know what is missing).

STATUS, stated plainly: the create paths underneath (provision_grading's `app create` /
`test create` / `workflow create`, make_devclient's app and build) follow the pinned CLI's
documented flags and have been run many times against our own, already-populated
organisations. They have NOT yet been exercised end to end against an EMPTY organisation.
Run `--dry-run` first, then one application (`--task s1-commerce-0001`), then the rest.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from bench import revyl as _revyl  # noqa: E402
from bench.config import BENCH_ROOT, ORG_ENV, RUNTIME_ROOT  # noqa: E402
from launch_rollout import load_dotenv  # noqa: E402
from provision import provision_grading as _grading  # noqa: E402
from provision.write_task_toml import set_runtime_values  # noqa: E402

TASKS_FILE = HERE / "tasks.txt"
KEY_ENV = {"grading": "REVYL_GRADING_API_KEY", "agent": "REVYL_AGENT_API_KEY"}
# the directories whose packages can name a parent application; a checkout that does not
# carry one of them (the public repository ships neither) simply has no children there
CHILD_ROOTS = ("tasks-step", "tasks-repair")


# ---------------------------------------------------------------- selection
def parse_tasks_file(path: Path) -> list[str]:
    """Package names from a tasks file: one per line, `#` starts a comment (whole line or
    trailing), blank lines ignored, order kept, duplicates dropped."""
    out: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        name = raw.split("#", 1)[0].strip()
        if name and name not in out:
            out.append(name)
    return out


def known_apps() -> list[str]:
    """Applications this checkout can set up: a task package with its grading suites beside it.
    Both halves are needed — the package names the four tests, grading-side holds them."""
    return sorted(p.parent.name for p in (BENCH_ROOT / "tasks").glob("*/task.toml")
                  if (BENCH_ROOT / "grading-side" / p.parent.name).is_dir())


def select(*, all_: bool, tasks: list[str], tasks_file: Path | None) -> list[str]:
    """The applications one invocation acts on. Precedence: --task, then --all, then the
    tasks file (the shipped tasks.txt by default). An unknown name is an error rather than
    a skip: a typo must not quietly leave an application unprovisioned."""
    have = known_apps()
    if tasks:
        want = list(dict.fromkeys(tasks))
    elif all_:
        want = have
    else:
        want = parse_tasks_file(tasks_file or TASKS_FILE)
    unknown = sorted(set(want) - set(have))
    if unknown:
        raise SystemExit(f"not applications of this checkout (need tasks/<pkg>/task.toml and grading-side/<pkg>/): {unknown}")
    return want


# ---------------------------------------------------------------- environment
def org_env(which: str) -> dict[str, str]:
    """The key and organisation id for ONE organisation, and nothing about the other.

    .env first, process environment for whatever the file lacks (the precedence
    launch_rollout.load_dotenv documents for the org keys: a stale shell export must never
    hijack the file). The returned mapping deliberately drops the other organisation's
    key, so nothing called from here can use it even by accident."""
    src = load_dotenv()
    key_name, org_name = KEY_ENV[which], ORG_ENV[which]
    key = src.get(key_name) or os.environ.get(key_name, "")
    if not key:
        raise SystemExit(f"{key_name} is not set: put it in runtime/.env (docs/organizations.md) "
                         f"or export it. `{which}` needs only this key.")
    org = src.get(org_name) or os.environ.get(org_name, "")
    st = _revyl.auth_status(key)
    if not org:
        # a first-time setup typically has the key and nothing else; the key names its org
        org = st.get("org_id", "")
        print(f"[auth] {org_name} is not set; the key resolves to {org} ({st.get('org_name')}). "
              f"Add this line to runtime/.env before launching rollouts:\n         {org_name}={org}")
    elif st.get("org_id") != org:
        raise SystemExit(f"{key_name} resolves to org {st.get('org_id')} ({st.get('org_name')}) != {org_name}={org}")
    return {key_name: key, org_name: org}


# ---------------------------------------------------------------- task.toml write-back
def packages_of(app: str) -> list[Path]:
    """task.toml of the application and of every package that inherits its [runtime.*] ids:
    the parent first, then each step (and, where the checkout has them, repair) package
    whose [metadata].parent_task names it."""
    out = [BENCH_ROOT / "tasks" / app / "task.toml"]
    for root in CHILD_ROOTS:
        d = BENCH_ROOT / root
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*/task.toml")):
            meta = tomllib.loads(p.read_text(encoding="utf-8")).get("metadata") or {}
            if meta.get("parent_task") == app:
                out.append(p)
    return out


def write_back(app: str, table: str, values: dict[str, str], *, dry_run: bool) -> list[str]:
    """Record minted ids in every package of the application. Returns the files changed
    (or that would change). A step package graded against the parent's OLD app id would
    fail the launch guard, so parent and children are always written together."""
    changed: list[str] = []
    for p in packages_of(app):
        rel = p.relative_to(BENCH_ROOT).as_posix()
        if dry_run:
            changed.append(rel)
        elif set_runtime_values(p, table, values):
            changed.append(rel)
    return changed


# ---------------------------------------------------------------- grading
def _ns(tasks: list[str], *, apply: bool, dry_run: bool, content: bool) -> argparse.Namespace:
    """The four fields provision_grading.audit reads, as its own CLI would have parsed them."""
    return argparse.Namespace(apply=apply, check=not apply, dry_run=dry_run, content=content, task=list(tasks))


def cmd_grading(apps: list[str], *, dry_run: bool) -> int:
    env = org_env("grading")
    print(f"== grading organisation: {len(apps)} application(s){' (dry run)' if dry_run else ''}")
    # pass 1: create whatever is missing. --content too, so a stale live test is rewritten
    # in place rather than merely reported by the final check.
    _, results = _grading.audit(_ns(apps, apply=True, dry_run=dry_run, content=True), env)
    for app in apps:
        r = results.get(app) or {}
        app_id = r.get("app_id", "")
        if not app_id or app_id == "<app-id>":
            # "<app-id>" is the dry run's stand-in for an id `app create` would mint
            if dry_run:
                print(f"   {app}: WOULD record the new grading app id in {len(packages_of(app))} task.toml file(s)")
            continue
        changed = write_back(app, "grading", {"app_id": app_id, "workflow": r["workflow"]}, dry_run=dry_run)
        if changed:
            print(f"   {app}: {'WOULD record' if dry_run else 'recorded'} app_id {app_id[:8]}… in {len(changed)} task.toml file(s)")
    if dry_run:
        print("== dry run: nothing was created and no task.toml was written")
        return 0
    # pass 2: read-only proof. What was missing before pass 1 must be present now, and the
    # live step text must equal the committed YAML (a suite revised in the repository but
    # never re-pushed would otherwise keep grading against the old contract).
    print("== verifying (read-only)")
    missing_total, verify = _grading.audit(_ns(apps, apply=False, dry_run=False, content=True), env)
    return _summary("grading", apps, {a: (verify.get(a) or {}).get("missing", ["not audited"]) for a in apps})


# ---------------------------------------------------------------- agent
def agent_state(app: str) -> dict:
    t = tomllib.loads((BENCH_ROOT / "tasks" / app / "task.toml").read_text(encoding="utf-8"))
    return (t.get("runtime") or {}).get("agent") or {}


def devclient_ok(app: str, key: str) -> bool:
    """True when task.toml pins a dev-client version that exists in the agent organisation's
    dev app — the same fact check_devclients.py reports, asked for one application."""
    ag = agent_state(app)
    if not (ag.get("dev_app_id") and ag.get("devclient_version_id")):
        return False
    try:
        versions = _revyl.build_list(key, RUNTIME_ROOT / ag.get("scaffold", f"scaffolds/{app}"), ag["dev_app_id"])
    except _revyl.RevylError:
        return False      # an app id from someone else's organisation: not found here, so not ok
    return any((v.get("id") or v.get("version_id")) == ag["devclient_version_id"] for v in versions)


def _require_in_dotenv(name: str) -> None:
    """make_devclient.py runs as a subprocess and reads runtime/.env itself (load_dotenv),
    not the process environment: a key that was only exported would reach this script and
    then fail there with a bare KeyError ten lines into a build. Say so up front instead."""
    if not load_dotenv().get(name):
        raise SystemExit(f"{name} must be in runtime/.env for `agent`: make_devclient.py reads the file, "
                         f"not the shell environment (docs/organizations.md)")


def cmd_agent(apps: list[str], *, dry_run: bool, version_n: int) -> int:
    env = org_env("agent")
    key = env[KEY_ENV["agent"]]
    print(f"== agent organisation: {len(apps)} application(s){' (dry run)' if dry_run else ''}")
    if not dry_run:
        _require_in_dotenv(KEY_ENV["agent"])
        _require_in_dotenv(ORG_ENV["agent"])
    status: dict[str, list[str]] = {}
    for app in apps:
        if devclient_ok(app, key):
            print(f"   {app}: dev client already pinned and present; skipped")
            status[app] = []
            continue
        # no --write-toml: that path regenerates the parent's whole block and demands the
        # grading app id too, which this command must not need. make_devclient leaves its
        # result in scaffolds/<pkg>.devclient.json; the ids are written back from there.
        cmd = [sys.executable, str(HERE / "make_devclient.py"), app, "--builder", "revyl", "--version-n", str(version_n)]
        if dry_run:
            print(f"   {app}: WOULD run: {' '.join(cmd[1:])}  (dev app bench-{app}-dev + one dev-client build, ~10 min)")
            print(f"   {app}: WOULD record dev_app_id / devclient_version_id in {len(packages_of(app))} task.toml file(s)")
            status[app] = ["dev client (dry run)"]
            continue
        print(f"   {app}: building the dev client (Revyl builds it; ~10 min) …", flush=True)
        # the child environment carries no grading key even if the shell has one
        child_env = {k: v for k, v in os.environ.items() if k != KEY_ENV["grading"]}
        p = subprocess.run(cmd, cwd=BENCH_ROOT, env=child_env, capture_output=True, text=True, timeout=3 * 3600)
        if p.returncode != 0:
            tail = (p.stdout + p.stderr).strip().splitlines()[-4:]
            print(f"   {app}: make_devclient failed (rc={p.returncode}): " + " | ".join(t[:160] for t in tail))
            status[app] = ["dev client build"]
            continue
        result = json.loads((RUNTIME_ROOT / "scaffolds" / f"{app}.devclient.json").read_text(encoding="utf-8"))
        changed = write_back(app, "agent", {"dev_app_id": result["dev_app_id"],
                                            "devclient_version_id": result["devclient_version_id"],
                                            "devclient_version": result["devclient_version"]}, dry_run=False)
        print(f"   {app}: recorded dev client {result['devclient_version']} in {len(changed)} task.toml file(s)")
        status[app] = [] if devclient_ok(app, key) else ["pinned dev client not found after the build"]
    if dry_run:
        print("== dry run: nothing was created and no task.toml was written")
        return 0
    return _summary("agent", apps, status)


# ---------------------------------------------------------------- check
def cmd_check(apps: list[str]) -> int:
    """Audit whichever organisation(s) a key is present for. Each half uses only its own
    key; having one key is a normal state (the person setting up the grading organisation
    need not hold the agent key) and is reported, not failed."""
    src = load_dotenv()
    rc = 0
    ran = False
    for which in ("grading", "agent"):
        if not (src.get(KEY_ENV[which]) or os.environ.get(KEY_ENV[which])):
            print(f"== {which} organisation: {KEY_ENV[which]} not set; skipped")
            continue
        ran = True
        env = org_env(which)
        if which == "grading":
            _, res = _grading.audit(_ns(apps, apply=False, dry_run=False, content=True), env)
            rc |= _summary("grading", apps, {a: (res.get(a) or {}).get("missing", ["not audited"]) for a in apps})
        else:
            key = env[KEY_ENV["agent"]]
            rc |= _summary("agent", apps, {a: ([] if devclient_ok(a, key) else ["dev client"]) for a in apps})
    if not ran:
        raise SystemExit("neither REVYL_GRADING_API_KEY nor REVYL_AGENT_API_KEY is set; nothing to check")
    return rc


def _summary(which: str, apps: list[str], missing: dict[str, list[str]]) -> int:
    """One line per application: ok, or what is missing. Exit status 1 when anything is."""
    print(f"== {which} organisation")
    bad = 0
    for app in apps:
        m = missing.get(app) or []
        bad += bool(m)
        print(f"   {'ok     ' if not m else 'MISSING'} {app}" + (f": {', '.join(m)}" if m else ""))
    print(f"== {len(apps) - bad}/{len(apps)} application(s) ready in the {which} organisation")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, helptext in (("grading", "fill the grading organisation (needs only the grading key)"),
                           ("agent", "fill the agent organisation (needs only the agent key)"),
                           ("check", "read-only audit of whichever organisations a key is set for")):
        sp = sub.add_parser(name, help=helptext)
        sel = sp.add_mutually_exclusive_group()
        sel.add_argument("--all", action="store_true", help="every application in this checkout")
        sel.add_argument("--task", action="append", default=[], help="one application package (repeatable)")
        sel.add_argument("--tasks-file", type=Path, help=f"a file of package names (default: {TASKS_FILE.name} beside this script)")
        if name != "check":
            sp.add_argument("--dry-run", action="store_true", help="print every writing command; run none")
        if name == "agent":
            sp.add_argument("--version-n", type=int, default=1, help="dev-client version suffix (bump on a native dependency change)")
    a = ap.parse_args(argv)
    apps = select(all_=a.all, tasks=a.task, tasks_file=a.tasks_file)
    if not apps:
        raise SystemExit("no applications selected (the tasks file is empty?)")
    if a.cmd == "grading":
        return cmd_grading(apps, dry_run=a.dry_run)
    if a.cmd == "agent":
        return cmd_agent(apps, dry_run=a.dry_run, version_n=a.version_n)
    return cmd_check(apps)


if __name__ == "__main__":
    sys.exit(main())
