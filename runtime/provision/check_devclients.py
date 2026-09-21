#!/usr/bin/env python3
"""check_devclients.py — refuse a task whose pinned dev-client `revyl dev` would reject.

`revyl dev` requires the build record to carry an Expo dev-client descriptor. Builds
registered with `revyl build upload` do NOT have one; only builds produced by
`revyl build --remote` (i.e. make_devclient.py --builder revyl) do. A task pinned to an
upload-registered dev-client gives its contestant no device loop at all, on every rollout,
and it reads as agent incompetence rather than a provisioning fault.

A pin can also go stale silently: building a good dev-client does not help if task.toml
still names the old version id. This check reads the pin task.toml actually carries and
asks the agent organisation whether THAT build has the metadata.

    python3 runtime/provision/check_devclients.py            # all tasks
    python3 runtime/provision/check_devclients.py s1-kanban-0001

Needs REVYL_AGENT_API_KEY (runtime/.env) — it reads the build list from the agent org.
Read-only: it lists builds and changes nothing.

THE FIELD PATH MATTERS. It is

    versions[].metadata.artifact_metadata.expo_dev_client

not `versions[].metadata.expo_dev_client`. Reading it one level too shallow reports MISSING
for a build that opens a live dev session perfectly well.
"""
from __future__ import annotations

import sys
import tomllib
from pathlib import Path

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
BENCH_ROOT = RUNTIME_ROOT.parent
sys.path.insert(0, str(RUNTIME_ROOT))

from bench import revyl as _revyl          # noqa: E402
from launch_rollout import load_dotenv      # noqa: E402  (same reader make_devclient uses)


def dev_client_descriptor(version: dict) -> dict | None:
    """The Expo dev-client descriptor `revyl dev` looks for, or None."""
    md = version.get("metadata") or {}
    return ((md.get("artifact_metadata") or {}).get("expo_dev_client")) or None


def main() -> int:
    env = load_dotenv()
    # .get, not env[...]: on a fresh clone there is no runtime/.env yet, and a bare KeyError
    # traceback tells the user nothing about which file to create.
    key = env.get("REVYL_AGENT_API_KEY")
    if not key:
        print("check_devclients: REVYL_AGENT_API_KEY is not set — copy runtime/.env.example to "
              "runtime/.env and fill it in (see docs/organizations.md)", file=sys.stderr)
        return 2
    pkgs = sys.argv[1:] or sorted(
        p.parent.name for p in (BENCH_ROOT / "tasks").glob("*/task.toml"))

    bad = []
    for pkg in pkgs:
        toml = BENCH_ROOT / "tasks" / pkg / "task.toml"
        agent = tomllib.loads(toml.read_text(encoding="utf-8")).get("runtime", {}).get("agent")
        if not agent:
            print(f"  {pkg:<26} skipped (not provisioned)")
            continue
        want = agent["devclient_version_id"]
        scaffold = RUNTIME_ROOT / agent["scaffold"]
        versions = _revyl.build_list(key, scaffold, agent["dev_app_id"])
        hit = next((v for v in versions
                    if (v.get("id") or v.get("version_id")) == want), None)
        if hit is None:
            bad.append(f"{pkg}: pinned dev-client {want} not found in app {agent['dev_app_id']}")
            print(f"  {pkg:<26} NOT FOUND {want}")
            continue
        desc = dev_client_descriptor(hit)
        source = (hit.get("metadata") or {}).get("source")
        if desc:
            print(f"  {pkg:<26} OK   {hit.get('version')} (scheme={desc.get('scheme')}, source={source})")
        else:
            bad.append(f"{pkg}: {hit.get('version')} has no expo_dev_client descriptor "
                       f"(source={source}) — `revyl dev` will refuse it")
            print(f"  {pkg:<26} REFUSED BY `revyl dev`: {hit.get('version')} (source={source})")

    if bad:
        print(f"\n{len(bad)} task(s) cannot give a contestant a device loop:")
        for b in bad:
            print("   -", b)
        print("\nrebuild through Revyl and re-pin:")
        print("  python3 runtime/provision/make_devclient.py <pkg> --builder revyl --version-n <next N>")
        print("  python3 runtime/provision/write_task_toml.py <pkg> --devclient-version-id <new id> \\")
        print("          --devclient-version bench-<pkg>-devclient-v<N>")
        return 1
    print("\nevery provisioned task is pinned to a dev-client `revyl dev` accepts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
