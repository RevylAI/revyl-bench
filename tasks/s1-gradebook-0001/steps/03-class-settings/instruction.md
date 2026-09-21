# Step 03 — class analytics, the ranking, and settings

Implement the Class tab and the Settings tab per the root contract.

## Requirements

1. **Assessments block**: one row per assessment in seed order reading
   `<assessment> <class average>% (<n> scores)`, the average over **recorded** scores
   only (ground rule 7). At the seed: `HW1 85.0% (6 scores)`, `HW2 83.0% (5 scores)`,
   `HW3 85.8% (6 scores)`, `Quiz 1 83.8% (6 scores)`, `Quiz 2 82.5% (5 scores)`,
   `Midterm 82.5% (6 scores)`.

2. **Hardest assessment**: the line `Hardest assessment: <assessment>` — the lowest
   class average, ties broken by the earlier assessment in the fixed order. At the seed
   `Quiz 2` and `Midterm` tie at `82.5%`, so the line reads
   `Hardest assessment: Quiz 2`.

3. **Ranking block**: one row per student reading `<position>. <name> <overall>
   <letter>`, ordered by ground rule 6 — overall descending, then exams average
   descending, then name A–Z. At the seed: `1. Ben 90.0 A`, `2. Ethan 85.3 B`,
   `3. Aisha 85.3 B`, `4. Chloe 85.3 B`, `5. Farah 75.1 C`, `6. Diana 72.5 C` — `Ethan`
   above `Aisha` on exams average despite name order, `Aisha` above `Chloe` on name.

4. **Saving a score recomputes the class view** (ground rule 8). Example from the seed:
   saving `38` for `Diana` on `Quiz 2` makes the `Quiz 2` row read `84.6% (6 scores)`,
   flips the hardest line to `Hardest assessment: Midterm` (the tie is broken; `Midterm`
   is now the sole lowest), and re-sorts the ranking so it ends `5. Diana 80.0 B`,
   `6. Farah 75.1 C`.

5. **Settings tab**: a `Course` block with `Students: <n>`, `Assessments: <n>` and
   `Scores recorded: <n>` — the recorded-score count, so `34` at the seed and `35` after
   the entry above — and a `Weights` block with `Homework 20%`, `Quizzes 30%`,
   `Exams 50%`.

6. Saved scores persist across navigation: leaving a tab and returning shows the same
   averages, the same ranking and the same totals (store state; no backend, no disk
   persistence). Selecting a tab always shows it from the top (ground rule 14).

## Observable outcome the hidden test checks

Class tab shows the six class averages with `Quiz 2 82.5% (5 scores)` and
`Hardest assessment: Quiz 2`, and the full seed ranking → Students tab → record `Diana` /
`Quiz 2` / `38` → Class tab → `Quiz 2 84.6% (6 scores)`, `Hardest assessment: Midterm`,
ranking ends `5. Diana 80.0 B`, `6. Farah 75.1 C` → Settings tab → `Students: 6`,
`Assessments: 6`, `Scores recorded: 35` and the `Weights` block.
