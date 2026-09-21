# Step 03 — refunds, reconciliation, and the Z-report

Implement the Refunds tab, the Till reconciliation block, and the Report tab per the
root contract. Everything here derives from the same ledger step 02 built, and the
`refund` / `zreport` audit lines join the graded log surface.

## Requirements

1. **Refund flow** (ground rule 5): the Refunds tab shows the catalog rows; tapping
   one selects it (`Selected: <product> $<price>`); the three reason options
   `Damaged (DMG)`, `Wrong item (WRG)`, `Changed mind (CHG)` are tappable to select;
   the one-shot `Refund` button refunds one unit at catalog price, appends
   `#<n> Refund $<amt>` to the ledger, emits exactly one
   `AUDIT|refund|<sku>|<reason-code>|<cents>` line (`AUDIT|refund|M-01|WRG|900` for
   an `Enamel mug` as `Wrong item (WRG)` — the code, never the label), clears both
   selections and shows `Refunded: <product> $<price> (<code>)` for the most recent
   refund. Refunds are not linked to any prior sale — any catalog product refunds at
   any time.

2. **Till reconciliation** (ground rule 2): the `Reconciliation` block above the
   transactions — `Opening float: $84.00`, `Cash sales: $<x>`, `Cash refunds: $<x>`,
   `Expected cash: $<x>` — derived by replaying the ledger. At a fresh install that
   is `Cash sales: $31.90`, `Cash refunds: $3.45`, `Expected cash: $112.45`
   (8400 + 3190 − 345). Never hardcode these — the tests move them. The invariant
   `expected cash = opening float + cash sales − cash refunds` holds in every state.

3. **Report tab** (ground rule 6): `No report run yet.` before the first run; the
   one-shot `Run Z-report` button snapshots the ledger at the tap, renders
   `Sales: <n>`, `Refunds: <n>`, `Transactions: <n>`, `Gross: $<x>`,
   `Refund total: $<x>`, `Net: $<x>` and the `By category` gross lines, and emits
   exactly one `AUDIT|zreport|<gross-cents>|<refund-cents>|<txn-count>` line
   (`AUDIT|zreport|3190|345|4` on the seed alone). Category lines are gross — a
   refund never reduces them.

4. Steps 01/02 behavior is unchanged: the headings, the catalog, the drawer block,
   the sale flow and its audit lines must all still pass — every submission is graded
   against the full suite.

## Observable outcome the hidden test checks

Launch → Till reads the seed reconciliation (`Cash sales: $31.90`,
`Cash refunds: $3.45`, `Expected cash: $112.45`, `#4 Refund $3.45` newest) → sell one
`Soup cup` tendered exactly at `5.15` → refund an `Enamel mug` as `Wrong item (WRG)`,
then an `Iced tea` as `Damaged (DMG)` (`Refunded: Iced tea $2.85 (DMG)`) → Till reads
`Cash sales: $37.05`, `Cash refunds: $15.30`, `Expected cash: $105.75` with
`#7 Refund $2.85` newest → Report: tap `Run Z-report` → `Sales: 4`, `Refunds: 3`,
`Transactions: 7`, `Gross: $37.05`, `Refund total: $15.30`, `Net: $21.75`,
`Drinks: $13.35`, `Food: $11.20`, `Merch: $12.50`. The captured log must contain the
journey's five audit lines from the root contract's 'Derived values' — including
`AUDIT|tender|515|0`, which is graded from the log alone (the zero-change screen
state is never validated).
