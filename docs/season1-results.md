# Season 1 — results

Results for season 1 of the benchmark: 20 whole-app tasks, each graded on a real iOS
simulator by four frozen device tests withheld from the agent. Every figure here is derived
from the raw rollout records by [`runtime/score/score_v0.py`](../runtime/score/score_v0.py) against the scoring
rules in [`scoring.md`](scoring.md).

## Leaderboard

| rank | model × harness (reasoning) | tasks solved | rollouts | mean score | first-try rate |
|---|---|---|---|---|---|
| 1 | **Claude Opus 5 × Claude Code 2.1.235 (high)** | 20/20 | 60 | **81.8%** | 86.7% |
| 2 | GPT-6 Astra × Codex 0.153.4 (medium) | 20/20 | 60 | 78.6% | 68.3% |
| 3 | GLM-5.2 × opencode 1.18.18 (default) | 20/20 | 60 | 76.3% | 90.0% |
| 4 | GPT-5.6 terra × Codex 0.153.4 (medium) | 15/20 | 60 | 72.4% | 50.0% |
| 5 | Muse Spark 1.3 × opencode 1.18.18 (default) | 15/20 | 60 | 68.5% | 65.0% |
| 6 | Nemotron 3 Ultra 550B-A55B × opencode 1.18.18 (default) ¹ ³ | 10/20 | 23 | 28.2% | 0.0% |
| 7 | Nemotron 3 Nano 30B-A3B × opencode 1.18.18 (default) ² ³ | 0/18 | 24 | 0.5% | 0.0% |

Each model runs on one pinned harness version at the stated reasoning setting, with a cap
of five submissions and 480 minutes per rollout. Ranks 1–5 ran every task at three seeds
(20 tasks × 3 seeds = 60 rollouts) and are the **official** rows. Ranks 6 and 7 are
**provisional** (³).

- **Mean score** is the mean over tasks of the task's mean rollout score. A rollout scores
  100 for passing all four tests on the first submission, discounted ×0.8 per extra
  submission, ×0.8 per regression, and by agent working time (never below ×0.6); a rollout
  that never passes all four tests keeps only partial credit. The rules are in
  [`scoring.md`](scoring.md).
- **Tasks solved** counts a task only when every seed of it ended with all four tests
  passing.
- **First-try rate** is the fraction of rollouts whose first submission passed all four
  tests. A submission lost to a build-service or grading fault is refunded and is not the
  agent's first try.

¹ One seed per task: 20 cells, 23 rollouts. Some of this row's runs overlapped a
build-service outage on 2026-09-10; league, bookings and invoicing were run a second time
and each of those cells is the mean of its two runs.

² A small open model, listed for scale rather than as a competitor: 15 tasks at one seed
(commerce and personal-finance were not run) plus auctions, bookings and invoicing at
three seeds.

³ `"legitimacy": "provisional"` in [`results/official.jsonl`](../results/official.jsonl): a
partial matrix, not the 20 × 3 the official rows ran. Read these two rows as an order of
magnitude, not as a rank.

Harness versions and the exact model id each row requested are in
[`runtime/contestants/registry.yaml`](../runtime/contestants/registry.yaml). Season 1 ran
under protocols 5 and 6 (6 adds the Revyl CLI skills bundle to the agent container); each
row's protocol is recorded in `results/official.jsonl`, where "5 + 6" marks a row that joins
campaigns run under both. The runtime in this repository has
moved on to protocol 9, so a row you grade yourself is not comparable cell-for-cell with
the rows above.

Token use, where the harness records it: Opus 5 1,098M in / 6.5M out, GLM-5.2 1,142M in /
5.8M out, Muse Spark 1.3 997M in / 3.7M out, each over 60 rollouts. Input counts every
prompt token, cached or not.

## Scores by task

Mean rollout score per task (three seeds unless marked). **✗** marks a task the model did
not solve on every seed; "—" is a task that was not run.

| task | Opus 5 | GPT-6 Astra | GLM-5.2 | GPT-5.6 terra | Muse Spark 1.3 | Nemotron 3 Ultra (n=1) | Nemotron 3 Nano (n=1) |
|---|---|---|---|---|---|---|---|
| auctions | 87.6 | 77.7 | 48.5 | 44.8 ✗ | 57.4 | 0.0 ✗ | 0.0 ✗ (n=3) |
| bookings | 73.9 | 64.8 | 76.5 | 92.8 | 79.6 | 30.4 ✗ (n=2) | 0.0 ✗ (n=3) |
| commerce | 86.4 | 88.0 | 66.7 | 88.6 | 80.1 | 31.9 | — |
| food-delivery | 84.3 | 86.4 | 74.2 | 73.8 | 54.2 ✗ | 0.0 ✗ | 0.0 ✗ |
| gradebook | 87.0 | 87.6 | 80.3 | 73.3 | 63.2 | 14.6 | 0.0 ✗ |
| habits | 82.5 | 70.4 | 80.7 | 93.9 | 79.8 | 56.9 | 0.0 ✗ |
| health-fitness | 74.0 | 68.7 | 71.8 | 63.7 | 68.7 | 32.8 | 0.0 ✗ |
| inventory | 83.8 | 56.8 | 75.3 | 50.0 ✗ | 64.0 ✗ | 39.2 | 9.1 ✗ |
| invoicing | 84.9 | 80.7 | 78.5 | 65.8 | 71.7 | 9.7 ✗ (n=2) | 0.0 ✗ (n=3) |
| kanban | 84.5 | 86.9 | 80.3 | 81.2 | 77.3 | 0.0 ✗ | 0.0 ✗ |
| league | 84.8 | 80.1 | 78.1 | 70.3 | 59.4 ✗ | 34.3 ✗ (n=2) | 0.0 ✗ |
| library | 82.8 | 72.9 | 79.6 | 63.7 ✗ | 39.5 ✗ | 48.1 | 0.0 ✗ |
| payroll | 76.2 | 80.2 | 80.6 | 62.0 | 79.6 | 50.2 | 0.0 ✗ |
| personal-finance | 77.1 | 81.0 | 87.2 | 90.2 | 67.2 | 4.5 ✗ | — |
| recipes | 86.6 | 80.5 | 76.8 | 54.6 ✗ | 83.9 | 38.2 | 0.0 ✗ |
| ride-booking | 82.9 | 86.4 | 84.6 | 92.3 | 81.8 | 70.3 | 0.0 ✗ |
| scheduler | 78.1 | 79.0 | 76.0 | 67.6 ✗ | 73.3 | 63.6 | 0.0 ✗ |
| split-bill | 79.6 | 77.5 | 72.8 | 65.0 | 74.4 | 7.3 ✗ | 0.0 ✗ |
| team-chat | 82.3 | 83.4 | 78.1 | 81.4 | 44.8 ✗ | 19.2 ✗ | 0.0 ✗ |
| till | 77.6 | 82.1 | 79.2 | 72.5 | 70.7 | 12.6 ✗ | 0.0 ✗ |

## How each model behaved

The score is `100 × outcome × submissions × time × regressions` ([`scoring.md`](scoring.md)).
This table shows where each model's points went, over the rollouts counted above.

| model | first try | rollouts solved | mean submissions | rollouts with a regression | median agent time | mean × submissions | mean × time |
|---|---|---|---|---|---|---|---|
| Claude Opus 5 | 52/60 | 60/60 | 1.13 | 0 | 26 min | 0.97 | 0.84 |
| GPT-6 Astra | 41/60 | 60/60 | 1.33 | 1 | 25 min | 0.93 | 0.84 |
| GLM-5.2 | 54/60 | 60/60 | 1.18 | 0 | 48 min | 0.97 | 0.79 |
| GPT-5.6 terra | 30/60 | 55/60 | 2.02 | 6 | 13 min | 0.83 | 0.90 |
| Muse Spark 1.3 | 39/60 | 55/60 | 1.67 | 4 | 50 min | 0.89 | 0.79 |
| Nemotron 3 Ultra | 0/23 | 12/23 | 3.74 | 3 | 57 min | 0.53 | 0.73 |

- **The top three solve everything; the discounts order them.** Opus 5, GPT-6 Astra and
  GLM-5.2 ended all 60 rollouts with all four tests passing. GLM-5.2 passes on the first
  submission most often (54/60) and never regresses, but its median agent time is 48
  minutes against Opus 5's 26, and the time factor (0.79 against 0.84) puts it third.
- **GPT-6 Astra is as fast as Opus 5 and submits more.** 19 of its 60 rollouts needed more
  than one submission, each extra one costing ×0.8.
- **GPT-5.6 terra is the fastest model and the least careful.** Median 13 minutes, the
  best time factor in the table, but only half its rollouts pass on the first submission,
  six hit the cap of five, and five never reach all four tests passing.
- **Muse Spark 1.3 is the mirror image:** better first-try rate than terra (39/60), the
  slowest median of the top five.
- **Nemotron 3 Ultra solves 12 of 23 rollouts, never on the first submission,** at a mean
  of 3.7 submissions. Nemotron 3 Nano solved none of its 24.
- **Adjacent ranks are close.** A bootstrap over the 20 tasks gives 95% intervals on the
  gap in mean score of [+0.3, +6.8] for Opus 5 over GPT-6 Astra, [−2.2, +7.0] for Astra
  over GLM-5.2, [−1.5, +9.1] for GLM-5.2 over terra and [−3.2, +10.8] for terra over Muse
  Spark. Only the first excludes zero: read ranks 2–5 as a group, not a strict order.
- **No task is easy for everyone.** GPT-5.6 terra has the best score in the table on
  bookings (92.8), habits (93.9), ride-booking (92.3) and personal-finance (90.2), and
  fails at least one seed of auctions, inventory, library, recipes and scheduler.
  Auctions separates the field most: 87.6 for Opus 5, 48.5 for GLM-5.2.

## Provenance

- Every rollout was graded the same way: the app is built from the exact source
  tree the agent committed, installed on an isolated iOS simulator, and graded by the four
  frozen device tests.
- Rollouts invalidated by bench-side faults (a failed build service, a grading fault) are
  excluded and documented with an audit trail, so they count neither for nor against a
  contestant. One exception (footnote ¹): for three Nemotron 3 Ultra cells the first run,
  made during the 2026-09-10 outage, was kept and averaged with its re-run.
- The scores, rollout ids, seeds and campaigns behind every row are in
  [`results/official.jsonl`](../results/official.jsonl), which is enough to re-derive every
  mean, cell and solved count on this page. First-try rate, submissions, regressions and
  agent time come from the per-rollout records, which are not in the repository. Each
  rollout id keys its full record in Revyl's artifact store: submission log, harness
  transcript, grading reports, source bundle and device-session recordings. Records are
  available for audit on request — open an issue in this repository.

