# The two organisations

Every evaluation runs against two Revyl organisations. The split is what makes the live
grading tests unreachable through the agent's Revyl key: the two credentials live in
different places, reach different resources, and the runtime checks both before anything
starts. An agent under evaluation cannot list, pull or run a test in the grading
organisation, and cannot see a submission's binary or report.

What the split does not cover: the suite definitions are also published in
[`grading-side/`](../grading-side/README.md). They are never mounted or copied into the
agent's container, but that container has outbound network access (npm, Expo, Revyl) and the
`allowed_hosts` list in `task.toml` is a declaration this runtime does not enforce, so an
agent could fetch this public repository. A run whose transcript shows the agent fetching
this repository or its `grading-side/` is excluded from scoring (`suite_fetch` check).

**You need two Revyl users as well as two organisations.** A Revyl API key belongs to the
user who created it and acts in that user's organisation, so one user cannot mint both
keys: create user A in the grading organisation and user B in the agent organisation, and
take one key from each. Use a grading organisation that holds nothing else — the launch
guard refuses to start if the agent key can see any `s1*` workflow.

| | agent organisation | grading organisation |
|---|---|---|
| purpose | the agent's development loop | building and grading every submission |
| holds | one dev app per task with the pinned dev-client build; the device sessions the agent drives during a rollout | one grading app per task; the four frozen device tests; the `<prefix>-suite` workflow that lists them; every submission's built binary |
| key | `REVYL_AGENT_API_KEY` | `REVYL_GRADING_API_KEY` |
| the key lives in | the agent container (`REVYL_API_KEY` there) and the launch host | the runner container and the launch host — never the agent container |
| id | `REVYL_AGENT_ORG_ID` | `REVYL_GRADING_ORG_ID` |

Both keys and both ids are set in `runtime/.env` on the launch host
(`runtime/.env.example` lists them). The ids are not secret; the keys are.

## What the runtime does with them

`runtime/launch_rollout.py` reads `.env`, resolves the task, and refuses to start unless
all four values are present. The resolved rollout (`rollout.json`) records which two
organisations graded it, so an archived episode never depends on the launch host's
configuration again.

Before a rollout starts, the guard rails in `runtime/bench/guards.py` check, with real
API calls:

- the agent key resolves to `REVYL_AGENT_ORG_ID`, and that organisation lists no `s1*`
  workflow — the grading suite must be invisible from the agent side;
- the grading key resolves to `REVYL_GRADING_ORG_ID`, and the task's `<prefix>-suite`
  workflow there lists every frozen test the task grades on;
- the task's dev-client build is pinned on its dev app in the agent organisation, so the
  agent's `revyl dev` session runs the right shell;
- the grading key can list builds on the task's grading app, which is where the runner
  will register each submission's binary.

During the rollout the agent container holds only the agent key. The runner holds the
grading key, builds the committed source, uploads the binary to the grading app, and runs
the four tests by name with an explicit build id. Failed checks return to the agent as
redacted evidence — criterion, judge reasoning, screenshots — never as the test
definitions.

## What provisioning creates

Provisioning happens once per task per deployment, by whoever operates that deployment —
never by the agent under test. One command per organisation does it:

```
python3 runtime/provision/setup_orgs.py grading   # reads only REVYL_GRADING_API_KEY
python3 runtime/provision/setup_orgs.py agent     # reads only REVYL_AGENT_API_KEY
python3 runtime/provision/setup_orgs.py check     # read-only audit of both
```

Each is idempotent (it asks the organisation what exists and creates only what is
missing), takes `--task <pkg>` to do one task and `--dry-run` to print every write without
making it. The walkthrough is [`grading-side/README.md`](../grading-side/README.md).

| in the agent organisation | in the grading organisation |
|---|---|
| a dev app `bench-<task>-dev` | a grading app `bench-<task>` |
| one dev-client build, registered and pinned by version id | the four frozen tests, created from `grading-side/<task>/{steps/*/tests,final/tests}/*.yaml` |
| | the `<prefix>-suite` workflow listing exactly those tests |

The minted ids — grading app, suite workflow, dev app, dev-client pin — are written into
the task package's `task.toml` under `[runtime.grading]` and `[runtime.agent]`. They are
provisioning output, not secrets, and they are specific to the pair of organisations
they were created in. The organisation ids themselves are never written into a package;
a second deployment provisions its own ids in its own organisations and points `.env` at
them.

The task packages in this repository ship without those ids — `[runtime.grading]` is absent
and `[runtime.agent]` carries only `scaffold`, `base_commit`, `expo_sdk` and `ios_scheme` —
because the ids Revyl's own deployment minted name apps in Revyl's organisations and are
useless anywhere else. `setup_orgs.py` writes yours in; commit them to your fork. Until it
has run for a task, `launch_rollout.py` refuses that task with "carries no provisioning ids".
