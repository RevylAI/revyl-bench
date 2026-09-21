#!/usr/bin/env python3
"""provision/provision_grading.py — audit or populate the grading organisation, per task.

    python3 provision/provision_grading.py --check [--task <pkg> ...]
    python3 provision/provision_grading.py --apply [--task <pkg> ...] [--dry-run]

What the grading organisation must hold for a task (docs/organizations.md):

  * a grading app `bench-<pkg>` — every submission's binary is uploaded to it and the
    launch guard checks the grading key can list its builds;
  * the four frozen tests, created from grading-side/<pkg>/{steps/*/tests,final/tests}/*.yaml
    — the runner runs them BY NAME with an explicit build id (`revyl test run <name> -b …`);
  * the workflow `<prefix>-suite` listing exactly those tests — the launch guard reads
    `workflow info` and refuses a task whose declared tests are not all in it.

This script is the repeatable form of provisioning the grading side, and what a second
deployment runs against its own grading organisation (usually through setup_orgs.py, which
also writes the minted ids into task.toml).

--check is read-only: for every provisioned task (grading-side/<pkg> exists) it reports
whether the app, the workflow and each declared test are present, and exits 1 if anything
is missing. --content adds the check that matters most and that presence alone cannot
make: the STEP TEXT of every live test must equal the committed YAML. A suite revised in
the repository but never re-pushed leaves the organisation grading against the OLD
contract — every agent then fails assertions its specification never stated — while
presence, the workflow and the AMI fingerprint all look fine. `--content` pulls
the org's definitions once (`revyl test pull --all` into a throwaway git project — the
CLI insists on a worktree) and diffs step_description lists block by block. --apply creates what --check finds missing:

  app       `revyl app create --name bench-<pkg> --platform ios` unless task.toml already
            names an app that exists, or one exists by name.
  tests     `revyl test create --from-file <yaml> --app <app-id> --force`, run from a
            TEMPORARY project directory: the CLI copies the file into <project>/.revyl/tests/,
            which must never land inside a scaffold (validate_repo rejects it). The YAML is
            rewritten first: `build.name` becomes the grading app's name (the committed
            files may name the app they were authored against), and `build.pinned_version` is dropped —
            the runner passes the build id on every run, and `test create` drops the pin
            anyway (CLI v0.1.63–0.1.96).
  workflow  `revyl workflow create <prefix>-suite --tests <a,b,c,d> --no-open`, or
            `revyl workflow add-tests` for the ones missing from an existing workflow.
  content   with --content, a live test whose step text differs from the committed YAML is
            rewritten IN PLACE (the pulled file keeps its `_meta.remote_id`, the `test:`
            body is replaced from the repo, build.name/pinned_version normalised as for
            create) and `revyl test push` updates the same test id, so the workflow and
            task.toml stay valid. Pull-verified afterwards.

A minted app id is printed with the write_task_toml.py invocation that records it; this
script never edits a package itself (setup_orgs.py does). --apply's create paths follow
the pinned CLI's documented flags; run them with --dry-run first, which prints every
command it would issue (with `<app-id>` standing in for the app it would create).
"""
from __future__ import annotations

import argparse
import contextlib
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bench import revyl as _revyl  # noqa: E402
from bench.config import BENCH_ROOT, ORG_ENV, RUNTIME_ROOT  # noqa: E402
from launch_rollout import load_dotenv  # noqa: E402

GRADING_SIDE = BENCH_ROOT / "grading-side"


def suite_files(pkg: str) -> dict[str, Path]:
    """frozen test name → yaml path (the file stem is the test name by convention)."""
    base = GRADING_SIDE / pkg
    return {y.stem: y for y in list(base.glob("steps/*/tests/*.yaml")) + list(base.glob("final/tests/*.yaml"))}


def provisioned_tasks(only: list[str]) -> list[str]:
    pkgs = sorted(p.parent.name for p in (BENCH_ROOT / "tasks").glob("*/task.toml") if (GRADING_SIDE / p.parent.name).is_dir())
    if only:
        unknown = sorted(set(only) - set(pkgs))
        if unknown:
            raise SystemExit(f"not provisioned tasks (no grading-side/<pkg>): {unknown}")
        pkgs = [p for p in pkgs if p in only]
    return pkgs


def project_dir(pkg: str, tmp: Path) -> Path:
    """A throwaway project the CLI accepts (-C needs a .revyl/config.yaml). Copied from the
    scaffold so `test create` writes its .revyl/tests/ copy here, never in the tree."""
    d = tmp / pkg
    (d / ".revyl").mkdir(parents=True, exist_ok=True)
    shutil.copy2(RUNTIME_ROOT / "scaffolds" / pkg / ".revyl" / "config.yaml", d / ".revyl" / "config.yaml")
    # CLI 0.1.96 refuses `test create` unless -C points at a git worktree ("the current
    # directory is not a usable Git worktree"), so the throwaway project is one too
    subprocess.run(["git", "init", "-q", str(d)], check=True)
    return d


def rewrite_yaml(src: Path, app_name: str, dst: Path) -> None:
    """The committed suite files name the app they were authored against
    and pin a reference build; the grading org's copy names the grading app and pins
    nothing. Data-preserving: PyYAML drops comments, which the remote copy never had."""
    import yaml
    doc = yaml.safe_load(src.read_text(encoding="utf-8"))
    build = doc.setdefault("test", {}).setdefault("build", {})
    build["name"] = app_name
    build.pop("pinned_version", None)
    dst.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=200), encoding="utf-8")


def step_texts(doc: dict) -> list[str]:
    """The graded text of a test definition, in order: one entry per block that carries a
    step_description (instructions and validations alike). Quoting, comments and block
    metadata are irrelevant to grading and are not compared."""
    blocks = ((doc or {}).get("test") or {}).get("blocks") or []
    return [str(b.get("step_description", "")).strip() for b in blocks if "step_description" in b]


def content_diff(committed: dict, live: dict) -> list[str]:
    """Human-readable differences between the committed suite file and the org's copy;
    empty when the org grades with exactly the committed text."""
    a, b = step_texts(committed), step_texts(live)
    out: list[str] = []
    if len(a) != len(b):
        out.append(f"{len(a)} graded blocks committed vs {len(b)} live")
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            out.append(f"block {i}: committed «{x[:90]}» live «{y[:90]}»")
    return out


def pull_live_definitions(key: str, proj: Path) -> dict[str, tuple[Path, dict]]:
    """test name → (local file, parsed doc) for every test in the org. One pull for the
    whole org: `revyl test pull --all` writes .revyl/tests/<name>.yaml with a `_meta`
    block (remote id, versions) that a later `push` needs to update in place."""
    import subprocess
    import yaml
    if not (proj / ".git").exists():   # the CLI refuses to pull outside a git worktree
        subprocess.run(["git", "init", "-q"], cwd=proj, check=True)
        subprocess.run(["git", "add", "-A"], cwd=proj, check=True)
        subprocess.run(["git", "-c", "user.name=provision", "-c", "user.email=bench@revyl.ai",
                        "commit", "-q", "-m", "init"], cwd=proj, check=True)
    _revyl._run(["test", "pull", "--all", "--force"], key=key, chdir=proj, timeout=900)
    out: dict[str, tuple[Path, dict]] = {}
    for p in sorted((proj / ".revyl" / "tests").glob("*.y*ml")):
        doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        name = ((doc.get("test") or {}).get("metadata") or {}).get("name") or p.stem
        out[name] = (p, doc)
    return out


def push_committed_body(key: str, proj: Path, local: Path, committed_yaml: Path, app_name: str) -> None:
    """Replace the pulled file's `test:` body with the committed one (keeping `_meta`, so
    the push updates the SAME remote id) and push it."""
    import yaml
    pulled = yaml.safe_load(local.read_text(encoding="utf-8"))
    committed = yaml.safe_load(committed_yaml.read_text(encoding="utf-8"))
    body = committed["test"]
    body.setdefault("build", {})["name"] = app_name
    body["build"].pop("pinned_version", None)      # the runner passes -b on every run
    local.write_text("# Revyl Test Definition\n" + yaml.safe_dump({"_meta": pulled["_meta"], "test": body},
                                                                  sort_keys=False, allow_unicode=True, width=200),
                     encoding="utf-8")
    # by NAME: a bare `revyl test push` re-uploads every pulled file as a new version of every
    # test in the organisation (measured: ~80 unrelated tests re-versioned by one bare push)
    _revyl._run(["test", "push", local.stem], key=key, chdir=proj, timeout=600)


def workflow_tests(key: str, proj: Path, name: str) -> list[str] | None:
    """Names of the tests in workflow `name`, or None when the workflow does not exist."""
    try:
        info = _revyl.workflow_info(key, proj, name)
    except _revyl.RevylError:
        return None
    if not isinstance(info, dict) or "tests" not in info:
        return None
    return [t.get("name", "") for t in info.get("tests", [])]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="read-only audit")
    mode.add_argument("--apply", action="store_true", help="create whatever is missing")
    ap.add_argument("--task", action="append", default=[], help="restrict to these packages (repeatable)")
    ap.add_argument("--dry-run", action="store_true", help="with --apply: print the commands, run nothing that writes")
    ap.add_argument("--content", action="store_true",
                    help="also compare each live test's step text with the committed YAML (one org-wide pull); "
                         "with --apply, push the committed body over a differing live test in place")
    a = ap.parse_args()
    missing_total, _ = audit(a)
    return 1 if (missing_total and not a.apply) else 0



@contextlib.contextmanager
def _best_effort_tmpdir(prefix: str):
    """mkdtemp + rmtree(ignore_errors=True): never raises on cleanup (see audit())."""
    td = tempfile.mkdtemp(prefix=prefix)
    try:
        yield td
    finally:
        shutil.rmtree(td, ignore_errors=True)


def audit(a: argparse.Namespace, env: dict[str, str] | None = None) -> tuple[int, dict[str, dict]]:
    """The whole check/apply pass, callable without a command line (setup_orgs.py drives it
    once per organisation setup). `a` carries the CLI's four fields: `apply`, `dry_run`,
    `content`, `task`. `env` defaults to runtime/.env; a caller that resolved the key some
    other way passes its own mapping with REVYL_GRADING_API_KEY and the grading org id.

    Returns (missing_total, results) where results[pkg] = {"app_id", "workflow", "missing",
    "report"}: `app_id` is the grading app this pass found or created (the id a caller
    must record in task.toml; "" when there is none, "<app-id>" in a dry run), `missing`
    is what was absent BEFORE this pass acted, so a second pass is the proof that --apply
    worked."""
    env = load_dotenv() if env is None else env
    results: dict[str, dict] = {}
    key = env.get("REVYL_GRADING_API_KEY", "")
    org = env.get(ORG_ENV["grading"], "")
    if not key or not org:
        raise SystemExit(f".env lacks REVYL_GRADING_API_KEY / {ORG_ENV['grading']} (see docs/organizations.md)")
    st = _revyl.auth_status(key)
    if st.get("org_id") != org:
        raise SystemExit(f"REVYL_GRADING_API_KEY resolves to org {st.get('org_id')} ({st.get('org_name')}) != {org}")
    print(f"[auth] grading org OK ({st.get('org_name')})")

    missing_total = 0
    # The throwaway project directories live in a temp dir that is removed BEST-EFFORT.
    # On Windows the revyl CLI (and the git it spawns for `test pull`) can still hold the
    # directory when the audit finishes; tempfile.TemporaryDirectory then dies inside
    # rmtree with WinError 32 and, on Python 3.11, recurses in its own error handler
    # even with ignore_cleanup_errors=True — the traceback replaced the audit's report
    # (seen on a first run against an empty organisation). A leftover temp
    # directory is harmless; a lost report is not.
    with _best_effort_tmpdir("provision-grading-") as td:
        tmp = Path(td)
        pkgs = provisioned_tasks(a.task)
        live: dict[str, tuple[Path, dict]] = {}
        pull_proj: Path | None = None
        if a.content and pkgs:
            pull_proj = project_dir(pkgs[0], tmp / "pull")
            live = pull_live_definitions(key, pull_proj)
            print(f"[content] pulled {len(live)} live test definitions")
        for pkg in pkgs:
            t = tomllib.loads((BENCH_ROOT / "tasks" / pkg / "task.toml").read_text(encoding="utf-8"))
            names = list(t["metadata"]["frozen_test_names"])
            prefix = names[0].split("-t_1-")[0]
            workflow = f"{prefix}-suite"
            app_name = f"bench-{pkg}"
            app_id = t.get("runtime", {}).get("grading", {}).get("app_id", "")
            yamls = suite_files(pkg)
            proj = project_dir(pkg, tmp)
            report: list[str] = []
            missing: list[str] = []

            # --- app ---
            apps = _revyl.app_list(key, proj)
            by_id = {x.get("id"): x for x in apps}
            by_name = {x.get("name"): x for x in apps}
            if app_id and app_id in by_id:
                report.append(f"app {app_id[:8]}… OK ({by_id[app_id].get('name')})")
            elif app_name in by_name:
                found = by_name[app_name]["id"]
                report.append(f"app {app_name} exists as {found[:8]}… but task.toml says {app_id[:8] or '(none)'} — "
                              f"record it: provision/write_task_toml.py {pkg} --grading-app-id {found}")
                app_id = found
                missing.append("app id not recorded")
            else:
                missing.append("app")
                if a.apply:
                    if a.dry_run:
                        report.append(f"WOULD: revyl app create --name {app_name} --platform ios --json")
                        # stand-in for the id `app create` would mint, so the dry run goes on to
                        # preview the test creates and the workflow for a fresh organisation
                        app_id = "<app-id>"
                    else:
                        created = _revyl.app_create(key, proj, app_name)
                        app_id = created.get("id") or created.get("app", {}).get("id")
                        report.append(f"CREATED app {app_name} = {app_id} — record it: "
                                      f"provision/write_task_toml.py {pkg} --grading-app-id {app_id}")
                else:
                    report.append(f"app {app_name} MISSING")

            # --- tests: the ones the workflow lists are the ones the runner can run ---
            have = workflow_tests(key, proj, workflow)
            absent = [n for n in names if n not in (have or [])]
            for n in names:
                if n not in yamls:
                    missing.append(f"suite file for {n}")
                    report.append(f"test {n}: no yaml under grading-side/{pkg}")
            if absent:
                missing.extend(f"test {n}" for n in absent)
                if a.apply and app_id:
                    for n in absent:
                        if n not in yamls:
                            continue
                        dst = proj / f"{n}.yaml"
                        rewrite_yaml(yamls[n], app_name, dst)
                        cmd = ["test", "create", "--from-file", str(dst), "--app", app_id, "--force"]
                        if a.dry_run:
                            report.append(f"WOULD: revyl {' '.join(cmd)}  (build.name={app_name}, pinned_version dropped)")
                        else:
                            _revyl._run(cmd, key=key, chdir=proj, timeout=600)
                            report.append(f"CREATED test {n}")
                else:
                    report.append(f"tests MISSING from {workflow}: {absent}")
            else:
                report.append(f"tests OK ({len(names)} in {workflow})")

            # --- content: the org must grade with the committed text, not a stale draft ---
            if a.content:
                import yaml
                for n in names:
                    if n not in yamls or n not in live:
                        continue          # absence is reported above
                    diff = content_diff(yaml.safe_load(yamls[n].read_text(encoding="utf-8")), live[n][1])
                    if not diff:
                        continue
                    missing.append(f"content of {n}")
                    if a.apply and pull_proj is not None:
                        if a.dry_run:
                            report.append(f"WOULD: rewrite {n} from grading-side and `revyl test push` "
                                          f"(same remote id) — {len(diff)} difference(s): {diff[0]}")
                        else:
                            push_committed_body(key, pull_proj, live[n][0], yamls[n], app_name)
                            report.append(f"PUSHED committed body over {n} ({len(diff)} difference(s) fixed)")
                    else:
                        report.append(f"test {n}: LIVE TEXT DIFFERS from grading-side — " + "; ".join(diff[:3]))
                if all(n in live for n in names if n in yamls):
                    if not any(m.startswith("content of ") for m in missing):
                        report.append(f"content OK ({len(names)} tests match grading-side)")

            # --- workflow ---
            if have is None:
                missing.append("workflow")
                if a.apply:
                    cmd = ["workflow", "create", workflow, "--tests", ",".join(names), "--no-open"]
                    if a.dry_run:
                        report.append(f"WOULD: revyl {' '.join(cmd)}")
                    else:
                        _revyl._run(cmd, key=key, chdir=proj)
                        report.append(f"CREATED workflow {workflow}")
                else:
                    report.append(f"workflow {workflow} MISSING")
            elif absent and a.apply:
                cmd = ["workflow", "add-tests", workflow, *absent]
                if a.dry_run:
                    report.append(f"WOULD: revyl {' '.join(cmd)}")
                else:
                    _revyl._run(cmd, key=key, chdir=proj)
                    report.append(f"ADDED to {workflow}: {absent}")
            else:
                extra = sorted(set(have) - set(names))
                report.append(f"workflow {workflow} OK" + (f" (also lists {extra})" if extra else ""))

            missing_total += len(missing)
            results[pkg] = {"app_id": app_id or "", "workflow": workflow,
                            "missing": list(missing), "report": list(report)}
            flag = "OK " if not missing else "!! "
            print(f"{flag}{pkg}")
            for line in report:
                print(f"     {line}")

    print(f"\n{'all present' if not missing_total else f'{missing_total} item(s) missing'}"
          f"{' (dry run: nothing created)' if a.apply and a.dry_run else ''}")
    return missing_total, results


if __name__ == "__main__":
    sys.exit(main())
