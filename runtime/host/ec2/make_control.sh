#!/usr/bin/env bash
# host/ec2/make_control.sh — one-time creation of the CONTROL HOST (v2.0 control plane).
#
# The control host is a small always-on Ubuntu instance inside the bench VPC that runs
# launch_rollout.py --transport ec2 under an IAM instance role, replacing a workstation as
# the launch environment. Two problems it removes: AWS SSO credentials expiring mid-
# campaign (the instance metadata service mints role creds continuously — there is
# nothing to expire), and the 30 s SSH polling / collect / teardown loop depending on
# a workstation staying awake and online for 8+ hours.
#
# Creates (idempotently — every step is find-or-create, same style as bootstrap.sh):
#   1. IAM role + instance profile "revyl-bench-control": exactly the API calls the
#      runtime makes (run/describe/terminate instances, PassRole for the rollout-host
#      profile, s3 rw on the runs bucket) plus the make_ami.sh calls so AMI-building can
#      move onto the control host later without another IAM round. TerminateInstances is
#      conditioned on the bench:rollout tag — the control host can kill bench rollout instances
#      and NOTHING else in the account.
#   2. Self-referencing SSH rule on the rollout-host SG: control host → rollout hosts
#      over private IPs, independent of anyone's own IP. The workstation-IP rule from
#      bootstrap.sh stays as the escape hatch.
#   3. The t3.small instance itself: stock Ubuntu 24.04 (ships Python 3.12, which
#      bench/config.py's tomllib and hosts.py's tarfile filter= need), 40 GB gp3 root
#      (runs/ artifacts accumulate), shutdown-behavior STOP (this host is long-lived — a stop
#      must never destroy it, unlike rollout hosts which terminate on shutdown), and
#      IMDSv2-required with hop-limit 1 (containers behind a docker bridge can't reach
#      the metadata service — pre-contains any future on-box workload from minting the
#      control role's credentials).
#
# Requires bootstrap.sh to have been run (reads ids from infra.json). Run ONCE from the
# workstation under a live SSO session; after this, the workstation is never needed for launches.
# Next steps after this script: ssh in, run setup-control.sh (provisions toolchain),
# then copy secrets by hand (never in user-data — user-data is readable via IMDS).
#
# Usage:  AWS_PROFILE=<admin-profile> ./host/ec2/make_control.sh
#         AWS_BIN=/path/to/aws.exe AWS_PROFILE=<admin-profile> ./host/ec2/make_control.sh   (Windows)
set -euo pipefail
cd "$(dirname "$0")"

# Prefer the official AWSCLIV2 install when present: on Windows a conda shim named `aws`
# can shadow it on PATH and silently kill the shell when invoked from Git Bash (bash
# exits at the first `aws iam` call with no error). Explicit AWS_BIN still wins.
if [ -z "${AWS_BIN:-}" ]; then
  if [ -x "${LOCALAPPDATA:-}/Programs/Amazon/AWSCLIV2/aws.exe" ]; then
    AWS_BIN="$LOCALAPPDATA/Programs/Amazon/AWSCLIV2/aws.exe"
  else
    AWS_BIN=aws
  fi
fi
# AWS_PROFILE names the admin profile on a workstation; unset, the default credential chain
# applies.
[ -n "${AWS_PROFILE:-}" ] && export AWS_PROFILE
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-west-2}"
export PYTHONIOENCODING=utf-8
# cli v2 pipes output through a pager when it thinks it has a console; in Git Bash
# that can block forever waiting for a keypress nobody can deliver
export AWS_PAGER=""
# Git Bash rewrites leading-slash args into Windows paths before native .exes see
# them — the SSM parameter name /aws/service/... arrived at aws.exe as C:/Program
# Files/Git/aws/service/... (observed: ParameterNotFound). Both vars are inert on
# real Linux.
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*"

aws() { "$AWS_BIN" "$@"; }
TAG="revyl-bench"
NAME="$TAG-control"

[ -f infra.json ] || { echo "FATAL: infra.json missing — run bootstrap.sh first" >&2; exit 1; }
# infra.json is flat string values; grep beats a python dependency in this bash context
jval() { grep -o "\"$1\": *\"[^\"]*\"" infra.json | sed 's/.*: *"//; s/"$//'; }
ACCOUNT=$(jval account); SUBNET_ID=$(jval subnet_id); SG_ID=$(jval security_group_id)
BUCKET=$(jval bucket); KEY=$(jval key_name); HOST_PROFILE=$(jval instance_profile)

echo "== identity"
echo "   aws_bin=$AWS_BIN"
# fail fast, visibly, before any mutation — a dead/expired session or a broken aws
# binary should stop the run here, not mid-IAM
aws sts get-caller-identity --query Arn --output text
echo "   account=$ACCOUNT region=$AWS_DEFAULT_REGION subnet=$SUBNET_ID sg=$SG_ID"

# --- 1. IAM role + instance profile -----------------------------------------------------
echo "== iam ($NAME)"
if ! aws iam get-role --role-name "$NAME" >/dev/null 2>&1; then
  aws iam create-role --role-name "$NAME" --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}]
  }' >/dev/null
fi
# put-role-policy is a full overwrite, so re-running converges the policy to this text.
aws iam put-role-policy --role-name "$NAME" --policy-name "$NAME-launch" --policy-document "{
  \"Version\": \"2012-10-17\",
  \"Statement\": [
    {\"Sid\": \"LaunchRolloutHosts\",
     \"Effect\": \"Allow\",
     \"Action\": [\"ec2:RunInstances\", \"ec2:DescribeInstances\", \"ec2:DescribeImages\"],
     \"Resource\": \"*\"},
    {\"Sid\": \"TagOnLaunchOnly\",
     \"Effect\": \"Allow\",
     \"Action\": \"ec2:CreateTags\",
     \"Resource\": \"*\",
     \"Condition\": {\"StringEquals\": {\"ec2:CreateAction\": \"RunInstances\"}}},
    {\"Sid\": \"TerminateOnlyBenchRollouts\",
     \"Effect\": \"Allow\",
     \"Action\": \"ec2:TerminateInstances\",
     \"Resource\": \"*\",
     \"Condition\": {\"Null\": {\"aws:ResourceTag/bench:rollout\": \"false\"}}},
    {\"Sid\": \"PassRolloutHostRole\",
     \"Effect\": \"Allow\",
     \"Action\": \"iam:PassRole\",
     \"Resource\": \"arn:aws:iam::$ACCOUNT:role/$HOST_PROFILE\"},
    {\"Sid\": \"RunsBucket\",
     \"Effect\": \"Allow\",
     \"Action\": [\"s3:PutObject\", \"s3:GetObject\"],
     \"Resource\": [\"arn:aws:s3:::$BUCKET/runs/*\", \"arn:aws:s3:::$BUCKET/campaigns/*\"]},
    {\"Sid\": \"RunsBucketList\",
     \"Effect\": \"Allow\",
     \"Action\": \"s3:ListBucket\",
     \"Resource\": \"arn:aws:s3:::$BUCKET\"},
    {\"Sid\": \"MakeAmiLater\",
     \"Effect\": \"Allow\",
     \"Action\": [\"ec2:CreateImage\", \"ec2:CreateSnapshot\"],
     \"Resource\": \"*\"}
  ]
}"
if ! aws iam get-instance-profile --instance-profile-name "$NAME" >/dev/null 2>&1; then
  aws iam create-instance-profile --instance-profile-name "$NAME" >/dev/null
  aws iam add-role-to-instance-profile --instance-profile-name "$NAME" --role-name "$NAME"
  # IAM instance profiles are eventually consistent — run-instances can reject a
  # just-created profile with InvalidParameterValue for ~10 s.
  echo "   created instance profile; waiting 15s for IAM propagation"
  sleep 15
fi
echo "   role=$NAME (instance profile same name)"

# --- 2. SG: control host <-> rollout hosts over private IPs ------------------------------
echo "== security group (self-referencing ssh)"
aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 22 \
  --source-group "$SG_ID" >/dev/null 2>&1 || true   # duplicate rule on re-run is fine
echo "   sg=$SG_ID allows 22 from itself"

# --- 3. the instance --------------------------------------------------------------------
echo "== control instance"
INSTANCE_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=$NAME" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
  --query "Reservations[0].Instances[0].InstanceId" --output text)
if [ "$INSTANCE_ID" = "None" ]; then
  # Canonical's official SSM parameter → latest 24.04 AMI id, no hardcoded AMI to rot
  UBUNTU_AMI=$(aws ssm get-parameter \
    --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id \
    --query Parameter.Value --output text)
  echo "   launching t3.small from $UBUNTU_AMI"
  INSTANCE_ID=$(aws ec2 run-instances --image-id "$UBUNTU_AMI" --instance-type t3.small \
    --subnet-id "$SUBNET_ID" --security-group-ids "$SG_ID" --key-name "$KEY" \
    --iam-instance-profile "Name=$NAME" \
    --instance-initiated-shutdown-behavior stop \
    --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":40,"VolumeType":"gp3","DeleteOnTermination":true}}]' \
    --metadata-options "HttpTokens=required,HttpPutResponseHopLimit=1" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME},{Key=bench:control,Value=1}]" \
    --query "Instances[0].InstanceId" --output text)
  aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
fi
PUB_IP=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query "Reservations[0].Instances[0].PublicIpAddress" --output text)
PRIV_IP=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query "Reservations[0].Instances[0].PrivateIpAddress" --output text)
echo "   instance=$INSTANCE_ID public=$PUB_IP private=$PRIV_IP"

cat <<EOF

== next steps (see setup-control.sh header for detail)
1. ssh -i ~/.ssh/revyl-bench.pem ubuntu@$PUB_IP
   (works because bootstrap.sh's workstation-IP rule is on the same SG; re-run bootstrap.sh
    if your IP rotated)
2. copy + run setup-control.sh on the control host (toolchain, optional tailscale, deploy key, clone)
3. secrets by hand:
     scp -i ~/.ssh/revyl-bench.pem <repo>/runtime/.env ubuntu@$PUB_IP:revyl-bench/runtime/.env
     scp -i ~/.ssh/revyl-bench.pem ~/.ssh/revyl-bench.pem ubuntu@$PUB_IP:.ssh/
4. validate from the control host:
     aws sts get-caller-identity        # arn:...:assumed-role/$NAME/...
     python3 runtime/launch_rollout.py --task ... --transport ec2 --dry-run
EOF
