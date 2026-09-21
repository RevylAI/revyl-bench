# revyl-bench

**How well can coding agents build real mobile apps from a specification, verified on
real devices, graded by device tests the agent never sees, and auditable down to the
screenshot?**

revyl-bench is a benchmark. An agent (a model paired with a coding harness) starts from a
blank Expo/TypeScript scaffold and a precise product specification. It builds the app in a
live device loop: writing code, hot-reloading onto a cloud iOS simulator, and driving the
real UI to check its work, then submits the source. The benchmark builds that source into
a binary and grades it against a **frozen suite of four device tests**, withheld from the
agent, on isolated simulators: one per build stage, plus a final end-to-end journey. Failed checks return as
redacted evidence: the criterion, the judge's reasoning, and screenshots of what the device
actually showed. The agent diagnoses, repairs, and resubmits within a fixed budget.

Season 1 is 20 tasks. Seven model and harness pairs have been evaluated on it, from
frontier models that solve all 20 to small open models that solve none:
[season 1 results](#season-1-results).

## What it measures

Static coding benchmarks score a diff against reference tests. revyl-bench measures the
skills that building software actually requires: long-horizon planning over a growing
system, **on-device investigation and verification**, evidence-driven repair, and
regression discipline. Every submission is graded against the full suite, so breaking
previously working code is caught and penalized.

The tasks resist memorization by construction. The apps are synthetic and never
published, so pretraining recall pays nothing. The test suites are readable in
[`grading-side/`](grading-side/) — so that anyone can grade in their own Revyl organisations —
but they are never mounted or copied into the agent's container, and the agent's Revyl key
cannot list, pull or run a test in the grading organisation. One limit, stated plainly:
the agent's container has outbound network access (it needs npm, Expo, GitHub and Revyl),
so an agent could fetch this public repository. A run whose transcript shows that is
excluded from scoring (the `suite_fetch` check). The suites add the order of the journey,
not new values: what they assert is stated in, or follows directly from, the task's
`instruction.md`. They were first published on 2026-09-20; a model trained on data
collected after that date may have seen them, and its result should say so.
The graded binary is always built by the benchmark from the exact source the agent
committed, and every verdict traces to a screenshot and a device-session recording.

## How an evaluation works

```
scaffold + spec ─→ agent builds & verifies on-device ─→ submits source
      ↑                                                       │
      │                                     benchmark builds the binary (~2–5 min)
 redacted feedback                                            │
 (failed criteria + screenshots)              frozen 4-test device suite (~10 min)
      │                                                       │
      └───────── fail: diagnose & repair ←── verdict ──→ all pass: done
```

One evaluation is one task attempt. Full detail: [`docs/how-it-works.md`](docs/how-it-works.md).

## Scoring

```
Score % = 100 × Outcome × Submissions × Time × Regressions

Outcome:      0.2 per consecutive stage passed, + 0.4 for the end-to-end test
Submissions:  ×0.80 per extra submission (probing the suite by submitting is a losing strategy)
Time:         up to −40%, log-curved, counting agent working time only
Regressions:  ×0.80 per "was passing, now fails" event
```

Rationale and worked examples: [`docs/scoring.md`](docs/scoring.md).

## Season 1 results

20 tasks, three seeds each, a cap of five submissions and 480 minutes per rollout. Each
model runs on one pinned harness version.

| rank | model × harness (reasoning) | tasks solved | mean score | first-try rate |
|---|---|---|---|---|
| 1 | **Claude Opus 5 × Claude Code (high)** | 20/20 | **81.8%** | 86.7% |
| 2 | GPT-6 Astra × Codex (medium) | 20/20 | 78.6% | 68.3% |
| 3 | GLM-5.2 × opencode (default) | 20/20 | 76.3% | 90.0% |
| 4 | GPT-5.6 terra × Codex (medium) | 15/20 | 72.4% | 50.0% |
| 5 | Muse Spark 1.3 × opencode (default) | 15/20 | 68.5% | 65.0% |
| 6 | Nemotron 3 Ultra 550B-A55B × opencode (default), one seed — *provisional* | 10/20 | 28.2% | 0.0% |
| 7 | Nemotron 3 Nano 30B-A3B × opencode (default), 18 tasks — *provisional* | 0/18 | 0.5% | 0.0% |

Rows 1–5 are official: the full 20 × 3 matrix, every rollout graded by a pinned runtime
image whose id is recorded per campaign in [`results/official.jsonl`](results/official.jsonl).
Rows 6 and 7 are provisional (marked so in the same file): a partial matrix — one seed, and
18 of 20 tasks — listed for scale and not comparable cell-for-cell with rows 1–5.

A task counts as solved only when every seed ends with all four tests passing. First-try
rate is the share of rollouts whose first submission passed all four. The top three solve
everything, so the submission and time discounts decide their order: GLM-5.2 passes first
time most often, but it is slower (median 48 minutes of agent time against Opus 5's 26),
which puts it third. Scores by task, how each model behaved, and the intervals on
adjacent ranks: [`docs/season1-results.md`](docs/season1-results.md). The rollout ids and
scores behind every row: [`results/official.jsonl`](results/official.jsonl).

## The task set

Twenty synthetic apps, each a distinct product archetype: budgeting, ride booking,
workout tracking, commerce, food delivery, team chat, habit tracking, task boards,
league standings, meal planning, expense splitting, warehouse inventory, room scheduling,
gradebooks, payroll, library lending, a cash register, invoicing, room booking with
waitlists, and a silent auction with proxy bidding. Each task pins every value (exact
strings, numbers, and formats) so correctness is objectively judgeable from the screen,
and each decomposes into three cumulative build stages plus a final journey.

The catalog, difficulty design, and per-task detail: [`docs/tasks.md`](docs/tasks.md).
Results: [`docs/season1-results.md`](docs/season1-results.md).

## Repository layout

| Path | Contents |
|---|---|
| [`tasks/`](tasks/) | The benchmark: product specifications, step specifications, and task metadata. This is the public layer of each task. |
| [`grading-side/`](grading-side/) | The frozen device-test suites, four per task, and how to load them into your own grading organisation. Withheld from the agent at run time; readable here. |
| [`runtime/`](runtime/) | The evaluation machinery: launching an evaluation, building and grading a submission, the agent and grader container images, the contestant registry, per-task scaffolds, and the scoring implementation. Start at [`runtime/README.md`](runtime/README.md). |
| [`docs/`](docs/) | Documentation: how it works, the two organisations, scoring, the task set, campaigns, and results. |
| [`results/`](results/) | The official record: for each leaderboard row, the campaigns behind it and every counted rollout id and score. |

## Running it yourself

Everything needed to grade a rollout is in this repository. You bring two Revyl
organisations — one for grading, one for the agent — and **two Revyl users, one per
organisation**, because a Revyl API key belongs to the user who created it and acts in that
user's organisation. `runtime/provision/setup_orgs.py` then fills both organisations from
the repository (the grading app, the four tests and the suite workflow per task on one side;
the dev app and its dev-client build on the other) and writes the new ids into each
`task.toml`. The walkthrough is [`grading-side/README.md`](grading-side/README.md); what
lives in which organisation and why is [`docs/organizations.md`](docs/organizations.md);
launching and scoring is [`runtime/README.md`](runtime/README.md).

What is not here: the per-task authoring record (derivation scripts, traceability reviews)
and the device reports behind each suite's stability check. Revyl holds those, along with
the full run records of every published row, and makes them available for audit on request:
open an issue in this repository.

## What's next

Season 1 is a starting point: 20 tasks, one stack (Expo / React Native, TypeScript), one
platform (iOS). The pipeline underneath — build the submitted source, run device tests on a
real simulator, return redacted evidence — does not depend on any of those, and the next
seasons widen each one:

- **Many more tasks.** We expect to grow the task set in the coming months. The next tiers
  add deeper derivations, longer multi-screen journeys, and state that has to survive
  across them.
- **More languages and platforms.** Native iOS in Swift / SwiftUI comes first — the runtime
  already carries its scaffolding and RUNBOOK (`runtime/container/RUNBOOK-swift*.md.tmpl`) —
  then native Android in Kotlin, graded the same way: on a device, from the source the
  agent submits.
- **More kinds of work than building from a blank scaffold:** step-level tasks that start
  from a verified partial build, and repair tasks that start from a working app with one
  injected bug.
- **More rows.** New models and harnesses as they ship, at three seeds.

## Documentation

- [`docs/how-it-works.md`](docs/how-it-works.md): the evaluation pipeline, step by step
- [`docs/organizations.md`](docs/organizations.md): the two Revyl organisations an evaluation runs against, and what each key may reach
- [`docs/scoring.md`](docs/scoring.md): the scoring formula and its rationale
- [`docs/tasks.md`](docs/tasks.md): the task set and its difficulty design
- [`docs/season1-results.md`](docs/season1-results.md): season 1 results: leaderboard, scores by task, how each model behaved
- [`docs/campaigns.md`](docs/campaigns.md): how a benchmark run is organised, scored and promoted into the official record
- [`runtime/README.md`](runtime/README.md): the runtime and how to launch an evaluation
- [`grading-side/README.md`](grading-side/README.md): the device-test suites and how to load them into your own organisations

## License

Copyright 2026 Revyl. Licensed under the [Apache License, Version 2.0](LICENSE).

The app scaffolds under `runtime/scaffolds/` are the `create-expo-app` template plus
Revyl's dev-client configuration; each carries Expo's own MIT `LICENSE` file, which
continues to apply to those files.

If you publish numbers from this benchmark, cite the repository and state the protocol
version and the harness version of every row (harness versions are in the leaderboard in
[`docs/season1-results.md`](docs/season1-results.md); protocol versions are in
[`results/official.jsonl`](results/official.jsonl)).
