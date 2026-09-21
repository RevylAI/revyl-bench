# FitTrack — build a mobile health & fitness tracker

You are a coding agent building a fresh iOS mobile app from the provided Expo scaffold
(Expo SDK 57, Expo Router, TypeScript). The product is a personal health & fitness
tracker: log workouts, browse a date-grouped history, see weekly progress, and keep a
persistent daily activity goal.

The work is split into three steps (see `steps/01-tabs`, `steps/02-log-history`,
`steps/03-progress-goal`, each with its own `instruction.md`), followed by a final
end-to-end acceptance run. Complete the steps in order.

## How your work is verified

After each submission, **hidden device tests** run your app on a real cloud iOS
simulator (iPhone 17 Pro Max, iOS 26.5) and grade journeys with screenshot validations.
You never see the test definitions. Every submission is graded against the **full suite**
— all step tests plus the final e2e — so a change that breaks an earlier step's behavior
is caught immediately. If a run fails, you receive the run report (failed-criteria text,
per-step verdicts, screenshots); fix your code and resubmit. Every requirement the
tests check is stated in this contract and the step contracts; nothing hidden is
required beyond what is written here.

The tests run a **baked-JS Release build** of your app, built by the benchmark from the
source you submit (`./submit.sh`) — you never build or upload a binary yourself. Code
changes are only visible to the verifier after a new submission. Iterate cheaply in the
dev-client session first; submit when you believe the JS is finished.

## Ground rules (binding — the tests depend on these)

1. **Integer internal values; formatted strings only at render.** Durations are integer
   minutes, calories integer kcal. Render with exactly one formatting convention:
   a duration renders as `<n> min` (e.g. `30 min`), calories render as `<n> cal`
   (e.g. `320 cal`).
2. **Deterministic data — no clocks.** No `Date.now()` and no `new Date()` anywhere in
   app code. Workout dates are the fixed string labels given below plus an integer
   `tsOrder` sort key. Every value on screen must be computable from this contract alone.
3. **Debounced one-shot mutation controls.** Exercise-type selection, the Save-workout
   button, and the daily-goal selector are one-shot: a rapid double-tap must have the
   same effect as a single tap (no duplicate workout, no goal bounce-back). Disabling
   the control for ~250ms after press is one acceptable implementation.
4. **Textual state summaries.** Progress and goal state are exact text strings (pinned
   below), not charts, bars, or pixel-encoded values.
5. **State survives tab navigation.** Logged workouts and the daily-goal setting must
   persist when the user navigates between tabs (module-level/store state is sufficient;
   no backend).

## Seed data (exact values — copy these verbatim)

Exercise types (`id`, `name`, `defaultDurationMinutes`, `defaultCalories`):

| name     | defaultDurationMinutes | defaultCalories |
|----------|------------------------|-----------------|
| Running  | 30                     | 320             |
| Cycling  | 45                     | 400             |
| Swimming | 30                     | 280             |
| Yoga     | 60                     | 180             |
| Strength | 40                     | 220             |

Seeded workout history (`exercise`, `dateLabel`, `tsOrder`, `durationMinutes`,
`calories`), in `tsOrder` order:

| exercise | dateLabel | tsOrder | durationMinutes | calories |
|----------|-----------|---------|-----------------|----------|
| Running  | Jul 14    | 0       | 30              | 320      |
| Cycling  | Jul 15    | 1       | 45              | 400      |
| Swimming | Jul 16    | 2       | 30              | 280      |
| Yoga     | Jul 17    | 3       | 60              | 180      |
| Running  | Jul 18    | 4       | 25              | 260      |

Derived values (the tests assert these exact numbers):
- Weekly active-minutes total from seed history: 30 + 45 + 30 + 60 + 25 = **190** minutes.
- Top exercise — the **most-logged exercise of the week** (ties broken by total
  minutes): **Running**, with 2 sessions (30 + 25 = 55 minutes); every other exercise
  has exactly 1 session.

Daily-goal options (`valueMinutes`, `label`): `30` → `30 min`, `60` → `60 min`.
Default daily goal: **30**.

Newly logged workouts get dateLabel `Jul 18` (the same day as the last seeded row) and
the next `tsOrder`.

## Pinned UI text (tests substring-match these exactly)

- Tab bar labels: `Log`, `History`, `Progress`.
- Each tab screen shows its title text `Log` / `History` / `Progress` on screen — from
  step 1 onward and permanently (every submission is graded against the full suite,
  so these titles must survive the real content arriving in steps 2 and 3). Step-1
  placeholder body content is your choice and is not asserted.
- Log tab: the five exercise-type names above; a duration input labeled
  `Duration minutes`; a calorie input labeled `Calories burned`; a save button labeled
  `Save workout`. **Selecting an exercise type pre-fills the duration and calorie inputs
  with that exercise's seeded default values** (e.g. selecting Cycling shows `45` and
  `400`); the user can then edit them.
- History tab: workouts grouped under their `dateLabel` as a group header (e.g.
  `Jul 18`), each entry rendered as `<Exercise> — <duration> min, <calories> cal` with
  an em dash — e.g. `Cycling — 45 min, 400 cal`. Ordering of groups and of entries
  within a group is your choice, as long as it is deterministic.
- Progress tab: `Weekly total: 190 min` and `Top exercise: Running`; a `Daily goal`
  section offering the `30 min` and `60 min` options with a summary line reading
  `Daily goal: 30 min` or `Daily goal: 60 min` matching the selected option.

## Out of scope

No real GPS/HealthKit/sensors, no charts, no live timers, no accounts or cloud sync, no
workout editing/deletion (append-only log), iOS only.
