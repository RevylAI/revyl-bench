"""Grade the host-frozen deadline snapshot without changing the agent workspace."""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import tarfile
import time
from pathlib import Path

from bench import attempts

from runner.grade import Grader, _atomic_write


def wait_for_deadline_marker(control: Path) -> dict:
    marker = control / "final_evaluation.json"
    wait_until = time.monotonic() + 180
    while not marker.exists():
        if time.monotonic() >= wait_until:
            raise RuntimeError("deadline source snapshot was not delivered")
        time.sleep(1)
    return json.loads(marker.read_text(encoding="utf-8"))


def source_fingerprint(path: Path) -> tuple:
    """Compare source bytes, paths, executable bits and links, ignoring tar timestamps."""
    files = {}
    with tarfile.open(path, "r:gz") as archive:
        for member in archive:
            if member.isdir():
                continue
            if member.name in files or not (member.isfile() or member.issym()):
                raise ValueError("unsupported or duplicate final source entry")
            content = (hashlib.sha256(archive.extractfile(member).read()).hexdigest()
                       if member.isfile() else member.linkname)
            files[member.name] = (member.type, member.mode & 0o777, content)
    return tuple(sorted(files.items()))


def grade_final_snapshot(spec, *, control: Path, log_dir: Path, work_dir: Path,
                         history: list[dict], rollout_started: float,
                         grading_key: str, expo_token: str, log=print, agent_mailbox: Path | None = None) -> dict:
    # Host termination and snapshot happen independently of a possibly busy grader.
    # A restart after the completed append must not grade the final source twice.
    completed = [r for r in history if r.get("origin") == "runner_final"]
    if completed:
        return completed[-1]
    evidence = wait_for_deadline_marker(control)
    if evidence.get("status") != "ready" or evidence.get("reason") not in {"wall_clock", "malformed_tool_call", "policy_stop"}:
        raise RuntimeError("deadline source snapshot failed: " + str(evidence.get("error", "invalid marker")))
    deadline = rollout_started + spec.caps.wall_clock_min * 60
    if evidence.get("rollout_id") != spec.rollout_id:
        raise ValueError("deadline snapshot rollout identity mismatch")
    for key in ("deadline_at", "frozen_at"):
        value = evidence.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("invalid deadline snapshot timestamp")
    trigger = evidence["reason"]
    anchor = evidence.get("stopped_at") if trigger in {"malformed_tool_call", "policy_stop"} else deadline
    if (isinstance(anchor, bool) or not isinstance(anchor, (int, float)) or not math.isfinite(anchor)
            or not rollout_started <= anchor <= deadline
            or abs(evidence["deadline_at"] - deadline) > 1
            or not anchor <= evidence["frozen_at"] <= anchor + 60):
        raise ValueError("deadline snapshot was not frozen at the declared deadline")
    source = log_dir / "final-evaluation" / "source.tar.gz"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != evidence.get("sha256"):
        raise ValueError("deadline source digest mismatch")
    if not (log_dir / "final-evaluation/workspace.bundle").is_file():
        raise ValueError("final workspace bundle missing before grading")
    bundle = log_dir / "final-evaluation/workspace.bundle"
    shutil.copyfile(bundle, log_dir / "workspace.bundle")
    k = max((r["k"] for r in history), default=0) + 1
    mailbox = log_dir / "final-evaluation"
    submit = mailbox / "submit"
    submit.mkdir(parents=True, exist_ok=True)
    (mailbox / "feedback").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, submit / f"s{k}.tar.gz")
    _atomic_write(submit / f"s{k}.request.json", json.dumps({
        "rollout_id": spec.rollout_id, "k": k, "sha256": digest,
        "commit_id": evidence.get("commit_id", ""),
    }))
    metadata = {
        "origin": "runner_final", "trigger": trigger,
        "final_evaluation_enabled": True, "source_snapshot_sha256": digest,
        "deadline_at": evidence["deadline_at"], "frozen_at": evidence["frozen_at"],
    }
    if trigger in {"malformed_tool_call", "policy_stop"}:
        metadata["stopped_at"] = anchor
    if trigger == "malformed_tool_call":
        metadata["formatting_failure"] = "malformed_tool_call"
    if agent_mailbox is not None:
        fingerprint = source_fingerprint(source)
        for prior in reversed(history):
            summary = prior.get("blocks_summary") or {}
            fraction, decided = summary.get("fraction"), summary.get("decided")
            reliable = (prior.get("failure_kind") in {"build_failed", "app_crash"} or (
                not prior.get("failure_kind") and type(decided) is int and decided > 0
                and decided == summary.get("total") and type(fraction) in (int, float)
                and math.isfinite(fraction) and 0 <= fraction <= 1))
            previous = agent_mailbox / "submit" / f"s{prior['k']}.tar.gz"
            if not reliable or not previous.is_file():
                continue
            if hashlib.sha256(previous.read_bytes()).hexdigest() != prior.get("tree_sha256"):
                continue
            try:
                same_source = source_fingerprint(previous) == fingerprint
            except (tarfile.TarError, ValueError):
                continue  # An uncomparable previous submission does not block a fresh grade.
            if same_source:
                reused = {**prior, **metadata, "k": k, "reused_from_k": prior["k"], "reused_at": attempts.now_iso(),
                          "commit_id": evidence.get("commit_id", ""), "tree_sha256": digest}
                attempts.append(log_dir / "attempts.jsonl", reused)
                log(f"[runner] reused reliable s{prior['k']} grade for identical final source")
                return reused
    grader = Grader(spec, mailbox=mailbox, log_dir=log_dir, work_dir=work_dir,
                    grading_key=grading_key, expo_token=expo_token, log=log,
                    final_evaluation=metadata)
    return grader.grade_submission(k, history=history, rollout_started=rollout_started)
