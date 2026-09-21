# RoomBoard — build a mobile meeting-room booking app

You are a coding agent building a fresh iOS mobile app from the provided Expo scaffold
(Expo SDK 57, Expo Router, TypeScript). The product is a meeting-room board for one office
on one working day: a list of rooms with capacities and equipment, each room's day
schedule of seeded bookings, a booking form with **conflict detection** (a request is
rejected with a specific visible reason when it overlaps an existing booking or exceeds
the room's capacity), an **availability** view that is entirely derived — the free gaps
between a room's bookings, each with its exact duration in minutes — and a utilization
summary of booked minutes and percentages, per room and for the whole office.

The work is split into three steps (see `steps/01-tabs-rooms`, `steps/02-booking`,
`steps/03-availability-utilization`, each with its own `instruction.md`), followed by a
final end-to-end acceptance run. Complete the steps in order.

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

1. **One fixed day, no real dates.** Every time in the app is a plain `HH:MM` string on
   a single unnamed working day. Office hours are `08:00` to `18:00` — **600 minutes per
   room**. Represent times internally as integer minutes from 08:00 (so `09:45` is 105).
   No `Date` objects, no time zones, no day names, no date or time-of-day text anywhere
   beyond the `HH:MM` strings pinned here. Times render with a plain hyphen and no
   spaces: `09:45-11:00`.

2. **Integer arithmetic only.** Durations and booked totals are integer minutes;
   utilization percentages are computed as integer tenths of a percent (rule 8). No
   floating-point arithmetic anywhere.

3. **The overlap rule (exact).** A booking occupies the half-open interval
   `[start, end)`. A requested slot conflicts with an existing booking **in the same
   room** if and only if `start < existing.end` AND `end > existing.start`. **Touching
   endpoints do not conflict**: a booking may start at the exact minute another ends, or
   end at the exact minute another starts. Bookings in different rooms never conflict.

4. **Validation order (binding).** A request is checked **capacity first, then overlap**:
   if the attendee count exceeds the room's capacity, the capacity rejection is shown
   even when the requested slot also overlaps an existing booking. An attendee count
   **equal** to the capacity is allowed. If the slot overlaps several existing bookings,
   the rejection names the **earliest-starting** one.

5. **Rejection is a rendered line, never a dialog.** The outcome of a request is a text
   result line on the Book screen (pinned strings below). The app never opens a native
   alert or confirmation dialog at any point. A rejected request changes nothing: no
   booking is created and every derived view is unchanged.

6. **Every derived view has no independent state.** A room's schedule, its availability
   gaps, its `Booked` line, the `<n> bookings` count on its Rooms-tab row, and the whole
   Settings tab are all recomputed from the single list of bookings. A successful booking
   rewrites all of them immediately.

7. **The availability rule (exact).** For each room, sort its bookings by start time. The
   availability gaps are: from `08:00` to the first booking's start, between each
   consecutive pair of bookings (previous end to next start), and from the last booking's
   end to `18:00`. A gap is rendered **only if its duration is greater than 0 minutes** —
   zero-length gaps (two touching bookings, a booking starting at `08:00`, a booking
   ending at `18:00`) are never shown, not even as a `0 min` row.

8. **The utilization rule (exact).** A room's utilization is its booked minutes over the
   600-minute day, as a percentage **rounded half-up to one decimal** and always rendered
   with exactly one decimal (`25.0%`, never `25%`). In integer arithmetic the tenths of a
   percent are `(10 * minutes + 3) div 6`. The office figure is total booked minutes over
   all five rooms' 3000 room-minutes; its tenths are `(2 * minutes + 3) div 6`. Truncating
   instead of rounding gives visibly different numbers on this seed (`26.7%` would become
   `26.6%`) and is wrong.

9. **Deterministic data — no clocks, no randomness.** No `Date.now()`, `new Date()`,
   `Math.random()`, or uuid libraries anywhere in app code. Every value on screen must be
   computable from this contract alone.

10. **Debounced one-shot controls.** `Request booking` is one-shot: a rapid double-tap
    performs the request **exactly once**. Disabling the control briefly after press
    (≈250–300 ms) is one acceptable implementation. It takes effect on the single tap
    that triggers it — there is no confirmation step. Tapping a room chip that is already
    selected is harmless.

11. **Verbatim text input, clear-on-focus.** The four form inputs accept typed text
    verbatim. Every input **clears its content when it receives focus** (TextInput
    `clearTextOnFocus`), so tapping an input always starts from empty. After a
    **rejection** the inputs keep their values; after a **successful booking** the four
    inputs reset to empty. Changing the selected room never changes the inputs. A request
    with an empty title books under the title `Booking`. The tests only ever submit
    well-formed `HH:MM` times inside office hours with the end after the start and an
    attendee count of at least 1; behavior for malformed, out-of-hours or incomplete
    input is your choice (still: no crash, no dialog).

12. **Textual state.** Counts, times, durations, percentages and the selected room are
    exact text strings (pinned below) — never encoded only in colours, icons or bar
    widths. The Book screen echoes the selected room as the line `Room: <name>`.

13. **State survives navigation.** Bookings made in the session persist when the user
    navigates between tabs and pushes/pops screens (module-level/store state is
    sufficient; no backend, no disk persistence — a fresh install starts from the seed
    below).

14. **Navigation shape.** The app opens directly on the Rooms tab — no login, onboarding,
    or splash gate — and the room list is interactive within two seconds of launch. The
    three tabs are a bottom tab bar. Tapping a room row **pushes** its detail screen
    (native stack header titled with the room name and a back button). Back returns to
    the tab bar. Every room row is tappable to open its detail.

15. **Everything the user must reach stays on screen.** The `Request booking` button and
    the result line stay visible and reachable while the on-screen keyboard is open;
    tapping `Request booking` dismisses the keyboard so the result line is readable. A
    newly booked row is visible on its room's schedule without manual scrolling.

## Seed data (exact values — copy these verbatim)

Five rooms, in this order:

| room | seats | equipment |
|---|---|---|
| Aurora | 12 | Screen, VC |
| Boardroom | 20 | Screen, VC, Whiteboard |
| Fern | 6 | Whiteboard |
| Huddle | 4 | Screen |
| Lumen | 8 | VC, Whiteboard |

Seeded bookings, per room, sorted by start time. Every time is inside `08:00`–`18:00`.

| room | start-end | title | attendees |
|---|---|---|---|
| Aurora | 08:30-09:45 | Design Review | 8 |
| Aurora | 11:00-12:30 | Sprint Planning | 10 |
| Aurora | 14:15-15:05 | Client Call | 3 |
| Boardroom | 09:00-11:30 | All Hands | 18 |
| Boardroom | 13:00-13:45 | Budget Sync | 7 |
| Boardroom | 16:00-17:30 | Board Prep | 9 |
| Fern | 10:00-11:00 | UX Critique | 5 |
| Fern | 11:00-11:45 | Copy Review | 3 |
| Fern | 15:30-16:15 | Retro Prep | 6 |
| Huddle | 08:00-08:25 | Standup | 4 |
| Huddle | 12:15-13:05 | Coaching | 2 |
| Huddle | 17:10-18:00 | Wrap Up | 3 |
| Lumen | 09:15-10:45 | Data Deep Dive | 6 |
| Lumen | 13:30-14:40 | Vendor Demo | 8 |

Rendered per the pinned schedule-row format (`<start>-<end> <title> (<attendees>)`),
these fourteen rows are, per room in start order:

- `Aurora`: `08:30-09:45 Design Review (8)`, `11:00-12:30 Sprint Planning (10)`,
  `14:15-15:05 Client Call (3)`
- `Boardroom`: `09:00-11:30 All Hands (18)`, `13:00-13:45 Budget Sync (7)`,
  `16:00-17:30 Board Prep (9)`
- `Fern`: `10:00-11:00 UX Critique (5)`, `11:00-11:45 Copy Review (3)`,
  `15:30-16:15 Retro Prep (6)`
- `Huddle`: `08:00-08:25 Standup (4)`, `12:15-13:05 Coaching (2)`,
  `17:10-18:00 Wrap Up (3)`
- `Lumen`: `09:15-10:45 Data Deep Dive (6)`, `13:30-14:40 Vendor Demo (8)`

Note the seed itself exercises the edge rules: Fern's `UX Critique` ends at `11:00`, the
exact minute `Copy Review` starts (touching, legal, no gap between them); Huddle's
`Standup` starts at `08:00` and its `Wrap Up` ends at `18:00` (no gap at the open or the
close of the day).

## Derived values (the tests assert these exact strings and orders)

**Booked minutes per room** (sum of booking durations):

- `Aurora`: 75 + 90 + 50 = **215 min** → 215/600 = 35.833…% → detail line
  `Booked 215 min (35.8%)`
- `Boardroom`: 150 + 45 + 90 = **285 min** → 47.5% exactly → `Booked 285 min (47.5%)`
- `Fern`: 60 + 45 + 45 = **150 min** → 25% exactly → `Booked 150 min (25.0%)` (one
  decimal, always)
- `Huddle`: 25 + 50 + 50 = **125 min** → 20.833…% → `Booked 125 min (20.8%)`
- `Lumen`: 90 + 70 = **160 min** → 26.666…% → `Booked 160 min (26.7%)` (rounded up —
  truncation gives `26.6%` and is wrong)

**Office totals**: 5 rooms, 14 seeded bookings, 215 + 285 + 150 + 125 + 160 =
**935 min** booked of 3000 room-minutes → 31.166…% → `31.2%` (again: truncation gives
`31.1%` and is wrong).

**Availability gaps per room** (rule 7; every room's booked minutes plus its gap minutes
sum to 600):

- `Aurora`: `08:00-08:30 (30 min)`, `09:45-11:00 (75 min)`, `12:30-14:15 (105 min)`,
  `15:05-18:00 (175 min)`
- `Boardroom`: `08:00-09:00 (60 min)`, `11:30-13:00 (90 min)`, `13:45-16:00 (135 min)`,
  `17:30-18:00 (30 min)`
- `Fern`: `08:00-10:00 (120 min)`, `11:45-15:30 (225 min)`, `16:15-18:00 (105 min)` —
  exactly three gaps; **no** row between the touching `11:00` end and `11:00` start
- `Huddle`: `08:25-12:15 (230 min)`, `13:05-17:10 (245 min)` — exactly two gaps; **no**
  gap starting at `08:00` and **no** gap ending at `18:00`
- `Lumen`: `08:00-09:15 (75 min)`, `10:45-13:30 (165 min)`, `14:40-18:00 (200 min)`

**Worked booking example — Aurora `09:45-11:00`.** This slot touches `Design Review`'s
end (`09:45`) and `Sprint Planning`'s start (`11:00`) and by rule 3 conflicts with
neither: it books, and it fills the 75-minute gap exactly. Requesting it with 6 attendees
yields the result line `Booked Aurora 09:45-11:00 for 6`; with 12 attendees — exactly the
capacity, allowed by rule 4 — `Booked Aurora 09:45-11:00 for 12`. Either way Aurora's row
becomes `4 bookings`, its booked line becomes `Booked 290 min (48.3%)` (290/600 =
48.333…%), its availability drops to **three** gaps (`08:00-08:30 (30 min)`,
`12:30-14:15 (105 min)`, `15:05-18:00 (175 min)`), and Settings shows `Bookings: 15`,
`Booked: 1010 min`, `Utilization: 33.7%` (1010/3000 = 33.666…%, rounded up) and
`Aurora: 290 min, 48.3%`.

**Worked rejection examples.**

- Requesting `Huddle` `12:00-13:00` with 6 attendees: 6 exceeds Huddle's capacity of 4,
  so the result line is `Rejected: 6 attendees exceeds capacity 4` — capacity is checked
  first (rule 4), even though the slot also overlaps `Coaching` (`12:15-13:05`).
- Requesting `Aurora` `12:00-13:00` with 6 attendees: capacity passes, but the slot
  overlaps `Sprint Planning` (`11:00` < `13:00` and `12:30` > `12:00`), so the result
  line is `Rejected: overlaps Sprint Planning (11:00-12:30)`.

**Worked booking example — Lumen `10:45-11:00`, title `Team Sync`.**

- With 10 attendees: `Rejected: 10 attendees exceeds capacity 8` (capacity first; the
  slot `10:00-11:00` tried en route also overlaps).
- At `10:00-11:00` with 8 attendees: `Rejected: overlaps Data Deep Dive (09:15-10:45)`.
- At `10:45-11:00` with 8 attendees: the start touches `Data Deep Dive`'s end, so it
  books — `Booked Lumen 10:45-11:00 for 8`. Lumen's schedule gains
  `10:45-11:00 Team Sync (8)` between `Data Deep Dive` and `Vendor Demo`, its row becomes
  `3 bookings`, its booked line `Booked 175 min (29.2%)` (175/600 = 29.166…%), and its
  middle gap shrinks: availability becomes `08:00-09:15 (75 min)`,
  `11:00-13:30 (150 min)`, `14:40-18:00 (200 min)`. Settings shows `Bookings: 15`,
  `Booked: 950 min`, `Utilization: 31.7%` (950/3000 = 31.666…%, rounded up) and
  `Lumen: 175 min, 29.2%`.

## Pinned UI text (tests match these exactly — render them verbatim)

- Tab bar labels: `Rooms`, `Book`, `Settings`. Each tab screen shows its heading text:
  `Rooms`, `Book`, `Settings`.
- **Rooms tab**: one row per room in seed order showing the room name, the text
  `Seats <n>`, the equipment tags joined with a comma and a space (`Screen, VC`), and the
  text `<n> bookings` counting that room's current bookings (the tests never see a count
  of 1). The count updates when a booking is made.
- **Room detail screen** (pushed): header title is the room name; the text `Seats <n>`;
  the equipment line; the line `Booked <m> min (<p>%)`; a `Schedule` section listing the
  room's bookings sorted by start as `<start>-<end> <title> (<attendees>)`, e.g.
  `08:30-09:45 Design Review (8)`; then an `Availability` section listing the gaps of
  rule 7 as `<start>-<end> (<n> min)`, e.g. `09:45-11:00 (75 min)`.
- **Book tab**: five room chips labelled with the room names (`Aurora` is selected at
  launch); the line `Room: <name>` echoing the selection; text inputs showing the hint
  texts `Meeting title`, `Start (HH:MM)`, `End (HH:MM)` and `Attendees`; a button
  labelled `Request booking`; and after a request, the result line — one of
  `Booked <room> <start>-<end> for <attendees>`,
  `Rejected: <attendees> attendees exceeds capacity <capacity>`, or
  `Rejected: overlaps <title> (<start>-<end>)`.
- **Settings tab**: an `Office` block with the four lines `Rooms: 5`, `Bookings: <n>`,
  `Booked: <m> min` and `Utilization: <p>%`; then a `By room` block with one line per
  room in seed order as `<name>: <m> min, <p>%` — at the seed exactly
  `Aurora: 215 min, 35.8%`, `Boardroom: 285 min, 47.5%`, `Fern: 150 min, 25.0%`,
  `Huddle: 125 min, 20.8%`, `Lumen: 160 min, 26.7%`.

## Final acceptance

The final e2e journey: launch → Rooms tab lists the five rooms with their seat counts →
`Huddle` detail shows the three seeded bookings, `Booked 125 min (20.8%)`, and exactly two
availability gaps (`08:25-12:15 (230 min)`, `13:05-17:10 (245 min)`) with no gap at the
open or close of the day → Book tab → select `Lumen`, title `Team Sync`, `10:00` to
`11:00`, 10 attendees → `Rejected: 10 attendees exceeds capacity 8` → attendees `8` →
`Rejected: overlaps Data Deep Dive (09:15-10:45)` → start `10:45` →
`Booked Lumen 10:45-11:00 for 8` → Lumen detail shows `10:45-11:00 Team Sync (8)` in
start order, availability `11:00-13:30 (150 min)` where `10:45-13:30` used to be, and
`Booked 175 min (29.2%)` → Settings shows `Bookings: 15`, `Booked: 950 min`,
`Utilization: 31.7%` and `Lumen: 175 min, 29.2%`. It must complete without manual
intervention.
