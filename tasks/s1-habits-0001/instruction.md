# Build a habit tracker (iOS, Expo SDK 57, TypeScript)

You are starting from a blank Expo Router scaffold. Build the app described here in three
steps. Everything the tests check is pinned in this document — if a string or a number is
not here, it is not asserted.

## How your work is verified

Every submission is graded against the FULL frozen suite: three step tests plus a final
end-to-end journey, run by Revyl device tests on a cloud iOS simulator with screenshot
validations. A submission is accepted only when all four are green.

## Ground rules (binding — the tests depend on these)

1. **A fixed 28-day window, and today is day 28.** The tracker covers days `1`..`28`.
   **Today is day 28.** It is a constant, not a clock reading.

2. **No clocks, no randomness.** No `Date.now()`, `new Date()`, `Math.random()`, or uuid
   libraries anywhere in app code. No dates or times are rendered. Every value on screen
   must be computable from this contract alone.

3. **Current streak — the rule the whole task turns on.** A habit's **current streak** is
   the number of consecutive completed days ending **exactly at day 28**. If day 28 is not
   completed, **the current streak is `0`**, however long the most recent run of completed
   days was.

   This is not the same as "the length of the last run of completed days". `Meditate` is
   completed on days 18-26 and not on 27 or 28: its most recent run is 9 days long and its
   current streak is `0`. `No sugar` is completed on every day from 5 to 27 and not on 28:
   its most recent run is 23 days long and its current streak is `0`.

4. **Frozen days — the rule this task turns on.** A day can be **frozen**: deliberately
   skipped. A frozen day **bridges** a streak — it neither breaks it nor counts toward it.
   `No sugar` is completed on days 5-27 and day 28 is **frozen**: its current streak is
   `23`, because the frozen day 28 reaches today without adding to the count. Treating a
   frozen day as completed would give `24`; treating it as missed would give `0`.

5. **Frozen days leave the completion denominator.** A day you deliberately skipped is not
   a day you were meant to do, so it is removed from the active days as well. `Morning run`
   is active days 1-28 with two frozen days, so its denominator is `26`, not `28`, and it
   reads `73%`. This is the same fact as rule 4 applied to a different quantity: an
   implementation can get every streak right and still be wrong here.

6. **Longest streak** is the longest run of consecutive completed days anywhere in the
   window, whether or not it reaches day 28. It is often not equal to the current streak.

7. **Completion % is over ACTIVE days, not the whole window.** Each habit has a start day.
   Its completion percentage is `completed days / active days`, where active days are
   `start day` through day 28 inclusive, **rounded half-up** to a whole percent. Dividing
   by 28 is wrong for any habit that did not start on day 1.

8. **Integer arithmetic.** Streaks, counts and percentages are integers. Do the percentage
   rounding in integer arithmetic; no floating point.

9. **Marking today.** Day 28 can be toggled for a habit. Marking it recomputes that
   habit's current streak, longest streak and completion % immediately, and the change is
   visible on the habits list without any further navigation.

10. **Debounced one-shot controls.** The mark control is debounced: one tap takes effect
   exactly once. No confirmation dialogs or alerts anywhere.

11. **State survives navigation, resets on a fresh install.** Marking persists while the
   app is open and across tab switches. There is no backend and no disk persistence.

12. **Alphabetical is NOT the order.** The habits list is in the seed order given below.

13. **Textual state.** Every streak, count and percentage is exact text on screen, matched
    verbatim by the tests.

14. **Navigation shape.** The app opens on the Habits tab. No login, onboarding or splash.
    Three bottom tabs: `Habits`, `Today`, `Settings`. Tapping a habit row pushes a detail
    screen with a back control at the top-left.

15. **Everything the user must reach stays on screen.** The 28-day grid on the detail
    screen is taller than one screen; it scrolls, and the tests scroll it. The habit's
    name and its `Current streak` line stay pinned at the top while the grid scrolls.

## Seed data (exact values — copy these verbatim)

Six habits, in this order. `start` is the first active day; the listed days are the
completed ones.

| habit | start | completed days |
|---|---|---|
| `Morning run` | 1 | 1,2,3,5,6,7,8,12,13,14,20,21,22,23,24,25,26,27,28 |
| `Read 20 pages` | 1 | 2,3,4,9,10,11,12,13,14,15,16,17,26,27,28 |
| `Meditate` | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,18,19,20,21,22,23,24,25,26 |
| `No sugar` | 5 | 5..27 (every day from 5 to 27 inclusive) |
| `Stretch` | 15 | 15,16,17,18,22,23,24,25,26,27,28 |
| `Journal` | 8 | 8,9,10,17,18,19,20,21,28 |

### Frozen days (exact)

| habit | frozen days |
|---|---|
| `Morning run` | 4, 11 |
| `Read 20 pages` | 5, 18 |
| `Meditate` | 27 |
| `No sugar` | 28 |
| `Stretch` | 19, 20, 21 |
| `Journal` | 22, 23 |

A day is either completed, frozen, or missed — never two of those.

## Derived values (the tests assert these exact strings)

**Habits tab**, one row per habit in seed order, each showing the habit name and
`Current streak: <n>`:

| habit | `Current streak:` | longest | active days | completed | `Completion:` |
|---|---|---|---|---|---|
| `Morning run` | `9` | `9` | 26 | 19 | `73%` |
| `Read 20 pages` | `3` | `9` | 26 | 15 | `58%` |
| `Meditate` | `0` | `12` | 27 | 21 | `78%` |
| `No sugar` | `23` | `23` | 23 | 23 | `100%` |
| `Stretch` | `11` | `11` | 11 | 11 | `100%` |
| `Journal` | `1` | `5` | 19 | 9 | `47%` |

`Meditate` is the row that separates ground rule 3 from the naive reading: its most recent
run is 9 days and its current streak is `0`, because day 28 is missed (not frozen).
`No sugar` separates ground rules 4 and 5: `23`, not `24` (frozen day 28 does not count)
and not `0` (it does not break the run either), at `100%` because its 5 frozen-free active
days are all completed.

Rounding cases: `Morning run` is `19/26 = 73.07…` → `73%`; `Read 20 pages` `15/26 = 57.69…`
→ `58%`; `Journal` `9/19 = 47.36…` → `47%`; `Meditate` `21/27 = 77.77…` → `78%`. Dividing by
the un-frozen span instead — `19/28`, `15/28`, `9/21`, `21/28` — gives `68%`, `54%`, `43%`,
`75%`, all wrong.

**Rendered detail lines** (each habit's three summary lines, verbatim):

- `Morning run` — `Current streak: 9`, `Longest streak: 9`, `Completion: 73%`
- `Read 20 pages` — `Current streak: 3`, `Longest streak: 9`, `Completion: 58%`
- `Meditate` — `Current streak: 0`, `Longest streak: 12`, `Completion: 78%`
- `No sugar` — `Current streak: 23`, `Longest streak: 23`, `Completion: 100%`
- `Stretch` — `Current streak: 11`, `Longest streak: 11`, `Completion: 100%`
- `Journal` — `Current streak: 1`, `Longest streak: 5`, `Completion: 47%`

**Day log lines.** The log renders every day 1..28 in order. For `No sugar` (start day 5)
it opens `Day 1: not started` … `Day 4: not started`, then `Day 5: done` through
`Day 27: done`, and ends `Day 28: frozen`. For `Stretch` (start day 15) it opens
`Day 1: not started`, days 19-21 render as `Day 19: frozen` … `Day 21: frozen`, and the
habit reads `Longest streak: 11` and `Completion: 100%` — its three frozen days leave the
denominator, so all 11 active days are completed.

**Marking today for `No sugar`.** Day 28 is its only incomplete active day. Marking it
takes the habit to 24 completed days out of 24 active days, so:

- `Current streak: 0` becomes `Current streak: 24`
- longest streak `23` becomes `24`
- `Completion: 100%` is unchanged — day 28 was frozen, so it was never in the denominator;
  marking it makes it a completed active day and the ratio stays 1

The jump from `0` to `24` is the check that ground rule 3 is implemented. An
implementation using the most recent run would move from `23` to `24` instead.

## Pinned UI text (tests match these exactly — render them verbatim)

- Tab bar labels: `Habits`, `Today`, `Settings`. Each tab screen shows its heading text:
  `Habits`, `Today`, `Settings`.
- **Habits tab**: one row per habit in seed order showing the habit name and the line
  `Current streak: <n>`.
- **Habit detail** (pushed): header title is the habit name; the lines
  `Current streak: <n>`, `Longest streak: <n>` and `Completion: <n>%`; then a `Day log`
  section listing all 28 days as `Day <n>: done`, `Day <n>: missed` or `Day <n>: frozen`, days 1 to 28 in order. A day before the habit's start day renders as `Day <n>: not started`.
- **Today tab**: one row per habit showing the habit name and a control labelled
  `Mark done` when day 28 is not completed and `Done today` when it is. The control's
  accessibility label must carry the habit name — `Mark done, No sugar` — because six
  controls share the same visible text and nothing could otherwise say which is meant.
  The visible text stays exactly `Mark done` / `Done today`.
- **Settings tab**: a `Totals` block with `Habits tracked: 6`, `Done today: <n>` and
  `Longest streak overall: <n>`. `Done today` counts the habits whose day 28 is completed;
  `Longest streak overall` is the largest longest-streak across all six habits. At the
  seed these read `Done today: 4` and `Longest streak overall: 23`.

## Final acceptance

Launch → Habits tab lists the six habits in seed order with `Current streak: 9` for
`Morning run`, `Current streak: 0` for `Meditate` and `Current streak: 0` for `No sugar` →
tap `No sugar` → detail shows `Current streak: 23`, `Longest streak: 23`, `Completion: 100%`;
the `Day log` scrolls and the name and `Current streak` line stay pinned → back → Today tab
→ tap `Mark done` on the `No sugar` row → Habits tab → `No sugar` now shows
`Current streak: 24` → tap `No sugar` → detail shows `Longest streak: 24` and
`Completion: 100%` → back → Settings tab → `Habits tracked: 6`, `Done today: 5` and
`Longest streak overall: 24` (both moved: `No sugar` became the fifth habit done today,
and its new 24-day streak became the longest overall, displacing its own 23). It must complete without manual intervention.
