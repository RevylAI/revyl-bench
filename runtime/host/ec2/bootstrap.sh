#!/usr/bin/env bash
# host/ec2/bootstrap.sh — one-time AWS infra for the EC2 transport.
#
# Creates (idempotently — every step is find-or-create) the bench's OWN isolated network
# and support objects in us-west-2 — an isolated VPC, deliberately separate from anything
# else the account runs:
#   1. VPC 10.99.0.0/16 "revyl-bench" + internet gateway + public subnet + route
#   2. security group "revyl-bench-host": SSH (22) from THIS workstation's public IP only,
#      all egress (EAS, Revyl, npm, Anthropic — the data plane is egress-only by design)
#   3. key pair "revyl-bench" → private key at ~/.ssh/revyl-bench.pem (0600, never committed)
#   4. S3 bucket revyl-bench-runs-<account> (account-suffixed: bucket names are GLOBALLY
#      unique, so a bare `revyl-bench` could be taken by anyone; suffixing makes
#      the name deterministic instead of first-come-first-served)
#   5. IAM role + instance profile "revyl-bench-host": s3:PutObject/GetObject/ListBucket on
#      that bucket ONLY — lets the host sync artifacts without any AWS keys in containers
#      (unused while the launch machine does the sync, but costs nothing and enables host-side
#      sync later without a second IAM round)
#
# Output: host/ec2/infra.json — every id the transport needs. Ids are not secrets; the
# only secret this script produces is the .pem, which stays in ~/.ssh.
#
# Usage:  AWS_PROFILE=<admin-profile> ./host/ec2/bootstrap.sh
#         AWS_BIN=/path/to/aws.exe AWS_PROFILE=<admin-profile> ./host/ec2/bootstrap.sh   (Windows)
set -euo pipefail
cd "$(dirname "$0")"

AWS_BIN="${AWS_BIN:-aws}"
# Windows: the winget install isn't on PATH in shells opened before it (or in this repo's
# tool shells) — fall back to its fixed install location so `bash host/ec2/bootstrap.sh`
# works with no env prefix.
command -v "$AWS_BIN" >/dev/null 2>&1 || AWS_BIN="$LOCALAPPDATA/Programs/Amazon/AWSCLIV2/aws.exe"
# AWS_PROFILE names the admin profile on a workstation; unset, the default credential chain
# applies (on the coordinator host that is the instance role, which must win).
[ -n "${AWS_PROFILE:-}" ] && export AWS_PROFILE
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-west-2}"
# aws-cli on Windows mangles output encoding under MSYS without this
export PYTHONIOENCODING=utf-8

aws() { "$AWS_BIN" "$@"; }
TAG="revyl-bench"

echo "== identity"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
echo "   account=$ACCOUNT region=$AWS_DEFAULT_REGION"

# --- 1. VPC + IGW + subnet + route ------------------------------------------------------
echo "== vpc"
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=tag:Name,Values=$TAG" --query "Vpcs[0].VpcId" --output text)
if [ "$VPC_ID" = "None" ]; then
  VPC_ID=$(aws ec2 create-vpc --cidr-block 10.99.0.0/16 \
    --tag-specifications "ResourceType=vpc,Tags=[{Key=Name,Value=$TAG},{Key=bench,Value=true}]" \
    --query Vpc.VpcId --output text)
  aws ec2 modify-vpc-attribute --vpc-id "$VPC_ID" --enable-dns-hostnames
fi
echo "   vpc=$VPC_ID"

IGW_ID=$(aws ec2 describe-internet-gateways --filters "Name=tag:Name,Values=$TAG" \
  --query "InternetGateways[0].InternetGatewayId" --output text)
if [ "$IGW_ID" = "None" ]; then
  IGW_ID=$(aws ec2 create-internet-gateway \
    --tag-specifications "ResourceType=internet-gateway,Tags=[{Key=Name,Value=$TAG}]" \
    --query InternetGateway.InternetGatewayId --output text)
  aws ec2 attach-internet-gateway --internet-gateway-id "$IGW_ID" --vpc-id "$VPC_ID"
fi
echo "   igw=$IGW_ID"

SUBNET_ID=$(aws ec2 describe-subnets --filters "Name=tag:Name,Values=$TAG" "Name=vpc-id,Values=$VPC_ID" \
  --query "Subnets[0].SubnetId" --output text)
if [ "$SUBNET_ID" = "None" ]; then
  SUBNET_ID=$(aws ec2 create-subnet --vpc-id "$VPC_ID" --cidr-block 10.99.1.0/24 \
    --availability-zone "${AWS_DEFAULT_REGION}a" \
    --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=$TAG}]" \
    --query Subnet.SubnetId --output text)
  # instances need a public IP to reach EAS/Revyl/npm (no NAT gateway — this is cheaper
  # and the SG still blocks all ingress except our SSH)
  aws ec2 modify-subnet-attribute --subnet-id "$SUBNET_ID" --map-public-ip-on-launch
fi
echo "   subnet=$SUBNET_ID"

RT_ID=$(aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$VPC_ID" \
  --query "RouteTables[0].RouteTableId" --output text)
aws ec2 create-route --route-table-id "$RT_ID" --destination-cidr-block 0.0.0.0/0 \
  --gateway-id "$IGW_ID" >/dev/null 2>&1 || true   # exists on re-run
echo "   route-table=$RT_ID (0.0.0.0/0 → igw)"

# --- 2. security group ------------------------------------------------------------------
echo "== security group"
SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$TAG-host" "Name=vpc-id,Values=$VPC_ID" \
  --query "SecurityGroups[0].GroupId" --output text)
if [ "$SG_ID" = "None" ]; then
  SG_ID=$(aws ec2 create-security-group --group-name "$TAG-host" --vpc-id "$VPC_ID" \
    --description "revyl-bench rollout hosts: ssh from the launch workstation only, all egress" \
    --query GroupId --output text)
fi
MY_IP=$(curl -s https://checkip.amazonaws.com | tr -d '[:space:]')
aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 22 \
  --cidr "$MY_IP/32" >/dev/null 2>&1 || true       # duplicate rule on re-run is fine
echo "   sg=$SG_ID (ssh from $MY_IP/32)"

# --- 3. key pair ------------------------------------------------------------------------
echo "== key pair"
PEM="$HOME/.ssh/revyl-bench.pem"
if ! aws ec2 describe-key-pairs --key-names "$TAG" >/dev/null 2>&1; then
  mkdir -p "$HOME/.ssh"
  aws ec2 create-key-pair --key-name "$TAG" --key-type ed25519 \
    --query KeyMaterial --output text > "$PEM"
  chmod 600 "$PEM"
  echo "   created $PEM"
elif [ ! -f "$PEM" ]; then
  echo "FATAL: key pair '$TAG' exists in AWS but $PEM is missing locally." >&2
  echo "       Delete the key pair (aws ec2 delete-key-pair --key-name $TAG) and re-run." >&2
  exit 1
fi
echo "   key=$TAG pem=$PEM"

# --- 4. S3 bucket -----------------------------------------------------------------------
echo "== s3"
BUCKET="revyl-bench-runs-$ACCOUNT"
if ! aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  aws s3api create-bucket --bucket "$BUCKET" \
    --create-bucket-configuration LocationConstraint="$AWS_DEFAULT_REGION"
  aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
fi
echo "   bucket=s3://$BUCKET"

# --- 5. IAM role + instance profile -----------------------------------------------------
echo "== iam"
ROLE="$TAG-host"
if ! aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROLE" --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}]
  }' >/dev/null
fi
aws iam put-role-policy --role-name "$ROLE" --policy-name "$TAG-s3-runs" --policy-document "{
  \"Version\": \"2012-10-17\",
  \"Statement\": [
    {\"Effect\": \"Allow\", \"Action\": [\"s3:PutObject\", \"s3:GetObject\"],
     \"Resource\": [\"arn:aws:s3:::$BUCKET/runs/*\", \"arn:aws:s3:::$BUCKET/campaigns/*\"]},
    {\"Effect\": \"Allow\", \"Action\": \"s3:ListBucket\", \"Resource\": \"arn:aws:s3:::$BUCKET\"}
  ]
}"
if ! aws iam get-instance-profile --instance-profile-name "$ROLE" >/dev/null 2>&1; then
  aws iam create-instance-profile --instance-profile-name "$ROLE" >/dev/null
  aws iam add-role-to-instance-profile --instance-profile-name "$ROLE" --role-name "$ROLE"
fi
echo "   role=$ROLE (instance profile same name)"

# --- output -----------------------------------------------------------------------------
cat > infra.json <<EOF
{
  "region": "$AWS_DEFAULT_REGION",
  "account": "$ACCOUNT",
  "vpc_id": "$VPC_ID",
  "subnet_id": "$SUBNET_ID",
  "security_group_id": "$SG_ID",
  "key_name": "$TAG",
  "pem_path": "~/.ssh/revyl-bench.pem",
  "bucket": "$BUCKET",
  "instance_profile": "$ROLE",
  "instance_type": "m6a.xlarge",
  "ami_id": null
}
EOF
echo "== wrote host/ec2/infra.json (ami_id: null — run make_ami.sh next)"
cat infra.json
