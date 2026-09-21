# Step 02 — computed grades, student detail, and score entry

Implement the Students tab's computed roster, the pushed student detail screen, and the
`Record a score` flow per the root contract's seed data, ground rules, and pinned UI
text.

## Requirements

1. **Roster rows** read `<name> <overall> <letter>` with every value **computed** from
   the score table (ground rules 1–5): category averages over recorded scores only,
   rounded half-up to 1 decimal; the overall as the 20/30/50 weighted sum **of the
   rounded averages**, rounded half-up to 1 decimal; the letter from the exact
   boundaries. At the seed the rows are `Aisha 85.3 B`, `Ben 90.0 A`, `Chloe 85.3 B`,
   `Diana 72.5 C`, `Ethan 85.3 B`, `Farah 75.1 C`.

2. **Student detail** (pushed, header title = the student's name, native back button):
   the `Homework` / `Quizzes` / `Exams` sections listing each assessment as
   `<assessment> <score>/<max>` or `<assessment> not recorded`, the three average lines,
   and `Overall grade:` / `Letter grade:`. For `Ben` that is `Homework average: 85.0%`,
   `Quizzes average: 95.0%`, `Exams average: 89.0%`, `Overall grade: 90.0`,
   `Letter grade: A` — exactly `90.0`, sitting on the boundary, is an `A`. For `Ethan`
   the homework section shows `HW2 not recorded` and `Homework average: 87.5%` (over 40
   possible points, not 60), and `Overall grade: 85.3`.

3. **Record a score** (below the roster): a `Student` row of name buttons, an
   `Assessment` row of assessment buttons, a score input (hint text `0`, digits only)
   and a `Save` button. Saving is one-shot (debounced), takes effect on the single tap
   with no confirmation step, and `Save` is disabled until a student, an assessment and
   a score have all been chosen.

4. **Saving recomputes** (ground rule 8): the student's category average, overall and
   letter update immediately, and the roster row shows the new values. Example from the
   seed: saving `38` for `Diana` on `Quiz 2` makes her quiz average `70.0%` and her
   overall exactly `80.0` — letter `B`, taking the higher letter on the boundary. After
   saving, `Diana`'s roster row is visible without manual scrolling (ground rule 14).

5. Saved scores persist across navigation: pushing and popping a detail screen shows the
   same values (store state; no backend, no disk persistence).

## Observable outcome the hidden test checks

Launch → the roster reads `Aisha 85.3 B`, `Ben 90.0 A`, … `Farah 75.1 C` → tap `Ben` →
detail shows the three averages, `Overall grade: 90.0` and `Letter grade: A` → back →
tap `Ethan` → detail shows `HW2 not recorded` and `Homework average: 87.5%` → back →
record `Diana` / `Quiz 2` / `38` → the `Diana` row reads `Diana 80.0 B` → her detail
shows `Quiz 2 38/40`, `Quizzes average: 70.0%`, `Overall grade: 80.0`, `Letter grade: B`.
