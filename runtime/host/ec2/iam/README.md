# IAM policies for the control host role `revyl-bench-control`

The role is created by `make_control.sh` with the inline policies `revyl-bench-control-launch`
(run/describe/terminate rollout hosts — terminate is gated on the `bench:rollout` tag).

## `revyl-bench-control-ami.json` — lets `make_ami.sh` finish cleanly from the control host

`make_ami.sh` run from the control host can `CreateImage`, but two operations fail without
this policy: (a) an inline `--tag-specifications` fails on `ec2:CreateTags` for `image/*`, and
(b) the EXIT trap cannot terminate the builder because it carries
`Name=revyl-bench-ami-builder`, not `bench:rollout`, so the builder (m6a.xlarge) keeps running
until someone with admin credentials kills it.

This policy allows exactly those two things and nothing else: `ec2:TerminateInstances` only
where `aws:ResourceTag/Name == revyl-bench-ami-builder` (never a rollout host, never the
control host), and `ec2:CreateTags` only on `image/*` + `snapshot/*`.

Before applying, edit the JSON: replace `<aws-account-id>` with your 12-digit account id and
`us-west-2` with your region — IAM rejects the file as malformed with the placeholder in it.
Apply with admin credentials (the role cannot modify itself):

    aws --profile <admin-profile> iam put-role-policy --role-name revyl-bench-control \
      --policy-name revyl-bench-control-ami \
      --policy-document file://runtime/host/ec2/iam/revyl-bench-control-ami.json
