"""bench.hosts — the Host abstraction the transports plug into.

launch_rollout.py's steps 5-8 (up, wait, collect, down) only ever touch the rollout host
through these primitives, so the protocol logic (runner-ready polling, harness-exit
signalling, END detection, artifact collection) is written ONCE and runs unchanged on
both transports:

  LocalHost — v1: the "host" is runs/_hosts/<rollout_id>/ on this machine; run() is a
              plain subprocess, files are plain files.
  Ec2Host   — v2: one EC2 instance per rollout (AMI revyl-bench-host); the same
              directory lives at /rollouts/<rollout_id>/ on the instance, run() goes over
              ssh, file reads are `ssh cat`, directory transfer is a tar pipe (no rsync
              dependency on Windows).

Both hosts expose:
  abs(rel)                 → absolute path string ON THE HOST (for docker -v mounts)
  exists(rel) / read(rel)  → file probe / contents (None if missing)
  write(rel, text)         → create/overwrite a file
  unlink(rel)              → best-effort delete
  run(argv, ...)           → command on the host, cwd = the rollout dir
  put_dir(local_dir)       → upload the seeded rollout dir (no-op for LocalHost: the
                             seed dir IS the host dir)
  fetch(rel, local_dest)   → copy a file/dir from the host into a local path (missing → False)
  close()                  → release the host (LocalHost: nothing; Ec2Host: terminate)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path


# Paths whose content ends up INSIDE the baked images (Dockerfile.runner copies
# bench/ + runner/ + the snapshot helper; Dockerfile.agent copies container/). Anything else in runtime/ is
# read from the launch machine at run time and does not need an AMI rebuild.
# image/ holds the Dockerfiles (REVYL_VERSION pin, base images): a pin bump there changes
# what the runner/agent containers ARE, so it must force a re-bake too (without image/
# in the list, a Dockerfile-only CLI pin bump left the hash unchanged and the guard silent).
IMAGE_CODE_DIRS = ("runner", "bench", "container", "image", "host/final_evaluation_snapshot.sh")


def runtime_tree_hash(runtime_root: str | Path) -> str:
    """Fingerprint of the committed code that the runner/agent images are built from.

    Concatenates the git tree object ids of IMAGE_CODE_DIRS at HEAD (tree ids are content
    hashes, so two checkouts with byte-identical runner/ get the same id regardless of
    commit history) and hashes them — one short string to store in infra.json
    (`ami_runtime_tree`) and compare at launch. Only COMMITTED content counts: an
    uncommitted grade.py edit does not change HEAD's tree, which is why make_ami.sh refuses
    a dirty tree before calling this.
    """
    import hashlib
    root = Path(runtime_root)
    # runtime/ may be a subtree of a bigger repo: the tree path must
    # be relative to the git root, not to runtime/.
    prefix = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-prefix"],
                            check=True, capture_output=True, text=True).stdout.strip()
    ids = []
    for d in IMAGE_CODE_DIRS:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", f"HEAD:{prefix}{d}"],
                             check=True, capture_output=True, text=True).stdout.strip()
        ids.append(f"{d}={out}")
    return hashlib.sha256("|".join(ids).encode()).hexdigest()[:16]


class LocalHost:
    """v1 transport: rollout dir on this machine, docker on this machine."""

    def __init__(self, root: Path):
        self.root = root

    def abs(self, rel: str) -> str:
        return str((self.root / rel).resolve())

    def exists(self, rel: str) -> bool:
        return (self.root / rel).exists()

    def read(self, rel: str) -> str | None:
        p = self.root / rel
        if not p.exists():
            return None
        return p.read_text(encoding="utf-8", errors="replace")

    def write(self, rel: str, text: str) -> None:
        (self.root / rel).write_text(text, encoding="utf-8")

    def unlink(self, rel: str) -> None:
        try:
            (self.root / rel).unlink()
        except FileNotFoundError:
            pass

    def run(self, argv: list[str], *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
        return subprocess.run(argv, cwd=str(self.root), check=check, text=True,
                              capture_output=capture, encoding="utf-8", errors="replace")

    def put_dir(self, local_dir: Path) -> None:
        assert Path(local_dir).resolve() == self.root.resolve(), "LocalHost seeds in place"

    def fetch(self, rel: str, dest: Path) -> bool:
        src = self.root / rel
        if not src.exists():
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dest)
        return True

    def close(self) -> None:
        pass


class Ec2Host:
    """v2 transport: one disposable EC2 instance per rollout.

    Instance lifecycle is owned here: launch() → use → close() terminates. The instance
    is tagged bench:rollout=<rollout_id> so a leak is findable with one describe-instances
    call. All state the rollout produces lives under /rollouts/<rollout_id>/ (same layout
    as LocalHost) and MUST be fetch()ed before close() — termination destroys the volume.
    """

    def __init__(self, rollout_id: str, infra: dict, *, aws_bin: str = "aws", profile: str | None = None,
                 log=print):
        self.rollout_id = rollout_id
        self.infra = infra
        self.aws_bin = aws_bin
        self.profile = profile
        self.log = log
        self.instance_id: str | None = None
        self.ip: str | None = None
        self.persistent = False            # attach()ed to a host that outlives this rollout
        self.rroot = f"/rollouts/{rollout_id}"
        self._pem = str(Path(infra["pem_path"].replace("~", str(Path.home()))))

    # ---- aws / ssh plumbing -----------------------------------------------------------
    def _aws(self, *args: str) -> str:
        cmd = [self.aws_bin]
        if self.profile:
            cmd += ["--profile", self.profile]
        cmd += ["--region", self.infra["region"], *args]
        p = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8")
        return p.stdout.strip()

    def _ssh_base(self) -> list[str]:
        # No host-key pinning: instances are throwaway VMs in the private VPC, and their
        # IPs recycle fast under campaign churn. accept-new hard-rejects a reused IP with
        # a new key, so the launcher polls a perfectly healthy sshd forever and then
        # terminates it as "never came up" — a known_hosts full of stale keys reads exactly
        # like a run of boot flakes.
        return ["ssh", "-i", self._pem, "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR",
                "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=15",
                f"ubuntu@{self.ip}"]

    def _ssh(self, remote_cmd: str, *, check: bool = True, capture: bool = True,
             input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
        return subprocess.run([*self._ssh_base(), remote_cmd], check=check, capture_output=capture,
                              input=input_bytes)

    # ---- lifecycle --------------------------------------------------------------------
    def launch(self, *, instance_type: str | None = None, ssh_wait_s: int = 600,
               _retry: bool = True) -> None:
        it = instance_type or self.infra.get("instance_type", "m6a.xlarge")
        ami = self.infra.get("ami_id")
        if not ami:
            raise RuntimeError("infra.json has no ami_id — run host/ec2/make_ami.sh first")
        self.log(f"[ec2] run-instances {it} ami={ami}")
        out = self._aws("ec2", "run-instances", "--image-id", ami, "--instance-type", it,
                        "--subnet-id", self.infra["subnet_id"],
                        "--security-group-ids", self.infra["security_group_id"],
                        "--key-name", self.infra["key_name"],
                        "--iam-instance-profile", f"Name={self.infra['instance_profile']}",
                        "--instance-initiated-shutdown-behavior", "terminate",
                        "--tag-specifications",
                        f"ResourceType=instance,Tags=[{{Key=Name,Value=revyl-bench-{self.rollout_id}}},"
                        f"{{Key=bench:rollout,Value={self.rollout_id}}}]",
                        "--query", "Instances[0].InstanceId", "--output", "text")
        self.instance_id = out
        self._aws("ec2", "wait", "instance-running", "--instance-ids", self.instance_id)
        # REVYL_BENCH_SSH_IP=private → reach the rollout host by its VPC-internal address.
        # Used by the control host (which sits in the same VPC and has no route to public IPs
        # blessed by the SG); the default for a workstation outside the VPC stays "public".
        # An env var, not an infra.json key, because this is a per-machine setting and
        # infra.json may be shared between machines — it would ping-pong between a
        # workstation and the control host.
        ip_field = ("PrivateIpAddress" if os.environ.get("REVYL_BENCH_SSH_IP") == "private"
                    else "PublicIpAddress")
        self.ip = self._aws("ec2", "describe-instances", "--instance-ids", self.instance_id,
                            "--query", f"Reservations[0].Instances[0].{ip_field}", "--output", "text")
        self.log(f"[ec2] {self.instance_id} running at {self.ip}; waiting for ssh")
        deadline = time.time() + ssh_wait_s
        while time.time() < deadline:
            if self._ssh("true", check=False).returncode == 0:
                break
            time.sleep(10)
        else:
            # First boots EBS-lazy-restore the AMI snapshot; under burst launches some
            # instances take >5 min to sshd and were being abandoned seconds from ready.
            # One relaunch on a fresh instance
            # absorbs the tail; a second failure is a real environment problem.
            self.log(f"[ec2] ssh to {self.ip} never came up — terminating {self.instance_id}"
                     + (" and relaunching once" if _retry else ""))
            self._aws("ec2", "terminate-instances", "--instance-ids", self.instance_id)
            if _retry:
                self.launch(instance_type=instance_type, ssh_wait_s=ssh_wait_s, _retry=False)
                return
            raise RuntimeError(f"ssh to {self.ip} never came up (after one relaunch)")
        self._ssh(f"mkdir -p {self.rroot}")
        self.log("[ec2] ssh ready")

    # ---- Host interface ---------------------------------------------------------------
    def abs(self, rel: str) -> str:
        return f"{self.rroot}/{rel}"

    def exists(self, rel: str) -> bool:
        return self._ssh(f"test -e {self.abs(rel)}", check=False).returncode == 0

    def read(self, rel: str) -> str | None:
        p = self._ssh(f"cat {self.abs(rel)}", check=False)
        if p.returncode != 0:
            return None
        return p.stdout.decode("utf-8", errors="replace")

    def write(self, rel: str, text: str) -> None:
        self._ssh(f"cat > {self.abs(rel)}", input_bytes=text.encode("utf-8"))

    def unlink(self, rel: str) -> None:
        self._ssh(f"rm -f {self.abs(rel)}", check=False)

    def run(self, argv: list[str], *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
        # naive shell-quote is fine here: our argv values are ids/paths we mint ourselves
        quoted = " ".join("'" + a.replace("'", "'\\''") + "'" for a in argv)
        p = self._ssh(f"cd {self.rroot} && {quoted}", check=check, capture=True)
        if capture:
            # normalize to text like LocalHost.run(capture=True)
            p.stdout = p.stdout.decode("utf-8", errors="replace") if isinstance(p.stdout, bytes) else p.stdout
            p.stderr = p.stderr.decode("utf-8", errors="replace") if isinstance(p.stderr, bytes) else p.stderr
        return p

    def put_dir(self, local_dir: Path) -> None:
        """Upload the seeded rollout dir via tar pipe (env files keep their bytes; the
        0600 modes are re-applied remotely because Windows tar can't carry them)."""
        self.log(f"[ec2] uploading {local_dir} → {self.rroot}")
        buf = _tar_bytes(local_dir)
        self._ssh(f"tar -C {self.rroot} -xzf -", input_bytes=buf)
        self._ssh(f"chmod 600 {self.rroot}/runner.env {self.rroot}/agent.env 2>/dev/null || true")

    def fetch(self, rel: str, dest: Path) -> bool:
        # sudo: the runner container (root) writes log/transcript/* and
        # device-sessions.json with their source 600 modes, so the ubuntu ssh user
        # cannot read them and tar hard-fails rc=2 (a lost log/ fetch looks like tar's
        # rc=1 "file changed" warning but is this). rc=1 warnings still tolerated.
        p = self._ssh(f"cd {self.rroot} && sudo tar -czf - {rel}", check=False)
        if p.returncode > 1 or not p.stdout:
            return False
        # extract into a temp dir then move, so `rel` lands exactly at `dest`
        with tempfile.TemporaryDirectory() as td:
            import io
            with tarfile.open(fileobj=io.BytesIO(p.stdout), mode="r:gz") as tf:
                tf.extractall(td, filter="data")
            src = Path(td) / rel
            if not src.exists():
                return False
            dest.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dest)
        return True

    def attach(self, ip: str, instance_id: str | None = None, *, ssh_wait_s: int = 60) -> None:
        """Use a host that already runs instead of launching one: the rollout gets
        /rollouts/<id> on it and close() removes that dir, never the instance. Many short
        rollouts on one m6a.xlarge instead of one instance each."""
        self.ip, self.instance_id, self.persistent = ip, instance_id, True
        deadline = time.time() + ssh_wait_s
        while self._ssh("true", check=False).returncode != 0:
            if time.time() > deadline:
                raise RuntimeError(f"ssh to the attached host {ip} does not answer")
            time.sleep(5)
        self._ssh(f"mkdir -p {self.rroot}")
        self.log(f"[ec2] attached {instance_id or ''} running at {ip}")

    def close(self) -> None:
        if self.persistent:
            self.log(f"[ec2] leaving {self.instance_id or self.ip} up; removing {self.rroot}")
            self._ssh(f"sudo rm -rf {self.rroot}", check=False)
            return
        if self.instance_id:
            self.log(f"[ec2] terminating {self.instance_id}")
            self._aws("ec2", "terminate-instances", "--instance-ids", self.instance_id)
            self.instance_id = None


def _tar_bytes(local_dir: Path) -> bytes:
    """gzip tar of local_dir's CONTENTS (not the dir itself), in memory — host dirs are
    a few MB (scaffold sans node_modules + templates), so memory is fine."""
    import io
    bio = io.BytesIO()
    with tarfile.open(fileobj=bio, mode="w:gz") as tf:
        for p in sorted(Path(local_dir).rglob("*")):
            tf.add(p, arcname=str(p.relative_to(local_dir)))
    return bio.getvalue()


def load_infra(runtime_root: Path) -> dict:
    p = runtime_root / "host" / "ec2" / "infra.json"
    if not p.exists():
        raise RuntimeError("host/ec2/infra.json missing — run host/ec2/bootstrap.sh first")
    return json.loads(p.read_text(encoding="utf-8"))
