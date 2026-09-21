# Step 02 — the sale flow: add, tender, greedy change, and the first audit lines

Implement the sale flow per the root contract's ground rules, audit contract and
pinned UI text: the current sale panel, the tender, the greedy change composition, the
transactions list on the Till tab — and the `sale-add` / `tender` audit lines, which
are graded from the device logs from this step on.

## Requirements

1. **Adding to a sale**: tapping a product row on the Sale tab adds one unit of that
   product to the current sale — every distinct tap registers (ground rule 8) — and
   emits exactly one `AUDIT|sale-add|<sku>|<qty>|<line-total-cents>` line with the
   line's **new** cumulative quantity and line total (tapping `Americano` twice emits
   `AUDIT|sale-add|D-01|1|320` then `AUDIT|sale-add|D-01|2|640`). The panel shows one
   line per sale line as `<product> x<qty> $<line-total>` plus `Total: $<t>`
   (`Total: $0.00` when empty).

2. **Tender**: the `Tendered` input (hint text `0.00`, dollar amount) and the one-shot
   `Tender` button. A tap computes change = tendered − total in integer cents, emits
   exactly one `AUDIT|tender|<tendered-cents>|<change-cents>` line
   (`AUDIT|tender|2000|1015` for `20.00` against `$9.85`), appends the sale to the
   ledger with the next transaction number (`#5` for the first live sale), clears the
   sale panel back to `Total: $0.00`, and clears the input. The tests never tender
   less than the total; an insufficient tender is your choice as long as it never
   crashes, never opens a dialog and never emits an audit line.

3. **Change composition is greedy** (ground rule 3): the `Last sale` block shows
   `Change due: $<c>` and one `<n> x <denom>` line per denomination used, descending
   — `$10.15` is `1 x $10`, `1 x 10c`, `5 x 1c`; `$0.30` is `1 x 25c`, `5 x 1c` with
   no `10c` line. No denomination lines when change is zero. The block clears on the
   next product tap.

4. **The Till transactions list**: below the step-01 drawer block, a `Transactions`
   list newest first, each row `#<n> Sale $<amt>` or `#<n> Refund $<amt>` — the four
   seed transactions at a fresh install (`#4 Refund $3.45` on top), live sales
   appended (`#5 Sale $9.85`).

5. Keyboard reachability per ground rule 12: with the `Tendered` input focused and
   the keyboard up, the input, the `Tender` button and the sale panel stay visible
   and tappable.

6. The ledger and everything derived from it persist across tab switches (store
   state; no backend, no disk persistence).

## Observable outcome the hidden test checks

Launch → tap `Americano` twice, tap `Brownie` → the panel reads `Americano x2 $6.40`,
`Brownie x1 $3.45`, `Total: $9.85` → type `20.00` into `Tendered`, tap `Tender` →
`Change due: $10.15` with `1 x $10`, `1 x 10c`, `5 x 1c`, panel back at
`Total: $0.00` → Till shows `#5 Sale $9.85` on top of `#4 Refund $3.45` and
`#3 Sale $15.35` → back on Sale, tap `Iced tea` and `Bagel` (`Total: $5.45`), type
`5.75`, tap `Tender` → `Change due: $0.30` with `1 x 25c`, `5 x 1c` and no `10c`
line. The captured log must contain the journey's seven audit lines from the root
contract's 'Derived values' (three `sale-add` lines and `AUDIT|tender|2000|1015` for
the first sale; two `sale-add` lines and `AUDIT|tender|575|30` for the second).
