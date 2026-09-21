# grading-side/ — the device-test suites

Every task in `tasks/` is graded by four Revyl device tests. This directory holds their
definitions. A task package names its tests (`frozen_test_names` in `task.toml`) and never
contains them; the definitions live here so that **anyone can load them into their own
Revyl organisation and grade rollouts themselves**.

## Layout

```
grading-side/<task>/
  steps/01-*/tests/<prefix>-t_1-*.yaml    the stage-1 suite
  steps/02-*/tests/<prefix>-t_2-*.yaml    the stage-2 suite
  steps/03-*/tests/<prefix>-t_3-*.yaml    the stage-3 suite
  final/tests/<prefix>-final-e2e.yaml     the end-to-end journey
```

A suite is one Revyl test: a list of blocks, each a tap, a scroll, a short wait, or a
validation of what the screen shows. All four suites run on every submission, and each
ends as one verdict, PASS or FAIL. How the four verdicts become a score is in
[`docs/scoring.md`](../docs/scoring.md).

## Withheld from the agent, not from you

The suites are readable here and withheld from the agent at run time: `grading-side/` is
never mounted into the agent's container, never copied into a scaffold, and the feedback an
agent gets after a submission is redacted to the failed criteria
(`runtime/bench/redact.py`). The agent's Revyl key cannot list, pull or run a test in the
grading organisation. Publishing them costs little because the benchmark is contract-first
— every string a suite asserts is already stated in the task's `instruction.md`. What the
suites add over the contract is the order of the journey and the number of blocks, not
values.

One limit, stated plainly: the agent's container has outbound network access (it needs npm,
Expo and Revyl), and `allowed_hosts` in `task.toml` is a declaration this runtime does not
enforce, so an agent could fetch this public repository. A run whose transcript shows the
agent fetching this repository or its `grading-side/` is excluded from scoring
(`suite_fetch` check).

If you train a model, keep this directory out of the training data; a result from a model
that has seen the suites is not comparable with the published rows.

## Loading the suites into your own grading organisation

You need **two Revyl organisations and two Revyl users**. A Revyl API key is scoped to the
user who created it, and a user's key acts in that user's organisation, so one key cannot
serve both sides:

| | organisation | user / key | what it holds |
|---|---|---|---|
| grading | your grading org | user A → `REVYL_GRADING_API_KEY` | the grading app `bench-<task>`, the four tests, the `<prefix>-suite` workflow, every submission's binary |
| agent | your agent (dev) org | user B → `REVYL_AGENT_API_KEY` | the dev app `bench-<task>-dev` and its pinned dev-client build — the only key the agent's container ever receives |

The split is what keeps the suites away from the agent: its key cannot list or pull a test
in the grading organisation. [`docs/organizations.md`](../docs/organizations.md) has the
full picture.

1. Copy `runtime/.env.example` to `runtime/.env` and fill in both keys. (If you leave an
   organisation id empty, `setup_orgs.py` prints the id the key resolves to and the line to
   add.)
2. Fill the grading organisation. Start with a dry run, then one task, then the rest — the
   command is idempotent, so re-running it only creates what is still missing. Do it in that
   order for a reason: the create paths underneath (`app create`, `test create`,
   `workflow create`, and the dev app and build on the agent side) follow the pinned CLI's
   documented flags and have been run many times against organisations that were already
   populated, but have not yet been exercised end to end against an empty one. If one
   misbehaves in yours, open an issue with the command's output.

   ```
   python3 runtime/provision/setup_orgs.py grading --task s1-commerce-0001 --dry-run   # prints every write, runs none
   python3 runtime/provision/setup_orgs.py grading --task s1-commerce-0001
   python3 runtime/provision/setup_orgs.py grading                                     # all 20 (runtime/provision/tasks.txt)
   ```

   Per task it creates the app `bench-<task>`, the four tests from the YAML here and the
   workflow `<prefix>-suite` listing exactly those tests, then writes the new app id into
   `[runtime.grading]` of `tasks/<task>/task.toml`. This side reads only
   `REVYL_GRADING_API_KEY`.
3. Fill the agent organisation: the dev app `bench-<task>-dev` and one dev-client build per
   task (Revyl builds it remotely, about 10 minutes each; no Expo account needed). The ids
   go into `[runtime.agent]`. This side reads only `REVYL_AGENT_API_KEY`.

   ```
   python3 runtime/provision/setup_orgs.py agent --task s1-commerce-0001
   ```
4. Commit the `task.toml` changes to your fork — the ids are not secrets, and the launcher
   reads them from there.
5. Before every campaign, check that nothing drifted. The check compares the step text of
   every live test with the YAML here, block by block, so an edit made in the Revyl UI is
   reported, and confirms each pinned dev-client still exists:

   ```
   python3 runtime/provision/setup_orgs.py check
   ```

The launcher (`runtime/launch_rollout.py`) runs the same presence checks as guards and
refuses to start a rollout for a task whose app, workflow or tests are missing.

## Rules

- Never copy this directory into an agent container, a scaffold or a task package.
- A suite is frozen with its task version. Changing a block changes what every published
  score for that task means; it needs a new `task_version`, not an edit in place.
