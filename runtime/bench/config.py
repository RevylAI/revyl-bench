"""bench.config — resolve a rollout: task.toml + contestants/registry.yaml → RolloutSpec.

Covers file role, naming, and the contestant registry. This module is imported by BOTH
launch_rollout.py (launch machine) and runner/ (inside the runner container, where it reads the
already-rendered rollout.json instead of the repos), so it must stay dependency-free
beyond the stdlib + PyYAML.

Three sources of truth, never merged in place:
  * revyl-bench/tasks/<pkg>/task.toml  — the task package (public + our [grading]/[agent]
    blocks written by the provisioning tooling). Names the grading app/workflow, the
    agent-org dev app + dev-client pin, the scaffold + base_commit.
  * contestants/registry.yaml           — the contestant (model × harness × config).
  * the launch environment (.env)       — which two organisations this deployment runs
    against (ORG_ENV below); the keys live beside them.
The RolloutSpec is the JOIN of the three plus caps and a freshly minted rollout_id; it is
dumped verbatim to /rollouts/<id>/rollout.json and copied into every attempts.jsonl
record so a scored row never depends on this code again.
"""
from __future__ import annotations

import dataclasses
import json
import os
import re
import secrets
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from bench.recipes import TECHNOLOGIES

# ---------------------------------------------------------------------------------------
# Repo locations. The runtime lives INSIDE the repository as the runtime/ subdirectory,
# so RUNTIME_ROOT is <repo>/runtime and the bench root (tasks/, docs/) is simply its
# parent. Override
# with REVYL_BENCH_DIR when the layout differs (e.g. on an EC2 host in v2 where only the
# task package is shipped).
# ---------------------------------------------------------------------------------------
RUNTIME_ROOT = Path(__file__).resolve().parent.parent
BENCH_ROOT = Path(os.environ.get("REVYL_BENCH_DIR", RUNTIME_ROOT.parent))
REGISTRY_PATH = RUNTIME_ROOT / "contestants" / "registry.yaml"

# The two Revyl organisations a deployment runs against (docs/organizations.md):
#   grading org — holds the hidden suites and the per-task grading app; builds and grades
#                 every submission; its key never enters the agent container.
#   agent org   — the dev loop: dev-client builds and the device sessions the agent drives;
#                 the only key the agent holds.
# Their ids are NOT secret (only the keys are). They used to be constants here, which
# pinned the whole runtime to one deployment; since 2026-09-05 they come from the launch
# environment (runtime/.env, loaded by launch_rollout.load_dotenv) so a second deployment —
# another deployment's own pair of organisations — needs no code change. guards.py still asserts
# "the key I was handed really is the org I was told", now against these values; a key
# that resolves to another org fails loudly before anything starts, which is the point.
ORG_ENV = {"grading": "REVYL_GRADING_ORG_ID", "agent": "REVYL_AGENT_ORG_ID"}


def org_ids(env: "Mapping[str, str] | None" = None) -> tuple[str, str]:
    """(grading_org_id, agent_org_id) from `env` (default: os.environ). Raises ValueError
    naming the missing variable — a rollout resolved without them would carry empty org
    ids into rollout.json and every guard would compare against ""."""
    src = os.environ if env is None else env
    missing = [v for v in ORG_ENV.values() if not src.get(v)]
    if missing:
        raise ValueError(f"{', '.join(missing)} not set — add the organisation ids to runtime/.env "
                         f"(see docs/organizations.md)")
    return src[ORG_ENV["grading"]], src[ORG_ENV["agent"]]

# The four logical slots of every suite. Frozen test names look like
# `<prefix>-t_1-tabs`, `<prefix>-t_2-…`, `<prefix>-t_3-…`, `<prefix>-final-e2e`;
# verdict vectors are keyed by these slots, never by the full names, so scoring code
# is task-agnostic.
SLOTS = ("t_1", "t_2", "t_3", "final")


@dataclass
class GradingSide:
    org_id: str
    app_id: str            # grading-org app the submission build is uploaded to
    workflow: str          # `<prefix>-suite` (kept for `workflow run`; v1 grades via 4× `test run`)
    tests: dict[str, str]  # slot → frozen test name, e.g. {"t_1": "s1rb-t_1-tabs", ...}
    # slot → exact substrings that must appear in the app's log output for that suite
    # (runner/observability.py). Public on purpose: the contract tells the agent which
    # lines to emit; this is the enforcement, not a secret. Empty for classic tasks.
    log_assertions: dict[str, list[str]] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.log_assertions is None:
            self.log_assertions = {}


# native (swift) episode budget, calibrated before use
SWIFT_MAX_SUBMISSIONS = 3
SWIFT_MAX_DEV_BUILDS = 8
# the agent image tag a native task launches in (see resolve(): images)
NATIVE_IMAGE_SDK = 57


@dataclass
class AgentSide:
    org_id: str
    dev_app_id: str
    devclient_version_id: str   # the mandatory `revyl dev --no-build --build-version-id` pin
    devclient_version: str      # human name, e.g. bench-s1-ride-booking-0001-devclient-v1
    scaffold: str               # path relative to the runtime repo, e.g. scaffolds/s1-ride-booking-0001
    base_commit: str            # the scaffold commit every rollout of this task starts from
    expo_sdk: int
    # sanitizedName(app.json expo.name) = the Xcode scheme `expo prebuild` generates; the
    # runner's remote-build recipe needs it (bench/recipes.py). "" only in pre-2026-08-26
    # rollout.json files (EAS builder era), never for a revyl-builder rollout (resolve() asserts).
    ios_scheme: str = ""
    # "expo" (create-expo-app scaffold, dev-client hot reload, expo_sdk set) or "swift"
    # (native SwiftUI scaffold from the scaffold generator: no dev-client, the
    # agent iterates by remote Debug builds through devbuild.sh, expo_sdk is 0). Chooses the
    # grading recipe (bench/recipes.py), the runbook and the caps. Absent in every
    # task.toml written before 2026-09-19 → "expo".
    technology: str = "expo"


@dataclass
class Caps:
    max_submissions: int = 5
    # native (swift) episodes only: remote Debug builds the agent may queue through
    # devbuild.sh; an Expo episode hot-reloads and never builds
    max_dev_builds: int = 0
    wall_clock_min: int = 480
    # a single grade (build + suite) may not exceed this — protects the wall clock from a
    # hung EAS build; the verdict becomes failure_kind=timeout (tooling, quarantined)
    grade_timeout_min: int = 60
    # Old serialized rollouts retain submission-only behavior.
    final_evaluation: bool = False


@dataclass
class RolloutSpec:
    rollout_id: str
    task: str                     # package name, e.g. s1-ride-booking-0001
    prefix: str                   # test prefix, e.g. s1rb
    seed: int
    protocol_version: int
    contestant_slug: str
    contestant: dict[str, Any]    # the FULL registry entry (self-describing rows)
    grading: GradingSide
    agent: AgentSide
    caps: Caps
    transport: str = "local"
    images: dict[str, str] = field(default_factory=dict)   # {"agent": tag, "runner": tag}
    created_at: str = ""
    # The CONTRACT generation this rollout was graded against. Without it, score_v0 has no
    # way to tell a v1-contract run from a v2-contract run of the same task and silently
    # averages them into a number that describes neither: an "n=2 macro" that is one run
    # against contract v1 averaged with one run against contract v2. Defaults to 0 for
    # legacy runs recorded before this field existed; score_v0 refuses to aggregate those.
    task_version: int = 0
    # Who builds the submission: "revyl" = the runner writes the image-owned recipe over
    # the tree and runs `revyl build --remote` (default since 2026-08-26); "eas" = the
    # earlier `eas build --profile preview` + `build upload` path, kept as a rollback and
    # A-B switch.
    builder: str = "revyl"
    # train/test tag, deterministic from rollout_id (bench.split). A real field, not a
    # post-dump annotation: RolloutSpec.load() drops unknown keys, so anything less never
    # reaches the runner's attempt records.
    split: str = ""

    # ---- serialization -------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def dump(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @staticmethod
    def load(path: Path) -> "RolloutSpec":
        """Inverse of dump(). Used by the runner, which never sees task.toml/registry."""
        d = json.loads(path.read_text(encoding="utf-8"))
        return RolloutSpec(
            rollout_id=d["rollout_id"], task=d["task"], prefix=d["prefix"], seed=d["seed"],
            protocol_version=d["protocol_version"], contestant_slug=d["contestant_slug"],
            contestant=d["contestant"],
            grading=GradingSide(**d["grading"]), agent=AgentSide(**d["agent"]),
            caps=Caps(**d["caps"]), transport=d.get("transport", "local"),
            images=d.get("images", {}), created_at=d.get("created_at", ""),
            task_version=int(d.get("task_version", 0)),
            # rollout.json files written before the field existed were all EAS-built
            builder=d.get("builder", "eas"),
            split=d.get("split", ""),
        )

    # ---- naming helpers — the ONLY place these formats live --------------------
    def build_version(self, k: int) -> str:
        """Grading-org build version for submission k. Globally unique forever because the
        rollout_id carries task prefix + contestant + seed + 8 random hex; Revyl requires
        org-unique version names and we never reuse a name for different JS."""
        return f"{self.rollout_id}-s{k}"


# ---------------------------------------------------------------------------------------
# loaders
# ---------------------------------------------------------------------------------------
def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    # yaml imported HERE, not at module top: only the launch-side resolve path reads the
    # registry. Some importers want this module for BENCH_ROOT alone, and a machine that
    # only reads collected episodes must not need PyYAML — the module's "stdlib + PyYAML"
    # dependency contract applies to resolve(), not to import.
    import yaml
    return yaml.safe_load(path.read_text(encoding="utf-8"))


TASK_ROOTS = ("tasks", "tasks-step", "tasks-repair")


def task_technology(task: str) -> str:
    """[runtime.agent] technology of a task package ("expo" when the key is absent)."""
    t = load_task_toml(task)
    return str((t.get("runtime") or {}).get("agent", {}).get("technology", "expo"))


def load_task_toml(task: str) -> dict[str, Any]:
    # tasks/ holds the whole-app benchmark; tasks-step/ holds the step tasks; tasks-repair/
    # holds the repair tasks cut from all-green trees. A checkout need not carry all three.
    # Separate trees on purpose — score_v0 and the campaign tooling walk tasks/ and would
    # otherwise start reporting extra rows against a benchmark that has twenty.
    for root in TASK_ROOTS:
        p = BENCH_ROOT / root / task / "task.toml"
        if p.exists():
            return tomllib.loads(p.read_text(encoding="utf-8"))
    raise FileNotFoundError(
        f"task.toml not found for {task!r} under {'/'.join(TASK_ROOTS)} (set REVYL_BENCH_DIR?)")


def slots_from_names(names: list[str]) -> dict[str, str]:
    """Map frozen test names onto the four slots by their `-t_N-` / `-final-` infix.
    Raises if the suite is not exactly {t_1,t_2,t_3,final} — a suite of a different shape
    would silently break verdict vectors, so fail at resolve time instead."""
    out: dict[str, str] = {}
    for n in names:
        m = re.search(r"-(t_[123])-", n)
        if m:
            out[m.group(1)] = n
        elif "-final-" in n:
            out["final"] = n
    # A whole-app task fills all four slots. A STEP task grades a PREFIX:
    # step 1 -> t_1, step 2 -> t_1,t_2, step 3 -> all four. Anything else is still a
    # mistake — a suite of arbitrary shape would silently produce verdict vectors that do
    # not line up with any contract, which is the failure this check exists to prevent.
    if len(out) != len(names):
        raise ValueError(f"frozen_test_names contains names that map to no slot: {names}")
    got = [s for s in SLOTS if s in out]
    prefixes = [list(SLOTS[:n]) for n in (1, 2, 3)] + [list(SLOTS)]
    if got not in prefixes:
        raise ValueError(
            f"frozen_test_names must fill a PREFIX of {SLOTS} — all four for a whole-app "
            f"task, or t_1.. for a step task; got {got} from {names}")
    return out


def mint_rollout_id(prefix: str, short: str, seed: int) -> str:
    """Naming: <prefix>-<contestant.short>-s<seed>-<8hex>. Filesystem/S3/DNS-safe, sortable
    by task then contestant. The hex is random (not a counter) so two machines can launch
    without coordinating."""
    return f"{prefix}-{short}-s{seed}-{secrets.token_hex(4)}"


def resolve(task: str, contestant_slug: str, seed: int, *, cap: int | None = None,
            wall_clock_min: int | None = None, transport: str = "local", builder: str = "revyl",
            registry_path: Path = REGISTRY_PATH, env: Mapping[str, str] | None = None) -> RolloutSpec:
    """The JOIN. Everything launch_rollout needs to seed a host is in the returned spec.
    `env` is the launch environment (the parsed .env); it supplies the two organisation
    ids, which are recorded in the spec so rollout.json says which orgs graded it."""
    grading_org, agent_org = org_ids(env)
    t = load_task_toml(task)
    reg = load_registry(registry_path)
    if contestant_slug not in reg["contestants"]:
        raise KeyError(f"unknown contestant {contestant_slug!r}; known: {sorted(reg['contestants'])}")
    entry = dict(reg["contestants"][contestant_slug])
    entry["slug"] = contestant_slug
    # Model-server swap WITHOUT a registry edit:
    # VLLM_BASE_URL in the launch environment overrides a vllm-backed contestant's
    # base_url. Guarded on the field existing — for every other contestant the variable
    # is meaningless and must not invent one. Applied to `entry` BEFORE render_setup and
    # before the spec is dumped, so rollout.json and every attempts.jsonl row record the
    # URL that actually served the episode, not the registry's default.
    # Only the vLLM-backed contestant: a direct-provider entry (one that points the harness
    # at a vendor's OpenAI-compatible endpoint, like the DeepInfra entry) also carries
    # base_url, and an environment with VLLM_BASE_URL set must not repoint them at the
    # self-hosted server.
    if entry.get("provider") == "vllm-modal" and "base_url" in entry and os.environ.get("VLLM_BASE_URL"):
        entry["base_url"] = os.environ["VLLM_BASE_URL"]

    rt = t.get("runtime", {})
    if "grading" not in rt or "agent" not in rt or "app_id" not in rt["grading"] or "dev_app_id" not in rt["agent"]:
        # A package without the minted ids has not been provisioned in this deployment's
        # organisations (the public export ships packages in exactly this state).
        raise ValueError(f"{task}/task.toml carries no provisioning ids ([runtime.grading].app_id, "
                         f"[runtime.agent].dev_app_id): the task is not provisioned in this deployment's "
                         f"organisations — see docs/organizations.md")
    g, a, md = rt["grading"], rt["agent"], t["metadata"]

    tests = slots_from_names(list(md["frozen_test_names"]))
    prefix = tests["t_1"].split("-t_1-")[0]          # e.g. s1rb

    # The package carries the ids provisioning minted (grading app, suite workflow, dev app,
    # dev-client pin); the organisations those ids live in come from the environment.
    # A package written before 2026-09-05 may still carry `org_id` lines — ignored: the
    # environment is the only source, so one .env edit re-points every task at once.
    grading = GradingSide(org_id=grading_org, app_id=g["app_id"], workflow=g["workflow"], tests=tests,
                          log_assertions={k: list(v) for k, v in (g.get("log_assertions") or {}).items()})
    technology = str(a.get("technology", "expo"))
    if technology not in TECHNOLOGIES:
        raise ValueError(f"{task}/task.toml [runtime.agent] technology must be one of {TECHNOLOGIES}, got {technology!r}")
    agent = AgentSide(org_id=agent_org, dev_app_id=a["dev_app_id"],
                      devclient_version_id=str(a.get("devclient_version_id", "")),
                      devclient_version=str(a.get("devclient_version", "")), scaffold=a["scaffold"],
                      base_commit=a["base_commit"], expo_sdk=int(a.get("expo_sdk", 0)),
                      ios_scheme=str(a.get("ios_scheme", "")), technology=technology)
    if builder not in ("revyl", "eas"):
        raise ValueError(f"builder must be revyl|eas, got {builder!r}")
    if builder == "revyl" and not agent.ios_scheme:
        # the recipe needs `-scheme <ios_scheme>`; provisioning writes it
        raise ValueError(f"{task}/task.toml [runtime.agent] lacks ios_scheme — re-provision the task")
    if technology == "expo" and not (agent.devclient_version_id and agent.expo_sdk):
        # the Expo runbook pins `revyl dev --no-build --build-version-id` to it
        raise ValueError(f"{task}/task.toml [runtime.agent] lacks devclient_version_id/expo_sdk — re-provision the task")

    task_version = int(md.get("task_version", 0))

    caps = Caps(final_evaluation=int(reg["protocol_version"]) >= 8)
    if technology == "swift":
        # a native episode is budgeted in builds (each 2–4 min on the runner): fewer
        # submissions, a development-build allowance instead of hot reload
        caps.max_submissions = SWIFT_MAX_SUBMISSIONS
        caps.max_dev_builds = SWIFT_MAX_DEV_BUILDS
    if cap is not None:
        caps.max_submissions = cap
    if wall_clock_min is not None:
        caps.wall_clock_min = wall_clock_min

    from datetime import datetime, timezone
    rollout_id = mint_rollout_id(prefix, entry["short"], seed)
    from bench.split import assign_split
    return RolloutSpec(
        rollout_id=rollout_id, split=assign_split(rollout_id),
        task=task, prefix=prefix, seed=seed,
        protocol_version=int(reg["protocol_version"]),
        contestant_slug=contestant_slug, contestant=entry,
        grading=grading, agent=agent, caps=caps, transport=transport, builder=builder,
        # a native task runs in the same thin-client image as the current Expo SDK (node is
        # unused there; the image is the revyl CLI, git, jq and the harness)
        images={"agent": f"revyl-bench-agent:{entry['harness']}-sdk{agent.expo_sdk or NATIVE_IMAGE_SDK}",
                "runner": "revyl-bench-runner:v1"},
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        task_version=task_version,
    )


def render_invoke(entry: dict[str, Any]) -> str:
    """Substitute ${field} placeholders in the registry `invoke`/`install` strings from
    the entry itself (e.g. ${model}, ${reasoning}, ${harness_version})."""
    def sub(s: str) -> str:
        return re.sub(r"\$\{(\w+)\}", lambda m: str(entry.get(m.group(1), m.group(0))), s)
    return sub(entry["invoke"])


def render_setup(entry: dict[str, Any]) -> str:
    """Optional per-harness shell run ONCE before the first invoke. Exists because not every
    harness takes its credential from the environment: opencode reads
    ~/.local/share/opencode/auth.json and prompts for tool permissions unless
    ~/.config/opencode/opencode.json says otherwise, and an interactive prompt with no tty
    hangs the rollout. Empty for harnesses that need nothing."""
    raw = entry.get("setup", "")
    if not raw:
        return ""
    return re.sub(r"\$\{(\w+)\}", lambda m: str(entry.get(m.group(1), m.group(0))), raw)


def render_install(entry: dict[str, Any]) -> str:
    return re.sub(r"\$\{(\w+)\}", lambda m: str(entry.get(m.group(1), m.group(0))), entry["install"])
