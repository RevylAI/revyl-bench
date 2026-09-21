# StackLend — build a lending desk for a small library

You are a coding agent building a fresh iOS mobile app from the provided Expo scaffold
(Expo SDK 57, Expo Router, TypeScript). The product is the lending desk of a small
library: a catalog of titles with copy counts, a member roster with membership tiers, a
loans ledger, checkout and return flows, and a desk dashboard whose every number is
**derived** from the ledger — days overdue, fines with a per-loan cap, per-member
allowances, and a collection-rate percentage.

The work is split into three steps (see `steps/01-tabs`, `steps/02-checkout-return`,
`steps/03-desk-settings`, each with its own `instruction.md`), followed by a final
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

1. **A synthetic day index, and today is Day 40.** The app models time as integer days
   rendered `Day <n>`. **Today is Day 40.** It is a constant, not a clock reading. No
   real dates, no times of day, no calendars anywhere.

2. **No clocks, no randomness.** No `Date.now()`, `new Date()`, `Math.random()`, or uuid
   libraries anywhere in app code. Every value on screen must be computable from this
   contract alone.

3. **Integer cents everywhere.** Every monetary value is stored as an integer number of
   cents and rendered as `$<dollars>.<cents>` with exactly two decimal places
   (`$4.00`, `$13.80`). No floating-point money arithmetic.

4. **Due day derivation.** A loan's due day is `checkout day + the member's tier loan
   period`. The three tiers are fixed:

   | tier | loan limit | loan period |
   |---|---|---|
   | `Basic` | 2 books | 7 days |
   | `Standard` | 3 books | 14 days |
   | `Plus` | 5 books | 21 days |

   A `Standard` member checking out on Day 40 is due on Day 54; a `Plus` member on
   Day 61; a `Basic` member on Day 47.

5. **Days overdue are never negative.** For a loan still out, days overdue is
   `max(0, today − due day)`; for a returned loan, days late is
   `max(0, return day − due day)`. A loan due after today is simply `Not overdue` — it
   never contributes a negative day to any total. Summing raw `today − due day` over the
   ledger gives `$5.40` where the correct accruing total is `$13.80`; that is wrong.

6. **The fine rule (exact, with a cap).** A loan's fine is
   `days overdue × $0.35`, **capped at `$4.00` per loan**. Worked pair, one on each side
   of the cap: 11 days overdue is `$3.85`; 12 days overdue is `12 × $0.35 = $4.20`,
   which the cap reduces to `$4.00`. The cap applies per loan, never to a member's or
   the desk's total. A returned loan's fine is fixed at return time from its days late
   and never changes afterwards.

7. **On time means on or before the due day.** A loan returned **on** its due day is an
   on-time return, not a late one. The seed ledger contains two returns that land
   exactly on their due day; counting them as late moves the collection rate from
   `62.5%` to `37.5%`, which is wrong.

8. **The allowance counts books currently out — only.** A member's loans-out count is
   the number of their loans not yet returned; returned loans never count against the
   limit. `Priya Raman` has 1 book out and 2 past returns: she is at `1 of 2`, not
   `3 of 2`. A member whose loans-out count equals their tier limit is **at the loan
   limit** and cannot check out.

9. **At-limit members are visibly blocked.** On an at-limit member's detail screen the
   `Check out` section shows, in place of the title list, exactly the text
   `At loan limit: <k> of <k> books out. Return a book first.` (with `<k>` the tier
   limit) and no `Check out` controls. The message appears the moment the member
   reaches the limit and disappears the moment a return takes them under it.

10. **Every action happens today.** A checkout made in the app is made on Day 40 (due
    day = 40 + the tier period). A return made in the app is made on Day 40 (days late
    computed against Day 40). There is no date picker and no way to act on another day.

11. **Everything is derived — no independent state.** Availability counts, allowances,
    fines, the desk analytics and the settings totals are always recomputed from the
    catalog, the roster and the ledger. A checkout or return rewrites every affected
    number immediately. State survives navigation (module-level/store state is
    sufficient); there is no backend and no disk persistence — a fresh install starts
    from the seed below.

12. **The collection rate.** `Collection rate` is on-time returns over completed
    (returned) loans, as a percentage **rounded half-up to one decimal place** and always
    rendered with one decimal (`62.5%`, `60.0%`). Worked example: after one late return
    is added to the seed ledger it is `5 / 9 = 55.55…`, which renders `55.6%`. Do the
    rounding in integer arithmetic. Loans still out are not in the denominator.

13. **Debounced one-shot controls.** The `Return` and `Check out` controls are one-shot:
    a rapid double-tap performs the action **exactly once**. Disabling the control
    briefly after press (≈250–300 ms) is one acceptable implementation. They take effect
    on the single tap that triggers them — there is no confirmation dialog, alert, or
    intermediate screen, and the app never opens a native alert dialog at any point.

14. **Textual state.** Every count, day, fine and percentage is an exact text string
    (pinned below) — never encoded only in colours, icons or bar widths. There is no
    text input anywhere in the app; every flow is taps only.

15. **Ordering (fixed).** The catalog lists titles in seed order. The members list is in
    seed order. The ledger's `Out` section is sorted by due day ascending (most overdue
    first); the `Returned` section by return day ascending, ties broken by member name
    A–Z. A member detail's `Books out` section is sorted by due day ascending, and its
    `Check out` list is in catalog order. `Most overdue` ties would break by title A–Z
    (no reachable state has one).

16. **Navigation shape.** The app opens directly on the Catalog tab — no login,
    onboarding, or splash gate — and is interactive within two seconds of launch. Five
    bottom tabs: `Catalog`, `Members`, `Loans`, `Desk`, `Settings`. Tapping a member row
    **pushes** their detail screen (native stack header titled with the member's name
    and a back button); back returns to the tab bar. Nothing else pushes.

17. **Everything the user must reach stays on screen.** The loans ledger is longer than
    one screen and scrolls; the tests scroll it. On a member detail the `Books out`
    section sits above the `Check out` section, and a loan created by a checkout is
    visible on the detail without manual scrolling.

18. **Controls are individually addressable.** Many `Return` and `Check out` controls
    share the same visible word, so each control's accessibility label must carry its
    identity: a ledger return control is `Return, <title>, <member>` (e.g.
    `Return, The Glass Harbor, Marcus Webb`) and a checkout control is
    `Check out, <title>` (e.g. `Check out, Salt and Circuit`). The visible text stays
    exactly `Return` / `Check out`.

## Seed data (exact values — copy these verbatim)

Titles, in this order, with total copies owned:

| title | copies |
|---|---|
| `The Glass Harbor` | 3 |
| `Salt and Circuit` | 2 |
| `A Field Guide to Nowhere` | 2 |
| `Paper Mountains` | 3 |
| `Winter Arithmetic` | 2 |
| `The Lighthouse Codex` | 2 |

Members, in this order:

| member | tier |
|---|---|
| `Maya Chen` | `Plus` |
| `Marcus Webb` | `Standard` |
| `Priya Raman` | `Basic` |
| `Theo Alvarez` | `Standard` |
| `Elif Kaya` | `Plus` |

Loans still out (9). The due day is derived — `checkout day + tier period` — and is
listed here so you can check your derivation:

| member | title | out day | due day |
|---|---|---|---|
| `Marcus Webb` | `Winter Arithmetic` | 22 | 36 |
| `Marcus Webb` | `The Glass Harbor` | 30 | 44 |
| `Marcus Webb` | `Salt and Circuit` | 35 | 49 |
| `Priya Raman` | `A Field Guide to Nowhere` | 21 | 28 |
| `Maya Chen` | `Paper Mountains` | 13 | 34 |
| `Maya Chen` | `The Lighthouse Codex` | 24 | 45 |
| `Theo Alvarez` | `The Glass Harbor` | 19 | 33 |
| `Theo Alvarez` | `Paper Mountains` | 32 | 46 |
| `Elif Kaya` | `Winter Arithmetic` | 8 | 29 |

Completed loans (8, already returned):

| member | title | out day | due day | returned day |
|---|---|---|---|---|
| `Maya Chen` | `The Glass Harbor` | 2 | 23 | 20 |
| `Marcus Webb` | `Paper Mountains` | 3 | 17 | 21 |
| `Priya Raman` | `Winter Arithmetic` | 5 | 12 | 12 |
| `Theo Alvarez` | `The Lighthouse Codex` | 6 | 20 | 29 |
| `Elif Kaya` | `Salt and Circuit` | 4 | 25 | 24 |
| `Maya Chen` | `A Field Guide to Nowhere` | 9 | 30 | 27 |
| `Priya Raman` | `The Glass Harbor` | 15 | 22 | 38 |
| `Theo Alvarez` | `Salt and Circuit` | 10 | 24 | 24 |

## Derived values (the tests assert these exact strings)

**Per-loan, at the seed** (today is Day 40). Days overdue = `max(0, 40 − due day)`;
fine = `days × $0.35` capped at `$4.00`:

| loan | due | overdue | status line |
|---|---|---|---|
| `A Field Guide to Nowhere` / `Priya Raman` | 28 | 12 | `Overdue 12 days, fine $4.00` (12 × $0.35 = $4.20, capped) |
| `Winter Arithmetic` / `Elif Kaya` | 29 | 11 | `Overdue 11 days, fine $3.85` (under the cap) |
| `The Glass Harbor` / `Theo Alvarez` | 33 | 7 | `Overdue 7 days, fine $2.45` |
| `Paper Mountains` / `Maya Chen` | 34 | 6 | `Overdue 6 days, fine $2.10` |
| `Winter Arithmetic` / `Marcus Webb` | 36 | 4 | `Overdue 4 days, fine $1.40` |
| `The Glass Harbor` / `Marcus Webb` | 44 | 0 | `Not overdue` |
| `The Lighthouse Codex` / `Maya Chen` | 45 | 0 | `Not overdue` |
| `Paper Mountains` / `Theo Alvarez` | 46 | 0 | `Not overdue` |
| `Salt and Circuit` / `Marcus Webb` | 49 | 0 | `Not overdue` |

That table is already in the `Out` section's order (due day ascending). The `Returned`
section (return day ascending, the Day 24 tie broken `Elif Kaya` before `Theo Alvarez`):

| loan | status line |
|---|---|
| `Winter Arithmetic` / `Priya Raman` | `Returned Day 12, on time` (returned ON the due day) |
| `The Glass Harbor` / `Maya Chen` | `Returned Day 20, on time` |
| `Paper Mountains` / `Marcus Webb` | `Returned Day 21, 4 days late, fine $1.40` |
| `Salt and Circuit` / `Elif Kaya` | `Returned Day 24, on time` |
| `Salt and Circuit` / `Theo Alvarez` | `Returned Day 24, on time` (returned ON the due day) |
| `A Field Guide to Nowhere` / `Maya Chen` | `Returned Day 27, on time` |
| `The Lighthouse Codex` / `Theo Alvarez` | `Returned Day 29, 9 days late, fine $3.15` |
| `The Glass Harbor` / `Priya Raman` | `Returned Day 38, 16 days late, fine $4.00` (16 × $0.35 = $5.60, capped) |

**Availability** = copies − loans out, per title: `The Glass Harbor` `1 of 3`,
`Salt and Circuit` `1 of 2`, `A Field Guide to Nowhere` `1 of 2`, `Paper Mountains`
`1 of 3`, `Winter Arithmetic` `0 of 2`, `The Lighthouse Codex` `1 of 2`.

**Per-member.** `Fines owed` is the sum of that member's fines — accruing on their
loans still out plus charged on their returns. Both of Marcus Webb's `$1.40` fines are
real: one accruing, one charged.

| member | tier | loans out | `Fines owed:` |
|---|---|---|---|
| `Maya Chen` | `Plus` | `2 of 5` | `$2.10` |
| `Marcus Webb` | `Standard` | `3 of 3` | `$2.80` |
| `Priya Raman` | `Basic` | `1 of 2` | `$8.00` |
| `Theo Alvarez` | `Standard` | `2 of 3` | `$5.60` |
| `Elif Kaya` | `Plus` | `1 of 5` | `$3.85` |

`Marcus Webb` is at his limit, so his detail shows
`At loan limit: 3 of 3 books out. Return a book first.` and no `Check out` controls.
`Priya Raman` is at `1 of 2` — her two past returns do not count (ground rule 8).

**Desk analytics at the seed:**

- `Most overdue: A Field Guide to Nowhere, 12 days` — the single loan out with the most
  days overdue (the next is 11).
- `Accruing on loans out: $13.80` — the sum $4.00 + $3.85 + $2.45 + $2.10 + $1.40. If
  the cap were ignored this would be `$14.00`; if negative overdue days were summed it
  would be `$5.40`. Both are wrong.
- `Charged on returns: $8.55` — $1.40 + $3.15 + $4.00. Ignoring the cap gives `$10.15`,
  which is wrong.
- `Total owed: $22.35` — accruing plus charged; also the sum of the five members'
  `Fines owed`.
- `Collection rate: 62.5%` — 5 on-time returns of 8 completed loans. Counting the two
  on-the-due-day returns as late gives `37.5%`; both are on time.
- Availability, one line per title in catalog order: `The Glass Harbor: 1 of 3`,
  `Salt and Circuit: 1 of 2`, `A Field Guide to Nowhere: 1 of 2`,
  `Paper Mountains: 1 of 3`, `Winter Arithmetic: 0 of 2`,
  `The Lighthouse Codex: 1 of 2`. Only `Winter Arithmetic` has every copy out at the
  seed.

**Settings totals at the seed:** `Members: 5`, `Titles: 6`, `Copies: 14`,
`Loans out: 9`, `Completed loans: 8`, `Total owed: $22.35`.

**Worked journey — returning `A Field Guide to Nowhere` (Priya Raman) on Day 40.** It
was due Day 28, so it is 12 days late; its fine was already capped at `$4.00` and the
return charges exactly that. Afterwards:

- The ledger reads `Out (8)` and `Returned (9)`; the new returned row reads
  `Returned Day 40, 12 days late, fine $4.00`; the top of the `Out` section is now
  `Winter Arithmetic` / `Elif Kaya`.
- `Most overdue: Winter Arithmetic, 11 days`.
- `Accruing on loans out: $9.80` and `Charged on returns: $12.55` — the `$4.00` moved
  from one bucket to the other — while `Total owed: $22.35` is **unchanged**. A
  same-day return never changes what is owed, only where it sits; an implementation
  that recomputes the charge from a different day, drops the accrual, or double-counts
  it moves the total, and that is wrong.
- `Collection rate: 55.6%` — 5 of 9, rounded half-up from 55.55…; `55.5%` and `56%`
  are both wrong renderings.
- `Priya Raman` is at `0 of 2` with `Fines owed: $8.00` unchanged; `Loans out: 8`,
  `Completed loans: 9`; `A Field Guide to Nowhere` shows `2 of 2 available`.

**Worked journey — also returning `The Glass Harbor` (Marcus Webb) on Day 40.** It is
due Day 44, so this is an on-time return with no fine: the new row reads
`Returned Day 40, on time`, `Marcus Webb` drops to `2 of 3` (his at-limit message
disappears), and the collection rate becomes `60.0%` — 6 of 10, rendered with the one
mandatory decimal. Totals: `Loans out: 7`, `Completed loans: 10`, `Total owed: $22.35`
still unchanged.

**Worked journey — checking out `Salt and Circuit` for `Theo Alvarez` on Day 40.** Theo
is `Standard`, so the new loan is due Day 54 (`40 + 14`, not `40 + 21` or `40 + 7`) and
shows `Not overdue`. His count moves to `3 of 3` and his detail now shows
`At loan limit: 3 of 3 books out. Return a book first.` in place of the `Check out`
list. `Salt and Circuit` drops to `0 of 2 available` (Desk line
`Salt and Circuit: 0 of 2`) and leaves every `Check out` list. After all three journey
actions: `Loans out: 8`, `Completed loans: 10`, `Collection rate: 60.0%`,
`Accruing on loans out: $9.80`, `Charged on returns: $12.55`, `Total owed: $22.35`,
`The Glass Harbor: 2 of 3`.

## Pinned UI text (tests match these exactly — render them verbatim)

- Tab bar labels: `Catalog`, `Members`, `Loans`, `Desk`, `Settings`. Each tab screen
  shows its heading text: `Catalog`, `Members`, `Loans`, `Desk`, `Settings`.
- **Catalog tab**: one row per title in seed order showing the title name and
  `<available> of <copies> available` (`1 of 3 available`, `0 of 2 available`).
- **Members tab**: one row per member in seed order showing the member name, the tier
  name, `Loans: <out> of <limit>` and `Fines owed: $<x>`.
- **Member detail** (pushed, header title = the member name, native back button): the
  lines `Tier: <tier>`, `Loan limit: <k> books`, `Loan period: <d> days`,
  `Loans out: <out> of <limit>`, `Fines owed: $<x>`; then a `Books out` section, one
  entry per loan out (due day ascending) with the line `<title>, due Day <n>` and its
  status line (`Overdue <k> days, fine $<x>` or `Not overdue`); then a `Check out`
  section listing every title with at least one copy available, in catalog order, each
  with a `Check out` control — or, when the member is at their limit, exactly the text
  `At loan limit: <k> of <k> books out. Return a book first.` and no controls.
- **Loans tab**: a section headed `Out (<n>)`, one entry per loan out in due-day order
  with the lines `<title>, <member>`, `Out Day <a>, due Day <b>`, its status line, and
  a `Return` control (accessibility label `Return, <title>, <member>`); then a section
  headed `Returned (<n>)`, one entry per completed loan in return-day order with the
  lines `<title>, <member>` and `Returned Day <r>, on time` or
  `Returned Day <r>, <k> days late, fine $<x>`.
- **Desk tab**: the line `Most overdue: <title>, <k> days` (or `No overdue loans.` if
  none is overdue — unreachable from the seed); a `Fines` block with the lines
  `Accruing on loans out: $<x>`, `Charged on returns: $<x>`, `Total owed: $<x>`; the
  line `Collection rate: <p>%` with exactly one decimal; an `Availability` block with
  one line per title in catalog order, `<title>: <available> of <copies>`.
- **Settings tab**: a `Library` block with the lines `Members: 5`, `Titles: 6`,
  `Copies: 14`, `Loans out: <n>`, `Completed loans: <n>`, `Total owed: $<x>`.

## Final acceptance

The final e2e journey: launch → Catalog lists the six titles with `The Glass Harbor`
at `1 of 3 available` and `Winter Arithmetic` at `0 of 2 available` → Members tab shows
`Marcus Webb` at `Loans: 3 of 3` and `Priya Raman` at `Loans: 1 of 2` → Loans tab
shows `Out (9)` topped by `A Field Guide to Nowhere` / `Priya Raman` with
`Overdue 12 days, fine $4.00` → return it, then return `The Glass Harbor` /
`Marcus Webb` → `Out (7)`, `Returned (10)`, and the two new rows read
`Returned Day 40, 12 days late, fine $4.00` and `Returned Day 40, on time` → Members →
`Theo Alvarez` detail shows `Loans out: 2 of 3` and a `Check out` section → check out
`Salt and Circuit` → `Loans out: 3 of 3` and
`At loan limit: 3 of 3 books out. Return a book first.` → Desk shows
`Most overdue: Winter Arithmetic, 11 days`, `Collection rate: 60.0%`,
`Accruing on loans out: $9.80`, `Charged on returns: $12.55`, `Total owed: $22.35`,
`Salt and Circuit: 0 of 2` and `The Glass Harbor: 2 of 3` → Settings shows
`Members: 5`, `Titles: 6`, `Copies: 14`, `Loans out: 8`, `Completed loans: 10`,
`Total owed: $22.35`. It must complete without manual intervention.
