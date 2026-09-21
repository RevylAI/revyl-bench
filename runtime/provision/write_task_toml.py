#!/usr/bin/env python3
"""provision/write_task_toml.py — Stage 0 step 3: append/replace the
[runtime.grading] and [runtime.agent] blocks in revyl-bench/tasks/<pkg>/task.toml, and drop EXPO_TOKEN
from [environment].env (the agent never builds).

    python provision/write_task_toml.py s1-ride-booking-0001 --grading-app-id <id> \
        --dev-app-id <id> --devclient-version-id <id> --devclient-version bench-…-devclient-v1 \
        --base-commit <sha> --sdk 57  (tables are namespaced under [runtime] because the Harbor schema already claims [agent])

Textual edit on purpose (no TOML writer in the stdlib; round-tripping comments matters —
the task.toml carries the provenance narrative). Idempotent: an existing block is replaced.
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
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bench.config import BENCH_ROOT, RUNTIME_ROOT  # noqa: E402
from bench.recipes import TECHNOLOGIES, ios_scheme as _ios_scheme  # noqa: E402

BLOCK_RE = re.compile(r"(?ms)^# --- revyl-bench-runtime provisioning \(auto-written\) ---\n.*?^# --- end runtime provisioning ---\n?")


def scheme_for(pkg: str, technology: str = "expo") -> str:
    """The Xcode scheme the grading recipe names. Expo: `sanitizedName(app.json expo.name)`,
    the scheme/workspace `expo prebuild` will generate on the Revyl build runner — recorded
    here so the runner renders `-workspace <scheme>.xcworkspace -scheme <scheme>` without
    ever running prebuild itself. Swift: the xcodegen target, i.e. `name:` in project.yml
    (make_swift_scaffold.py writes both from --app-name)."""
    sc = RUNTIME_ROOT / "scaffolds" / pkg
    if technology == "swift":
        m = re.search(r"(?m)^name:\s*([A-Za-z][A-Za-z0-9]*)\s*$", (sc / "project.yml").read_text(encoding="utf-8"))
        if not m or not (sc / f"{m.group(1)}.xcodeproj").is_dir():
            raise SystemExit(f"{sc}/project.yml has no `name:` with a matching .xcodeproj")
        return m.group(1)
    app = json.loads((sc / "app.json").read_text(encoding="utf-8"))
    return _ios_scheme(app["expo"]["name"])


def render_blocks(*, prefix: str, grading_app_id: str, dev_app_id: str, devclient_version_id: str,
                  devclient_version: str, pkg: str, base_commit: str, sdk: int, ios_scheme: str,
                  technology: str = "expo") -> str:
    # No org ids here: the organisations a deployment runs against are
    # named by runtime/.env (REVYL_GRADING_ORG_ID / REVYL_AGENT_ORG_ID), so another
    # deployment re-provisions these ids in its own orgs without touching the package.
    if technology not in TECHNOLOGIES:
        raise SystemExit(f"technology must be one of {TECHNOLOGIES}, got {technology!r}")
    # an Expo task pins the dev-client and the SDK; a native task has neither (the agent
    # builds Debug versions itself through devbuild.sh) and says so with `technology`
    tech_lines = (f'expo_sdk = {sdk}\n' if technology == "expo"
                  else f'technology = "{technology}"\n')
    return f"""# --- revyl-bench-runtime provisioning (auto-written) ---
# Ids minted by provisioning (docs/organizations.md): the grading app and suite workflow
# in the grading organisation, the dev app and dev-client pin in the agent organisation.
# NOT secret — only the keys are. The organisations themselves are named by the launch
# environment (REVYL_GRADING_ORG_ID / REVYL_AGENT_ORG_ID in runtime/.env), not here.
[runtime.grading]
app_id = "{grading_app_id}"
workflow = "{prefix}-suite"

[runtime.agent]
dev_app_id = "{dev_app_id}"
devclient_version_id = "{devclient_version_id}"
devclient_version = "{devclient_version}"
scaffold = "scaffolds/{pkg}"
base_commit = "{base_commit}"
{tech_lines}ios_scheme = "{ios_scheme}"
# --- end runtime provisioning ---
"""


def existing_runtime(pkg: str) -> dict[str, str]:
    """The [runtime.grading]/[runtime.agent] values already in task.toml (flat: key -> value),
    so a re-finalize (new base_commit) does not have to be re-told every app/version id."""
    import tomllib
    t = tomllib.loads((BENCH_ROOT / "tasks" / pkg / "task.toml").read_text(encoding="utf-8"))
    rt = t.get("runtime", {})
    out: dict[str, str] = {}
    out.update({k: str(v) for k, v in rt.get("grading", {}).items()})
    out.update({k: str(v) for k, v in rt.get("agent", {}).items()})
    return out


def write_blocks(pkg: str, *, grading_app_id: str, dev_app_id: str, devclient_version_id: str,
                 devclient_version: str, base_commit: str, sdk: int, technology: str = "expo") -> Path:
    p = BENCH_ROOT / "tasks" / pkg / "task.toml"
    s = p.read_text(encoding="utf-8")
    ios_scheme = scheme_for(pkg, technology)
    m = re.search(r'frozen_test_names\s*=\s*\[\s*"([^"]+)"', s)
    if not m:
        raise SystemExit("task.toml has no frozen_test_names")
    prefix = m.group(1).split("-t_1-")[0]
    block = render_blocks(prefix=prefix, grading_app_id=grading_app_id, dev_app_id=dev_app_id,
                          devclient_version_id=devclient_version_id, devclient_version=devclient_version,
                          pkg=pkg, base_commit=base_commit, sdk=sdk, ios_scheme=ios_scheme,
                          technology=technology)
    if BLOCK_RE.search(s):
        # Anything a human put INSIDE the auto-written region is about to be destroyed.
        # It has happened to a [metadata.*] table:
        # placed just after the marker, it looked like it was before [runtime.grading] and
        # was silently replaced along with the block. Refuse instead of eating it.
        managed = BLOCK_RE.search(s).group(0)
        strays = [ln for ln in managed.splitlines()
                  if ln.startswith("[") and not ln.startswith("[runtime.")]
        if strays:
            raise SystemExit(
                f"{p}: the auto-written region contains non-runtime table(s) "
                f"{strays} — they would be destroyed. Move them ABOVE the line\n"
                f"  # --- revyl-bench-runtime provisioning (auto-written) ---\n"
                f"and re-run.")
        s = BLOCK_RE.sub(lambda _: block, s)
    else:
        s = s.rstrip("\n") + "\n\n" + block
    # the agent container never gets EXPO_TOKEN (runner builds from source)
    s = re.sub(r'env = \{ REVYL_API_KEY = "\$\{REVYL_API_KEY\}", EXPO_TOKEN = "\$\{EXPO_TOKEN\}" \}',
               'env = { REVYL_API_KEY = "${REVYL_API_KEY}" }   # agent-org key only; builds run in the runner',
               s)
    p.write_text(s, encoding="utf-8", newline="\n")
    print(f"[task.toml] wrote [grading]/[agent] → {p} (technology={technology} base_commit={base_commit[:12]} ios_scheme={ios_scheme})")
    return p


def set_runtime_values(path: Path, table: str, values: dict[str, str]) -> bool:
    """Set `key = "value"` lines inside one `[runtime.<table>]` table of a task.toml, in
    place, leaving every other byte alone. Returns True when the file changed.

    Why this exists beside write_blocks: write_blocks REGENERATES the whole auto-written
    region of a PARENT package and needs every id at once. Two callers have less than that:
      * a second deployment setting up ONE organisation at a time (setup_orgs.py) knows the
        grading app id or the dev-client ids, never both in the same run — the two org keys
        are deliberately not held by one process;
      * step packages (tasks-step/<pkg>-step<n>/task.toml) carry plain [runtime.grading] /
        [runtime.agent] tables copied from the parent by make_step_tasks.py, with no marker
        comments, and their `scaffold` / `base_commit` lines are per-step and must survive.
    So this edits only the named keys. A key that is absent from the table is appended to
    it. A table that is absent is CREATED: an exported repository ships every task.toml
    with [runtime.grading] removed (its ids name apps in the exporting deployment's
    organisations), so for a second deployment the missing table is the normal starting
    state, not a malformed package. It is placed where write_blocks would have put it:
    [runtime.grading] directly before [runtime.agent], anything else before the
    end-of-region marker, or at the end of the file.

    Textual for the same reason as the rest of this module: no TOML writer in the stdlib,
    and the comments in these files are the provenance narrative."""
    s = path.read_text(encoding="utf-8")
    # the table runs from its header to the next table header, the end-of-region marker,
    # or the end of the file — whichever comes first
    m = re.search(rf"(?ms)^\[runtime\.{re.escape(table)}\][ \t]*\n(.*?)(?=^\[|^# --- end runtime provisioning ---|\Z)", s)
    if not m:
        header = f"[runtime.{table}]\n"
        agent = re.search(r"(?m)^\[runtime\.agent\][ \t]*\n", s)
        end = re.search(r"(?m)^# --- end runtime provisioning ---", s)
        if table == "grading" and agent:
            at, block = agent.start(), header + "\n"       # blank line between the two tables
        elif end:
            at, block = end.start(), header
        else:
            at, block = len(s), ("" if s.endswith("\n\n") else "\n" if s.endswith("\n") else "\n\n") + header
        s = s[:at] + block + s[at:]
        m = re.search(rf"(?ms)^\[runtime\.{re.escape(table)}\][ \t]*\n(.*?)(?=^\[|^# --- end runtime provisioning ---|\Z)", s)
    body = m.group(1)
    for k, v in values.items():
        line = f'{k} = "{v}"'
        if re.search(rf"(?m)^{re.escape(k)}\s*=.*$", body):
            # lambda: the id is data, not a regex template (a backslash or \g in it must not expand)
            body = re.sub(rf"(?m)^{re.escape(k)}\s*=.*$", lambda _m, line=line: line, body, count=1)
        else:
            # append after the table's last line, and put back the blank line that separated
            # this table from the next one (rstrip removed it)
            stripped = body.rstrip("\n")
            # a table this call just created has a body of exactly one blank line (the
            # separator before the next table): that gap must survive as well
            had_gap = body.endswith("\n\n") or body == "\n"
            body = (stripped + "\n" if stripped else "") + line + "\n" + ("\n" if had_gap else "")
    new = s[:m.start(1)] + body + s[m.end(1):]
    if new == path.read_text(encoding="utf-8"):
        return False
    path.write_text(new, encoding="utf-8", newline="\n")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pkg")
    # Every id is optional: when omitted it is read back from the existing [runtime.*] blocks
    # (re-finalize flow: a scaffold re-commit -> `write_task_toml.py <pkg> --base-commit <sha>`).
    ap.add_argument("--grading-app-id")
    ap.add_argument("--dev-app-id")
    ap.add_argument("--devclient-version-id")
    ap.add_argument("--devclient-version")
    ap.add_argument("--base-commit")
    ap.add_argument("--sdk", type=int)
    ap.add_argument("--technology", choices=TECHNOLOGIES, help="default: the existing block's, else expo")
    a = ap.parse_args()
    have = existing_runtime(a.pkg)
    technology = a.technology or have.get("technology") or "expo"

    def pick(flag: str, key: str, default: str | None = None) -> str:
        v = getattr(a, flag)
        if v is None:
            v = have.get(key, default)
        if v is None:
            raise SystemExit(f"--{flag.replace('_', '-')} not given and task.toml has no [runtime.*] {key}")
        return str(v)

    native = technology != "expo"
    write_blocks(a.pkg, grading_app_id=pick("grading_app_id", "app_id"), dev_app_id=pick("dev_app_id", "dev_app_id"),
                 devclient_version_id=pick("devclient_version_id", "devclient_version_id", "" if native else None),
                 devclient_version=pick("devclient_version", "devclient_version", "" if native else None),
                 base_commit=pick("base_commit", "base_commit"), sdk=int(pick("sdk", "expo_sdk", "0" if native else None)),
                 technology=technology)
    return 0


if __name__ == "__main__":
    sys.exit(main())
