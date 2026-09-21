#!/usr/bin/env python3
"""provision/make_devclient.py <pkg> — Stage 0 step 2: the agent-org dev app
+ the ONE dev-client build every rollout of this task pins for `revyl dev`.

USE THE DEFAULT `--builder revyl`. The `--builder eas` path is kept only as a fallback and
it produces a dev-client `revyl dev` REFUSES: `revyl build upload` (both --url and --file,
CLI 0.1.95 and 0.1.96) does not record `metadata.expo_dev_client`, and `revyl dev` rejects
any build without it — "selected build does not contain Expo dev-client metadata". A task
provisioned that way runs BLIND, with no device loop, and it reads as agent incompetence
rather than as a provisioning fault. Letting Revyl build the dev-client is what records
the metadata.

That is only the FIRST of two gates. The second is the scaffold's own .revyl/config.yaml:
`revyl dev` refuses a config with no `build.profiles`, even under --no-build, which is why
recipes.scaffold_config() emits a stub profile. A scaffold without the stub has no
device loop regardless of how good its dev-client is.

ALWAYS verify before launching any rollout of a new task (checks BOTH gates at once):
    cd runtime/scaffolds/<pkg>
    REVYL_API_KEY=$AGENT_KEY revyl dev --platform ios --no-build --build-version-id <id>

Under REVYL_AGENT_API_KEY (from ./.env):
  1. `revyl app create --name bench-<pkg>-dev --platform ios --json`   → dev_app_id
     (idempotent: reuses an existing app of that name)
  2. `eas build --platform ios --profile development-simulator` from scaffolds/<pkg>
     (~8–12 min; runs under this machine's `eas login` unless EXPO_TOKEN is in .env)
  3. `revyl build upload --url <artifact> --app <dev_app_id> --platform ios
      --version bench-<pkg>-devclient-v<N>`                          → devclient_version_id
     (this one IS set current — the dev app's current build should be the dev-client)
Prints the ids as JSON and, with --write-toml, appends the [grading]/[agent] blocks to the
task's task.toml via write_task_toml.py.

Why the dev-client is per TASK, not per rollout: it is only the Expo dev launcher shell
+ the scaffold's native modules; every rollout's JS is served by its own Metro through the
Revyl relay. `N` bumps only when the scaffold's native dependency set changes.
"""
from __future__ import annotations

import sys as _sys
# Windows consoles default to cp1252; our logs contain arrows/dashes → force UTF-8 so a
# print() never crashes a provisioning step half-way.
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bench import eas as _eas   # noqa: E402
from bench import revyl as _revyl  # noqa: E402
from bench.config import ORG_ENV, RUNTIME_ROOT  # noqa: E402
from launch_rollout import load_dotenv  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pkg")
    ap.add_argument("--version-n", type=int, default=1, help="dev-client version suffix N (bump on native dep change)")
    ap.add_argument("--builder", choices=("revyl", "eas"), default="revyl",
                    help="revyl = let Revyl build it so metadata.expo_dev_client is "
                         "recorded (required by `revyl dev`); eas = the old "
                         "EAS-build + upload path, which produces a dev-client "
                         "`revyl dev` REFUSES")
    ap.add_argument("--artifact-url", help="skip the EAS build and register this artifact url")
    ap.add_argument("--build-id", help="resume: poll this EAS build id instead of queueing a new one")
    ap.add_argument("--write-toml", action="store_true")
    ap.add_argument("--grading-app-id", help="needed with --write-toml")
    ap.add_argument("--base-commit", help="needed with --write-toml")
    ap.add_argument("--sdk", type=int, help="needed with --write-toml (expo)")
    ap.add_argument("--technology", choices=("expo", "swift"), default="expo",
                    help="swift = a native scaffold: create the dev app the agent's own "
                         "development builds (devbuild.sh) go to, build NO dev-client "
                         "(there is no hot reload to pin), write the toml with technology")
    a = ap.parse_args()

    # Fail on the arg combination BEFORE the ~10-45 min build, not after it: the old code
    # only checked inside the --write-toml branch at the very end.
    native = a.technology != "expo"
    if a.write_toml and not (a.grading_app_id and a.base_commit and (native or a.sdk)):
        raise SystemExit("--write-toml needs --grading-app-id --base-commit" + ("" if native else " --sdk"))

    env = load_dotenv()
    key = env["REVYL_AGENT_API_KEY"]
    token = env.get("EXPO_TOKEN", "")
    scaffold = RUNTIME_ROOT / "scaffolds" / a.pkg
    if not (scaffold / ".revyl" / "config.yaml").exists():
        raise SystemExit(f"scaffold missing at {scaffold}")

    # The agent org id comes from .env beside the key (docs/organizations.md); a dev client
    # registered on the wrong org would be invisible to every rollout's `revyl dev` pin.
    agent_org = env.get(ORG_ENV["agent"], "")
    if not agent_org:
        raise SystemExit(f".env lacks {ORG_ENV['agent']} (see docs/organizations.md)")
    st = _revyl.auth_status(key)
    if st.get("org_id") != agent_org:
        raise SystemExit(f"REVYL_AGENT_API_KEY resolves to org {st.get('org_id')} != agent org {agent_org}")
    print(f"[auth] agent org OK ({st.get('org_name')})")

    # 1. dev app
    name = f"bench-{a.pkg}-dev"
    apps = _revyl.app_list(key, scaffold)
    existing = [x for x in apps if x.get("name") == name]
    if existing:
        dev_app_id = existing[0]["id"]
        print(f"[app] reuse {name} = {dev_app_id}")
    else:
        d = _revyl.app_create(key, scaffold, name, "ios")
        dev_app_id = d.get("id") or d.get("app_id") or (d.get("app") or {}).get("id")
        if not dev_app_id:
            raise SystemExit(f"could not parse app id from {json.dumps(d)[:300]}")
        print(f"[app] created {name} = {dev_app_id}")

    # 2. dev-client build
    version = f"bench-{a.pkg}-devclient-v{a.version_n}"
    if native:
        # nothing to build: a native episode has no dev-client, the agent queues its own
        # Debug builds on this app through devbuild.sh
        version, vid, art = "", "", None
        print("[build] native scaffold: no dev-client (the agent builds through devbuild.sh)")
    elif a.builder == "revyl":
        # `revyl build upload` does NOT record
        # metadata.expo_dev_client on CLI 0.1.96, and `revyl dev` refuses any build without
        # it — so an EAS-built, upload-registered dev-client leaves the agent with no device
        # loop at all. Letting Revyl build it is what records the metadata.
        # The recipe is rendered from bench/recipes.py as the development/Debug profile:
        # Debug is what boots the dev-client launcher rather than baked JS.
        import json as _json
        from bench import recipes as _recipes
        app = _json.loads((scaffold / "app.json").read_text(encoding="utf-8"))
        recipe = _recipes.build_recipe(a.pkg, app_id=dev_app_id,
                                       scheme=_recipes.ios_scheme(app["expo"]["name"]),
                                       profile="development", configuration="Debug")
        cfg = scaffold / ".revyl" / "config.yaml"
        prev = cfg.read_text(encoding="utf-8")
        cfg.write_text(recipe, encoding="utf-8")
        try:
            res = _revyl.build_remote(key, scaffold, profile="development",
                                      version=version, timeout_s=2700)
            vid = res.get("version_id") or res.get("build_version_id")
            if not vid:
                raise SystemExit(f"remote dev-client build did not return a version_id: "
                                 f"{ {k: v for k, v in res.items() if k != 'log_tail'} }\n"
                                 f"{str(res.get('log_tail'))[-1200:]}")
        finally:
            # the scaffold's committed config is part of base_commit — never leave the
            # grading recipe behind (that would silently repin every rollout of this task)
            cfg.write_text(prev, encoding="utf-8")
        # Revyl built AND registered it, so there is no external artifact to upload and no
        # step 3. Fall through to the shared tail anyway: the sidecar json and --write-toml
        # are what setup_orgs.py and launch_rollout.py depend on, and returning here made the
        # DEFAULT builder the one path that silently wrote neither.
        art = None
    elif a.artifact_url:
        art = a.artifact_url
    else:
        if a.build_id:
            eb = _eas.wait_build(a.build_id, token=token)
        else:
            eb = _eas.build(scaffold, profile="development-simulator", token=token)
        if eb.status != "FINISHED" or not eb.artifact_url:
            raise SystemExit(f"dev-client build {eb.build_id} {eb.status}: {eb.error_tail}")
        art = eb.artifact_url
        print(f"[eas] artifact {art}")

    # 3. register (idempotent on name: if it already exists, look it up). Skipped for
    #    --builder revyl, which registered the build as part of building it.
    if a.builder != "revyl" and not native:
        have = [b for b in _revyl.build_list(key, scaffold, dev_app_id)
                if (b.get("version") or b.get("name")) == version]
        if have:
            vid = have[0].get("id") or have[0].get("version_id")
            print(f"[revyl] {version} already registered = {vid}")
        else:
            vid = _revyl.build_upload_url(key, scaffold, url=art, app_id=dev_app_id, version=version,
                                          set_current=True)
            print(f"[revyl] registered {version} = {vid}")

    result = {"pkg": a.pkg, "dev_app_id": dev_app_id, "devclient_version": version,
              "devclient_version_id": vid, "builder": a.builder, "artifact_url": art}
    print(json.dumps(result, indent=2))
    (RUNTIME_ROOT / "scaffolds" / f"{a.pkg}.devclient.json").write_text(json.dumps(result, indent=2) + "\n",
                                                                       encoding="utf-8")
    if a.write_toml:
        from provision.write_task_toml import write_blocks
        write_blocks(a.pkg, grading_app_id=a.grading_app_id, dev_app_id=dev_app_id,
                     devclient_version_id=vid, devclient_version=version,
                     base_commit=a.base_commit, sdk=a.sdk or 0, technology=a.technology)
    return 0


if __name__ == "__main__":
    sys.exit(main())
