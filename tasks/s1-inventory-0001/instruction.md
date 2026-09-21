# StockRoom — build a mobile warehouse-inventory app

You are a coding agent building a fresh iOS mobile app from the provided Expo scaffold
(Expo SDK 57, Expo Router, TypeScript). The product is a warehouse inventory tracker:
a catalog of items with on-hand stock, a movements ledger that every quantity on screen
is **derived from** (receipts, issues and stocktake adjustments), a stocktake sheet that
compares a fixed physical count against live expected stock, a reorder list computed
from thresholds and pack sizes, and a settings screen whose totals must reconcile with
the ledger at every moment.

The work is split into three steps (see `steps/01-tabs-catalog`,
`steps/02-movements-ledger`, `steps/03-stocktake-reorder-settings`, each with its own
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

The tests run a **baked-JS Release build** of your app, built by the benchmark from the
source you submit (`./submit.sh`) — you never build or upload a binary yourself. Code
changes are only visible to the verifier after a new submission. Iterate cheaply in the
dev-client session first; submit when you believe the JS is finished.

## Ground rules (binding — the tests depend on these)

1. **Integer units, integer cents.** Every stock quantity is an integer number of units;
   every unit cost is an integer number of cents. No floating-point arithmetic anywhere —
   the percentage and money rules below are all computable in integers, and must be.

2. **On-hand is derived from the ledger — always.** An item's on-hand stock is its
   opening stock plus every `Receive`, minus every `Issue`, plus every signed `Adjust`
   in the movements ledger. The seed below states **opening stock and a seed ledger**,
   never an on-hand figure: the app (and you, on paper) must replay the ledger to get
   on-hand. Every screen that shows a quantity — the catalog, the item detail, the
   stocktake sheet, the reorder list, the Settings totals — derives from the same ledger,
   so a single movement updates all of them at once. The reconciliation invariant
   `opening total + units received - units issued + units adjusted = units on hand`
   holds in every state the tests visit.

3. **The reorder rule (exact).** An item needs reordering when its on-hand stock is
   **strictly below** its reorder threshold — an item sitting exactly *at* its threshold
   (`Machine screws` in the seed) is **not** on the list and does not count toward the
   badge. For an item on the list, the quantity to order is computed in whole supplier
   packs:

   `packs to order = ceil((threshold + buffer - on hand) / pack size)`

   where `buffer` is the fixed restock buffer of `10` units (shown in Settings; it never
   changes, never scales, and applies identically to every item), and `ceil` rounds any
   remainder **up** to a whole pack. Worked example: `Pallet wrap` at 5 on hand,
   threshold 8, pack size 2 gives `(8 + 10 - 5) / 2 = 6.5`, which is **7 packs** — not 6
   (floor), and not the 2 packs you get by forgetting the buffer. Ordering units instead
   of packs, using `<=` instead of `<`, dropping the buffer, or flooring each produce
   visibly different numbers on the seed, and the tests assert the correct ones.

4. **Stocktake: expected is live, counted is fixed.** The stocktake sheet has one row per
   item comparing **expected** — the item's *current* on-hand stock, at all times — with
   **counted**, the fixed count-sheet value from the seed. Expected is **not** a snapshot
   taken at launch or at the start of a count: a movement made while the sheet exists
   changes that item's expected and its variance immediately. `variance = counted -
   expected`, rendered signed (`+21`, `-6`, `0`).

5. **Shrinkage (exact).** A row with negative variance is **short**. Per-item shrinkage
   for a short row is `units short / expected`, as a percentage to **1 decimal, rounded
   half-up** — done in integer tenths of a percent: `tenths = (2 * short * 1000 +
   expected) / (2 * expected)` with integer division. Worked example: `Carton tape` short
   1 on expected 16 is exactly `6.25%`, which renders as `6.3%` (half-up), not `6.2%`.
   The summary's overall `Shrinkage` is **total units short across all items divided by
   total expected units across all 12 items**, same rounding. It is **not** the mean of
   the per-item percentages (that gives `6.0%` on the seed where the correct answer is
   `2.6%`), and it is not derived from the net variance (that gives `0.7%`). Overages
   never offset shortages in shrinkage.

6. **Applying the count.** The `Apply count` button, in one tap: appends to the ledger
   one `Adjust` movement per item whose variance is nonzero **at that moment**, signed,
   in catalog order (each takes the next sequence number); which sets every item's
   on-hand to its counted value. The count sheet's counted values themselves never
   change, so after applying, every expected equals its counted value, every variance is
   `0`, and the summary reads all-exact with `Shrinkage: 0.0%`. The state line flips
   from `Draft count` to `Count applied`. Applying again when every variance is zero
   appends nothing.

7. **Deterministic data — no clocks, no randomness.** No `Date.now()`, `new Date()`,
   `Math.random()`, or uuid libraries anywhere in app code. No dates or time-of-day text
   is rendered anywhere. Movements are ordered by an **integer sequence number**: the
   seed ledger holds `#1` through `#11`, and each new movement takes the next integer.
   Every value on screen must be computable from this contract alone.

8. **Debounced one-shot controls.** The `Receive`, `Issue` and `Apply count` buttons are
   one-shot: a rapid double-tap performs the action **exactly once**. Disabling the
   control briefly after press (≈250–300 ms) is one acceptable implementation. They take
   effect on the single tap that triggers them — there is no confirmation dialog, alert,
   or intermediate screen, and the app never opens a native alert dialog at any point.
   The tests never issue more than an item has on hand; what you do about an overdraw
   attempt is your choice as long as it never crashes and never opens a dialog.

9. **Textual state.** Quantities, variances, percentages, totals and the `Low` marker are
   exact text strings (pinned below) — never encoded only in colours, icons or bar
   widths.

10. **State survives navigation.** The ledger (and therefore everything derived from it)
    persists when the user navigates between tabs and pushes/pops screens (module-level/
    store state is sufficient; no backend, no disk persistence — a fresh install starts
    from the seed below).

11. **Navigation shape.** The app opens directly on the Items tab — no login, onboarding,
    or splash gate — and the catalog is interactive within two seconds of launch. The
    five tabs are a bottom tab bar. Tapping an item row **pushes** its detail screen
    (native stack header titled with the item name and a back button). Back returns to
    the tab bar. Every item row is tappable to open its detail.

12. **Everything the user must reach stays on screen.** The catalog and the stocktake
    sheet are longer than one screen and scroll. While the `Qty` input on an item detail
    is focused and the on-screen keyboard is up, the input and the `Receive` and `Issue`
    buttons all remain visible and tappable (a keyboard-avoiding container is the
    reference approach). On the Stocktake tab the `Variance summary` block and the
    `Apply count` button stay **pinned at the top and visible while the item rows scroll
    beneath them**.

13. **The Reorder tab carries a badge.** The `Reorder` item in the bottom tab bar shows a
    small numeric badge with the number of items currently below their threshold. With
    the seed alone that badge reads `6`. It updates as movements and stocktake
    adjustments change on-hand, and shows no badge at all when no item is below
    threshold.

## Seed data (exact values — copy these verbatim)

The catalog: 12 items in 3 categories. **Catalog order** — used everywhere a list of
items appears except the movements ledger — is categories alphabetically, then items
alphabetically within a category, exactly as printed here. Opening stock is the stock
level **before** the seed ledger below is replayed.

| item | SKU | category | opening | threshold | pack size | unit cost |
|---|---|---|---|---|---|---|
| Anchor bolts | F-101 | Fasteners | 90 | 60 | 25 | $0.85 |
| Hex nuts | F-102 | Fasteners | 340 | 200 | 100 | $0.12 |
| Machine screws | F-103 | Fasteners | 150 | 150 | 50 | $0.18 |
| Washers | F-104 | Fasteners | 500 | 250 | 200 | $0.05 |
| Bubble wrap rolls | P-201 | Packaging | 6 | 12 | 4 | $7.40 |
| Carton tape | P-202 | Packaging | 30 | 24 | 6 | $2.15 |
| Large cartons | P-203 | Packaging | 55 | 40 | 10 | $1.60 |
| Pallet wrap | P-204 | Packaging | 9 | 8 | 2 | $12.90 |
| Ear plugs | S-301 | Safety | 220 | 100 | 50 | $0.30 |
| Hard hats | S-302 | Safety | 14 | 10 | 5 | $9.75 |
| Hi-vis vests | S-303 | Safety | 20 | 15 | 10 | $6.20 |
| Work gloves | S-304 | Safety | 36 | 30 | 12 | $3.45 |

The seed movements ledger, in sequence order:

| seq | item | type | qty |
|---|---|---|---|
| #1 | Work gloves | Receive | 24 |
| #2 | Anchor bolts | Issue | 45 |
| #3 | Hex nuts | Issue | 90 |
| #4 | Washers | Issue | 120 |
| #5 | Bubble wrap rolls | Receive | 8 |
| #6 | Carton tape | Issue | 14 |
| #7 | Large cartons | Issue | 27 |
| #8 | Pallet wrap | Issue | 4 |
| #9 | Hard hats | Issue | 2 |
| #10 | Hi-vis vests | Issue | 8 |
| #11 | Work gloves | Issue | 34 |

The count sheet (fixed physical count — these values never change):

| item | counted |
|---|---|
| Anchor bolts | 45 |
| Hex nuts | 244 |
| Machine screws | 147 |
| Washers | 401 |
| Bubble wrap rolls | 14 |
| Carton tape | 15 |
| Large cartons | 25 |
| Pallet wrap | 5 |
| Ear plugs | 205 |
| Hard hats | 12 |
| Hi-vis vests | 13 |
| Work gloves | 24 |

The restock buffer is `10` units.

## Derived values (the tests assert these exact strings and orders)

**On-hand at a fresh install** (opening + seed receipts − seed issues):

| item | arithmetic | on hand | below threshold? |
|---|---|---|---|
| Anchor bolts | 90 − 45 | 45 | yes (45 < 60) |
| Hex nuts | 340 − 90 | 250 | no |
| Machine screws | 150 | 150 | **no — exactly at 150** |
| Washers | 500 − 120 | 380 | no |
| Bubble wrap rolls | 6 + 8 | 14 | no |
| Carton tape | 30 − 14 | 16 | yes |
| Large cartons | 55 − 27 | 28 | yes |
| Pallet wrap | 9 − 4 | 5 | yes |
| Ear plugs | 220 | 220 | no |
| Hard hats | 14 − 2 | 12 | no |
| Hi-vis vests | 20 − 8 | 12 | yes |
| Work gloves | 36 + 24 − 34 | 26 | yes |

Category unit totals: `Fasteners` 45+250+150+380 = **825**, `Packaging` 14+16+28+5 =
**63**, `Safety` 220+12+12+26 = **270**; total **1158** units. Ledger totals: **11**
movements, **32** units received (24+8), **344** units issued (45+90+120+14+27+4+2+8+34),
**0** adjusted. Reconciliation: 1470 opening + 32 − 344 = 1158.

Stock value (on-hand × unit cost, summed in cents): `Fasteners` $114.25
(45×85 + 250×12 + 150×18 + 380×5 = 11425¢), `Packaging` $247.30 (14×740 + 16×215 +
28×160 + 5×1290 = 24730¢), `Safety` $347.10 (220×30 + 12×975 + 12×620 + 26×345 =
34710¢); total **$708.65**.

**The reorder list at a fresh install** — 6 items below threshold, catalog order,
`ceil((threshold + 10 − on hand) / pack)`:

| item | need | ÷ pack | packs |
|---|---|---|---|
| Anchor bolts | 60+10−45 = 25 | 25/25 = 1.0 | 1 |
| Carton tape | 24+10−16 = 18 | 18/6 = 3.0 | 3 |
| Large cartons | 40+10−28 = 22 | 22/10 = 2.2 | 3 |
| Pallet wrap | 8+10−5 = 13 | 13/2 = 6.5 | 7 |
| Hi-vis vests | 15+10−12 = 13 | 13/10 = 1.3 | 2 |
| Work gloves | 30+10−26 = 14 | 14/12 = 1.17 | 2 |

Header line: `6 items below threshold, 18 packs to order`; badge `6`. `Machine screws`
(exactly at threshold) is absent. Wrong readings give different numbers: `<=` adds a
seventh row; no buffer gives 9 packs; flooring gives 14 packs.

**The stocktake sheet at a fresh install** (expected = the on-hand column above; counted
from the count sheet):

| item | expected | counted | variance | shrink |
|---|---|---|---|---|
| Anchor bolts | 45 | 45 | 0 | |
| Hex nuts | 250 | 244 | -6 | 6/250 = 2.4% |
| Machine screws | 150 | 147 | -3 | 3/150 = 2.0% |
| Washers | 380 | 401 | +21 | |
| Bubble wrap rolls | 14 | 14 | 0 | |
| Carton tape | 16 | 15 | -1 | 1/16 = 6.25 → 6.3% |
| Large cartons | 28 | 25 | -3 | 3/28 = 10.7% |
| Pallet wrap | 5 | 5 | 0 | |
| Ear plugs | 220 | 205 | -15 | 15/220 = 6.8% |
| Hard hats | 12 | 12 | 0 | |
| Hi-vis vests | 12 | 13 | +1 | |
| Work gloves | 26 | 24 | -2 | 2/26 = 7.7% |

Summary: `Items short: 6`, `Items over: 2`, `Items exact: 4`, `Units short: 30`
(6+3+1+3+15+2), `Units over: 22` (21+1), `Net variance: -8 units`, and
`Shrinkage: 2.6%` (30/1158 = 2.59%, half-up to one decimal). The mean of the six
per-item percentages is 6.0% and the net-based figure is 0.7% — both wrong; `2.6%` is
asserted.

**After receiving 40 `Anchor bolts`** (a journey the tests perform; movement `#12`):
on-hand 85, no longer `Low`, with `Received total: 40` and `#12 Receive 40` at the top
of the movement slice on its detail; the ledger reads `12 movements` with
`#12 Anchor bolts: Receive 40` newest-first at the top;
`Fasteners: received 40, issued 255`; the `Fasteners` header reads
`4 items, 865 units`. The reorder list
drops to `5 items below threshold, 17 packs to order` and the badge to `5`. On the
stocktake sheet — expected is live — `Anchor bolts` becomes `Expected 85`, `Counted 45`,
`Variance -40`, `Shrink 47.1%` (40/85 = 47.06%), and the summary becomes
`Items short: 7`, `Net variance: -48 units`, `Shrinkage: 5.8%` (70/1198).

**After issuing 5 `Bubble wrap rolls`** (from the state above; movement `#13`): on-hand
9 — below its threshold of 12, so `Low` appears — with `On hand: 9` and
`Issued total: 5` on its detail; the ledger reads `13 movements`.

**After receiving 5 `Bubble wrap rolls` instead** (a different journey: seed state,
then one receipt as movement `#12`): `Bubble wrap rolls` shows `Expected 19`,
`Counted 14`, `Variance -5` on the stocktake sheet; the summary becomes
`Items short: 7`, `Shrinkage: 3.0%` (35/1163).

**Applying the count from that state** appends nine `Adjust` movements in catalog order
(`#13` Hex nuts -6, `#14` Machine screws -3, `#15` Washers +21,
`#16` Bubble wrap rolls -5, `#17` Carton tape -1, `#18` Large cartons -3,
`#19` Ear plugs -15, `#20` Hi-vis vests +1, `#21` Work gloves -2; net -13) and sets
every on-hand to its counted value:

- Stocktake: `Count applied`, every `Variance 0`, `Items exact: 12`,
  `Net variance: 0 units`, `Shrinkage: 0.0%`.
- Reorder: `Machine screws` (147 < 150) joins with `order 1 pack`
  (ceil(13/50)); `Carton tape` grows to `order 4 packs` (need 19, ceil 19/6);
  `Large cartons: order 3 packs` (need 25, ceil 2.5); `Anchor bolts: order 1 pack`,
  `Pallet wrap: order 7 packs`, `Hi-vis vests: order 2 packs`,
  `Work gloves: order 2 packs`. Header `7 items below threshold, 20 packs to order`;
  badge `7`.
- Settings: `Units on hand: 1150` (the counted total), `Movements: 21`,
  `Units received: 37`, `Units issued: 344`, `Units adjusted: -13`; reconciliation
  1470 + 37 − 344 − 13 = 1150. Stock value recomputes to `Fasteners: $114.04`,
  `Packaging: $240.35`, `Safety: $341.90`, total `$696.29`.

**Applying the count after the 40-bolt receipt instead** (final journey: `#12` is the
receipt, `#13`–`#21` are nine adjustments including `Anchor bolts -40`; net -48) lands
on the **same** post-apply stock — every on-hand equals its counted value, so
`Units on hand: 1150`, badge `7`, `20 packs to order`, `Stock value: $696.29` and
`Fasteners: $114.04` — while the ledger shows the different path:
`Movements: 21`, `Units received: 72`, `Units issued: 344`, `Units adjusted: -48`
(reconciliation 1470 + 72 − 344 − 48 = 1150). `Anchor bolts` is back at 45 on hand,
so its `Low` marker and its `order 1 pack` row return.

## Pinned UI text (tests match these exactly — render them verbatim)

- Tab bar labels: `Items`, `Movements`, `Stocktake`, `Reorder`, `Settings`. Each tab
  screen shows its heading text: `Items`, `Movements`, `Stocktake`, `Reorder`,
  `Settings`. The `Reorder` tab item carries the numeric badge from ground rule 13.
  Numbers render as plain integers with no thousands separators (`1158`), money as
  `$<dollars>.<cents>` with two cent digits, variances and adjustments signed (`+21`,
  `-6`), zero unsigned (`0`).
- **Items tab**: the catalog in catalog order, grouped under a header per category
  showing the category name and the line `<n> items, <m> units` (e.g.
  `4 items, 825 units`). Each item row shows the item name, `On hand: <n>`, and the
  marker text `Low` exactly when the item is strictly below its threshold.
- **Item detail screen** (pushed, header title = the item name): the lines `SKU: <sku>`,
  `Category: <category>`, `On hand: <n>`, `Reorder threshold: <n>`, `Pack size: <n>`,
  `Unit cost: $<c>`; a movement composer — a numeric input labelled `Qty` showing the
  hint text `0` and two buttons `Receive` and `Issue` (a tap applies the typed quantity
  as a new movement and clears the input); then a `Movements` section listing this
  item's movements newest first as `#<seq> <type> <qty>` (an `Adjust` shows its sign:
  `#15 Adjust +21`), with the lines `Received total: <n>` and `Issued total: <n>`.
- **Movements tab**: the line `<n> movements`; a `Totals` block with one line per
  category, `<category>: received <r>, issued <i>`; then the full ledger newest first,
  each row `#<seq> <item>: <type> <qty>` (e.g. `#11 Work gloves: Issue 34`,
  `#12 Anchor bolts: Receive 40`).
- **Stocktake tab**: the state line `Draft count` (before applying) or `Count applied`
  (after); a `Variance summary` block with the lines `Items short: <n>`,
  `Items over: <n>`, `Items exact: <n>`, `Units short: <n>`, `Units over: <n>`,
  `Net variance: <±n> units` (`Net variance: 0 units` when zero) and
  `Shrinkage: <p>%`; the `Apply count` button; then one row per item in catalog order
  showing the item name, `Expected <e>`, `Counted <c>`, `Variance <±v>`, and — on short
  rows only — `Shrink <p>%`.
- **Reorder tab**: the line `<n> items below threshold, <p> packs to order`; then one
  row per listed item in catalog order as `<item>: order <p> packs` (`order 1 pack`,
  singular, when p is 1). When no item is below threshold, the text
  `Nothing to reorder.`.
- **Settings tab**: a `Stock` block with the lines `Items tracked: 12`,
  `Units on hand: <n>`, `Stock value: $<v>`, then one line per category
  `<category>: $<v>`. A `Ledger` block with the lines `Movements: <n>`,
  `Units received: <n>`, `Units issued: <n>`, `Units adjusted: <±n>`
  (`Units adjusted: 0` when zero). A `Rules` block with the line
  `Restock buffer: 10 units`.

## Final acceptance

The final e2e journey: launch → Items tab shows the three category headers with
`Anchor bolts` reading `On hand: 45` and `Low`, and `Machine screws` reading
`On hand: 150` with no `Low` marker → push `Anchor bolts`, type `40` into `Qty`, tap
`Receive` → the detail reads `On hand: 85` and `Received total: 40` → back → Movements
tab reads `12 movements` with `#12 Anchor bolts: Receive 40` at the top and
`Fasteners: received 40, issued 255` → Reorder tab reads
`5 items below threshold, 17 packs to order` with no `Anchor bolts` row → Stocktake tab
shows `Anchor bolts` at `Expected 85`, `Counted 45`, `Variance -40`, `Shrink 47.1%` and
the summary at `Items short: 7`, `Net variance: -48 units`, `Shrinkage: 5.8%` → tap
`Apply count` → `Count applied`, `Items exact: 12`, `Shrinkage: 0.0%` → Reorder tab
reads `7 items below threshold, 20 packs to order` with `Anchor bolts: order 1 pack`
and `Machine screws: order 1 pack` → Settings shows `Units on hand: 1150`,
`Stock value: $696.29`, `Fasteners: $114.04`, `Movements: 21`, `Units received: 72`,
`Units issued: 344`, `Units adjusted: -48` → Items tab shows `Anchor bolts` back at
`On hand: 45` with `Low`. It must complete without manual intervention.
