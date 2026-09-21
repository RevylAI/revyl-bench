#!/usr/bin/env bash
# host/ec2/setup-control.sh — provision the control host (runs ON the host, as ubuntu).
#
# Installs exactly what launch_rollout.py --transport ec2 needs on the LAUNCH machine
# (verified against the code 2026-08-21):
#   - Python 3.12 + PyYAML   (tomllib in bench/config.py needs >= 3.11; PyYAML is the
#                             only non-stdlib import; 24.04's system python is 3.12)
#   - awscli v2              (bench/hosts.py + the s3 sync; apt ships the ancient v1)
#   - openssh-client         (Ec2Host is tar-over-ssh; no scp/rsync/docker needed —
#                             for the ec2 transport ALL docker calls go over ssh to the
#                             rollout host, and check_images is skipped)
#   - node 22 + eas-cli@22.0.0  (guards run `eas whoami` under EXPO_TOKEN; pins match
#                             image/Dockerfile.runner)
#   - revyl CLI at the pin   (guards make 5 revyl calls + assert the version; teardown
#                             stops device sessions). The pin is runtime/image/REVYL_CLI_VERSION;
#                             this script runs BEFORE the clone exists, so pass it explicitly:
#                             `bash setup-control.sh $(cat runtime/image/REVYL_CLI_VERSION)`
#                             (or the same value in the REVYL_VERSION env var).
#   - tailscale              (OPTIONAL access path: with it the SG needs zero internet
#                             ingress. `sudo tailscale up` stays manual — it needs your
#                             auth key; skip it and keep ssh over the workstation-IP rule)
#   - git + a read-only deploy key for the repository (REVYL_BENCH_REPO)
#
# Idempotent: every step is skip-if-present, so re-running after adding the deploy key
# to GitHub finishes the clone. Secrets are NOT handled here — runtime/.env and
# ~/.ssh/revyl-bench.pem are scp'd by hand afterwards (never via user-data: user-data
# is readable through the instance metadata service).
#
# Usage (from your workstation; <host> = the control host's address):
#   scp -i ~/.ssh/revyl-bench.pem runtime/host/ec2/setup-control.sh ubuntu@<host>:
#   ssh -i ~/.ssh/revyl-bench.pem ubuntu@<host> bash setup-control.sh $(cat runtime/image/REVYL_CLI_VERSION)
set -euo pipefail

echo "== apt base"
sudo DEBIAN_FRONTEND=noninteractive apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q python3-yaml git tmux unzip curl

echo "== awscli v2"
if ! command -v aws >/dev/null 2>&1; then
  curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
  unzip -q /tmp/awscliv2.zip -d /tmp/awscliv2
  sudo /tmp/awscliv2/aws/install
  rm -rf /tmp/awscliv2 /tmp/awscliv2.zip
fi
aws --version

echo "== node 22 + eas-cli"
if ! command -v node >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q nodejs
fi
command -v eas >/dev/null 2>&1 || sudo npm i -g eas-cli@22.0.0
echo "   node=$(node --version) eas=$(eas --version 2>/dev/null | head -1)"

# The pin lives in runtime/image/REVYL_CLI_VERSION; resolve it from $1, then REVYL_VERSION, then a
# sibling checkout if this script is run from inside one. Anything else is a hard error —
# an unpinned install here would drift from the images the guards are supposed to match.
PIN_FILE="$(dirname "$0")/../../image/REVYL_CLI_VERSION"
# `|| true` inside the substitution: under `set -e` a failed `[ -f … ]` would otherwise abort the
# script silently BEFORE the FATAL line below (reproduced in review, 2026-08-25).
REVYL_VERSION="${1:-${REVYL_VERSION:-$( { [ -f "$PIN_FILE" ] && tr -d '[:space:]' < "$PIN_FILE"; } || true )}}"
[ -n "$REVYL_VERSION" ] || { echo "FATAL: pass the revyl CLI pin: bash setup-control.sh <pin> (= the one line in runtime/image/REVYL_CLI_VERSION)" >&2; exit 1; }
echo "== revyl cli (pinned $REVYL_VERSION, same install as the images)"
if ! revyl --version 2>/dev/null | grep -Fxq "revyl version $REVYL_VERSION"; then
  curl -fsSL https://revyl.com/install.sh | sudo REVYL_VERSION="$REVYL_VERSION" REVYL_INSTALL_DIR=/usr/local/bin sh
fi
revyl --version | grep -Fx "revyl version $REVYL_VERSION" || { echo "FATAL: revyl CLI != $REVYL_VERSION" >&2; exit 1; }

echo "== tailscale"
command -v tailscale >/dev/null 2>&1 || curl -fsSL https://tailscale.com/install.sh | sh
tailscale status >/dev/null 2>&1 || \
  echo "   NOT CONNECTED — run: sudo tailscale up   (auth key from the admin console)"

echo "== deploy key + repo clone"
DEPLOY_KEY="$HOME/.ssh/revyl-bench-deploy"
if [ ! -f "$DEPLOY_KEY" ]; then
  ssh-keygen -t ed25519 -N "" -C "revyl-bench-control deploy key" -f "$DEPLOY_KEY"
fi
# Route github.com through the deploy key without touching any other ssh identity
if ! grep -q "revyl-bench-deploy" "$HOME/.ssh/config" 2>/dev/null; then
  mkdir -p "$HOME/.ssh"
  # accept-new: first-ever connect to github.com must not die on the host-key prompt
  # (this script runs non-interactively; observed "Host key verification failed")
  printf "\nHost github.com\n  IdentityFile %s\n  IdentitiesOnly yes\n  StrictHostKeyChecking accept-new\n" "$DEPLOY_KEY" >> "$HOME/.ssh/config"
  chmod 600 "$HOME/.ssh/config"
fi
# REVYL_BENCH_REPO: the repository this host runs from (owner/name). Set it to your fork
# if you run from one (your fork is where your provisioned task.toml ids are committed);
# unset, it is the public repository.
REPO="${REVYL_BENCH_REPO:-RevylAI/revyl-bench}"
if [ ! -d "$HOME/revyl-bench" ]; then
  # The public repository is cloned anonymously over https: a deploy key can only be added
  # by an admin of the repository, which nobody outside Revyl is for RevylAI/revyl-bench —
  # an ssh clone of the default would fail for every outside user. The ssh + deploy-key
  # path below is for REVYL_BENCH_REPO = your own (possibly private) fork.
  if [ -z "${REVYL_BENCH_REPO:-}" ] && git clone "https://github.com/$REPO.git" "$HOME/revyl-bench" 2>/dev/null; then
    echo "   cloned ~/revyl-bench ($REPO, https)"
  elif git clone "git@github.com:$REPO.git" "$HOME/revyl-bench" 2>/dev/null; then
    echo "   cloned ~/revyl-bench ($REPO)"
  else
    echo "   CLONE FAILED — add this READ-ONLY deploy key to $REPO, then re-run:"
    echo "     (workstation) gh repo deploy-key add - --repo $REPO --title revyl-bench-control <<< '$(cat "$DEPLOY_KEY.pub")'"
    echo "   pubkey: $(cat "$DEPLOY_KEY.pub")"
  fi
fi

echo "== environment"
# private-IP path: the control host reaches rollout hosts by VPC-internal address (bench/hosts.py
# reads this env var; the SG's self-referencing rule from make_control.sh allows it)
grep -q "REVYL_BENCH_SSH_IP" "$HOME/.bashrc" || \
  echo 'export REVYL_BENCH_SSH_IP=private' >> "$HOME/.bashrc"
# The instance role must win the credential chain: never set AWS_PROFILE on this host.
# (bootstrap.sh/make_ami.sh take it from the environment on a WORKSTATION; if either ever
# runs here, invoke as `AWS_PROFILE= ./script.sh`.)
if grep -q "AWS_PROFILE" "$HOME/.bashrc"; then
  echo "   WARNING: AWS_PROFILE set in ~/.bashrc — remove it, the instance role must be used"
fi

echo
echo "== remaining manual steps"
echo "1. sudo tailscale up                       # optional; only if you use tailscale for access"
echo "2. add the deploy key + re-run this script # if the clone failed above"
echo "3. secrets, from your workstation:"
echo "     scp -i ~/.ssh/revyl-bench.pem <repo>/runtime/.env ubuntu@<host>:revyl-bench/runtime/.env"
echo "     scp -i ~/.ssh/revyl-bench.pem ~/.ssh/revyl-bench.pem ubuntu@<host>:.ssh/"
echo "     ssh ... 'chmod 600 ~/revyl-bench/runtime/.env ~/.ssh/revyl-bench.pem'"
echo "4. validate: aws sts get-caller-identity   # assumed-role/revyl-bench-control/i-..."
echo "5. cd ~/revyl-bench && python3 runtime/launch_rollout.py --task ... --transport ec2 --dry-run"
