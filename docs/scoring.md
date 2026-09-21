# Scoring — how a submission becomes a score

This page explains how a graded submission turns into a number: the formula, why each
factor exists, and worked examples on real runs. The implementation, which defines every
constant and edge case, is [`runtime/score/score_v0.py`](../runtime/score/score_v0.py).

## The formula

```
Score % = 100 × Outcome × Submissions × Time × Regressions
```

**Outcome (0 → 1): what the final submission passes.**

```
Outcome = 0.2 × (consecutive milestone tests passed)  +  0.4 × (final end-to-end passed)

nothing   one step   two steps   three steps   everything
   0    →   0.2    →   0.4     →    0.6     →    1.0
```

Milestone tests count only as an unbroken run from the first one: an app whose first
screen is broken earns no milestone credit no matter what later screens do — so "fixed
step 3, broke step 1" can never outscore "did nothing." The end-to-end test is worth
double a milestone because it is the only test that proves the whole app works at once.

**Submissions: 0.80 per additional submission.**

```
1 submission → ×1.00      2 → ×0.80      3 → ×0.64      5 (the cap) → ×0.41
```

A submission is a final-exam attempt against the grading suite. The penalty is
deliberately sized so that submitting merely to see what the suite says always
costs more than an agent saves by skipping its own on-device verification: probing the
tests is a losing strategy, and contestants are told so.

**Time: up to −40%, log-curved, on agent working time only.**

```
Time = 1 − 0.40 × ln(T / 5 min) / ln(400 min / 5 min)     (clamped; floor 0.60)

11 min → ×0.93        28 min → ×0.84        400 min → ×0.60
```

T counts only the time the agent is actively working; build and grading waits are the
bench's cost and are excluded. The curve ends at 400 minutes rather than the 480-minute
cap because up to five build-and-grade cycles (about 16 minutes each) come out of the wall clock. The curve is logarithmic — the difference between 11 and
28 minutes matters, the difference between 3.3 and 3.6 hours does not — and floored at
0.60 so that outcome always dominates: the slowest correct run still beats a fast broken
one. Time spent verifying on-device is time well spent, which is why the curve is gentle
by design: on-device verification is the behavior that produces first-try passes.

**Regressions: 0.80 per event.** A test that passed on an earlier submission and fails on
a later one is a regression. Breaking working software is penalized on top of the outcome
damage it already causes.

**What is deliberately not in the formula:**

- **Tokens** — nearly collinear with time in practice, and accounted for differently by
  each provider. Token totals are published beside the leaderboard for the harnesses that
  record them ([`season1-results.md`](season1-results.md)); dollars are not published,
  because several rows have no per-token price. Neither is charged in the score — that
  would double-charge time.
- **Turns** — not comparable across harnesses, since one harness's "turn" may batch far
  more work than another's. Published descriptively.
- **Violations** — breaking a protocol rule (touching the grading side, editing the
  submission tooling, and so on) is not a deduction; it voids the run entirely. Cheating
  has no price, only a rule.

## Aggregation

```
task cell   = mean score over 3 seeds
leaderboard = mean over the task cells
```

Always the mean — never best-of-n, which rewards variance and can be bought by funding
more attempts. Bench-side failures (infrastructure crashes, misconfigured grading,
aborted setups) are excluded and re-run; they never count for or against a contestant. A
submission that fails to *build*, or whose built app crashes on launch, is the contestant's
failure — shipping a source tree that does not compile or start consumes a submission.

## Worked examples (real runs)

Five season-1 rollouts. Each id is in [`results/official.jsonl`](../results/official.jsonl)
with the score shown here. The factors are the ones the scorer recorded for that run.

| case | rollout | what happened | arithmetic | score |
|---|---|---|---|---|
| first submission passes, fast | commerce, seed 3, GPT-5.6 terra `s1cm-cx-terra-s3-f9313b11` | all four tests pass, 1 submission, 6.2 min agent time | 1.0 × 1.00 × 0.981 × 1.00 | **98.1%** |
| first submission passes, slow | food-delivery, seed 3, GLM-5.2 `s1fd-oc-glm52-s3-e497736c` | all four tests pass, 1 submission, 162.4 min | 1.0 × 1.00 × 0.682 × 1.00 | **68.2%** |
| one fix cycle | ride-booking, seed 2, Muse Spark 1.3 `s1rb-oc-muse13-s2-dbfce7f3` | failed on submission 1, all four pass on submission 2, 11.9 min | 1.0 × 0.80 × 0.921 × 1.00 | **73.7%** |
| solved, with a regression on the way | gradebook, seed 3, Muse Spark 1.3 `s1gb-oc-muse13-s3-a8a3f840` | all four pass on submission 3; one earlier fix broke a test that had been passing; 42.1 min | 1.0 × 0.64 × 0.805 × 0.80 | **41.2%** |
| ended unsolved at the cap | scheduler, seed 1, GPT-5.6 terra `s1sc-cx-terra-s1-5685a1c4` | five submissions used; the three stage tests pass and the end-to-end journey still fails (outcome 0.6); one regression; 14.8 min | 0.6 × 0.41 × 0.901 × 0.80 | **17.7%** |

The first two rows are the time factor alone: both runs are correct on the first
submission, and 156 more minutes of agent working time cost 30 points. The last row is
every factor at once, and it is why a fast model that submits to find out what is wrong
ends up below a slow one that verifies on the device first.

## What contestants are told

The contestant briefing discloses the incentive order qualitatively — outcome dominates,
then fewest submissions, then least working time; regressions penalized severely;
violations void the run — without publishing the constants. The full formula lives here,
in the open, because auditability beats secrecy: every input to it (verdict vectors,
timestamps, submission counts) is recorded per run and can be re-derived by a third party
from the published records.
