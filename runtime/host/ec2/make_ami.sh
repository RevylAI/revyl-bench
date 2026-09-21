#!/usr/bin/env bash
# host/ec2/make_ami.sh — build the `revyl-bench-host` AMI.
#
# Launches a throwaway Ubuntu 24.04 x86_64 builder in the bench VPC, installs docker +
# compose, copies THIS repo up (secrets excluded), builds the runner + agent images ON the
# instance (uploading a repo tarball of a few MB beats uploading ~5GB of built images from
# a workstation's uplink), snapshots it into an AMI, terminates the builder, and writes the
# ami_id back into infra.json.
#
# x86_64 is required: the rollout images are built/tested amd64 on the workstation, and the
# transport must run byte-identical containers — so m6a/c6i instance families, never
# Graviton.
#
# Rebuild triggers — ANY change to what the images contain:
#   - harness pin bump in contestants/registry.yaml, Dockerfile change
#   - ANY commit touching runner/, bench/ or container/ (Dockerfile.runner does
#     `COPY bench /app/bench` + `COPY runner /app/runner`; the agent image copies
#     container/). The runner image is baked into the AMI and launch_rollout.py never
#     rebuilds or re-pulls it on the host, so a grading-logic fix that stays in git only
#     never runs, and nothing reports it.
# To make that trap impossible to repeat, this script records the git tree hash of
# runner/+bench/+container/+image/ it baked as `ami_runtime_tree` in infra.json, and
# launch_rollout.py aborts an ec2 launch whose checkout has a different hash.
#
# Usage:  AWS_PROFILE=<admin-profile> ./host/ec2/make_ami.sh        # workstation (SSO)
#         REVYL_BENCH_SSH_IP=private ./host/ec2/make_ami.sh           # control host (IAM role)
#         AWS_BIN=/path/to/aws.exe AWS_PROFILE=<admin-profile> ./host/ec2/make_ami.sh
# REVYL_BENCH_SSH_IP=private reaches the builder by its VPC address (same convention as
# bench/hosts.py) — required from the control host, whose public egress IP is not in the SG.
set -euo pipefail
cd "$(dirname "$0")"
# Ubuntu ships python3 only; a Windows workstation's Git Bash resolves `python`.
command -v python >/dev/null 2>&1 || python() { python3 "$@"; }
RUNTIME_ROOT="$(cd ../.. && pwd)"

# The fingerprint only describes COMMITTED code, so refuse to bake a dirty tree: the AMI
# would carry code no git hash names, and the launch-time guard would pass on a checkout
# that does not match what actually runs.
if [ -n "$(git -C "$RUNTIME_ROOT" status --porcelain -- runner bench container image provision contestants)" ]; then
  echo "FATAL: uncommitted changes under runtime/{runner,bench,container,image,provision,contestants} — commit first" >&2
  git -C "$RUNTIME_ROOT" status --short -- runner bench container image provision contestants >&2
  exit 1
fi
RUNTIME_TREE=$(python -c "import sys; sys.path.insert(0, r'$RUNTIME_ROOT'); from bench.hosts import runtime_tree_hash; print(runtime_tree_hash(r'$RUNTIME_ROOT'))")
RUNTIME_SHA=$(git -C "$RUNTIME_ROOT" rev-parse HEAD)
echo "== runtime code fingerprint: tree=$RUNTIME_TREE commit=$RUNTIME_SHA"

AWS_BIN="${AWS_BIN:-aws}"
command -v "$AWS_BIN" >/dev/null 2>&1 || AWS_BIN="$LOCALAPPDATA/Programs/Amazon/AWSCLIV2/aws.exe"
# Must be an absolute path: the aws() wrapper below calls "$AWS_BIN", and if that is the
# bare word `aws` the wrapper calls ITSELF — infinite recursion, exit 139 (hit on the
# control host; a Windows workstation never sees it because AWS_BIN resolves to aws.exe).
AWS_BIN="$(command -v "$AWS_BIN")" || { echo "FATAL: aws cli not found" >&2; exit 1; }
# Same rule as launch_rollout.py::_aws_cli: use AWS_PROFILE if set, otherwise run
# profile-less (the control host authenticates via its IAM instance role — forcing a
# profile there fails with "profile not found"). Workstation users export AWS_PROFILE.
[ -n "${AWS_PROFILE:-}" ] && export AWS_PROFILE
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-$(python -c "import json;print(json.load(open('infra.json'))['region'])")}"
aws() { "$AWS_BIN" "$@"; }

j() { python -c "import json;print(json.load(open('infra.json'))['$1'])"; }
SUBNET_ID=$(j subnet_id); SG_ID=$(j security_group_id); KEY_NAME=$(j key_name)
PEM=$(eval echo "$(j pem_path)")
# The builder is a throwaway instance in the bench VPC, and the VPC reuses private IPs: it
# can come up on an address a previous throwaway had left in the
# control host's known_hosts, and `accept-new` refused the CHANGED key ("REMOTE HOST
# IDENTIFICATION HAS CHANGED"), killing the bake before the first ssh. Its host key
# carries no trust we rely on — the pem is what authenticates us to it — so do not
# record it and do not check it.
SSH=(ssh -i "$PEM" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=10 -o User=ubuntu)

echo "== base AMI (Ubuntu 24.04 amd64, canonical-owned)"
BASE_AMI=$(aws ec2 describe-images --owners 099720109477 \
  --filters "Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*" \
            "Name=state,Values=available" \
  --query "sort_by(Images, &CreationDate)[-1].ImageId" --output text)
echo "   base=$BASE_AMI"

echo "== launch builder (m6a.xlarge, 60GB gp3 — image builds need npm + docker layer room)"
IID=$(aws ec2 run-instances --image-id "$BASE_AMI" --instance-type m6a.xlarge \
  --subnet-id "$SUBNET_ID" --security-group-ids "$SG_ID" --key-name "$KEY_NAME" \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":60,"VolumeType":"gp3","DeleteOnTermination":true}}]' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=revyl-bench-ami-builder},{Key=bench,Value=true}]' \
  --query "Instances[0].InstanceId" --output text)
# The control-host role also lacks ec2:TerminateInstances — if this fails the
# builder (m6a.xlarge, ~$0.17/h) keeps running until someone with SSO terminates it, so
# shout the instance id rather than hiding the error.
trap 'echo "== terminating builder $IID"; aws ec2 terminate-instances --instance-ids "$IID" >/dev/null \
  || echo "!! could not terminate builder $IID — terminate it by hand from an SSO session" >&2' EXIT
aws ec2 wait instance-running --instance-ids "$IID"
# same convention as bench/hosts.py: the control host sits inside the VPC and its public
# egress IP is not in the SG, so it must reach the builder by private address.
IP_FIELD=PublicIpAddress; [ "${REVYL_BENCH_SSH_IP:-}" = "private" ] && IP_FIELD=PrivateIpAddress
IP=$(aws ec2 describe-instances --instance-ids "$IID" \
  --query "Reservations[0].Instances[0].$IP_FIELD" --output text)
echo "   builder=$IID ip=$IP"

echo "== wait for ssh"
for i in $(seq 1 30); do "${SSH[@]}" "$IP" true 2>/dev/null && break; sleep 10; done
"${SSH[@]}" "$IP" true

echo "== install docker + compose"
"${SSH[@]}" "$IP" 'sudo bash -s' <<'EOS'
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -yq ca-certificates curl git python3 unzip
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu noble stable" > /etc/apt/sources.list.d/docker.list
apt-get update -q
apt-get install -yq docker-ce docker-ce-cli containerd.io docker-compose-plugin
usermod -aG docker ubuntu
# aws cli for the (optional, later) host-side S3 sync via the instance profile
curl -fsSL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o /tmp/awscliv2.zip
unzip -q /tmp/awscliv2.zip -d /tmp && /tmp/aws/install && rm -rf /tmp/aws /tmp/awscliv2.zip
mkdir -p /rollouts && chown ubuntu:ubuntu /rollouts
EOS

echo "== upload repo (secrets + runs + scaffold node_modules excluded) + build images"
tar -C "$RUNTIME_ROOT" -czf - \
  --exclude='.env*' --exclude='runs' --exclude='.git' --exclude='__pycache__' \
  --exclude='node_modules' --exclude='*.pem' \
  . | "${SSH[@]}" "$IP" 'mkdir -p ~/revyl-bench-runtime && tar -C ~/revyl-bench-runtime -xzf -'
# build_images.sh reads contestants/registry.yaml with pyyaml.
# Every harness in the registry is built (no args): a contestant whose harness has no
# image cannot run (launch asks for revyl-bench-agent:<harness>-sdk<NN>), and a registry
# entry is only added once its install line is real. A broken install line fails the
# bake here, which is the right place to find out.
"${SSH[@]}" "$IP" 'sudo apt-get install -yq python3-yaml'
"${SSH[@]}" "$IP" 'cd ~/revyl-bench-runtime && python() { python3 "$@"; }; export -f python && bash provision/build_images.sh'
# every harness in the registry must now have an image for both SDKs, or the bake is
# useless for that contestant (the launcher refuses: "AMI lacks {agent: …}"). Found
# 2026-09-06: this line named claude-code and opencode only, so the codex image was
# never built and the first codex rollout died at launch.
"${SSH[@]}" "$IP" 'cd ~/revyl-bench-runtime && python3 - <<"PY"
import re, subprocess, sys, yaml
reg = yaml.safe_load(open("contestants/registry.yaml", encoding="utf-8"))
want = sorted({f"revyl-bench-agent:{e["harness"]}-sdk{sdk}" for e in reg["contestants"].values() for sdk in (56, 57)})
have = set(subprocess.run(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"], capture_output=True, text=True).stdout.split())
missing = [t for t in want if t not in have]
print("agent images:", ", ".join(want))
if missing:
    sys.exit(f"FATAL: agent image(s) not built: {missing}")
PY'
"${SSH[@]}" "$IP" 'docker images | grep revyl-bench'

echo "== snapshot AMI"
NAME="revyl-bench-host-$(date -u +%Y%m%d-%H%M%S)"
# No --tag-specifications here: the control host's `revyl-bench-control` role has
# ec2:CreateImage but not ec2:CreateTags on image/*, and an inline tag spec makes the
# whole CreateImage call fail (observed after a 25-min build). Tag best-effort after.
AMI_ID=$(aws ec2 create-image --instance-id "$IID" --name "$NAME" \
  --description "revyl-bench rollout host: docker + runner/agent images pre-built (runtime tree $RUNTIME_TREE)" \
  --query ImageId --output text)
aws ec2 create-tags --resources "$AMI_ID" --tags Key=Name,Value=revyl-bench-host \
  || echo "   (warn: could not tag $AMI_ID — role lacks ec2:CreateTags; harmless)"
echo "   ami=$AMI_ID ($NAME) — waiting for available"
# `aws ec2 wait image-available` gives up after 10 min (40×15s); a 60GB gp3 AMI snapshot
# routinely takes 15-30 min (observed 2026-08-20: first build hit the cap while the AMI
# was healthy and merely pending). Poll for up to 45 min instead. The builder can
# terminate while this waits — EBS snapshot copying continues after instance deletion.
for i in $(seq 1 90); do
  STATE=$(aws ec2 describe-images --image-ids "$AMI_ID" --query "Images[0].State" --output text)
  [ "$STATE" = "available" ] && break
  if [ "$STATE" = "failed" ] || [ "$STATE" = "error" ]; then
    echo "FATAL: AMI $AMI_ID entered state $STATE" >&2; exit 1
  fi
  sleep 30
done
[ "$STATE" = "available" ] || { echo "FATAL: AMI $AMI_ID still $STATE after 45 min" >&2; exit 1; }

# ami_runtime_tree / ami_runtime_commit: what code this AMI carries. launch_rollout.py's
# ec2 pre-flight compares ami_runtime_tree to the checkout (bench.hosts.runtime_tree_hash)
# and aborts on mismatch — "pinning is not enough, verify it stuck".
python - "$AMI_ID" "$RUNTIME_TREE" "$RUNTIME_SHA" <<'PY'
import json, sys
d = json.load(open("infra.json"))
d["ami_id"] = sys.argv[1]
d["ami_runtime_tree"] = sys.argv[2]
d["ami_runtime_commit"] = sys.argv[3]
json.dump(d, open("infra.json", "w"), indent=2)
print(open("infra.json").read())
PY
echo "== done (builder terminates via trap)"
