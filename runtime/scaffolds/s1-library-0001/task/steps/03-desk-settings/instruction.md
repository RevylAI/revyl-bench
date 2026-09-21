# Step 03 — the desk dashboard and settings totals

Implement the Desk tab and the Settings tab per the root contract. Every number on both
is derived live from the catalog, the roster and the ledger — including the ledger as
step 02's flows rewrite it.

## Requirements

1. **Desk tab**, in this order:
   - `Most overdue: <title>, <k> days` — the single loan out with the most days
     overdue (`No overdue loans.` if none is overdue; ties would break by title A–Z).
     At the seed: `Most overdue: A Field Guide to Nowhere, 12 days`.
   - A `Fines` block: `Accruing on loans out: $<x>` (fines on loans still out),
     `Charged on returns: $<x>` (fines fixed at return time), `Total owed: $<x>`
     (their sum). At the seed: `$13.80`, `$8.55`, `$22.35`. The cap and the
     never-negative rule both feed these — `$14.00`, `$10.15` and `$5.40` are the
     wrong readings the root contract works through.
   - `Collection rate: <p>%` — on-time returns over completed loans, rounded half-up
     to exactly one decimal (ground rules 7 and 12). At the seed: `62.5%`.
   - An `Availability` block, one line per title in catalog order as
     `<title>: <available> of <copies>`. At the seed `Winter Arithmetic: 0 of 2` and
     every other title has one or more copies in.

2. **Settings tab**: a `Library` block with the lines `Members: 5`, `Titles: 6`,
   `Copies: 14`, `Loans out: <n>`, `Completed loans: <n>`, `Total owed: $<x>` — at the
   seed `Loans out: 9`, `Completed loans: 8`, `Total owed: $22.35`.

3. **Everything recomputes on every flow.** Returning `A Field Guide to Nowhere`
   (12 days late, charge `$4.00`) moves the Desk to
   `Most overdue: Winter Arithmetic, 11 days`, `Accruing on loans out: $9.80`,
   `Charged on returns: $12.55`, `Collection rate: 55.6%` — while `Total owed: $22.35`
   does **not** move, because a same-day return only shifts a fine between buckets.
   Settings becomes `Loans out: 8`, `Completed loans: 9`.

4. An on-time return adds to the denominator with no charge: returning
   `The Glass Harbor` for `Marcus Webb` (due Day 44) afterwards gives
   `Collection rate: 60.0%` — rendered with the mandatory single decimal, not `60%`.

5. Both tabs keep their step-01 headings, and the Desk and Settings values stay
   consistent with whatever the ledger currently says after any sequence of returns
   and checkouts. State persists across tab switches (no backend, no disk
   persistence; a fresh install starts from the seed).

## Observable outcome the hidden test checks

Desk shows `Most overdue: A Field Guide to Nowhere, 12 days`, the `$13.80` / `$8.55` /
`$22.35` fines block, `Collection rate: 62.5%` and the availability lines → Settings
shows the seed `Library` block → return `A Field Guide to Nowhere` on the Loans tab →
Desk now shows `Most overdue: Winter Arithmetic, 11 days`, `$9.80` / `$12.55`, an
unchanged `Total owed: $22.35` and `Collection rate: 55.6%` → Settings shows
`Loans out: 8`, `Completed loans: 9` → navigating away and back changes nothing.
