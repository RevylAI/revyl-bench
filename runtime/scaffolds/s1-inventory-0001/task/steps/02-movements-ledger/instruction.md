# Step 02 — derived on-hand, the item detail, and the movements ledger

Implement derived stock and the movement flow per the root contract's seed data, ground
rules, and pinned UI text: the full Items rows, the pushed item detail with its
receive/issue composer, and the Movements tab.

## Requirements

1. **On-hand is derived** (ground rule 2): replay the seed ledger over the opening
   stock. At a fresh install that is `Anchor bolts` 45, `Hex nuts` 250,
   `Machine screws` 150, `Washers` 380, `Bubble wrap rolls` 14, `Carton tape` 16,
   `Large cartons` 28, `Pallet wrap` 5, `Ear plugs` 220, `Hard hats` 12,
   `Hi-vis vests` 12, `Work gloves` 26. Never hardcode these — the tests move them.

2. **Items tab rows**: each row shows the item name, `On hand: <n>`, and the marker text
   `Low` exactly when on-hand is **strictly below** the threshold — six seed items are
   `Low` (`Carton tape`, at `On hand: 16`, among them); `Machine screws`, exactly at
   its threshold of 150 (`On hand: 150`), is not. Category headers
   show `<n> items, <m> units` (`4 items, 825 units` / `4 items, 63 units` /
   `4 items, 270 units` at seed).

3. **Item detail** (pushed, header title = the item name, native back button): the lines
   `SKU: <sku>`, `Category: <category>`, `On hand: <n>`, `Reorder threshold: <n>`,
   `Pack size: <n>`, `Unit cost: $<c>`; the composer — a numeric input labelled `Qty`
   with the hint text `0`, and the buttons `Receive` and `Issue`; a `Movements` section
   listing this item's movements newest first as `#<seq> <type> <qty>` with
   `Received total: <n>` and `Issued total: <n>`. For `Anchor bolts` at seed that is
   `SKU: F-101`, `Category: Fasteners`, `On hand: 45`, `Reorder threshold: 60`,
   `Pack size: 25`, `Unit cost: $0.85`, with the slice `#2 Issue 45`,
   `Received total: 0`, `Issued total: 45`.

4. **Receive / Issue**: a tap appends one ledger movement with the typed quantity and
   the next sequence number (`#12` for the first new movement), clears the input, and
   updates **every** derived figure at once — the detail's `On hand`, the row and its
   `Low` marker, the category header units, and the Movements tab. The buttons are
   one-shot (debounced), no confirmation dialog ever (ground rule 8). While the `Qty`
   input is focused and the keyboard is up, the input and both buttons stay visible and
   tappable (ground rule 12).

5. **Movements tab**: the line `<n> movements` (`11 movements` at seed); a `Totals`
   block with `<category>: received <r>, issued <i>` per category
   (`Fasteners: received 0, issued 255`, `Packaging: received 8, issued 45`,
   `Safety: received 24, issued 44` at seed); then the full ledger newest first, each
   row `#<seq> <item>: <type> <qty>` (`#11 Work gloves: Issue 34` at the top).

6. The ledger and everything derived from it persist across navigation (store state; no
   backend, no disk persistence).

## Observable outcome the hidden test checks

Launch → Items shows the seed category units with `Carton tape` marked `Low` and
`Machine screws` not → push `Anchor bolts` → detail shows the seed facts and its ledger
slice → type `40` into `Qty`, tap `Receive` → `On hand: 85`, `Received total: 40`,
`#12 Receive 40` at the top of the slice → back → the row reads `On hand: 85` with no
`Low` and the `Fasteners` header reads `4 items, 865 units` → Movements tab reads
`12 movements`,
`#12 Anchor bolts: Receive 40` at the top, `Fasteners: received 40, issued 255` → push
`Bubble wrap rolls`, type `5`, tap `Issue` → `On hand: 9` and `Issued total: 5`, and
the row is now marked `Low` (9 is below its threshold of 12).
