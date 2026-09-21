# How revyl-bench works — the evaluation pipeline, step by step

This document describes the mechanics: exactly what happens when a contestant is
evaluated, from the moment an attempt is launched to the number on the leaderboard. For
the scoring formula, see [`scoring.md`](scoring.md). The evaluation machinery lives
in this repo under [`runtime/`](../runtime/), so each step below links the code that
implements it.

## The units

- **Contestant** — a model paired with a coding harness, at pinned versions and
  configuration (for example, *a frontier model × a coding agent, high-reasoning
  setting*). Each contestant is one entry in
  [`runtime/contestants/registry.yaml`](../runtime/contestants/registry.yaml). Pinned
  means pinned: two attempts by the same contestant run byte-identical software.
- **Rollout** — one contestant attempting one task once, under a single random seed.
  ("Rollout" is used throughout this repo for a single end-to-end attempt.) It is the
  atomic unit of evaluation: one disposable host, one isolated workspace, one graded
  outcome.
- **Contestant run** — the full evaluation matrix: every task × 3 seeds, each rollout
  scored independently, then averaged (seeds first, then tasks) into a single
  leaderboard row. A full season-1 row is **20 tasks × 3 seeds = 60 rollouts**.

## The two-sided trust model

Every rollout involves two isolated parties that communicate only through a shared
mailbox directory. The exact container mounts are in
[`runtime/host/compose.yaml.tmpl`](../runtime/host/compose.yaml.tmpl); the images are in
[`runtime/image/`](../runtime/image/).

```
┌─ AGENT container ──────────────┐        ┌─ RUNNER container ─────────────────┐
│ the contestant's harness       │        │ the benchmark's grader             │
│ · workspace (Expo scaffold)    │mailbox │ · holds grading + build credentials│
│ · live device dev loop         │ ⇄      │ · builds the SOURCE the agent      │
│ · can ONLY submit source       │        │   submits                          │
│ · never sees tests/credentials │        │ · runs the frozen 4-test suite     │
└────────────────────────────────┘        │ · returns redacted verdicts        │
                                           └────────────────────────────────────┘
```

The agent's Revyl credentials reach the **agent organisation** — cloud iOS simulators for
its own development loop — and nothing else. The grading credentials, the live test
definitions, and the build pipeline all live with the runner. Two structural guarantees
follow: the agent's key cannot list, pull, run or probe the tests in the grading
organisation, and the graded binary is always built by the benchmark from the exact source
tree the agent committed. A contestant cannot hand-craft or substitute a binary.

One limit, stated plainly. The suite definitions are public in
[`grading-side/`](../grading-side/README.md) and are never mounted or copied into the agent
container — but that container has outbound network access (it needs npm, Expo and Revyl),
and `allowed_hosts` in `task.toml` is a declaration this runtime does not enforce, so an
agent could fetch this public repository. A run whose transcript shows the agent fetching
this repository or its `grading-side/` is excluded from scoring (`suite_fetch` check). What
the suites add over the contract is the order of the journey and the block count, not
values.

The two organisations, what each key may reach, and what provisioning creates in each:
[`organizations.md`](organizations.md).

## One rollout, start to finish

### Provisioning (once per task, not per rollout)

The benchmark prepares each task's scaffold — a blank `create-expo-app` TypeScript
template plus the development client, committed per task under
[`runtime/scaffolds/`](../runtime/scaffolds/) — builds the shared development-client
binary the dev loop uses, and registers the frozen 4-test suite on the grading side.
Whoever operates a deployment does this once, in their own two Revyl organisations, with
`runtime/provision/setup_orgs.py` (suites from [`grading-side/`](../grading-side/README.md));
see [`organizations.md`](organizations.md). The agent under test never sees this step.

### Launch and setup (~1 min; roughly +2 min on cloud instances)

A single command
([`runtime/launch_rollout.py`](../runtime/launch_rollout.py)) creates a fresh host — one
cloud instance per rollout in production, terminated when the rollout ends. The command
runs on a small, always-on coordinator host inside the deployment's own cloud network: an
EC2 instance under an IAM instance role (no human credentials that could expire
mid-campaign) that reaches rollout hosts over internal addresses and supervises each
rollout unattended. It is provisioned once by
[`runtime/host/ec2/make_control.sh`](../runtime/host/ec2/make_control.sh) and
[`setup-control.sh`](../runtime/host/ec2/setup-control.sh); launching from a workstation
remains supported as a fallback.

The scaffold is copied in at a pinned base commit, git history is initialized, and the
rollout is given the task contract (`task/instruction.md` plus three step contracts), a
RUNBOOK describing the environment and how evaluation works
([`runtime/container/RUNBOOK.md.tmpl`](../runtime/container/RUNBOOK.md.tmpl)), and
`submit.sh`. Setup guards ([`runtime/bench/guards.py`](../runtime/bench/guards.py)) then
verify the whole configuration — credentials resolve to the correct sides, the suite has
exactly its four frozen tests, the development-client pin exists, the images are present.
Any guard failure aborts before anything runs, and the rollout is a no-result (re-run),
never a score.

### The agent works (typically 10–30 min per submission cycle, up to an 8-hour limit)

The harness is invoked once, with the RUNBOOK as its prompt. From here the benchmark
does not interfere; every choice is the contestant's:

- read the contract and plan;
- write the app;
- verify on a real cloud iOS simulator through the development loop — hot-reloading
  code and driving the actual UI (`tap`, `type`, `swipe`, `screenshot`, `hierarchy`,
  and natural-language `validation`);
- when it believes the complete app works, run `./submit.sh`. The RUNBOOK is explicit
  that a submission is a final-exam attempt, not a progress check.

### Submission intake (seconds)

`submit.sh`
([`runtime/container/submit.sh`](../runtime/container/submit.sh)) commits the tree,
packages `git archive HEAD`, computes its SHA-256, and drops it in the mailbox. The
runner ([`runtime/runner/main.py`](../runtime/runner/main.py)) verifies the hash and
enforces the sequence and budget rules — at most **5 submissions** per rollout, one in
flight at a time — then accepts. The submission is now immutable and fully attributable:
its commit id and tree hash are recorded permanently.

### Build (~2–5 min)

The runner — never the agent — builds an iOS simulator binary from the submitted source
on Revyl's remote build runners (`revyl build --remote`, native `expo prebuild` plus
`xcodebuild -configuration Release`). The build recipe is owned by the runner image and
is applied over whatever `.revyl/config.yaml` the submission carried. The binary is
registered under a globally unique version name derived from the rollout id and
submission number. (Build and grading are one function:
[`runtime/runner/grade.py`](../runtime/runner/grade.py).) A tree that fails to build is a
**failed submission charged to the agent** — the RUNBOOK advises verifying `tsc` and
`expo export` locally first.

### Grading (~10 min)

The suite's four frozen device tests run against that binary on isolated cloud
simulators: one test per build step (`t_1`, `t_2`, `t_3`) plus a `final` end-to-end
journey. **Every submission is graded against all four**, so a change that breaks an
earlier step is caught as a regression and penalized. Each test drives the real UI and
judges every checkpoint against frozen criteria, with screenshot evidence. The grader
asserts that each report is bound to exactly this submission's binary; a mismatch is
retried once, then set aside as a benchmark fault (never charged to the contestant).

### Verdict and feedback (seconds)

The agent receives the verdict vector (`t_1`, `t_2`, `t_3`, `final`, each PASS or FAIL),
the list of regressions, and a **redacted** feedback bundle
([`runtime/bench/redact.py`](../runtime/bench/redact.py)). For each failed checkpoint,
and only for failures, the bundle contains the criterion text, the judge's reasoning,
and the screenshots of what the device actually showed. Passing steps, the test
structure, and the test definitions are never disclosed. If a test failed without
checkpoint-level detail — for example, the driver aborted on an untappable element — the
bundle says so instead of arriving empty.

### Iterate or finish

If all four tests pass, the rollout ends immediately. Otherwise the agent diagnoses from
the feedback, fixes the app in the development loop, and resubmits — until all four
tests pass, the 5-submission cap is reached, or the time limit expires. Each cycle costs
roughly 12–20 minutes of fixed build-and-grade time (the figure the RUNBOOK gives the agent), which is exactly why the scoring
rewards finishing in few submissions.

### Collection and teardown (~1 min)

The benchmark collects everything into the rollout's permanent record: a run folder
inside its campaign, `runtime/campaigns/<campaign>/runs/<task>_s<seed>_<id>/`, mirrored
to the deployment's object store (your runs bucket) under the same path (see [`campaigns.md`](campaigns.md)
for what a campaign is and how the scorer reads one):

- `attempts.jsonl` — one line per submission, with timestamps, commit/tree/build ids,
  the verdict vector, regressions, and a failure classification, plus a final line
  carrying tokens, turns, and device-usage statistics derived from the transcript
  (record shape: [`runtime/bench/attempts.py`](../runtime/bench/attempts.py));
- the full harness transcript;
- a git bundle from which every submission commit is recoverable;
- the raw grading reports;
- the exact feedback the agent saw.

The host is then destroyed; on cloud instances the artifacts are mirrored to the object
store first and
the instance terminates itself. Every verdict remains auditable down to a screenshot and
a device-session recording.

## From rollouts to a leaderboard row

Each rollout gets a score (see [`scoring.md`](scoring.md); implementation:
[`runtime/score/score_v0.py`](../runtime/score/score_v0.py)): outcome first — what
passed — discounted by extra submissions, agent working time, and regressions. Then:

```
task cell        = mean score over that task's 3 seeds
contestant row   = mean over the task cells (20 in a full season-1 row)
```

Published per contestant: **tasks solved** (for example, "20/20" — every seed passing all
four tests), the **mean score**, token totals where the harness records them, and in
[`results/official.jsonl`](../results/official.jsonl) every counted rollout id with its
score, seed and campaign, so the means, cells and solved counts can be re-derived by a
third party. The per-rollout records behind them (submissions used, verdict vectors,
timings, reports) are held by Revyl and available for audit on request: open an issue in
this repository.

Rollouts invalidated by benchmark-side failures — an infrastructure crash, a wrong-build
grading, a guard abort — are excluded and re-run; they never count for or against a
contestant. Protocol violations by an agent (touching the grading side, editing
`submit.sh`, and the like) void the rollout entirely: cheating carries no price, only a
rule.
