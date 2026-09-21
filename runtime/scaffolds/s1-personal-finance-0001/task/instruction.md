# PocketLedger — build a mobile personal-finance app

You are a coding agent building a fresh iOS mobile app from the provided Expo scaffold
(Expo SDK 57, Expo Router, TypeScript). The product is a personal-finance app: an
account overview with a date-grouped transaction list, transaction re-categorization
that recalculates per-category budget progress with over-budget warnings, spending
insights, and a persistent weekly-alert preference.

The work is split into three steps (see `steps/01-tabs`, `steps/02-transactions-budget`,
`steps/03-insights-alerts`, each with its own `instruction.md`), followed by a final
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

1. **Integer cents everywhere; dollars only at render.** All money lives as integer
   cents. Exactly one formatting convention renders it:
   `$<dollars with en-US thousands separators>.<2-digit cents>` — e.g. 245000 →
   `$2,450.00`, 4000 → `$40.00`. Income amounts render with a leading `+`
   (`+$1,500.00`) in a distinct (green) style; expense amounts render with a leading
   `-` (`-$60.00`).
2. **Deterministic data — no clocks.** No `Date.now()` and no `new Date()` anywhere in
   app code. Transaction dates are the fixed `dateLabel` strings given below, ordered
   by the integer `tsOrder` sort key (never by parsing dates). Week buckets are the
   fixed `weekLabel` strings. Every value on screen must be computable from this
   contract alone.
3. **Debounced one-shot mutation controls.** The category **Apply** action and the
   weekly-alert toggle are one-shot: a rapid double-tap must have the same effect as a
   single tap (the re-categorization applies exactly once; the toggle does not bounce
   back). Disabling the control briefly after press is one acceptable implementation.
4. **Textual state summaries.** Budget progress, over-budget overage, top category,
   weekly totals, and the alert preference are exact text strings (pinned below) —
   never encoded only in charts, bars, or a switch's visual position. (Decorative
   progress bars/charts may accompany the text.)
5. **State survives tab navigation.** The re-categorization and the weekly-alert
   setting persist when the user navigates between tabs (module-level/store state is
   sufficient; no backend, no disk persistence required).
6. **Budgets track expenses only.** Income transactions have no category and are
   excluded from budget totals, spending insights, and weekly totals.

## Seed data (exact values — copy these verbatim)

Accounts (`id`, `name`, `balanceCents`) — balances are displayed as-is and are NOT
derived from the transaction list; they never change at runtime:

| name | balanceCents | renders as |
|---|---|---|
| Everyday Checking | 245000 | $2,450.00 |
| Rainy Day Savings | 800000 | $8,000.00 |

Categories (`id`, `name`): `dining` Dining, `transport` Transport, `groceries`
Groceries, `entertainment` Entertainment, `rent` Rent.

Monthly budgets (`categoryId`, `monthlyCents`):

| category | monthlyCents | renders as |
|---|---|---|
| dining | 20000 | $200.00 |
| transport | 15000 | $150.00 |
| groceries | 30000 | $300.00 |
| entertainment | 10000 | $100.00 |
| rent | 200000 | $2,000.00 |

Transactions (`id`, `label`, `amountCents`, `categoryId`, `kind`, `dateLabel`,
`weekLabel`, `tsOrder`) — `amountCents` is always positive; `kind` carries the sign at
render; income rows have no category:

| id | label | amountCents | category | kind | dateLabel | weekLabel | tsOrder |
|---|---|---|---|---|---|---|---|
| t01 | Rent | 200000 | rent | expense | Jul 1 | Week of Jul 1 | 1 |
| t02 | Grocery Run | 9000 | groceries | expense | Jul 2 | Week of Jul 1 | 2 |
| t03 | Taco Tuesday | 4500 | dining | expense | Jul 3 | Week of Jul 1 | 3 |
| t04 | Paycheck | 150000 | — | income | Jul 8 | Week of Jul 8 | 4 |
| t05 | Metro Card | 6000 | transport | expense | Jul 9 | Week of Jul 8 | 5 |
| t06 | Grocery Run | 8500 | groceries | expense | Jul 10 | Week of Jul 8 | 6 |
| t07 | Movie Night | 4000 | entertainment | expense | Jul 11 | Week of Jul 8 | 7 |
| t08 | Sushi Dinner | 8500 | dining | expense | Jul 15 | Week of Jul 15 | 8 |
| t09 | Rideshare | 3500 | transport | expense | Jul 16 | Week of Jul 15 | 9 |
| t10 | Grocery Run | 8500 | groceries | expense | Jul 17 | Week of Jul 15 | 10 |
| t11 | Pizza Night | 6000 | entertainment | expense | Jul 18 | Week of Jul 15 | 11 |
| t12 | Coffee Beans | 5000 | dining | expense | Jul 22 | Week of Jul 22 | 12 |
| t13 | Bus Pass | 2500 | transport | expense | Jul 23 | Week of Jul 22 | 13 |

Weekly spending totals (the Insights trend renders exactly these four rows; keep them
as fixed values — they must NOT change when a transaction is re-categorized, because
re-categorization changes neither the amount nor the week):

| weekLabel | totalCents | renders as |
|---|---|---|
| Week of Jul 1 | 213500 | $2,135.00 |
| Week of Jul 8 | 18500 | $185.00 |
| Week of Jul 15 | 26500 | $265.00 |
| Week of Jul 22 | 7500 | $75.00 |

Derived values (the tests assert these exact numbers — arithmetic shown so you can
verify your implementation on paper):

- Seeded per-category expense totals: Dining 4500+8500+5000 = **18000** →
  `Dining: $180.00 of $200.00`; Transport 6000+3500+2500 = **12000**; Groceries
  9000+8500+8500 = **26000**; Entertainment 4000+6000 = **10000** (exactly at
  budget); Rent **200000** (exactly at budget).
- Re-categorizing **Pizza Night** (6000, `entertainment` → `dining`) moves exactly one
  transaction: Dining becomes 18000+6000 = **24000** → `Dining: $240.00 of $200.00`
  with warning `Over budget: Dining +$40.00` (24000−20000 = 4000); Entertainment
  becomes 10000−6000 = **4000** → `Entertainment: $40.00 of $100.00` with no warning.
- Weekly totals check: 200000+9000+4500 = 213500; 6000+8500+4000 = 18500 (Paycheck is
  income, excluded); 8500+3500+8500+6000 = 26500; 5000+2500 = 7500.
- Top spending category (computed from live per-category totals): **Rent** (200000) —
  it dominates before and after any re-categorization in this journey.

## Pinned UI text (tests match these exactly — render them verbatim)

- Tab bar labels: `Accounts`, `Budget`, `Insights`. Each tab screen shows its heading
  text: `Accounts`, `Budget`, `Insights`.
- Accounts screen: the two account cards (names + balances above), then a list label
  `Transactions` (rendered upper-case: `TRANSACTIONS`), then the transaction list grouped under its `dateLabel` group
  headers (e.g. `Jul 1`), each row showing the label, its category name (or `Income`),
  and the signed amount.
- Budget screen: one row per category, text `<Name>: <spent> of <budget>` — e.g.
  `Dining: $180.00 of $200.00` before re-categorization. When a category is over
  budget, a warning line `Over budget: <Name> +<overage>` — e.g.
  `Over budget: Dining +$40.00`.
- Transaction detail screen (opened by tapping a transaction row): the transaction's
  label, signed amount (e.g. `-$60.00`), and `dateLabel` (e.g. `Jul 18`); a `Category`
  picker (label rendered upper-case: `CATEGORY`) listing the five category names with the current selection visibly marked
  (e.g. a checkmark); an `Apply category` button that, once applied, reads
  `Category updated`; a `Back to Accounts` button. For income transactions, show
  `Income is not categorized.` instead of the picker.
- Insights screen: `Top category: Rent`; a `Weekly spending` section (label rendered upper-case: `WEEKLY SPENDING`) with the four
  weekly rows (`weekLabel` + total, e.g. `Week of Jul 1` `$2,135.00`); an
  `Alert preferences` section (label rendered upper-case: `ALERT PREFERENCES`) with a toggle row labeled `Weekly spending alert`
  showing its state as text `On` / `Off`, and a summary line `Weekly alert: On` /
  `Weekly alert: Off`. The enabled toggle row is visually distinct (e.g. green
  background).

## Final acceptance

The final e2e journey: launch → verify account cards and the date-grouped list →
open Pizza Night → re-categorize to Dining → verify Budget shows
`Dining: $240.00 of $200.00` with `Over budget: Dining +$40.00` and
`Entertainment: $40.00 of $100.00` → open Insights → verify `Top category: Rent` and
`Weekly alert: Off` → enable the weekly alert → verify `Weekly alert: On` → navigate
to Accounts and back → verify the setting persisted. It must complete without manual
intervention.
