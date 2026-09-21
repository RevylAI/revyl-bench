# TillTape — build a mobile cash-register app

You are a coding agent building a fresh iOS mobile app from the provided Expo scaffold
(Expo SDK 57, Expo Router, TypeScript). The product is a cash register for a small
counter: a seeded product catalog, a cash drawer opened with a counted float, a sale
flow that tenders cash and composes change by a pinned greedy rule, a refund flow with
reason codes, a reconciliation view deriving expected cash from the transaction ledger,
and a Z-report summary. Its distinguishing requirement is a **contract-mandated audit
log**: every audited action emits exactly one pinned `console.log` line, and those
lines are graded from the device's captured logs — the logic path is graded even where
the screen shows nothing.

The work is split into three steps (see `steps/01-tabs-catalog`,
`steps/02-sale-tender`, `steps/03-refunds-zreport`, each with its own
`instruction.md`), followed by a final end-to-end acceptance run. Complete the steps in
order.

## How your work is verified

After each submission, **hidden device tests** run your app on a real cloud iOS
simulator and grade journeys with screenshot validations. You never see the test
definitions. Every submission is graded against the **full suite** — all step tests
plus the final e2e — so a change that breaks an earlier step's behavior is caught
immediately. If a run fails, you receive the run report (failed-criteria text,
per-step verdicts, screenshots); fix your code and resubmit. Every requirement the
tests check is stated in this contract and the step contracts; nothing hidden is
required beyond what is written here.

**Device logs are graded too.** The simulator captures your app's console output
(os_log, which includes the JS `console.log` channel). For the journeys the tests
perform, specific audit lines from 'The audit contract' below must appear in the
captured logs, matched as **exact substrings** — a deterministic comparison, no judge
and no screenshot. Emitting them is part of the product, not optional telemetry: a
journey whose screens are perfect but whose audit lines are missing or malformed fails
those checks. Every graded line is stated verbatim in 'Derived values' below.

The tests run a **baked-JS Release build** of your app, built by the benchmark from the
source you submit (`./submit.sh`) — you never build or upload a binary yourself. Code
changes are only visible to the verifier after a new submission. Iterate cheaply in the
dev-client session first; submit when you believe the JS is finished.

## Ground rules (binding — the tests depend on these)

1. **Integer cents.** Every price, line total, tender, change and till amount is an
   integer number of cents. No floating-point money arithmetic anywhere. Money renders
   as `$<dollars>.<cents>` with two cent digits (`$0.65`, `$112.45`), no thousands
   separators; counts render as plain integers.

2. **Everything is derived from the transaction ledger.** The till holds one ordered
   ledger of transactions — the 4 seeded ones below plus every sale and refund made
   in-session — numbered `#1`, `#2`, … sequentially (each new transaction takes the
   next integer; the first live transaction is `#5`). Cash sales, cash refunds,
   expected cash and every Z-report figure are derived by replaying the ledger, and
   the reconciliation invariant `expected cash = opening float + cash sales − cash
   refunds` holds in every state the tests visit. The seed states the opening float
   and the seed transactions; every derived figure is computable on paper from them.

3. **The change rule (exact — greedy, and the drawer has no nickels).** Change =
   tendered − total. It is composed greedily over the drawer's denominations, largest
   first: while change remains, take one unit of the largest denomination not
   exceeding the remainder. The denominations are `$20`, `$10`, `$5`, `$1`, `25c`,
   `10c`, `1c` — there is **no 5c slot**, nickels are never used — and composition
   assumes unlimited pieces of each (the drawer float below is the opening snapshot
   only; it never limits change). Worked examples: change `$0.65` composes as
   `2 x 25c`, `1 x 10c`, `5 x 1c` — eight pieces; the five-piece minimum-coin split
   (`1 x 25c` plus `4 x 10c`) is NOT the rule and renders visibly differently. Change
   `$0.30` composes as `1 x 25c`, `5 x 1c` — not `3 x 10c`, and not a quarter plus a
   nickel. The tests assert the greedy composition.

4. **The audit contract is binding.** Every audited action emits exactly one
   `console.log` line in the pinned format of 'The audit contract' below, and the
   substring `AUDIT|` never appears in any other log output your app produces.

5. **Refunds are one unit at catalog price, with a reason.** A refund refunds exactly
   one unit of one catalog product at its catalog price. Refunds are **not** linked to
   any prior sale — any catalog product can be refunded at any time (a walk-in return
   from a previous shift), including one never sold this session. A refund requires a
   selected product and a selected reason; the tests always select both before tapping
   `Refund`, and what you do when either is missing is your choice as long as it never
   crashes and never opens a dialog. The reasons and their codes: `Damaged (DMG)`,
   `Wrong item (WRG)`, `Changed mind (CHG)`.

6. **The Z-report is a snapshot at the tap.** Tapping `Run Z-report` recomputes the
   report from the ledger at that moment and displays it, replacing any previous
   report. `By category` lines are **gross sales** per category — a refund never
   reduces a category line; refunds appear only in `Refund total` and `Net` (a
   per-category *net* reading gives `Food: $2.60` on the seed where `Food: $6.05` is
   correct). `Net = Gross − Refund total`. `Transactions` counts sales and refunds
   together.

7. **Deterministic data — no clocks, no randomness.** No `Date.now()`, `new Date()`,
   `Math.random()`, or uuid libraries anywhere in app code. No dates or time-of-day
   text is rendered anywhere. Transactions are ordered by their integer number alone.
   Every value on screen and every audit line must be computable from this contract
   alone.

8. **Debounced one-shot controls; no dialogs ever.** `Tender`, `Refund` and
   `Run Z-report` are one-shot: a rapid double-tap performs the action **exactly
   once** (disabling the control briefly after press, ≈250–300 ms, is one acceptable
   implementation), and each performance emits its audit line exactly once. Product
   rows are the opposite: **each distinct tap registers** — tapping `Americano` twice
   adds two units and emits two audit lines (the tests always tap in separate
   deliberate steps, never rapidly). No action has a confirmation dialog, alert, or
   intermediate screen, and the app never opens a native alert dialog at any point.

9. **Textual state.** Totals, change compositions, reconciliation figures, report
   figures, selections and refund confirmations are exact text strings (pinned below)
   — never encoded only in colours or icons.

10. **State survives navigation.** The ledger (and everything derived from it)
    persists when the user switches tabs (module-level/store state is sufficient; no
    backend, no disk persistence — a fresh install starts from the seed below).

11. **Navigation shape.** The app opens directly on the Sale tab — no login,
    onboarding, or splash gate — and is interactive within two seconds of launch. The
    four tabs are a bottom tab bar. There are no pushed screens; everything lives on
    the four tabs.

12. **Everything the user must reach stays on screen.** On the Sale tab the current
    sale panel, the `Tendered` input and the `Tender` button stay visible without
    scrolling — including while the input is focused with the on-screen keyboard up (a
    keyboard-avoiding container is the reference approach) — and the `Last sale` block
    is fully visible after a tender; the product list scrolls in the remaining space
    if it must. On the Refunds tab the three reason options, the `Refund` button and
    the `Refunded:` line stay visible while the product list scrolls if needed. On the
    Till tab the `Reconciliation` block stays at the top while the transactions scroll
    beneath it.

## The audit contract (graded from device logs)

Every audited action emits **exactly one** line via `console.log`, the line being
exactly the pinned text — nothing prepended, nothing appended:

- `AUDIT|sale-add|<sku>|<qty>|<line-total-cents>` — on every product-row tap on the
  Sale tab. `<qty>` is the line's **new** quantity in the current sale and
  `<line-total-cents>` its new line total: tapping `Americano` twice emits
  `AUDIT|sale-add|D-01|1|320` and then `AUDIT|sale-add|D-01|2|640` — two lines,
  cumulative, not `1|320` twice.
- `AUDIT|tender|<tendered-cents>|<change-cents>` — when `Tender` completes a sale.
  Tendering `$20.00` against a `$9.85` sale emits `AUDIT|tender|2000|1015`. An exact
  tender emits a zero: `AUDIT|tender|515|0`.
- `AUDIT|refund|<sku>|<reason-code>|<cents>` — when `Refund` completes a refund.
  Refunding an `Enamel mug` as `Wrong item (WRG)` emits `AUDIT|refund|M-01|WRG|900` —
  the code, never the label.
- `AUDIT|zreport|<gross-cents>|<refund-cents>|<txn-count>` — on every `Run Z-report`
  tap, carrying the report's gross sales, refund total and transaction count. On the
  seed alone that is `AUDIT|zreport|3190|345|4`.

All numeric fields are plain non-negative integers in cents (counts are plain
integers): no separators, no signs, no decimal points. Lines are emitted synchronously
with the tap that causes them. The seeded transactions emitted nothing — the log
starts empty at launch. Every derived value inside a graded line (line totals, change,
gross, refund total, counts) is computable by hand from the seed data below, and the
specific lines the tests grade are spelled out in 'Derived values'.

## Seed data (exact values — copy these verbatim)

The catalog: 8 products in 3 categories. **Catalog order** — used everywhere products
are listed — is categories alphabetically, then products alphabetically within a
category, exactly as printed here.

| product | SKU | category | price |
|---|---|---|---|
| Americano | D-01 | Drinks | $3.20 |
| Flat white | D-02 | Drinks | $4.10 |
| Iced tea | D-03 | Drinks | $2.85 |
| Bagel | F-01 | Food | $2.60 |
| Brownie | F-02 | Food | $3.45 |
| Soup cup | F-03 | Food | $5.15 |
| Enamel mug | M-01 | Merch | $9.00 |
| Tote bag | M-02 | Merch | $12.50 |

The drawer float (the opening composition of the cash drawer — a fixed snapshot that
never changes on screen; expected cash is tracked as an amount, not as piece counts):

| denomination | count | value |
|---|---|---|
| $20 | 1 | $20.00 |
| $10 | 2 | $20.00 |
| $5 | 4 | $20.00 |
| $1 | 15 | $15.00 |
| 25c | 20 | $5.00 |
| 10c | 30 | $3.00 |
| 1c | 100 | $1.00 |

Opening float total: **$84.00** (8400 cents).

The seed transactions, in ledger order (already in the ledger at a fresh install; they
emitted no audit lines):

| txn | type | detail | amount | tendered | change |
|---|---|---|---|---|---|
| #1 | Sale | 2 x Americano, 1 x Bagel | $9.00 | $10.00 | $1.00 |
| #2 | Sale | 1 x Flat white, 1 x Brownie | $7.55 | $20.00 | $12.45 |
| #3 | Sale | 1 x Tote bag, 1 x Iced tea | $15.35 | $16.00 | $0.65 |
| #4 | Refund | 1 x Brownie, Damaged (DMG) | $3.45 | | |

The seed changes compose (greedy rule, worked): `$1.00` as `1 x $1`; `$12.45` as
`1 x $10`, `2 x $1`, `1 x 25c`, `2 x 10c`; `$0.65` as `2 x 25c`, `1 x 10c`, `5 x 1c`
(the no-nickel edge of ground rule 3).

## Derived values (the tests assert these exact strings and lines)

**Seed state (fresh install).** Cash sales 900 + 755 + 1535 = 3190 →
`Cash sales: $31.90`; cash refunds 345 → `Cash refunds: $3.45`; expected cash
8400 + 3190 − 345 = 11245 → `Expected cash: $112.45`, alongside
`Opening float: $84.00`. The transactions list, newest first: `#4 Refund $3.45`,
`#3 Sale $15.35`, `#2 Sale $7.55`, `#1 Sale $9.00`. Per-category gross: `Drinks`
640 + 410 + 285 = 1335, `Food` 260 + 345 = 605, `Merch` 1250. A Z-report run on the
seed alone shows `Sales: 3`, `Refunds: 1`, `Transactions: 4`, `Gross: $31.90`,
`Refund total: $3.45`, `Net: $28.45`, `Drinks: $13.35`, `Food: $6.05`,
`Merch: $12.50` and emits `AUDIT|zreport|3190|345|4`.

**A two-sale journey the tests perform** (from a fresh install). Tap `Americano`
twice (the panel reads `Americano x2 $6.40` with `Total: $6.40`) and `Brownie` once —
the panel reads `Americano x2 $6.40`, `Brownie x1 $3.45`, `Total: $9.85` — and the
taps emit `AUDIT|sale-add|D-01|1|320`,
`AUDIT|sale-add|D-01|2|640`, `AUDIT|sale-add|F-02|1|345`. Tender `20.00`: change
2000 − 985 = 1015 → `Change due: $10.15` composing as `1 x $10`, `1 x 10c`, `5 x 1c`;
the tender emits `AUDIT|tender|2000|1015`, the sale panel resets to `Total: $0.00`,
and the ledger gains `#5 Sale $9.85`. Then a second sale: `Iced tea` plus `Bagel` is
`Total: $5.45` (emitting `AUDIT|sale-add|D-03|1|285`, `AUDIT|sale-add|F-01|1|260`);
tendering `5.75` gives change 30 → `Change due: $0.30` composing as `1 x 25c`,
`5 x 1c` (no `10c` line — greedy, not minimum-coin), emitting `AUDIT|tender|575|30`,
and the ledger gains `#6 Sale $5.45`.

**A sale-and-refunds journey the tests perform** (from a fresh install). Sell one
`Soup cup` (`AUDIT|sale-add|F-03|1|515`) tendered exactly at `5.15` —
`Change due: $0.00`, no denomination lines, `AUDIT|tender|515|0`, ledger `#5 Sale
$5.15`. Refund an `Enamel mug` as `Wrong item (WRG)` (`AUDIT|refund|M-01|WRG|900`,
ledger `#6 Refund $9.00`), then an `Iced tea` as `Damaged (DMG)`
(`AUDIT|refund|D-03|DMG|285`, ledger `#7 Refund $2.85`, and the confirmation line
reads `Refunded: Iced tea $2.85 (DMG)`). The Till then reads `Cash sales: $37.05`
(3190 + 515), `Cash refunds: $15.30` (345 + 900 + 285), `Expected cash: $105.75`
(8400 + 3705 − 1530 = 10575), with `#7 Refund $2.85` newest. Running the Z-report
shows `Sales: 4`, `Refunds: 3`, `Transactions: 7`, `Gross: $37.05`,
`Refund total: $15.30`, `Net: $21.75`, `Drinks: $13.35`, `Food: $11.20`
(605 + 515), `Merch: $12.50` and emits `AUDIT|zreport|3705|1530|7`.

**The final journey** (fresh install; both sales of the two-sale journey, then a
refund). After the `$9.85` and `$5.45` sales, refund a `Tote bag` as
`Changed mind (CHG)`: `AUDIT|refund|M-02|CHG|1250`, ledger `#7 Refund $12.50`,
confirmation `Refunded: Tote bag $12.50 (CHG)`. The Till reads `Cash sales: $47.20`
(3190 + 985 + 545 = 4720), `Cash refunds: $15.95` (345 + 1250), `Expected cash:
$115.25` (8400 + 4720 − 1595 = 11525), with `#7 Refund $12.50` newest. The Z-report
shows `Sales: 5`, `Refunds: 2`, `Transactions: 7`, `Gross: $47.20`,
`Refund total: $15.95`, `Net: $31.25` (4720 − 1595 = 3125), `Drinks: $22.60`
(1335 + 640 + 285 = 2260), `Food: $12.10` (605 + 345 + 260 = 1210), `Merch: $12.50`
and emits `AUDIT|zreport|4720|1595|7`.

## Pinned UI text (tests match these exactly — render them verbatim)

- Tab bar labels: `Sale`, `Refunds`, `Till`, `Report`. Each tab screen shows its
  heading text: `Sale`, `Refunds`, `Till`, `Report`.
- **Sale tab**: the catalog in catalog order, grouped under a header per category —
  `Drinks`, `Food`, `Merch` — each product row showing the product name and its price
  (`Americano` with `$3.20`, `Tote bag` with `$12.50`). The current sale panel: one
  line per sale line as `<product> x<qty> $<line-total>` (`Americano x2 $6.40`) and
  the line `Total: $<t>` (`Total: $0.00` when the sale is empty). A numeric input
  labelled `Tendered` showing the hint text `0.00` (it takes a dollar amount such as
  `20.00` and clears after a completed tender) and the `Tender` button. After a
  tender, a `Last sale` block: `Change due: $<c>` followed by one line per
  denomination used, `<n> x <denom>` in descending denomination order (`1 x $10`,
  `1 x 10c`, `5 x 1c`); no denomination lines when change is zero. The block clears
  when the next product tap starts a new sale.
- **Refunds tab**: the catalog rows (product name and price); tapping one selects it,
  shown as `Selected: <product> $<price>`; the three reason options `Damaged (DMG)`,
  `Wrong item (WRG)`, `Changed mind (CHG)`, tappable to select; the `Refund` button;
  after a completed refund the line `Refunded: <product> $<price> (<code>)` showing
  the most recent refund, with the selections cleared.
- **Till tab**: a `Reconciliation` block with the lines `Opening float: $84.00`,
  `Cash sales: $<x>`, `Cash refunds: $<x>`, `Expected cash: $<x>`; a `Transactions`
  list newest first, each row `#<n> Sale $<amt>` or `#<n> Refund $<amt>`; a
  `Drawer at open` block with one line per denomination of the float table,
  `<count> x <denom>` (`1 x $20`, `2 x $10`, `4 x $5`, `15 x $1`, `20 x 25c`,
  `30 x 10c`, `100 x 1c`).
- **Report tab**: the `Run Z-report` button. Before the first run, the text
  `No report run yet.`. After a run: the lines `Sales: <n>`, `Refunds: <n>`,
  `Transactions: <n>`, `Gross: $<x>`, `Refund total: $<x>`, `Net: $<x>`, then a
  `By category` block with one line per category, `<category>: $<gross>`.

## Final acceptance

The final e2e journey: launch → Sale tab shows the catalog with `Americano` at `$3.20`
and `Tote bag` at `$12.50` → tap `Americano`, tap `Americano` again, tap `Brownie` →
the panel reads `Americano x2 $6.40`, `Brownie x1 $3.45`, `Total: $9.85` → type
`20.00` into `Tendered`, tap `Tender` → `Change due: $10.15` with `1 x $10`,
`1 x 10c`, `5 x 1c` → tap `Iced tea`, tap `Bagel`, type `5.75`, tap `Tender` →
`Change due: $0.30` with `1 x 25c`, `5 x 1c` and no `10c` line → Refunds tab: tap
`Tote bag`, tap `Changed mind (CHG)`, tap `Refund` → `Refunded: Tote bag $12.50
(CHG)` → Till tab reads `Cash sales: $47.20`, `Cash refunds: $15.95`,
`Expected cash: $115.25` with `#7 Refund $12.50` newest and `Opening float: $84.00`
→ Report tab: tap `Run Z-report` → `Sales: 5`, `Refunds: 2`, `Transactions: 7`,
`Gross: $47.20`, `Refund total: $15.95`, `Net: $31.25`, `Drinks: $22.60`,
`Food: $12.10`, `Merch: $12.50`. It must complete without manual intervention, and
the captured device log must contain the journey's audit lines from 'Derived values'.
