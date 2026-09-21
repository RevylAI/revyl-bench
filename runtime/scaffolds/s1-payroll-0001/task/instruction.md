# ShiftPay — build a mobile timesheet & payroll app

You are a coding agent building a fresh iOS mobile app from the provided Expo scaffold
(Expo SDK 57, Expo Router, TypeScript). The product is a small-team payroll tool: a roster
of employees, each with a fixed week of shifts; a pushed timesheet screen that breaks every
shift into regular, overtime and evening hours and prices the week to the cent; an edit
flow that changes one shift's end time and immediately reprices everything downstream; and
a company payroll view that is **entirely derived** — total payroll, the top earner, and
the overtime share of cost all recompute from the shifts alone.

The work is split into three steps (see `steps/01-tabs`, `steps/02-timesheets-edit`,
`steps/03-payroll-settings`, each with its own `instruction.md`), followed by a final
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

1. **Time is strings and integer minutes.** A shift is a weekday index (`1`–`7`, see the
   table below) plus two plain time-of-day strings, start and end, in 24-hour `HH:MM`
   form. Shifts never cross midnight (end is after start, same day) and an employee has
   **at most one shift per day**. All derivation is done in **integer minutes**; hours
   appear only at display time, via the rounding rule (ground rule 3). There are no real
   dates anywhere — the weekday index is data, never the device calendar.

2. **The pay pipeline, in this exact order (binding).** Four rules, applied per employee
   in this sequence — a different order gives different numbers and is wrong:

   - **R1 — the unpaid break.** A shift whose start-to-end span is **strictly more than
     6 hours (360 minutes)** has a 30-minute unpaid break deducted: paid minutes =
     span − 30. A span of exactly 6 hours keeps all of it. Worked example:
     `08:30-17:15` spans 525 minutes, so 495 minutes (8.25h) are paid; `12:00-18:00`
     spans exactly 360 and all 360 are paid.
   - **R2 — the daily split.** Per day, paid minutes **strictly beyond 8 hours
     (480 minutes)** are daily overtime; the rest are regular. A day of exactly 480 paid
     minutes has zero overtime. Worked example: `07:00-16:30` pays 540 minutes → 480
     regular + 60 daily overtime.
   - **R3 — the weekly conversion.** Sum the week's **regular** minutes from R2 (daily
     overtime does not count towards this sum). Regular minutes **strictly beyond
     40 hours (2400 minutes)** convert to overtime; regular is capped at 2400. Overtime
     for the week is therefore *daily overtime + converted regular* — it is **not**
     `total paid − 40h`. Worked examples, both from the seed:
     - Ava's days give 45h regular + 4h daily overtime. R3 converts 5h: her week is
       **Regular 40.00h, Overtime 9.00h**.
     - Ben's days give 39.25h regular + 2.50h daily overtime — 41.75h paid in total.
       His regular is under 40h, so **nothing converts**: his week is **Regular 39.25h,
       Overtime 2.50h**. Reading "weekly overtime" as `41.75 − 40 = 1.75h`, or adding
       that on top of the daily overtime for `4.25h`, are both wrong.
   - **R4 — the evening window.** Evening minutes are the part of the shift's
     **clock interval** after `18:00`. A shift ending at exactly `18:00` has zero. The
     unpaid break is treated as taken **before** `18:00` (every seeded or editable shift
     that carries a break starts at least 30 minutes before `18:00`), so the break never
     reduces evening minutes. Evening minutes are a **premium overlay**, not a third
     bucket: an evening minute is still regular or overtime under R2/R3 and *also* earns
     the evening premium.

3. **Rounding (exact, binding).** Minutes convert to hours by dividing by 60 and rounding
   **half-up to 2 decimals**: 205 minutes → `3.42h` (3.4166…), 335 minutes → `5.58h`
   (5.5833…). Money rounds **half-up to whole cents**, so a half-cent goes up:
   `39.25h × $18.50 = $726.125` renders as `$726.13`, never `$726.12`.

4. **Weekly figures come from minutes, never from rounded dailies.** Each Week figure
   (regular, overtime, evening, paid) is the **sum in minutes**, converted to hours once.
   Worked example: Chloe's five daily regular displays read `7.42 + 7.50 + 3.42 + 6.00 +
   3.42 = 27.76`, but her week is 1665 minutes = **`27.75h`**. Adding the rounded daily
   displays is wrong.

5. **Pay is priced from the weekly rounded hours, component by component.** Per employee:
   regular pay = weekly regular hours (2-decimal) × base rate; overtime pay = weekly
   overtime hours × **1.5 × base rate**; evening premium = weekly evening hours ×
   **$3.00** (a flat add-on per evening hour, on top of whatever those hours earn under
   regular/overtime). Each component is rounded to cents separately (ground rule 3), and
   **gross pay is the sum of the three rounded components**. All seed rates make
   1.5 × rate exact cents.

6. **Company figures are sums of the per-employee figures.** Total payroll is the sum of
   the four gross pays (already cents — no further rounding). Overtime cost is the sum of
   the four overtime pay components. The **overtime share** is
   `overtime cost ÷ total payroll × 100`, rounded half-up to **1 decimal**, rendered like
   `11.6%`. The **top earner** is the employee with the highest gross pay; if two grosses
   are equal to the cent, the one **earlier in the roster order** wins. Company hour
   totals in Settings are the sums of the per-employee weekly hour figures.

7. **Deterministic data — no clocks, no randomness.** No `Date.now()`, `new Date()`,
   `Math.random()`, or uuid libraries anywhere in app code. No dates or time-of-day text
   is rendered beyond the shift strings themselves. Every value on screen must be
   computable from this contract alone.

8. **Everything downstream is derived.** Timesheet lines, Week blocks, gross pays, the
   Payroll tab and the Settings totals have no independent state: they are always exactly
   the pipeline applied to the current shifts. Editing a shift's end time rewrites all of
   them immediately.

9. **Debounced one-shot controls.** The end-time buttons on the Edit shift screen are
   one-shot: a rapid double-tap applies the change **exactly once**. Disabling the control
   briefly after press (≈250–300 ms) is one acceptable implementation. They take effect on
   the single tap that triggers them — there is no confirmation dialog, alert, or
   intermediate screen, and the app never opens a native alert dialog at any point.

10. **Textual state.** Hours, money and the percentage are exact text strings (pinned
    below) — never encoded only in colours, icons or bar widths. Money renders as
    `$<dollars>.<cents>` with two decimals and **no thousands separator**: `$3203.43`,
    not `$3,203.43`.

11. **State survives navigation.** An applied shift edit persists when the user navigates
    between tabs and pushes/pops screens (module-level/store state is sufficient; no
    backend, no disk persistence — a fresh install starts from the seed below).

12. **Navigation shape.** The app opens directly on the Team tab — no login, onboarding,
    or splash gate — and the roster is interactive within two seconds of launch. The three
    tabs are a bottom tab bar. Tapping a roster row **pushes** the employee's timesheet
    screen (native stack header titled with the employee name and a back button); tapping
    a shift row there **pushes** the Edit shift screen. Back pops each in turn. Every
    roster row and every shift row is tappable.

13. **Rows are individually addressable.** A roster row's accessibility label carries the
    employee name; a shift row's accessibility label starts with its day and times
    (`Thu 09:00-16:30`) — within one timesheet that is unique, and it is how both users of
    assistive tech and the tests say *which* row they mean. The Week block sits **above**
    the shift rows and is visible without scrolling; the shift list scrolls beneath it.

## Seed data (exact values — copy these verbatim)

Weekday indices (data, not the calendar): `1` Mon, `2` Tue, `3` Wed, `4` Thu, `5` Fri,
`6` Sat, `7` Sun. Display uses the three-letter names.

Roster, in this order (the roster order is also the tie rule of ground rule 6):

| employee | hourly rate |
|---|---|
| Ava Torres | $22.50 |
| Ben Okafor | $18.50 |
| Chloe Nguyen | $27.50 |
| Dev Patel | $16.00 |

Shifts — one fixed week, start/end as plain `HH:MM` strings:

| employee | day | shift |
|---|---|---|
| Ava Torres | 1 | `07:00-16:30` |
| Ava Torres | 2 | `07:00-16:00` |
| Ava Torres | 3 | `07:00-15:30` |
| Ava Torres | 4 | `07:00-16:30` |
| Ava Torres | 5 | `07:00-17:00` |
| Ava Torres | 6 | `08:00-13:00` |
| Ben Okafor | 1 | `08:30-17:15` |
| Ben Okafor | 2 | `08:30-19:00` |
| Ben Okafor | 3 | `08:30-16:15` |
| Ben Okafor | 4 | `08:30-17:15` |
| Ben Okafor | 5 | `08:30-17:00` |
| Chloe Nguyen | 2 | `14:00-21:55` |
| Chloe Nguyen | 3 | `15:00-23:00` |
| Chloe Nguyen | 4 | `17:35-21:00` |
| Chloe Nguyen | 5 | `12:00-18:00` |
| Chloe Nguyen | 6 | `17:35-21:00` |
| Dev Patel | 1 | `10:00-16:00` |
| Dev Patel | 3 | `09:00-15:30` |
| Dev Patel | 4 | `09:00-16:30` |
| Dev Patel | 7 | `11:00-16:35` |

That is 20 shifts: Ava 6, Ben 5, Chloe 5, Dev 4.

## Derived values (the tests assert these exact strings)

**Daily lines** (`Reg <r>h, OT <o>h, Eve <e>h`, all 2-decimal). These show the **daily
rule only** — R3's weekly conversion appears only in the Week block, never in a daily
line. Ava's daily lines sum to 45h regular and 4h overtime even though her Week block
says 40 and 9. The boundary rows to check:

- `Ava Mon 07:00-16:30` → `Reg 8.00h, OT 1.00h, Eve 0.00h` (break, then daily OT)
- `Ava Wed 07:00-15:30` → `Reg 8.00h, OT 0.00h, Eve 0.00h` (paid exactly 8h — no OT)
- `Ben Mon 08:30-17:15` → `Reg 8.00h, OT 0.25h, Eve 0.00h`
- `Ben Tue 08:30-19:00` → `Reg 8.00h, OT 2.00h, Eve 1.00h` (one evening hour)
- `Chloe Tue 14:00-21:55` → `Reg 7.42h, OT 0.00h, Eve 3.92h` (445 and 235 minutes)
- `Chloe Fri 12:00-18:00` → `Reg 6.00h, OT 0.00h, Eve 0.00h` (exactly 6h — no break;
  ends at exactly 18:00 — no evening)
- `Chloe Thu 17:35-21:00` and `Chloe Sat 17:35-21:00` → `Reg 3.42h, OT 0.00h, Eve 3.00h`
- `Dev Mon 10:00-16:00` → `Reg 6.00h, OT 0.00h, Eve 0.00h` (exactly 6h — no break)
- `Dev Wed 09:00-15:30` → `Reg 6.00h, OT 0.00h, Eve 0.00h` (6.5h span, break — the same
  6.00 as Mon by a different route)
- `Dev Thu 09:00-16:30` → `Reg 7.00h, OT 0.00h, Eve 0.00h`
- `Dev Sun 11:00-16:35` → `Reg 5.58h, OT 0.00h, Eve 0.00h` (335 minutes rounds down)

**Week blocks and gross pay** (per employee — `Regular`, `Overtime`, `Evening`, `Paid`
hours and `Gross`):

| employee | Regular | Overtime | Evening | Paid | pay arithmetic | Gross |
|---|---|---|---|---|---|---|
| Ava Torres | `40.00h` | `9.00h` | `0.00h` | `49.00h` | 40.00×22.50 = 900.00; 9.00×33.75 = 303.75; 0 | `$1203.75` |
| Ben Okafor | `39.25h` | `2.50h` | `1.00h` | `41.75h` | 39.25×18.50 = 726.125 → 726.13; 2.50×27.75 = 69.375 → 69.38; 1.00×3.00 = 3.00 | `$798.51` |
| Chloe Nguyen | `27.75h` | `0.00h` | `14.92h` | `27.75h` | 27.75×27.50 = 763.125 → 763.13; 0; 14.92×3.00 = 44.76 | `$807.89` |
| Dev Patel | `24.58h` | `0.00h` | `0.00h` | `24.58h` | 24.58×16.00 = 393.28; 0; 0 | `$393.28` |

Rendered per the pinned UI text, Ben's Week block is therefore the five lines
`Regular 39.25h`, `Overtime 2.50h`, `Evening 1.00h`, `Paid 41.75h`, `Gross $798.51`.
Chloe's evening week is 895 minutes → `14.92h` (14.9166…). Her regular week is 1665
minutes → `27.75h`, not the `27.76` her rounded daily lines add up to (ground rule 4).

**Company view (seed state)**: total payroll `$3203.43` (900.00+303.75 + 726.13+69.38+3.00
+ 763.13+44.76 + 393.28); top earner `Ava Torres` at `$1203.75`; overtime cost
303.75 + 69.38 = `$373.13`, so the overtime share is 373.13 ÷ 3203.43 × 100 = 11.6478… →
`11.6%`. The Payroll tab lists employees by **gross descending** (roster order breaks a
tie): `Ava Torres $1203.75`, `Chloe Nguyen $807.89`, `Ben Okafor $798.51`,
`Dev Patel $393.28`. Settings totals: `Employees: 4`, `Shifts: 20`,
`Paid hours: 143.08`, `Overtime hours: 11.50`, `Evening hours: 15.92`.

**Editing Dev's Thursday shift.** The Edit shift screen always offers exactly three
end-time buttons — `18:00`, `19:30`, `22:00` (every seeded shift starts before 18:00, so
all three are valid ends for any shift). Two asserted edits, applied in sequence to
`Dev Thu 09:00-16:30`:

- **End `18:00`** — the shift now reads `Thu 09:00-18:00`: span 540, paid 510, and the
  day becomes `Reg 8.00h, OT 0.50h, Eve 0.00h`;
  Dev's week becomes `Regular 25.58h`, `Overtime 0.50h`, `Evening 0.00h`, and gross
  25.58×16.00 + 0.50×24.00 = 409.28 + 12.00 = `$421.28`.
- **End `19:30`** — span 630, paid 600: the day **crosses the daily-OT boundary** and
  gains an evening tail: `Reg 8.00h, OT 2.00h, Eve 1.50h`; Dev's week becomes
  `Regular 25.58h`, `Overtime 2.00h`, `Evening 1.50h`, `Paid 27.58h`, and gross
  409.28 + 2.00×24.00 + 1.50×3.00 = 409.28 + 48.00 + 4.50 = `$461.78`.

**Company view after the `19:30` edit**: total payroll `$3271.93`; overtime cost
373.13 + 48.00 = `$421.13`; overtime share 421.13 ÷ 3271.93 × 100 = 12.8710… → `12.9%`;
top earner still `Ava Torres $1203.75`; Settings `Paid hours: 146.08`,
`Overtime hours: 13.50`, `Evening hours: 17.42`, `Shifts: 20` (an edit changes no counts).

## Pinned UI text (tests match these exactly — render them verbatim)

- Tab bar labels: `Team`, `Payroll`, `Settings`. Each tab screen shows its heading text:
  `Team`, `Payroll`, `Settings`.
- **Team tab**: one row per employee in roster order showing the name, the rate as
  `$<rate>/h` (`$22.50/h`, `$18.50/h`, `$27.50/h`, `$16.00/h`) and the text `<n> shifts`
  (`6 shifts`, `5 shifts`, `5 shifts`, `4 shifts`).
- **Timesheet screen** (pushed): header title is the employee name; the line
  `Rate $<rate>/h`; a `Week` block with the five lines `Regular <r>h`, `Overtime <o>h`,
  `Evening <e>h`, `Paid <p>h`, `Gross $<g>`; then a `Shifts` section listing the shifts
  in weekday order, each row showing `<Day> <start>-<end>` and its daily line
  `Reg <r>h, OT <o>h, Eve <e>h`.
- **Edit shift screen** (pushed from a shift row): header title `Edit shift`; the employee
  name; the shift's current `<Day> <start>-<end>` and current daily line; a `New end time`
  row with the three buttons `18:00`, `19:30`, `22:00`. Tapping a button applies the edit
  immediately (one-shot, no confirmation) and the screen now shows the updated times and
  updated daily line; the back button returns to the timesheet.
- **Payroll tab**: a `Company` block with the three lines `Total payroll $<t>`,
  `Top earner <name> $<g>`, `Overtime share <s>%`; then an `Employees` section listing
  `<name> $<gross>` by gross descending.
- **Settings tab**: a `Pay rules` block with the three lines `Overtime x1.5`,
  `Evening +$3.00/h after 18:00`, `Unpaid break 30 min over 6h`; then a `Week` block with
  the five lines `Employees: 4`, `Shifts: 20`, `Paid hours: <p>`, `Overtime hours: <o>`,
  `Evening hours: <e>`.

## Final acceptance

The final e2e journey: launch → Team tab lists the four employees with their rates and
shift counts → tap `Ava Torres` → her Week block reads `Regular 40.00h`, `Overtime 9.00h`,
`Gross $1203.75` while her Mon daily line reads `Reg 8.00h, OT 1.00h, Eve 0.00h` → back →
Payroll tab shows `Total payroll $3203.43`, `Top earner Ava Torres $1203.75`,
`Overtime share 11.6%` → Settings tab shows `Paid hours: 143.08` and
`Overtime hours: 11.50` → Team tab → tap `Dev Patel` → `Gross $393.28`, Thu row
`Reg 7.00h, OT 0.00h, Eve 0.00h` → tap the `Thu 09:00-16:30` shift row → tap `19:30` →
the shift reads `Thu 09:00-19:30` with `Reg 8.00h, OT 2.00h, Eve 1.50h` → back → Dev's
Week block reads `Overtime 2.00h`, `Evening 1.50h`, `Gross $461.78` → Payroll tab →
`Total payroll $3271.93`, `Overtime share 12.9%`, `Dev Patel $461.78` → Settings tab →
`Paid hours: 146.08`, `Overtime hours: 13.50`, `Evening hours: 17.42`. It must complete
without manual intervention.
