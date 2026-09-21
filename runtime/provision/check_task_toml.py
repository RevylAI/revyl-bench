#!/usr/bin/env python3
"""check_task_toml.py — refuse a task.toml that has lost its launch blocks.

launch_rollout.py cannot resolve a task without [runtime.grading] and [runtime.agent].
Those blocks are appended by write_task_toml.py at the END of the file, which makes them
easy to destroy: any edit that rewrites "from section X to end of file" takes them with it.
A package can lose them that way while its last rollouts are green, and nothing else
notices until the next launch fails.

A task is considered PROVISIONED if grading-side/<pkg>/ exists (it has been through
provisioning). Unprovisioned packages are allowed to have no runtime blocks.
"""
import sys, tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
# No org_id: the organisations come from runtime/.env at launch (bench.config.ORG_ENV),
# never from the package.
REQUIRED = {
    "grading": ("app_id", "workflow"),
    "agent": ("dev_app_id", "scaffold", "base_commit", "ios_scheme"),
}
# an Expo task also pins the dev-client its runbook hot-reloads into; a native task
# (technology = "swift") has none
EXPO_AGENT_KEYS = ("devclient_version_id", "devclient_version", "expo_sdk")

def main() -> int:
    bad = []
    for toml in sorted((ROOT / "tasks").glob("*/task.toml")):
        pkg = toml.parent.name
        provisioned = (ROOT / "grading-side" / pkg).is_dir()
        rt = tomllib.load(toml.open("rb")).get("runtime", {})
        if not provisioned:
            print(f"  {pkg:<24} skipped (not provisioned)")
            continue
        missing = [
            f"[runtime.{blk}].{key}"
            for blk, keys in REQUIRED.items()
            for key in keys
            if key not in rt.get(blk, {})
        ]
        if rt.get("agent", {}).get("technology", "expo") == "expo":
            missing += [f"[runtime.agent].{k}" for k in EXPO_AGENT_KEYS if k not in rt.get("agent", {})]
        if missing:
            bad.append((pkg, missing))
            print(f"  {pkg:<24} MISSING {', '.join(missing)}")
        else:
            print(f"  {pkg:<24} OK")
    if bad:
        print(f"\n{len(bad)} provisioned task(s) cannot be launched — restore the "
              f"[runtime.*] blocks (they live at the END of task.toml).")
        return 1
    print("\nall provisioned tasks carry launchable [runtime.*] blocks")
    return 0

if __name__ == "__main__":
    sys.exit(main())
