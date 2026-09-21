"""bench.guards — the abort-on-any-failure checks launch_rollout runs before starting a
rollout. Each check returns a (name, ok, detail) triple; the caller aborts
if any ok is False. Nothing here mutates anything.

Why these exact checks (each one is a failure we have already had or can see coming):
  * agent key org == REVYL_AGENT_ORG_ID (.env, carried in spec.agent.org_id) — the agent key
    follows the account's ACTIVE org; if someone switched orgs in the UI the "agent" key
    would suddenly be a different org.
  * agent key sees no s1* workflows — the withheld suite must be unreachable with the agent's key.
  * grading key org == REVYL_GRADING_ORG_ID (spec.grading.org_id) and `workflow info
    <prefix>-suite` lists exactly the 4 frozen tests — grading against a partial suite
    would silently mis-score.
  * dev-client pin exists on the agent dev app — `revyl dev` with a bad pin resolves
    "latest uploaded" (v0.1.63+ trap) → could be nothing / the wrong shell.
  * builder=revyl (default): the grading key can `build list` the grading app (the app the
    remote build will register into) and the recipe renders for this task (ios_scheme +
    template present) — a missing scheme must fail here, not as builder_fault on s1.
    builder=eas (rollback): eas whoami under EXPO_TOKEN — the runner's build step must not
    discover a bad token 35 minutes into the first submission.
  * images present — compose would otherwise try to pull from a registry that doesn't exist.
  * .env has the contestant's key_env — the harness would start and immediately 401.
  * revyl CLI == image/REVYL_CLI_VERSION on the launch machine (guards + teardown use it)
    and inside every image (local transport; the ec2 transport proves it via the AMI
    fingerprint + the Dockerfile-time assertion). The server enforces a minimum CLI
    version and gives an old client no warning; the auth-status call above is what turns
    the NEXT server-side minimum bump into a loud guard failure instead of a mid-rollout one.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from . import eas as _eas
from . import recipes as _recipes
from . import revyl as _revyl
from .config import RolloutSpec

Check = tuple[str, bool, str]


def _docker_image_present(tag: str) -> bool:
    p = subprocess.run(["docker", "image", "inspect", tag], capture_output=True, text=True)
    return p.returncode == 0


def run_all(spec: RolloutSpec, *, grading_key: str, agent_key: str, expo_token: str,
            env: dict[str, str], project_dir: Path, check_images: bool = True,
            need_harness_key: bool = True) -> list[Check]:
    """project_dir: any dir with a .revyl/config.yaml (the seeded workspace) — the CLI needs
    project context for list/info commands."""
    out: list[Check] = []

    # --- revyl CLI pin (launch machine) ---
    have = _revyl.version()
    out.append(("revyl CLI on launch machine == pin", bool(_revyl.PINNED_VERSION) and have == _revyl.PINNED_VERSION,
                f"have {have or 'none'} want {_revyl.PINNED_VERSION or 'MISSING image/REVYL_CLI_VERSION'} ({_revyl.REVYL_BIN})"))

    # --- agent key ---
    try:
        a = _revyl.auth_status(agent_key)
        # spec.agent.org_id is REVYL_AGENT_ORG_ID from .env (config.resolve); a key that
        # resolves elsewhere means the .env pair (key, org id) is inconsistent
        # The detail string is printed by launch_rollout.py and captured into the campaign's
        # launch log, so it carries no e-mail address and only the first 8 characters of each
        # org id: enough to see WHICH organisation a mismatched key resolved to (the name is
        # there too), not enough to identify the account to whoever reads a shared log.
        out.append(("agent key → agent org", a.get("org_id") == spec.agent.org_id,
                    f"org_id={str(a.get('org_id') or '')[:8]}… ({a.get('org_name')}) "
                    f"want {str(spec.agent.org_id)[:8]}…"))
        wfs = _revyl.workflow_list(agent_key, project_dir)
        leaked = [w.get("name") for w in wfs if str(w.get("name", "")).startswith("s1")]
        out.append(("agent key sees no s1* workflows", not leaked, f"visible={leaked or 'none'}"))
        builds = _revyl.build_list(agent_key, project_dir, spec.agent.dev_app_id)
        ids = {b.get("id") or b.get("version_id") for b in builds}
        names = {b.get("version") or b.get("name") for b in builds}
        if spec.agent.technology == "swift":
            # no dev-client on a native task: the agent's own Debug builds (devbuild.sh) land
            # on this app, so the guard is that the app answers under the agent key
            out.append(("agent dev app reachable (native: no dev-client pin)", True,
                        f"{len(builds)} versions on app {spec.agent.dev_app_id[:8]}…"))
        else:
            pinned = spec.agent.devclient_version_id in ids or spec.agent.devclient_version in names
            out.append(("dev-client pin exists on agent dev app", pinned,
                        f"want {spec.agent.devclient_version} ({spec.agent.devclient_version_id[:8]}…); "
                        f"have {sorted(n for n in names if n)}"))
    except Exception as e:  # noqa: BLE001
        out.append(("agent key checks", False, f"exception: {e}"))

    # --- grading key ---
    try:
        g = _revyl.auth_status(grading_key)
        out.append(("grading key → grading org", g.get("org_id") == spec.grading.org_id,
                    f"org_id={str(g.get('org_id') or '')[:8]}… ({g.get('org_name')}) "
                    f"want {str(spec.grading.org_id)[:8]}…"))
        info = _revyl.workflow_info(grading_key, project_dir, spec.grading.workflow)
        have = sorted(t["name"] for t in info.get("tests", []))
        want = sorted(spec.grading.tests.values())
        # A whole-app task declares all four and this is equality. A STEP task
        # declares a PREFIX of the same workflow — it grades the same tests in the same
        # grading app, just fewer of them — so equality would abort every step-1 and
        # step-2 rollout before it started. Subset is the real invariant: every test this
        # task will grade must exist in the workflow.
        ok = set(want) <= set(have)
        label = ("suite has exactly the 4 frozen tests" if len(want) == 4
                 else f"declared {len(want)}-test prefix is present in the suite")
        out.append((label, ok, f"have={have} want={want}"))
    except Exception as e:  # noqa: BLE001
        out.append(("grading key checks", False, f"exception: {e}"))

    # --- builder ---
    if spec.builder == "eas":
        try:
            who = _eas.whoami(expo_token)
            out.append(("eas whoami under EXPO_TOKEN", bool(who), who))
        except Exception as e:  # noqa: BLE001
            out.append(("eas whoami under EXPO_TOKEN", False, str(e)))
    else:
        try:
            builds = _revyl.build_list(grading_key, None, spec.grading.app_id)
            out.append(("grading key can list builds on the grading app (revyl builder)", True,
                        f"{len(builds)} versions on app {spec.grading.app_id[:8]}…"))
        except Exception as e:  # noqa: BLE001
            out.append(("grading key can list builds on the grading app (revyl builder)", False, str(e)))
        try:
            r = _recipes.build_recipe(spec.task, app_id=spec.grading.app_id, scheme=spec.agent.ios_scheme,
                                      technology=spec.agent.technology)
            out.append(("grading recipe renders for this task", True,
                        f"technology={spec.agent.technology} scheme={spec.agent.ios_scheme} {len(r)} bytes "
                        f"from {_recipes.RECIPE_DIR.name}/"))
        except Exception as e:  # noqa: BLE001
            out.append(("grading recipe renders for this task", False, str(e)))

    # --- images (present + baked CLI == pin; the agent/runner both call revyl) ---
    if check_images:
        for role, tag in spec.images.items():
            present = _docker_image_present(tag)
            out.append((f"docker image {role}", present, tag))
            if present:
                p = subprocess.run(["docker", "run", "--rm", "--entrypoint", "revyl", tag, "--version"],
                                   capture_output=True, text=True)
                baked = re.search(r"v\d+\.\d+\.\d+", p.stdout + p.stderr)
                baked_v = baked.group(0) if baked else ""
                out.append((f"revyl CLI in image {role} == pin", baked_v == _revyl.PINNED_VERSION,
                            f"have {baked_v or 'none'} want {_revyl.PINNED_VERSION}"))

    # --- contestant key present (skipped in p0 mode: no harness runs there) ---
    if need_harness_key:
        key_env = spec.contestant["key_env"]
        out.append((f".env has {key_env}", bool(env.get(key_env)), "present" if env.get(key_env) else "MISSING"))
    return out


def format_checks(checks: list[Check]) -> str:
    return "\n".join(f"  [{'OK ' if ok else 'FAIL'}] {name}: {detail}" for name, ok, detail in checks)
