#!/usr/bin/env python3
"""launch_rollout.py — the OUTER script: one rollout = task × contestant × seed.
Runs on the control plane (the launch machine; has all keys via ./.env).

    python launch_rollout.py --task s1-ride-booking-0001 --contestant opencode/glm-5.2 --seed 1
                             [--transport local|ec2] [--cap 5] [--wall-clock-min 480]
                             [--mode full|p0] [--detach] [--dry-run] [--keep-host] [--host IP[,ID]]
                             [--campaign <name>]
    python launch_rollout.py --resume <rollout_id>        # wait + collect + tear down a detached run

Steps: 1 resolve → 2 host → 3 seed → 4 guard rails → 5 up → 6 wait → 7 collect → 8 down.
`--campaign <name>` (docs/campaigns.md) puts the run inside an existing campaign folder:
the run folder is `campaigns/<name>/runs/<task>_s<seed>_<8hex>/`, `status.json` there is
advanced at every step (launched → running → collected, or a terminal fault), the
phantom-FAIL check runs at collect while the reports are still local, and the mirror
goes to `s3://<bucket>/campaigns/<name>/runs/…`. Every rollout belongs to a campaign:
`--campaign` is required (`campaign.py new` creates one; an ad-hoc rollout is a `smoke`
or `experiment` campaign of one cell). The live host's staging dir is `hosts/<id>/`.
`--mode p0` starts the agent container with `sleep infinity` instead of the harness so a
human can `docker exec -u agent -it <rollout_id>-agent bash`, drop a tree into /workspace,
and run ./submit.sh — that is how p0 mode proves every wire before any model runs.

Transport `ec2` (v2): steps 5-8 go through the bench.hosts Host interface, so
the protocol logic is transport-blind. `local` = the seeded dir on this machine; `ec2` =
launch one instance from infra.json's AMI, tar-pipe the same seeded dir to
/rollouts/<rollout_id>/, run docker over ssh, pull artifacts back, `aws s3 sync`, then
terminate. Prereqs for ec2: host/ec2/bootstrap.sh once (VPC/SG/key/bucket/role) and
host/ec2/make_ami.sh whenever images change.
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
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from bench import config as _config
from bench import guards as _guards
from bench import hosts as _hosts
from bench import revyl as _revyl
from bench.config import RUNTIME_ROOT, RolloutSpec
import campaigns as _campaigns
from startup_limit import startup_permit

# the live host's staging dir (seeded scaffold, secrets, ec2.json for --resume). Transient,
# never a record: the record is the run folder inside the campaign.
HOSTS_DIR = RUNTIME_ROOT / "hosts"


# ---------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------
def load_dotenv(path: Path = RUNTIME_ROOT / ".env") -> dict[str, str]:
    """Minimal .env reader (KEY=VALUE, # comments, optional quotes). Values are never
    printed anywhere in this script.

    VLLM_* keys in the process environment OVERRIDE the file (and count even when the
    file lacks them): a caller that serves its own model retargets the endpoint per rollout
    by exporting into the child environment (one launch per server), and a .env written
    once must not silently pin every future rollout to the first one. ONLY VLLM_* — the grading/agent keys and AWS_PROFILE/AWS_BIN keep their
    documented .env-first precedence, so a stale shell export can never hijack them."""
    out: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.split(" #", 1)[0].strip().strip('"').strip("'")
            out[k.strip()] = v
    out.update({k: v for k, v in os.environ.items() if k.startswith("VLLM_")})
    return out


def sh(cmd: list[str], *, cwd: Path | None = None, check: bool = True, capture: bool = False,
       input_text: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=check, text=True,
                          capture_output=capture, input=input_text, encoding="utf-8", errors="replace")


def render(tmpl: str, mapping: dict[str, str]) -> str:
    for k, v in mapping.items():
        tmpl = tmpl.replace("{{" + k + "}}", v)
    leftover = [t for t in tmpl.split("{{")[1:] if "}}" in t]
    if leftover:
        raise ValueError(f"unrendered placeholders: {[t.split('}}')[0] for t in leftover]}")
    return tmpl


def write_secret(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def log(msg: str) -> None:
    print(f"[launch {time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------------------------------
# step 3: seed the host directory
# ---------------------------------------------------------------------------------------
def seed_host(spec: RolloutSpec, host: Path, env: dict[str, str], *, mode: str,
              campaign: str | None = None) -> None:
    for d in ("mailbox/submit", "mailbox/feedback", "log", "control", "harness-log", "seed"):
        (host / d).mkdir(parents=True, exist_ok=True)

    # 3a. scaffold copy (plain files; the git history is created inside the seed container)
    src = RUNTIME_ROOT / spec.agent.scaffold
    if not src.is_dir():
        raise SystemExit(f"scaffold missing: {src} — provision the task first")
    dst = host / "seed" / "scaffold"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("node_modules", ".git", ".expo", "build",
                                                            "ios", "android", "*.tmp"))
    # the visible task layer must be present in the scaffold (make_scaffold copies it)
    if not (dst / "task" / "instruction.md").exists():
        raise SystemExit("scaffold has no task/instruction.md — provisioning incomplete")

    # 3b. rollout-specific files. Step tasks get their own runbook: the shared one told a
    # step-1 agent to implement steps 01→02→03 and expect four graded tests — i.e. it
    # instructed the exact build-ahead behaviour that made half the seed candidates fail
    # gating. RUNBOOK-step.md.tmpl scopes the job to one step and the declared tests.
    fields = {
        "EXPO_SDK": str(spec.agent.expo_sdk),
        "MAX_SUBMISSIONS": str(spec.caps.max_submissions),
        "MAX_DEV_BUILDS": str(spec.caps.max_dev_builds),
        "WALL_CLOCK_MIN": str(spec.caps.wall_clock_min),
        "DEVCLIENT_VERSION_ID": spec.agent.devclient_version_id,
        "APP": spec.agent.ios_scheme,
    }
    step_suffix = spec.task.rsplit("-", 1)[-1]
    if "-repair-" in spec.task:
        # a repair task: the tree is a complete app with one planted defect; the brief
        # (task/bug-report.md in the scaffold, written from the failed criteria of the
        # defect's own grading run) is what the agent has to go on. Graded on all four.
        tmpl = "RUNBOOK-repair.md.tmpl"
    elif step_suffix.startswith("step") and step_suffix[4:].isdigit():
        n = int(step_suffix[4:])
        declared = list(spec.grading.tests)
        named = ", ".join(f"`{s}`" for s in declared)
        words = {1: "one", 2: "two", 3: "three", 4: "four"}[len(declared)]
        yours = f"yours are `t_{n}` and `final`" if "final" in declared else f"yours is `t_{n}`"
        fields |= {
            "STEP_N": str(n),
            "STARTING_POINT": (
                "The scaffold is a fresh `create-expo-app` default template (with "
                "`expo-dev-client`), plus a `task/` directory with the product contract "
                "and this runbook." if n == 1 else
                f"The app is partially built: steps 1 through {n - 1} are already "
                f"implemented and your starting tree passes their tests. A `task/` "
                f"directory holds the product contract, alongside this runbook."),
            "GRADED_TESTS": (
                f"{words} hidden device tests ({named} — {yours})" if len(declared) > 1
                else f"one hidden device test ({named})"),
        }
        tmpl = "RUNBOOK-step.md.tmpl"
        if spec.agent.technology == "swift":
            # the native twin: the same one-step job, the build-counted loop of RUNBOOK-swift
            tmpl = "RUNBOOK-swift-step.md.tmpl"
            fields["STARTING_POINT"] = (
                "The scaffold is the blank SwiftUI shell (the tab bar and nothing behind it), plus a "
                "`task/` directory with the product contract and this runbook." if n == 1 else
                f"The app is partially built: steps 1 through {n - 1} are already implemented and your "
                f"starting tree passes their tests. A `task/` directory holds the product contract, "
                f"alongside this runbook.")
    elif spec.agent.technology == "swift":
        # a native task: no dev-client, the agent iterates by remote Debug builds
        # (devbuild.sh) and its budget is counted in builds. A native repair task has no
        # runbook yet and must not launch with the Expo one.
        tmpl = "RUNBOOK-swift.md.tmpl"
    else:
        tmpl = "RUNBOOK.md.tmpl"
    if spec.agent.technology == "swift" and tmpl not in ("RUNBOOK-swift.md.tmpl", "RUNBOOK-swift-step.md.tmpl"):
        raise SystemExit(f"{spec.task}: native repair tasks have no runbook yet (would render {tmpl})")
    runbook = render((RUNTIME_ROOT / "container" / tmpl).read_text(encoding="utf-8"), fields)
    # templates may carry maintainer notes in HTML comments; the agent reads the rendered
    # file verbatim, so those must never ship
    runbook = re.sub(r"<!--.*?-->\n?", "", runbook, flags=re.DOTALL)
    (host / "seed" / "RUNBOOK.md").write_text(runbook, encoding="utf-8", newline="\n")
    (host / "seed" / "infra_runtime.json").write_text(json.dumps({
        "rollout_id": spec.rollout_id, "task": spec.task,
        "agent_dev_app_id": spec.agent.dev_app_id,
        "devclient_version_id": spec.agent.devclient_version_id,
        "devclient_version": spec.agent.devclient_version,
        "max_submissions": spec.caps.max_submissions, "submissions_used": 0,
        "max_dev_builds": spec.caps.max_dev_builds, "dev_builds_used": 0,
        "wall_clock_min": spec.caps.wall_clock_min,
        "technology": spec.agent.technology,
        # native only: submit.sh refuses a tree that no development build has compiled
        "require_dev_build": spec.agent.technology == "swift",
    }, indent=2), encoding="utf-8", newline="\n")
    if spec.agent.technology == "swift":
        # the agent's development recipe: the bench's Swift template as a Debug build on the
        # agent org's dev app. seed.sh installs it as the workspace's .revyl/config.yaml
        # (the scaffold's committed stub refuses to build) and keeps a copy that devbuild.sh
        # restores before every build. Grading never reads it: grade.py renders its own.
        from bench import recipes as _recipes
        (host / "seed" / "devbuild-config.yaml").write_text(
            _recipes.build_recipe(spec.task, app_id=spec.agent.dev_app_id, scheme=spec.agent.ios_scheme,
                                  profile="development", configuration="Debug", technology="swift"),
            encoding="utf-8", newline="\n")
    shutil.copy2(RUNTIME_ROOT / "host" / "seed.sh", host / "seed" / "seed.sh")

    # 3c. spec + env files (600) + invoke + compose
    spec.dump(host / "rollout.json")
    # Persist the launch mode so human and p0-mode rollouts are identifiable
    # by a DECLARED field — before this, p0-mode runs were byte-identical to real ones and
    # exclusion rested on a compose-entrypoint heuristic.
    d = json.loads((host / "rollout.json").read_text(encoding="utf-8"))
    d["mode"] = mode
    if campaign:
        # the campaign name rides in rollout.json (RolloutSpec.load drops unknown keys, so
        # it never reaches the runner): --resume reads it back to find the run folder, and
        # the copy collected into the run folder says which campaign the run belongs to
        d["campaign"] = campaign
    (host / "rollout.json").write_text(json.dumps(d, indent=2), encoding="utf-8", newline="\n")
    # EXPO_TOKEN reaches the runner ONLY for the EAS rollback builder; the default revyl builder
    # needs nothing beyond the grading key.
    expo_line = f"EXPO_TOKEN={env.get('EXPO_TOKEN', '')}\n" if spec.builder == "eas" else ""
    write_secret(host / "runner.env",
                 f"REVYL_API_KEY={env['REVYL_GRADING_API_KEY']}\n{expo_line}"
                 f"BENCH_AGENT_KEY={env['REVYL_AGENT_API_KEY']}\n")
    key_env = spec.contestant["key_env"]
    write_secret(host / "agent.env",
                 f"REVYL_API_KEY={env['REVYL_AGENT_API_KEY']}\n{key_env}={env.get(key_env, '')}\n"
                 f"BENCH_ROLLOUT_ID={spec.rollout_id}\n")
    invoke = _config.render_invoke(spec.contestant)
    (host / "invoke.sh").write_text(f"#!/usr/bin/env bash\n# rendered from contestants/registry.yaml[{spec.contestant_slug}]\n"
                                    f"cd /workspace\n{invoke}\n", encoding="utf-8", newline="\n")
    # per-harness one-time setup (credential files, permission config), run by the
    # entrypoint before the first invoke. Empty for claude-code/codex, non-empty for
    # opencode — see config.render_setup.
    setup = _config.render_setup(spec.contestant)
    (host / "setup.sh").write_text(
        ("#!/usr/bin/env bash\n# rendered from contestants/registry.yaml"
         f"[{spec.contestant_slug}].setup\nset -eu\n{setup}\n") if setup else "",
        encoding="utf-8", newline="\n")
    # resume line — the entrypoint re-invokes the harness until END.json exists (a session
    # can end itself mid-rollout; observed in an early rollout). Empty file = reuse full invoke.
    resume = spec.contestant.get("invoke_resume", "")
    if resume:
        import re as _re
        resume = _re.sub(r"\$\{(\w+)\}", lambda m: str(spec.contestant.get(m.group(1), m.group(0))), resume)
        resume = f"#!/usr/bin/env bash\ncd /workspace\n{resume}\n"
    (host / "invoke_resume.sh").write_text(resume, encoding="utf-8", newline="\n")
    entry = '["sleep", "infinity"]' if mode == "p0" else '["/usr/bin/tini", "--", "/opt/bench/entrypoint.sh"]'
    compose = render((RUNTIME_ROOT / "host" / "compose.yaml.tmpl").read_text(encoding="utf-8"), {
        "ROLLOUT_ID": spec.rollout_id, "RUNNER_IMAGE": spec.images["runner"],
        "AGENT_IMAGE": spec.images["agent"], "AGENT_ENTRYPOINT": entry,
    })
    (host / "compose.yaml").write_text(compose, encoding="utf-8", newline="\n")
    log(f"seeded {host}")


def seed_volume(spec: RolloutSpec, h) -> None:
    """Create the `workspace` named volume and populate it via host/seed.sh inside the agent
    image (asserts base_commit). Volume name follows compose's `<project>_workspace`.
    Runs ON the rollout host (h.run), so on ec2 the volume lives on the instance."""
    vol = f"{spec.rollout_id}_workspace"
    h.run(["docker", "volume", "create", vol], capture=True)
    p = h.run(["docker", "run", "--rm", "-u", "agent", "-v", f"{vol}:/workspace",
               "-v", f"{h.abs('seed')}:/seed:ro", "--entrypoint", "bash",
               spec.images["agent"], "/seed/seed.sh", spec.agent.base_commit, spec.rollout_id],
              capture=True, check=False)
    print((p.stdout or "").strip())
    if p.returncode != 0:
        print((p.stderr or "").strip(), file=sys.stderr)
        raise SystemExit(f"seed.sh failed rc={p.returncode}")


# ---------------------------------------------------------------------------------------
# steps 5–8 — transport-blind: only bench.hosts primitives touch the rollout host
# ---------------------------------------------------------------------------------------
def compose(h, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return h.run(["docker", "compose", "-f", "compose.yaml", *args], check=check)


def container_state(h, name: str) -> str:
    p = h.run(["docker", "inspect", "-f", "{{.State.Status}}", name], capture=True, check=False)
    return (p.stdout or "").strip() if p.returncode == 0 else "missing"


def up(spec: RolloutSpec, h) -> None:
    compose(h, "up", "-d", "runner")
    for _ in range(60):
        if h.exists("log/runner.ready"):
            break
        if container_state(h, f"{spec.rollout_id}-runner") == "exited":
            print((h.read("log/runner.log") or "")[-2000:])
            raise SystemExit("runner exited before ready — see log/runner.log")
        time.sleep(2)
    else:
        raise SystemExit("runner never became ready")
    log("runner ready")
    compose(h, "up", "-d", "agent")
    log(f"agent up ({spec.images['agent']})")


def freeze_final_evaluation(spec: RolloutSpec, h, deadline_at: float, *,
                            reason: str = "wall_clock", stopped_at: float | None = None) -> dict:
    """Stop every agent process before capturing a trusted, immutable final tree."""
    marker = "control/final_evaluation.json"
    existing = h.read(marker)
    if existing:
        return json.loads(existing)
    evidence = {"rollout_id": spec.rollout_id, "reason": reason,
                "deadline_at": deadline_at}
    if reason in {"malformed_tool_call", "policy_stop"}:
        evidence["stopped_at"] = stopped_at if stopped_at is not None else time.time()
    try:
        name = f"{spec.rollout_id}-agent"
        state = container_state(h, name)
        if state in ("running", "paused", "restarting"):
            h.run(["docker", "kill", name], capture=True, check=False)
        if container_state(h, name) not in ("exited", "dead"):
            raise RuntimeError("agent_not_quiescent_at_deadline")
        evidence["frozen_at"] = time.time()
        evidence["host_stopped"] = state in ("running", "paused", "restarting")
        submitted = False
        if getattr(spec, "protocol_version", 0) >= 9:
            state = json.loads(h.read("log/state.json") or "{}")
            requests = h.run(["find", h.abs("mailbox/submit"), "-maxdepth", "1",
                              "-type", "f", "-name", "s*.request.json", "-print"], capture=True)
            submitted = state.get("last_k", 0) > 0 or bool(requests.stdout.strip())
        if submitted and reason == "wall_clock":
            evidence.update(status="skipped", skip_reason="explicit_submission")
        else:
            if reason == "wall_clock" and evidence["frozen_at"] > deadline_at + 60:
                raise RuntimeError("deadline_freeze_late: exceeded 60s cutoff tolerance")
            h.run(["mkdir", "-p", h.abs("log/final-evaluation")], capture=True)
            # Only the runner and trusted helper mount this directory; the agent does not.
            h.run(["chmod", "777", h.abs("log/final-evaluation")], capture=True)
            helper = "control/final_evaluation_snapshot.sh"
            h.write(helper, (RUNTIME_ROOT / "host/final_evaluation_snapshot.sh").read_text(encoding="utf-8"))
            result = h.run([
                "docker", "run", "--rm", "--network", "none", "--read-only",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--tmpfs", "/tmp:rw,nosuid,nodev", "--user", "agent",
                "-v", f"{spec.rollout_id}_workspace:/workspace:ro",
                "-v", f"{h.abs(helper)}:/snapshot.sh:ro",
                "-v", f"{h.abs('log/final-evaluation')}:/output",
                "--entrypoint", "/bin/bash", spec.images["agent"], "/snapshot.sh",
            ], capture=True)
            evidence.update(json.loads(result.stdout))
            evidence["status"] = "ready"
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        evidence.update(status="error", error=str(exc))
    h.run(["mkdir", "-p", h.abs("log/final-evaluation")], capture=True)
    h.write("log/final-evaluation/freeze.json", json.dumps(evidence))
    h.write(marker + ".tmp", json.dumps(evidence))
    h.run(["mv", h.abs(marker + ".tmp"), h.abs(marker)], capture=True)
    return evidence


def wait_for_end(spec: RolloutSpec, h) -> dict:
    seen = 0
    deadline_at = None
    final_enabled = getattr(spec.caps, "final_evaluation", False)
    while not h.exists("mailbox/feedback/END.json"):
        if final_enabled and deadline_at is None:
            state = json.loads(h.read("log/state.json") or "null")
            if state is not None:
                deadline_at = float(state["started_at"]) + spec.caps.wall_clock_min * 60
        # harness exit → tell the runner (it finishes any in-flight grade first)
        st = container_state(h, f"{spec.rollout_id}-agent")
        if (st in ("exited", "dead") and not h.exists("control/harness_exit.json")
                and not h.exists("control/final_evaluation.json")):
            p = h.run(["docker", "inspect", "-f", "{{.State.ExitCode}}", f"{spec.rollout_id}-agent"],
                      capture=True, check=False)
            rc = (p.stdout or "").strip()
            # the entrypoint's stop marker (harness-log/ is the agent's /log): says whether
            # the loop stopped because the harness kept failing (`harness_crash`) or because
            # the model kept exiting without submitting (`no_progress`). Absent when the
            # container died outside the loop (OOM, docker kill) — the runner then falls
            # back to the exit code.
            try:
                stop = json.loads(h.read("harness-log/harness_stop.json") or "null")
            except (ValueError, TypeError):
                stop = None
            stop_reason = (stop or {}).get("reason")
            if (final_enabled and deadline_at is not None and rc == "0"
                    and stop_reason in {"malformed_tool_call", "no_progress", "policy_budget_exhausted"}):
                from datetime import datetime
                finished = h.run(["docker", "inspect", "-f", "{{.State.FinishedAt}}",
                                  f"{spec.rollout_id}-agent"], capture=True).stdout.strip()
                stopped_at = datetime.fromisoformat(finished.replace("Z", "+00:00")).timestamp()
                # Save before signalling the runner, even when its previous grade is busy.
                trigger = ("malformed_tool_call" if stop_reason == "malformed_tool_call" else "policy_stop")
                if stopped_at > deadline_at:
                    trigger = "wall_clock"
                freeze_final_evaluation(spec, h, deadline_at, stopped_at=stopped_at, reason=trigger)
            h.write("control/harness_exit.json", json.dumps({"rc": rc, "ts": time.time(), "stop": stop}))
            log(f"agent container exited rc={rc} stop={(stop or {}).get('reason')} → signalled runner")
        if deadline_at is not None and time.time() >= deadline_at:
            if not h.exists("control/final_evaluation.json"):
                evidence = freeze_final_evaluation(spec, h, deadline_at)
                log(f"deadline final evaluation: {evidence['status']}")
        # surface runner progress lines as they land
        txt = h.read("log/runner.log") or ""
        new = txt[seen:]
        seen = len(txt)
        for line in new.splitlines():
            if any(t in line for t in ("status=", "DONE", "rejected", "[end]", "[eas]", "registered", "WRONG")):
                print("  " + line)
        remaining = deadline_at - time.time() if deadline_at is not None else 30
        time.sleep(max(0.1, min(30, remaining)) if remaining > 0 else 1)
    d = json.loads(h.read("mailbox/feedback/END.json"))
    log(f"END: {d}")
    # the runner exits after END collection; give it a moment
    for _ in range(60):
        if container_state(h, f"{spec.rollout_id}-runner") in ("exited", "missing"):
            break
        time.sleep(5)
    return d


def _end_reason(run_dir: Path) -> str | None:
    """The END record's reason from the collected attempts.jsonl (None if no END row)."""
    reason = None
    try:
        for line in (run_dir / "attempts.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("type") == "end":
                    reason = r.get("end_reason")
    except (OSError, ValueError):
        return None
    return reason


def collect(spec: RolloutSpec, h, env: dict[str, str], *, transport: str, run_dir: Path) -> Path:
    """Everything worth keeping → the run folder campaigns/<name>/runs/<task>_s<seed>_<8hex>/
    (the S3 layout, minus the bucket), then mirror it. status.json advances to
    `collected` with the checks computed while reports/ and feedback/ are still here,
    the mirror goes to s3://<bucket>/campaigns/… and is recorded, and after a successful
    mirror the heavy artifacts leave this host when the campaign says so. Secrets
    (runner.env/agent.env) are never fetched."""
    out = run_dir
    out.mkdir(parents=True, exist_ok=True)
    for name in ("rollout.json", "compose.yaml", "invoke.sh"):
        h.fetch(name, out / name)
    # log/ contents land at the run root (attempts.jsonl, runner.log, reports/, ...)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "log"
        if h.fetch("log", tmp):
            shutil.copytree(tmp, out, dirs_exist_ok=True)
    # attempts.jsonl is the scoring input — a collect that lost it must ABORT before
    # down() so the host (and on ec2, the instance holding the only full copy) survives
    # for salvage. First EC2 smoke test hit exactly this: log/ fetch failed silently,
    # down() terminated the instance, and the raw reports were gone.
    if not (out / "attempts.jsonl").exists():
        if run_dir is not None:
            _campaigns.transition(out, lifecycle="collect_failed", by="launch_rollout",
                                  error="attempts.jsonl missing after log fetch; host kept for salvage")
        raise SystemExit(f"collect FAILED: {out / 'attempts.jsonl'} missing after log fetch — "
                         f"host NOT torn down; inspect and re-collect via --resume {spec.rollout_id}")
    fetched = {
        "harness_log": bool(h.fetch("harness-log/harness.log", out / "harness.log")),
        "feedback": bool(h.fetch("mailbox/feedback", out / "feedback")),
        "submit": bool(h.fetch("mailbox/submit", out / "submit")),     # the exact graded tarballs
    }
    log(f"collected → {out}")
    if run_dir is not None:
        # the checks need reports/ and feedback/, which the slim below deletes: compute
        # them now, store the verdict, and the scorer reads the stored field
        checks = _campaigns.run_checks(out, by="collect")
        _campaigns.transition(out, lifecycle="collected", by="launch_rollout",
                              pipeline={"attempts_sha256": _campaigns.attempts_sha256(out)},
                              checks=checks, fetched=fetched)
        if checks["phantom_fail"]:
            log(f"phantom-FAIL signature in {checks['phantom_slots']} — the scorer will exclude this run")
        if checks["suite_fetch"]:
            # printed at collect so the operator sees it while the transcript is still local
            log(f"suite-fetch: the transcript names this repository / grading-side ({checks['suite_fetch_hits'][0][:140]}) "
                f"— the scorer will exclude this run until it is reviewed")
        # A harness_crash END is the bench's fault (the harness could not run; the model had
        # no turn), so the run must not count AND its cell must be launched again. Voiding
        # it here does both: cell_state() ignores a void run, so the next
        # `campaign.py launch` fills the cell, and the scorer lists it as excluded with
        # this reason. `harness_exit` (the model declining to submit) stays valid and scored.
        if _end_reason(out) == "harness_crash":
            _campaigns.transition(out, legitimacy="void", by="launch_rollout",
                                  reason="harness_crash: the harness failed to run 10 times in a row "
                                         "(see harness.log); bench fault — cell reopened for re-launch")
            log("END harness_crash → run voided; `campaign.py launch` will re-run this cell")
    if transport == "ec2":
        infra = _hosts.load_infra(RUNTIME_ROOT)
        aws_bin, profile = _aws_cli(env)
        prefix = f"runs/{spec.rollout_id}"
        if run_dir is not None:
            prefix = ((_campaigns.read_status(out) or {}).get("mirror") or {}).get("prefix") or prefix
        target = f"s3://{infra['bucket']}/{prefix}/"
        ok, err = _campaigns.s3_sync(str(out), target, aws_bin=aws_bin, profile=profile, region=infra["region"])
        if ok:
            log(f"synced → {target}")
        else:
            # non-fatal: artifacts are already safe on this machine; SSO token may just be
            # stale. In a campaign the failure is recorded and `campaign.py sync` retries.
            log(f"s3 sync FAILED (artifacts kept locally): {err}")
        if run_dir is not None:
            _campaigns.transition(out, by="launch_rollout",
                                  mirror={"synced": ok, "at": _campaigns.now_iso(), "prefix": prefix,
                                          "error": None if ok else err})
            if ok and _campaigns.manifest_for_run(out).get("slim_after_mirror"):
                try:
                    removed = _campaigns.slim(out)
                except OSError as exc:
                    log(f"cleanup FAILED (campaign.py sync retries it): {exc}")
                else:
                    _campaigns.transition(out, by="launch_rollout", slimmed=removed)
                    log(f"slimmed {removed} from this host (in S3 under {prefix}/; campaign.py fetch brings them back)")
            if ok:
                # the sync above uploaded a status.json that did not yet say "synced"; push
                # the final one on its own so the store carries the record, not a draft
                ok2, err2 = _campaigns.s3_copy(str(out / _campaigns.STATUS), target + _campaigns.STATUS,
                                               aws_bin=aws_bin, profile=profile, region=infra["region"])
                if not ok2:
                    log(f"status.json push FAILED (campaign.py sync retries it): {err2}")
    elif run_dir is not None:
        _campaigns.transition(out, by="launch_rollout",
                              mirror={"synced": False, "at": _campaigns.now_iso(),
                                      "reason": "transport=local: no mirror, the artifacts stay on this machine"})
    return out


def down(spec: RolloutSpec, h, env: dict[str, str], staging: Path, *, keep_host: bool,
         run_dir: Path | None = None) -> None:
    compose(h, "down", "-v", "--remove-orphans", check=False)
    # agent-org hygiene: stop dev sessions THIS rollout left running. Per-session, not
    # `--all` — the agent org is shared, so with parallel rollouts (v2 matrix) an org-wide
    # stop kills the sibling's live dev session mid-exploration.
    try:
        _stop_rollout_sessions(spec, env, staging, run_dir=run_dir)
    except Exception as e:  # noqa: BLE001
        log(f"device session stop failed (non-fatal): {e}")
    for f in ("runner.env", "agent.env"):
        h.unlink(f)
        try:
            (staging / f).unlink()
        except FileNotFoundError:
            pass
    h.close()                                     # ec2: terminate-instances; local: no-op
    if not keep_host:
        shutil.rmtree(staging, ignore_errors=True)
    log("down")


def _stop_rollout_sessions(spec: RolloutSpec, env: dict[str, str], staging: Path,
                           run_dir: Path | None = None) -> None:
    """Stop exactly the dev sessions this rollout created. The runner snapshots the
    workspace's .revyl/device-sessions.json to log/ at END (collected into the run
    folder — a top-level file, so the campaign slim never removes it);
    `revyl device stop -s <index>` resolves indexes against the sessions file in the -C
    project dir, so we place OUR file into the staging scaffold's .revyl/ first. Falls
    back to org-wide --all only when no sessions file exists AND no sibling rollout is
    live (the pre-refactor safety net, now provably-alone-only)."""
    key = env["REVYL_AGENT_API_KEY"]
    scaffold = staging / "seed" / "scaffold"
    sess_file = None
    for cand in ((run_dir / "device-sessions.json") if run_dir is not None else staging / "nowhere",
                 staging / "log" / "device-sessions.json"):
        if cand.exists():
            sess_file = cand
            break
    if sess_file is None:
        siblings = [d for d in HOSTS_DIR.iterdir() if d.is_dir() and d.name != spec.rollout_id] \
            if HOSTS_DIR.exists() else []
        if siblings:
            log(f"no device-sessions.json and {len(siblings)} sibling rollout(s) live — skipping org-wide stop")
            return
        _revyl.device_stop_all(key, scaffold)
        return
    sessions = json.loads(sess_file.read_text(encoding="utf-8")).get("sessions") or []
    if not sessions:
        return
    (scaffold / ".revyl").mkdir(exist_ok=True)
    shutil.copy2(sess_file, scaffold / ".revyl" / "device-sessions.json")
    # device_stop_session raises on failure (check=True since 2026-08-25 — a silent failure is
    # how sessions leaked under the legacy-config gate). Catch PER INDEX so one refused stop
    # never skips the remaining sessions of this rollout; report the tally instead.
    stopped, failed = 0, 0
    for s in sessions:
        idx = s.get("index")
        if idx is None:
            continue
        try:
            _revyl.device_stop_session(key, scaffold, idx)
            stopped += 1
        except _revyl.RevylError as e:
            failed += 1
            log(f"device stop -s {idx} FAILED for {spec.rollout_id}: {str(e)[-300:]}")
    log(f"stopped {stopped}/{stopped + failed} dev session(s) of {spec.rollout_id}"
        + (f" — {failed} FAILED (check the agent org for leaked sessions)" if failed else ""))


def _aws_cli(env: dict[str, str]) -> tuple[str, str | None]:
    """aws binary + profile: .env override first (AWS_BIN/AWS_PROFILE), then the
    environment, then bare `aws` / profile-less."""
    aws_bin = env.get("AWS_BIN") or os.environ.get("AWS_BIN") or "aws"
    profile = env.get("AWS_PROFILE") or os.environ.get("AWS_PROFILE") or None
    return aws_bin, profile


# EC2 error codes that a retry cannot fix; anything else (InsufficientInstanceCapacity,
# RequestLimitExceeded, InternalError, an unnamed refusal) is retried.
_PERMANENT_LAUNCH_ERRORS = ("UnauthorizedOperation", "AuthFailure", "InvalidAMIID", "InvalidParameter",
                            "InvalidSubnetID", "InvalidGroup", "InvalidKeyPair", "OptInRequired",
                            "VcpuLimitExceeded", "InstanceLimitExceeded")


def _launch_with_retry(h, *, ssh_wait_s: int, attempts: int = 3, sleep=time.sleep,
                       stagger_s: float = 4.0) -> None:
    """run-instances for a rollout host, retried while it is AWS that refuses.

    A caller that launches a whole wave of hosts in the same second (sixteen at once has
    been measured) gets, about once per wave, one call back with the CLI's service-error
    exit while the others succeed, and that rollout is lost before it exists.
    Capacity and rate-limit refusals both create nothing, so a retry is safe as long as
    no instance id was assigned; anything after run-instances is the caller's to
    terminate. A short random start offset spreads the wave. The CLI's last stderr line
    is logged, since it is the only place the refusal names itself.
    """
    import random
    sleep(random.uniform(0.0, stagger_s))
    for attempt in range(1, attempts + 1):
        try:
            h.launch(ssh_wait_s=ssh_wait_s)
            return
        except subprocess.CalledProcessError as e:
            # Retry only a refused run-instances: nothing was created. Ec2Host.launch keeps
            # the id of a host it terminated for never accepting ssh when it relaunches
            # once, so a stale instance_id does not mean a live instance;
            # the failing command is the reliable witness.
            refused_launch = "run-instances" in list(e.cmd or [])
            if not refused_launch:
                raise
            tail = ((e.stderr or "").strip().splitlines() or ["(no stderr)"])[-1]
            # A refusal that cannot change with time (credentials, a bad AMI id or
            # parameter) is not worth a minute of backoff; capacity and rate limits are.
            permanent = any(code in tail for code in _PERMANENT_LAUNCH_ERRORS)
            if permanent or attempt == attempts:
                log(f"[ec2] run-instances refused (attempt {attempt}/{attempts}, "
                    f"{'permanent' if permanent else 'giving up'}): {tail[:200]}")
                raise
            delay = min(5.0 * 3 ** (attempt - 1), 45.0) + random.uniform(0.0, 3.0)
            log(f"[ec2] run-instances refused (attempt {attempt}/{attempts}): {tail[:200]} — retrying in {delay:.0f}s")
            sleep(delay)


def make_host(spec: RolloutSpec, staging: Path, transport: str, env: dict[str, str], *,
              skip_guards: bool = False, host: str | None = None):
    """LocalHost over the staging dir, or an Ec2Host — freshly launched, or attached to a
    running host (`host` = ip[,instance-id]) — with the staged
    rollout dir uploaded. ec2.json (instance id + ip, persistent flag) is dropped in the
    staging dir so --resume can rehydrate without a new instance."""
    if transport == "local":
        return _hosts.LocalHost(staging)
    infra = _hosts.load_infra(RUNTIME_ROOT)
    aws_bin, profile = _aws_cli(env)
    h = _hosts.Ec2Host(spec.rollout_id, infra, aws_bin=aws_bin, profile=profile, log=log)
    state = staging / "ec2.json"
    if state.exists():                            # --resume path
        d = json.loads(state.read_text(encoding="utf-8"))
        h.instance_id, h.ip, h.persistent = d["instance_id"], d["ip"], bool(d.get("persistent"))
        log(f"[ec2] rehydrated {h.instance_id} at {h.ip}" + (" (attached host)" if h.persistent else ""))
    else:
        # Pre-flight: the AMI must have been baked from THIS checkout's runner/bench/container
        # code. infra.json's ami_runtime_tree is written by make_ami.sh; the runner image is
        # COPY'd into the AMI and nothing re-pulls it on the host, so a checkout that is
        # ahead of the AMI runs stale grading logic with no error anywhere: a fix that is
        # merged but not baked never runs. Checked BEFORE run-instances
        # so a mismatch costs nothing. --skip-guards bypasses it, like the other guards.
        want = infra.get("ami_runtime_tree")
        have = _hosts.runtime_tree_hash(RUNTIME_ROOT)
        if want is None:
            raise SystemExit(f"infra.json has no ami_runtime_tree — AMI {infra.get('ami_id')} predates the "
                             f"code-fingerprint guard; re-run host/ec2/make_ami.sh")
        if want != have and not skip_guards:
            raise SystemExit(f"AMI {infra.get('ami_id')} was baked from runtime tree {want} but this checkout "
                             f"is {have} (runner/, bench/ or container/ changed since) — re-run "
                             f"host/ec2/make_ami.sh, or --skip-guards to knowingly run old image code")
        log(f"[ec2] ami {infra.get('ami_id')} runtime tree {want} matches checkout")
        # ssh_wait_s=900: the FIRST boot of a freshly registered AMI lazy-loads its EBS
        # snapshot and can take more than 5 min to accept ssh (measured: `running` to sshd
        # answering in just over 6 min) — hosts.py's 300 s default gave up first and
        # the instance was left running. Everything after run-instances is wrapped so a
        # failure terminates the instance instead of leaking it (the try/except around
        # seed_volume/up in main() starts only after make_host returns).
        try:
            if host:
                ip, _, iid = host.partition(",")
                h.attach(ip.strip(), iid.strip() or None)
            else:
                _launch_with_retry(h, ssh_wait_s=900)
            state.write_text(json.dumps({"instance_id": h.instance_id, "ip": h.ip, "persistent": h.persistent}),
                             encoding="utf-8")
            h.put_dir(staging)
        except BaseException:
            if h.instance_id:
                log(f"[ec2] launch failed after run-instances — terminating {h.instance_id}")
                h.close()
            raise
        # the AMI must carry this rollout's images — a stale AMI would silently run old code
        p = h.run(["docker", "image", "inspect", spec.images["agent"], spec.images["runner"]],
                  capture=True, check=False)
        if p.returncode != 0:
            h.close()
            raise SystemExit(f"AMI {infra.get('ami_id')} lacks {spec.images} — re-run host/ec2/make_ami.sh")
    return h


# ---------------------------------------------------------------------------------------
# campaigns: the run folder, its status file and the mirror prefix come from the manifest
# ---------------------------------------------------------------------------------------
def _campaign_run_dir(name: str, spec: RolloutSpec, *, existing: bool) -> Path:
    """The run folder of this rollout inside campaign `name`, after checking that the
    campaign exists and describes the same contestant and protocol as the rollout — a
    rollout launched into the wrong folder would sit there as a `mismatch` forever."""
    cdir = _campaigns.campaign_dir(name)
    try:
        m = _campaigns.read_manifest(cdir)
    except FileNotFoundError:
        raise SystemExit(f"campaign {name!r} does not exist under {_campaigns.campaigns_root()} — "
                         f"create it first: python3 runtime/campaign.py new …")
    want_slug, want_proto = (m.get("contestant") or {}).get("slug"), int(m.get("protocol_version") or 0)
    if want_slug != spec.contestant_slug or want_proto != int(spec.protocol_version):
        raise SystemExit(f"campaign {name!r} is {want_slug} under protocol {want_proto}, this rollout is "
                         f"{spec.contestant_slug} under protocol {spec.protocol_version} — wrong campaign")
    run_dir = cdir / "runs" / _campaigns.run_folder_name(spec.task, spec.seed, spec.rollout_id)
    if existing and not _campaigns.status_path(run_dir).exists():
        raise SystemExit(f"{run_dir} has no status.json — was {spec.rollout_id} launched with --campaign {name}?")
    return run_dir


def _register_run(name: str, spec: RolloutSpec, staging: Path, *, transport: str, mode: str) -> Path:
    """Create the run folder with rollout.json and status.json `launched`, stamped with
    the pipeline that will grade it (the AMI's tree hash for ec2, the checkout's for
    local). A p0 run is void from the start: not a contestant run."""
    run_dir = _campaign_run_dir(name, spec, existing=False)
    run_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(staging / "rollout.json", run_dir / "rollout.json")
    rollout = json.loads((run_dir / "rollout.json").read_text(encoding="utf-8"))
    pipeline = _campaigns.current_pipeline(RUNTIME_ROOT, transport=transport)
    _campaigns.init_status(run_dir, rollout, campaign=name, pipeline=pipeline, transport=transport)
    if mode != "full":
        _campaigns.transition(run_dir, legitimacy="void", reason=f"mode={mode}: not a contestant run", by="launch_rollout")
    log(f"campaign {name}: run folder runs/{run_dir.name}  pipeline ami={pipeline.get('ami_id')} "
        f"tree={pipeline.get('runtime_tree_hash')} cli={pipeline.get('revyl_cli_version')}")
    return run_dir


# ---------------------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task")
    ap.add_argument("--contestant")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--campaign", metavar="NAME",
                    help="the campaign this rollout belongs to (campaign.py new); the run folder, "
                         "status.json and the mirror prefix come from it")
    ap.add_argument("--transport", choices=["local", "ec2"], default="local")
    ap.add_argument("--builder", choices=["revyl", "eas"], default="revyl",
                    help="who builds submissions: revyl = `revyl build --remote` (default); eas = the older EAS path (kept as a rollback)")
    ap.add_argument("--cap", type=int)
    ap.add_argument("--wall-clock-min", type=int)
    ap.add_argument("--mode", choices=["full", "p0"], default="full")
    ap.add_argument("--detach", action="store_true", help="return after `up`; finish later with --resume")
    ap.add_argument("--dry-run", action="store_true", help="resolve + seed + guards, no containers")
    ap.add_argument("--keep-host", action="store_true", help="keep hosts/<id> after collect")
    ap.add_argument("--host", metavar="IP[,INSTANCE_ID]",
                    help="ec2 transport: run on this already-running host instead of "
                         "launching an instance; the rollout's dir on it is removed at down, the host stays up")
    ap.add_argument("--skip-guards", action="store_true")
    ap.add_argument("--resume", metavar="ROLLOUT_ID")
    a = ap.parse_args()

    env = load_dotenv()
    # Two keys and the two organisation ids they belong to (docs/organizations.md). The
    # ids are checked here, not only inside resolve(), so a fresh deployment gets one
    # complete list of what .env lacks instead of one missing name per attempt.
    for k in ("REVYL_GRADING_API_KEY", "REVYL_AGENT_API_KEY",
              _config.ORG_ENV["grading"], _config.ORG_ENV["agent"]):
        if not env.get(k):
            raise SystemExit(f".env lacks {k} (see docs/organizations.md)")

    if a.resume:
        staging = HOSTS_DIR / a.resume
        spec = RolloutSpec.load(staging / "rollout.json")
        # RolloutSpec.load drops unknown keys; the campaign name rides in the raw file
        raw = json.loads((staging / "rollout.json").read_text(encoding="utf-8"))
        if not raw.get("campaign"):
            raise SystemExit(f"{staging / 'rollout.json'} names no campaign: this rollout predates the campaign "
                             f"layer and cannot be resumed into one — collect it by hand")
        run_dir = _campaign_run_dir(raw["campaign"], spec, existing=True)
        transport = "ec2" if (staging / "ec2.json").exists() else "local"
        h = make_host(spec, staging, transport, env)
        _wait_and_collect(spec, h, env, transport=transport, run_dir=run_dir)
        down(spec, h, env, staging, keep_host=a.keep_host, run_dir=run_dir)
        return 0

    if not (a.task and a.contestant):
        ap.error("--task and --contestant are required (or --resume)")
    if a.host and a.transport != "ec2":
        ap.error("--host is for --transport ec2 (local runs docker on this machine)")
    if not a.campaign:
        ap.error("--campaign is required: every rollout belongs to a campaign (docs/campaigns.md). "
                 "Create one with `python3 runtime/campaign.py new --purpose smoke|experiment|… --contestant … --tasks …`")

    # 1. resolve
    try:
        spec = _config.resolve(a.task, a.contestant, a.seed, cap=a.cap, wall_clock_min=a.wall_clock_min, builder=a.builder,
                               transport=a.transport, env=env)
    except (ValueError, KeyError, FileNotFoundError) as e:
        # a configuration problem (unknown task or contestant, unprovisioned package, missing
        # .env value) is an operator message, not a traceback
        raise SystemExit(f"cannot resolve the rollout: {e}")
    log(f"rollout {spec.rollout_id}  task={spec.task} contestant={spec.contestant_slug} seed={spec.seed} "
        f"cap={spec.caps.max_submissions} wall={spec.caps.wall_clock_min}m builder={spec.builder} images={spec.images}")
    # before any staging dir exists: a wrong campaign name or contestant must leave nothing
    # behind (the seeded dir holds runner.env/agent.env). Validated on --dry-run too.
    _campaign_run_dir(a.campaign, spec, existing=False)

    # Limit costly startup only; completed agents keep running outside this permit.
    with startup_permit():
        # 2+3. host + seed (always seeded locally; ec2 uploads the seeded dir afterwards)
        staging = HOSTS_DIR / spec.rollout_id
        staging.mkdir(parents=True, exist_ok=False)
        seed_host(spec, staging, env, mode=a.mode, campaign=a.campaign)
        run_dir: Path | None = None
        if not a.dry_run:                                           # a dry run leaves no record anywhere
            run_dir = _register_run(a.campaign, spec, staging, transport=a.transport, mode=a.mode)

        # 4. guard rails (run from the launch machine — Revyl/EAS checks are transport-independent;
        # the local docker-image check only applies to local transport, ec2 verifies its AMI
        # inside make_host)
        if not a.skip_guards:
            checks = _guards.run_all(spec, grading_key=env["REVYL_GRADING_API_KEY"], agent_key=env["REVYL_AGENT_API_KEY"],
                                     expo_token=env.get("EXPO_TOKEN", ""), env=env,
                                     project_dir=staging / "seed" / "scaffold",
                                     check_images=(not a.dry_run and a.transport == "local"),
                                     need_harness_key=(a.mode != "p0"))
            print(_guards.format_checks(checks))
            if not all(ok for _, ok, _ in checks):
                if not a.dry_run:
                    # Tombstone the abort BEFORE deleting the staging
                    # dir — without this, a guard-aborted rollout leaves zero artifacts and
                    # abort counts are un-derivable.
                    out = run_dir
                    out.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(staging / "rollout.json", out / "rollout.json")
                    sd = json.loads((staging / "rollout.json").read_text(encoding="utf-8"))
                    failed = [name for name, ok, _ in checks if not ok]
                    (out / "attempts.jsonl").write_text(json.dumps({
                        "type": "end", "rollout_id": sd["rollout_id"], "task": sd["task"],
                        "contestant": sd["contestant"], "seed": sd["seed"],
                        "protocol_version": sd["protocol_version"],
                        "end_reason": "guard_abort", "k_final": 0, "failed_guards": failed,
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
                    }) + "\n", encoding="utf-8")
                    if run_dir is not None:
                        _campaigns.transition(run_dir, lifecycle="guard_abort", by="launch_rollout", failed_guards=failed)
                    shutil.rmtree(staging, ignore_errors=True)
                raise SystemExit("guard rails failed — aborting (nothing started)")
        if a.dry_run:
            log(f"dry run complete; host dir kept at {staging}")
            return 0

        # 5. up (on failure after an ec2 instance exists, terminate it — a leaked instance
        # bills until someone notices; ec2.json survives for post-mortem). In a campaign any
        # failure between `launched` and `running` is recorded as `launch_failed`: without
        # that terminal state a failed launch would look live forever.
        try:
            h = make_host(spec, staging, a.transport, env, skip_guards=a.skip_guards, host=a.host)
            try:
                seed_volume(spec, h)
                up(spec, h)
            except BaseException:
                if getattr(h, "persistent", False):
                    # an attached host outlives this rollout: take its containers and volumes
                    # down, or the next gate on the host contends with them
                    compose(h, "down", "-v", "--remove-orphans", check=False)
                h.close()
                raise
        except BaseException as e:
            if run_dir is not None:
                _campaigns.transition(run_dir, lifecycle="launch_failed", by="launch_rollout",
                                      error=f"{type(e).__name__}: {str(e)[:300]}")
            raise
    if run_dir is not None:
        _campaigns.transition(run_dir, lifecycle="running", by="launch_rollout",
                              host=getattr(h, "instance_id", None) or a.transport)
    if a.detach or a.mode == "p0":
        log(f"detached. agent shell:  docker exec -u agent -it {spec.rollout_id}-agent bash")
        log(f"finish with:            python launch_rollout.py --resume {spec.rollout_id}")
        return 0

    # 6–8
    _wait_and_collect(spec, h, env, transport=a.transport, run_dir=run_dir)
    down(spec, h, env, staging, keep_host=a.keep_host, run_dir=run_dir)
    return 0


def _wait_and_collect(spec: RolloutSpec, h, env: dict[str, str], *, transport: str, run_dir: Path | None) -> None:
    """Steps 6 and 7. In a campaign, anything that raises here (ssh dropping during the
    wait, a fetch failing, Ctrl-C) is recorded as `collect_failed` while the run is
    still live — otherwise the run would sit at `running` forever and its cell could never
    be relaunched. The host is not torn down, exactly as before: --resume finishes it."""
    try:
        wait_for_end(spec, h)
        collect(spec, h, env, transport=transport, run_dir=run_dir)
    except BaseException as e:
        if run_dir is not None and _campaigns.mark_fault(run_dir, "collect_failed",
                                                         error=f"{type(e).__name__}: {str(e)[:300]}"):
            log(f"recorded collect_failed for {spec.rollout_id}; host kept — inspect, then --resume {spec.rollout_id}")
        raise


if __name__ == "__main__":
    sys.exit(main())
