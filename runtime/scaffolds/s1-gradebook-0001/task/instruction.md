# MarkBook — build a mobile gradebook app

You are a coding agent building a fresh iOS mobile app from the provided Expo scaffold
(Expo SDK 57, Expo Router, TypeScript). The product is a teacher's gradebook: a student
roster whose grades are **entirely computed** from a table of raw scores through three
layers — per-category averages, a weighted overall grade, and a letter grade — plus a
form for recording a new score (which recomputes every affected value), and a class view
with per-assessment averages, the hardest assessment, and a ranking of the students.

The work is split into three steps (see `steps/01-tabs`, `steps/02-students-entry`,
`steps/03-class-settings`, each with its own `instruction.md`), followed by a final
end-to-end acceptance run. Complete the steps in order.

## How your work is verified

After each submission, **hidden device tests** run your app on a real cloud iOS
simulator and grade journeys with screenshot validations. You never see the test
definitions. Every submission is graded against the **full suite** — all step tests
plus the final e2e — so a change that breaks an earlier step's behavior is caught
immediately. If a run fails, you receive the run report (failed-criteria text,
per-step verdicts, screenshots); fix your code and resubmit. Every requirement the
tests check is stated in this contract and the step contracts; nothing hidden is
required beyond what is written here.

The tests run a **baked-JS Release build** of your app, built by the benchmark from the
source you submit (`./submit.sh`) — you never build or upload a binary yourself. Code
changes are only visible to the verifier after a new submission. Iterate cheaply in the
dev-client session first; submit when you believe the JS is finished.

## Ground rules (binding — the tests depend on these)

1. **Nothing is stored, everything is computed.** The seed contains **only** the roster,
   the assessments and the raw scores. Every category average, overall grade, letter
   grade, ranking position, class average, hardest-assessment verdict and Settings total
   is derived from the score table.

2. **The weights (exact).** `Homework` counts **20%**, `Quizzes` **30%**, `Exams`
   **50%** of the overall grade.

3. **Category averages (exact).** A student's category average is
   `points earned / points possible`, as a percentage, **over the assessments that
   student has a recorded score for**. A missing score is **excluded — it is not a
   zero**, and its assessment's maximum does not count towards points possible. `Ethan`
   has no `HW2` score, so his homework average is `35/40 = 87.5%`, not `35/60 = 58.3%`.
   (Every student has at least one recorded score in every category, at seed and in
   every state the tests visit.)

4. **The rounding rule (exact, and the order is binding).** All rounding is
   **half-up to 1 decimal**: a value ending in exactly 5 at the second decimal rounds
   **up**, never to even — `85.25 → 85.3`, `86.25 → 86.3`, `75.05 → 75.1`. The overall
   grade is computed in two steps and the order matters:

   - **first** round each category average to 1 decimal (these rounded values are what
     the screens display), **then**
   - the overall grade is `0.20 × homework + 0.30 × quizzes + 0.50 × exams` **of those
     rounded category averages**, rounded half-up to 1 decimal.

   Weighting the unrounded averages instead gives different numbers and is wrong.
   Worked example: `Farah`'s rounded averages are `88.3` / `86.3` / `63.0`, so her
   overall is `0.2×88.3 + 0.3×86.3 + 0.5×63.0 = 75.05 → 75.1`; weighting her unrounded
   averages (`88.333…`, `86.25`, `63`) gives `75.041… → 75.0`, which the tests fail.

   Do the arithmetic in integers, not floats: a rounded category average is a whole
   number of **tenths** of a percent, so `2×A + 3×B + 5×C` (A, B, C in tenths) is the
   overall in whole **thousandths**, and half-up to tenths is exact. `Aisha` is
   `2×850 + 3×875 + 5×840 = 8525 → 85.3` (a float or a round-to-even gives `85.2`).

5. **Letter grades (exact boundaries).** From the **rounded** overall grade:
   `A` at `90.0` or above, `B` at `80.0` or above, `C` at `70.0` or above, `D` at `60.0`
   or above, `F` below that. A grade sitting **exactly on a boundary earns the higher
   letter**: `Ben`'s overall is exactly `90.0` and is an `A`, not a `B`.

6. **The ranking rule (exact), applied in this order.** The class ranking sorts students
   by **overall grade descending**; ties broken by **exams category average
   descending**; then by **name A–Z**. Positions are numbered 1–6 with no shared ranks.
   Both tie-break levels decide a real pair in the seed data, so both must be
   implemented.

7. **Class statistics (exact).** An assessment's class average is the mean of its
   **recorded** scores as a percentage of its maximum, rounded half-up to 1 decimal.
   The **hardest assessment** is the one with the **lowest** class average; a tie is
   broken by **the earlier assessment in the fixed assessment order** (`HW1`, `HW2`,
   `HW3`, `Quiz 1`, `Quiz 2`, `Midterm`). The seed produces a real tie.

8. **Saving a score recomputes everything.** Saving updates the student's category
   average, overall grade and letter, the class ranking, the assessment's class average,
   the hardest-assessment line and the `Scores recorded` total, immediately. Saving a
   score for a student–assessment pair that already has one **replaces** it.

9. **Deterministic data — no clocks, no randomness.** No `Date.now()`, `new Date()`,
   `Math.random()`, or uuid libraries anywhere in app code. No dates or time-of-day text
   is rendered anywhere. Every value on screen must be computable from this contract
   alone.

10. **Debounced one-shot saving.** The `Save` button is one-shot: a rapid double-tap
    saves **exactly one** score. Disabling it briefly after press (≈250–300 ms) is one
    acceptable implementation. It takes effect on the single tap that triggers it —
    there is no confirmation dialog, alert, or intermediate screen, and the app never
    opens a native alert dialog at any point. `Save` is disabled until a student, an
    assessment and a score have all been chosen.

11. **Verbatim numeric input.** The score input accepts digits only and is interpreted
    as a whole number of points.

12. **State survives navigation.** Saved scores persist when the user navigates between
    tabs and pushes/pops screens (module-level/store state is sufficient; no backend, no
    disk persistence — a fresh install starts from the seed below).

13. **Navigation shape.** The app opens directly on the Students tab — no login,
    onboarding, or splash gate — and the roster is interactive within two seconds of
    launch. The three tabs are a bottom tab bar. Tapping a roster row **pushes** that
    student's detail screen (native stack header titled with the student's name and a
    back button). Back returns to the tab bar. Every roster row is tappable.

14. **Everything the user must reach stays on screen.** While the score input is focused
    and the on-screen keyboard is up, the input and the `Save` button remain visible and
    tappable. **After saving, the saved student's roster row is visible without manual
    scrolling**, wherever the recomputed values placed it. **Selecting a tab always
    shows it from the top** — a tab's content starts at the top whenever the user
    switches to it, never at a stale scroll offset.

15. **Textual state.** Averages, grades, letters, ranking positions and counts are exact
    text strings (pinned below) — never encoded only in colours, icons or bar widths.
    Every category average and class average renders with exactly 1 decimal and a `%`;
    every overall grade renders with exactly 1 decimal and no `%` (`90.0`, not `90`).

## Seed data (exact values — copy these verbatim)

Students (six, roster order is alphabetical): `Aisha`, `Ben`, `Chloe`, `Diana`, `Ethan`,
`Farah`.

Categories and weights:

| category | weight |
|---|---|
| Homework | 20% |
| Quizzes | 30% |
| Exams | 50% |

Assessments, in this fixed order, with the maximum score for each:

| assessment | category | out of |
|---|---|---|
| HW1 | Homework | 20 |
| HW2 | Homework | 20 |
| HW3 | Homework | 20 |
| Quiz 1 | Quizzes | 40 |
| Quiz 2 | Quizzes | 40 |
| Midterm | Exams | 100 |

Scores (a dash means **not recorded** — excluded from every average and count, per
ground rule 3):

| student | HW1 | HW2 | HW3 | Quiz 1 | Quiz 2 | Midterm |
|---|---|---|---|---|---|---|
| Aisha | 17 | 17 | 17 | 38 | 32 | 84 |
| Ben | 17 | 17 | 17 | 38 | 38 | 89 |
| Chloe | 17 | 16 | 17 | 37 | 34 | 84 |
| Diana | 15 | 16 | 17 | 18 | *(not recorded)* | 86 |
| Ethan | 18 | *(not recorded)* | 17 | 34 | 28 | 89 |
| Farah | 18 | 17 | 18 | 36 | 33 | 63 |

## Derived values (the tests assert these exact strings and orders)

**Per-student derivations at the seed** (category averages rounded first, then weighted
— ground rule 4):

| student | homework | quizzes | exams | overall | letter |
|---|---|---|---|---|---|
| Aisha | 85.0% | 87.5% | 84.0% | 85.3 | B |
| Ben | 85.0% | 95.0% | 89.0% | 90.0 | A |
| Chloe | 83.3% | 88.8% | 84.0% | 85.3 | B |
| Diana | 80.0% | 45.0% | 86.0% | 72.5 | C |
| Ethan | 87.5% | 77.5% | 89.0% | 85.3 | B |
| Farah | 88.3% | 86.3% | 63.0% | 75.1 | C |

The worked cases to check: `Ben` sits exactly on the `A` boundary (`2×850 + 3×950 +
5×890 = 9000 → 90.0`, an `A` under ground rule 5); `Aisha` and `Ethan` both land on
exactly `85.25 → 85.3` (half-up, not `85.2`); `Chloe`'s quiz average is `71/80 = 88.75 →
88.8%`; `Farah` is the rounding-order case from ground rule 4 (`75.1`, not `75.0`);
`Ethan`'s homework average is over `40` possible points, not `60`; `Diana`'s quiz
average is her `Quiz 1` alone, `18/40 = 45.0%`.

**The class ranking at the seed**, in order:

| # | student | overall | letter |
|---|---|---|---|
| 1 | Ben | 90.0 | A |
| 2 | Ethan | 85.3 | B |
| 3 | Aisha | 85.3 | B |
| 4 | Chloe | 85.3 | B |
| 5 | Farah | 75.1 | C |
| 6 | Diana | 72.5 | C |

Both tie-break levels decide a real pair here, so both must work:

- `Ethan` above `Aisha` — decided by **exams average** (89.0% v 84.0%), *against* name
  order.
- `Aisha` above `Chloe` — decided by **name A–Z** (exams averages both 84.0%).

**Class averages at the seed** (over recorded scores only):

| assessment | class average | scores |
|---|---|---|
| HW1 | 85.0% | 6 |
| HW2 | 83.0% | 5 |
| HW3 | 85.8% | 6 |
| Quiz 1 | 83.8% | 6 |
| Quiz 2 | 82.5% | 5 |
| Midterm | 82.5% | 6 |

`Quiz 2` and `Midterm` **tie at 82.5% as the joint lowest**; `Quiz 2` comes earlier in
the assessment order, so the hardest assessment at the seed is `Quiz 2` (ground rule 7).

**Worked example — recording a score.** Saving `38` for `Diana` on `Quiz 2`:

- `Diana`'s quiz average becomes `56/80 = 70.0%`, her overall becomes
  `0.2×80.0 + 0.3×70.0 + 0.5×86.0 = 80.0` — **exactly on the `B` boundary**, so her
  letter changes from `C` to `B`.
- The ranking re-sorts: `Diana` moves from 6th to 5th, above `Farah`; positions 1–4 are
  unchanged.
- `Quiz 2`'s class average becomes `203/240 = 84.58… → 84.6%` over `6` scores, so
  `Midterm` (`82.5%`) is now the sole lowest and the hardest assessment becomes
  `Midterm`.
- `Scores recorded` goes from `34` to `35`. No other student's numbers change.

**Settings totals**: `Students: 6`, `Assessments: 6`, and `Scores recorded: 34` at the
seed — thirty-four, because `Diana`'s `Quiz 2` and `Ethan`'s `HW2` are not recorded —
becoming `Scores recorded: 35` after the entry above.

## Pinned UI text (tests match these exactly — render them verbatim)

- Tab bar labels: `Students`, `Class`, `Settings`. Each tab screen shows its heading
  text: `Students`, `Class`, `Settings`.
- **Students tab**: one row per student in roster (alphabetical) order reading
  `<name> <overall> <letter>` — for example `Ben 90.0 A` — each row pushing the
  student's detail screen. Below the roster, a `Record a score` section containing: a
  row labelled `Student` followed by one tappable button per student name, a row
  labelled `Assessment` followed by one tappable button per assessment name, a score
  input with the hint text `0` (digits only), and a button labelled `Save`. The pickers
  are **plain tappable buttons showing the names**, not a wheel picker, dropdown or
  modal — the selected button in each row is visually marked and its name is readable
  without opening anything. The rows scroll horizontally if the buttons do not fit.
- **Student detail screen** (pushed): header title is the student's name; three sections
  in the order `Homework`, `Quizzes`, `Exams`, each listing its assessments in seed
  order as `<assessment> <score>/<max>` (`HW1 17/20`) or `<assessment> not recorded`,
  and each containing its average line: `Homework average: <x.x>%`,
  `Quizzes average: <x.x>%`, `Exams average: <x.x>%`. Then the lines
  `Overall grade: <x.x>` and `Letter grade: <letter>`. For `Farah` that is `HW1 18/20`,
  `HW2 17/20`, `HW3 18/20`, `Homework average: 88.3%`, `Quiz 1 36/40`, `Quiz 2 33/40`,
  `Quizzes average: 86.3%`, `Midterm 63/100`, `Exams average: 63.0%`,
  `Overall grade: 75.1`, `Letter grade: C`.
- **Class tab**: an `Assessments` block with one row per assessment in seed order
  reading `<assessment> <class average>% (<n> scores)` — for example
  `Quiz 2 82.5% (5 scores)`; then the line `Hardest assessment: <assessment>`; then a
  `Ranking` block with one row per student in ranking order reading
  `<position>. <name> <overall> <letter>` — for example `1. Ben 90.0 A`.
- **Settings tab**: a `Course` block with the three lines `Students: <n>`,
  `Assessments: <n>` and `Scores recorded: <n>`, then a `Weights` block with the three
  lines `Homework 20%`, `Quizzes 30%` and `Exams 50%`.

## Final acceptance

The final e2e journey: launch → Students tab lists `Aisha 85.3 B`, `Ben 90.0 A`,
`Chloe 85.3 B`, `Diana 72.5 C`, `Ethan 85.3 B`, `Farah 75.1 C` → tap the `Farah` row →
detail shows `Homework average: 88.3%`, `Quizzes average: 86.3%`, `Exams average: 63.0%`,
`Overall grade: 75.1`, `Letter grade: C` → back → Class tab shows
`Quiz 2 82.5% (5 scores)`, `Midterm 82.5% (6 scores)` and `Hardest assessment: Quiz 2`,
with the ranking `1. Ben 90.0 A`, `2. Ethan 85.3 B`, `3. Aisha 85.3 B`, `4. Chloe 85.3 B`
→ Students tab → in `Record a score`, save `Diana` / `Quiz 2` / `38` → the `Diana` roster
row now reads `Diana 80.0 B` → tap it → detail shows `Quiz 2 38/40`,
`Quizzes average: 70.0%`, `Overall grade: 80.0`, `Letter grade: B` → back → Class tab →
`Quiz 2 84.6% (6 scores)`, `Hardest assessment: Midterm`, and the ranking now ends
`5. Diana 80.0 B`, `6. Farah 75.1 C` → Settings tab → `Students: 6`, `Assessments: 6`,
`Scores recorded: 35` and the `Weights` block. It must complete without manual
intervention.
