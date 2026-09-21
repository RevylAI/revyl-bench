# runtime/ — the evaluation machinery

The operational half of revyl-bench: the runner (grades a submission against the frozen
suite), the agent container (where a contestant harness builds the app), the mailbox
protocol between them, and `launch_rollout.py`.

Task packages live beside this directory at `../tasks`. The bench root defaults to this
directory's parent; override it with `REVYL_BENCH_DIR`.

Quick map:
- `launch_rollout.py` — outer script (one rollout = task × contestant × seed)
- `campaign.py` — a benchmark run as one folder: `new`, `launch` (every cell of a
  tasks × seeds matrix, N at a time, resumable), `status`, `set`, `extend`, `sync`,
  `fetch`; `campaigns.py` is the library behind it (manifests, status files, the
  `phantom_fail` and `suite_fetch` checks, discovery); `campaigns/` is where the folders land. The scorer
  reads them with `score/score_v0.py --campaign`. See [`../docs/campaigns.md`](../docs/campaigns.md)
- `bench/` — shared library (config, revyl/eas wrappers, recipes = the grading build recipe
  and scaffold config shape, redaction, attempts.jsonl, guard rails)
- `container/` — what the agent gets: `submit.sh`, `RUNBOOK.md.tmpl`, `entrypoint.sh`
- `runner/` — `main.py` (mailbox loop, END) + `grade.py` (one submission)
- `image/` — Dockerfiles + **`REVYL_CLI_VERSION`, the single revyl CLI pin** (changing it
  forces an AMI re-bake); `host/` — compose template + `host/ec2/` (bench VPC `bootstrap.sh`,
  rollout-host `make_ami.sh`, and the control host: `make_control.sh` + `setup-control.sh`)
- `contestants/registry.yaml` — model × harness × config registry
- `scaffolds/<task>/` — the blank tree every rollout of a task starts from, pinned by
  `base_commit` in the task package
- `score/` — the scoring implementation (`docs/scoring.md` is the readable version)
- `hosts/` — the live hosts' staging dirs (transient); `campaigns/` — the store on this
  machine (git-ignored; the object store holds the identical tree)

- `provision/` — `setup_orgs.py grading|agent|check` fills your two Revyl organisations from
  the repository (suites from [`../grading-side/`](../grading-side/README.md), dev clients
  built remotely by Revyl) and writes the minted ids into each `task.toml`;
  `build_images.sh <harness>` builds the agent and runner images

**Requirements:** Python ≥ 3.11 (`tomllib`) with PyYAML (`pip install -r requirements.txt`),
Docker, git, bash (Git Bash on Windows, not WSL), and the revyl CLI at exactly the version
in [`image/REVYL_CLI_VERSION`](image/REVYL_CLI_VERSION) — the server rejects older ones and
the images are built against this one. Install exactly that version — the same command
`host/ec2/setup-control.sh` uses — from the repository root:

```
curl -fsSL https://revyl.com/install.sh | sudo REVYL_VERSION="$(tr -d '[:space:]' < runtime/image/REVYL_CLI_VERSION)" REVYL_INSTALL_DIR=/usr/local/bin sh
revyl --version        # must print: revyl version <the pin>
```

No Mac and no Expo account are needed: simulators and builds run on Revyl. The runner builds
every submission with `revyl build --remote` (`expo prebuild` plus an `xcodebuild` Release
build, on Revyl's build runners); the agent never builds the graded binary. See
[`../docs/organizations.md`](../docs/organizations.md) for the two organisations (and two
users) a deployment needs.

The scaffolds' `app.json` files carry `"owner": "revyl"` and an `extra.eas.projectId`. On the
default `--builder revyl` path nothing reads them. They matter only on the legacy
`--builder eas` path: delete both keys and run `eas init` under your own Expo account (that
edits the scaffold, so the task's `base_commit` has to be recorded again).

Not part of this repository's 20 tasks: `container/RUNBOOK-{step,repair,swift*}.md.tmpl`,
`container/devbuild.sh` and the step and repair branches in
`launch_rollout.py` belong to other task kinds (step-level, repair and native-Swift tasks)
that are not published yet — see [What's next](../README.md#whats-next).

## Configuration — `runtime/.env`

Copied from `.env.example`; never committed, never baked into an image. It holds:

| variable | what it is |
|---|---|
| `REVYL_GRADING_API_KEY`, `REVYL_GRADING_ORG_ID` | the grading organisation: the frozen tests, grading apps, every submission's binary. Key minted by a user of THAT organisation |
| `REVYL_AGENT_API_KEY`, `REVYL_AGENT_ORG_ID` | the agent organisation: dev clients and the agent's device sessions. Key minted by a second user, of this organisation (keys are user-scoped) |
| `EXPO_TOKEN` | only for the legacy `--builder eas` path |
| the contestant's key (`key_env` in the registry) | the model credential the harness uses |

The two organisations, and why there are two, are described in
[`../docs/organizations.md`](../docs/organizations.md). `launch_rollout.py` refuses to
start without the four Revyl values, and the guard rails verify that each key really
resolves to the organisation named beside it.

## Run one task locally (no AWS)

`--transport local` runs the agent and runner containers with Docker on the launch machine.
It needs no AWS account, no `host/ec2/infra.json` and no AMI — only Docker, the pinned revyl
CLI, `runtime/.env`, and the task provisioned in your two organisations
([`../grading-side/README.md`](../grading-side/README.md)). `local` is `launch_rollout.py`'s
default transport; `campaign.py new` defaults to `ec2`, so say `--transport local` there.

```
cd runtime
./provision/build_images.sh opencode        # the runner image + that harness's agent images (SDK 56 and 57)
python3 campaign.py new --purpose smoke --contestant opencode/glm-5.2 \
    --tasks s1-commerce-0001 --transport local            # prints the campaign name; one seed
python3 launch_rollout.py --task s1-commerce-0001 --contestant opencode/glm-5.2 --seed 1 \
    --transport local --campaign <that name> --dry-run    # every guard, no containers, no cost
python3 campaign.py launch --name <that name> --width 1
python3 campaign.py status --name <that name>
python3 score/score_v0.py --campaign <that name>
```

A local run is collected into `campaigns/<campaign>/runs/…` like any other, but there is no
bucket to mirror it to, so the scorer flags it `unmirrored` (it is still scored). A `smoke`
campaign is never a leaderboard row; use `--purpose benchmark` (seeds 1, 2, 3) for that.

## What a rollout costs

One rollout is capped at 480 minutes of wall clock and 5 submissions. A submission takes
about 12–20 minutes end to end (remote build ≈ 2–5 min, the four device tests ≈ 10 min), and
the agent's own device session runs for as long as it works. Model usage is the large term:
in season 1 the three rows whose harness records tokens used, per rollout on average, about
18M input / 0.11M output tokens (Opus 5), 19M / 0.10M (GLM-5.2) and 17M / 0.06M (Muse Spark
1.3); input counts every prompt token, cached or not
([`../docs/season1-results.md`](../docs/season1-results.md)). A full row is 60 rollouts.

On the Revyl side, the grading organisation needs remote builds enabled and enough
concurrent test-run capacity: each submission runs its four device tests in parallel, and
several rollouts grading at once multiply that. When the organisation's concurrent-run limit
is reached, `runner/grade.py` does not score the slot as a failure: it waits for a slot (in
60-second steps, up to 20 minutes, within the grade budget) and runs the test again. The
agent organisation needs a device session for every rollout that is running. Size
`campaign.py launch --width` to what your organisations allow.

## Launching an evaluation on EC2

```
cd runtime
python3 campaign.py new --purpose smoke --contestant opencode/glm-5.2 --tasks s1-commerce-0001 --transport ec2
python3 launch_rollout.py --task s1-commerce-0001 --contestant opencode/glm-5.2 --seed 1 --transport ec2 \
    --campaign <the campaign printed by new> --dry-run
python3 campaign.py launch --name <the campaign> --width 1
```

Every rollout belongs to a campaign ([`../docs/campaigns.md`](../docs/campaigns.md)):
`campaign.py new` creates the folder, `campaign.py launch` runs every cell of its matrix,
and a single `launch_rollout.py --campaign <name>` is one cell of it. `--dry-run`
resolves the task, seeds a host directory and runs every guard with no containers and
no cost; run it first for any new task or contestant. A real launch creates one
disposable host per rollout (`--transport ec2`, or `local` for Docker on the launch
machine), seeds it under `hosts/<rollout-id>/`, brings up the agent and runner
containers, waits for the end, collects the run into
`campaigns/<campaign>/runs/<task>_s<seed>_<id>/`, mirrors it and tears the host down.

What a deployment needs before the first launch: an AWS account bootstrapped by
`host/ec2/bootstrap.sh` (VPC, bucket, instance profile), a rollout-host image from
`host/ec2/make_ami.sh` pinned in `host/ec2/infra.json` (`infra.example.json` shows the
shape), the revyl CLI at the pinned version on the launch machine, and the two
organisations provisioned for every task you intend to run. The launcher refuses to start
if the checkout's runtime tree does not match the image it would launch.

## Launching rollouts — the control host

Production launches run from a small always-on coordinator instance in the bench VPC,
created by `host/ec2/make_control.sh` and provisioned by `setup-control.sh`. It runs under
an IAM instance role — no human credentials that can expire — and reaches rollout hosts
over VPC-internal addresses (`REVYL_BENCH_SSH_IP=private`; the variable defaults to
`public` so launches from a workstation keep working). Campaign routine on the host:

```
cd ~/revyl-bench && git pull
python3 runtime/campaign.py new --purpose benchmark --contestant <slug> \
    --transport ec2 --ssh-ip private                     # prints the campaign name
python3 runtime/campaign.py launch --name <campaign> --width 4
```

`--ssh-ip private` is recorded in the campaign and exported as `REVYL_BENCH_SSH_IP` to every
rollout it launches. One cell by hand is
`REVYL_BENCH_SSH_IP=private python3 runtime/launch_rollout.py --task <pkg> --contestant <slug> --seed <n> --transport ec2 --campaign <campaign>`;
`--campaign` is required, because the run folder, its status file and the mirror prefix all
come from it.

Run it detached and disconnect — the host owns the rollout end-to-end (poll, collect,
mirror to the object store, terminate). Secrets live only in `runtime/.env` and the
instance key pair on that host, copied by hand — never via user-data or an image, because
user-data is readable through the instance metadata service. Finished rollout directories
are mirrored to the object store and scored from there.
