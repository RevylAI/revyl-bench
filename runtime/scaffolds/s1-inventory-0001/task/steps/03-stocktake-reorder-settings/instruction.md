# Step 03 — the stocktake sheet, the reorder list, and settings totals

Implement the Stocktake, Reorder and Settings tabs per the root contract. Everything on
all three is derived from the same ledger step 02 built; nothing here has independent
state except the fixed count sheet.

## Requirements

1. **Stocktake tab**: the state line `Draft count`; a `Variance summary` block
   (`Items short: <n>`, `Items over: <n>`, `Items exact: <n>`, `Units short: <n>`,
   `Units over: <n>`, `Net variance: <±n> units`, `Shrinkage: <p>%`); the `Apply count`
   button; then one row per item in catalog order with `Expected <e>`, `Counted <c>`,
   `Variance <±v>`, and `Shrink <p>%` on short rows only. The summary block and the
   button stay pinned at the top while the rows scroll (ground rule 12).

2. **Expected is live** (ground rule 4): expected is the current on-hand, never a
   snapshot. At seed the summary is `Items short: 6`, `Items over: 2`, `Items exact: 4`,
   `Units short: 30`, `Units over: 22`, `Net variance: -8 units`, `Shrinkage: 2.6%`,
   with `Hex nuts` at `Expected 250`, `Counted 244`, `Variance -6`, `Shrink 2.4%`;
   `Carton tape` at `Shrink 6.3%` (6.25 half-up — do the rounding in integer tenths);
   `Washers` at `Variance +21` with no `Shrink`. A receipt of 5 `Bubble wrap rolls`
   moves that row to `Expected 19`, `Counted 14`, `Variance -5` and the summary to
   `Items short: 7`, `Shrinkage: 3.0%`.

3. **Shrinkage** (ground rule 5): per-item on short rows, `short / expected` to 1
   decimal half-up; the overall figure is total units short over total expected units —
   **not** the mean of the row percentages (6.0% at seed) and **not** net-based (0.7%);
   `2.6%` is the seed value the tests assert.

4. **Apply count** (ground rule 6): one tap appends one signed `Adjust` movement per
   nonzero-variance item in catalog order (next sequence numbers), setting every
   on-hand to its counted value. After applying: `Count applied`, every `Variance 0`,
   `Items exact: 12`, `Net variance: 0 units`, `Shrinkage: 0.0%` — and the Items rows,
   category units, Movements totals, Reorder list and Settings all move in the same
   tap. One-shot, no dialog.

5. **Reorder tab**: the line `<n> items below threshold, <p> packs to order`; one row
   per below-threshold item in catalog order as `<item>: order <p> packs`
   (`order 1 pack` singular); empty state `Nothing to reorder.`. The rule is ground
   rule 3: strict `<`, plus the fixed buffer of 10 units, `ceil`, in whole packs. At
   seed: `Anchor bolts: order 1 pack`, `Carton tape: order 3 packs`,
   `Large cartons: order 3 packs`, `Pallet wrap: order 7 packs`,
   `Hi-vis vests: order 2 packs`, `Work gloves: order 2 packs` —
   `6 items below threshold, 18 packs to order`, and no `Machine screws` row. The
   `Reorder` tab item carries the badge (`6` at seed; ground rule 13). After the
   5-roll receipt and `Apply count`, the list is
   `7 items below threshold, 20 packs to order` with `Machine screws: order 1 pack`
   and `Carton tape: order 4 packs`; badge `7`.

6. **Settings tab**: the `Stock` block (`Items tracked: 12`, `Units on hand: 1158`,
   `Stock value: $708.65`, `Fasteners: $114.25`, `Packaging: $247.30`,
   `Safety: $347.10` at seed); the `Ledger` block (`Movements: 11`,
   `Units received: 32`, `Units issued: 344`, `Units adjusted: 0` at seed); the `Rules`
   block (`Restock buffer: 10 units`). After the 5-roll receipt and `Apply count`:
   `Units on hand: 1150`, `Movements: 21`, `Units received: 37`, `Units issued: 344`,
   `Units adjusted: -13`, `Stock value: $696.29`. The reconciliation invariant of
   ground rule 2 must hold in both states.

## Observable outcome the hidden test checks

Reorder tab shows the six seed rows, `18 packs to order`, badge `6`, no
`Machine screws` → Settings shows the seed `Stock` and `Ledger` blocks → Stocktake
shows the seed summary with `Shrink 2.4%` / `Shrink 6.3%` / `Variance +21` → receive
`5` `Bubble wrap rolls` from its detail → Stocktake now shows `Expected 19`,
`Variance -5`, `Items short: 7`, `Shrinkage: 3.0%` → tap `Apply count` → `Count applied`,
`Items exact: 12`, `Shrinkage: 0.0%` → Reorder reads
`7 items below threshold, 20 packs to order` → Settings reads `Units on hand: 1150`,
`Movements: 21`, `Units received: 37`, `Units adjusted: -13`, `Stock value: $696.29`.
