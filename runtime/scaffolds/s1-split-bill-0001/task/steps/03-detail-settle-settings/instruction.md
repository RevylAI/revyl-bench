# Step 03 — expense detail, settle up, settings totals

Implement the expense detail screen, the settle-up action, and the Settings tab per the
root contract.

## Requirements

1. **Open an expense**: tapping any expense row in a group screen pushes the detail
   screen (header title `Expense`, native back button) showing the `description` and
   amount at the top, then `<payer displayName> paid` (or `You paid`), then a `Split`
   section listing **every** group member in group order with that member's share.
   Example from the seed: `Ramen` opens with `Marco Silva paid` and the split
   `You $17.34`, `Marco Silva $17.33`, `Elena Vasquez $17.33`.

2. **Settle up**: every Balances row with a non-zero balance shows a `Settle up` button
   (a settled row shows none). Tapping it is one-shot (debounced) and clears your balance
   with that member **in every group where you have one**, recording one settlement per
   affected group (ground rule 5). The row then reads `<displayName> is settled up`, and
   the summary, the tab badge, the Settings totals **and the Groups tab row of every
   affected group** all update. From the seed, settling with `Marco Silva` (who owes you
   `$61.44`) changes three Groups rows: `Tahoe Trip` → `You owe $188.88`, `Lunch Crew` →
   `You are owed $13.66`, `Ski Weekend` → `You are owed $8.22`; `Apartment` is unchanged
   because you have no balance with him there.

3. **Settings tab**: a `Totals` block with `Total owed to you: $<amount>` (the sum of
   the positive balances) and `Total you owe: $<amount>` (the absolute sum of the
   negative balances) — with the seed alone, `Total owed to you: $77.81` and
   `Total you owe: $83.38`. A `Display` section holds one row labelled
   `Hide settled members` with a toggle switch; turning it on makes the Balances tab
   omit every row whose balance is zero, and changes nothing else anywhere.

4. Settlements and the `Hide settled members` switch persist across navigation: leaving
   the tab and returning shows the same rows, the same totals, and the same switch
   position (store state; no backend, no disk persistence).

## Observable outcome the hidden test checks

Open `Lunch Crew` → tap the `Ramen` row → detail shows `Marco Silva paid` and the split
`You $17.34` / `Marco Silva $17.33` / `Elena Vasquez $17.33` → back → back → Balances tab
→ badge `3` → tap `Settle up` on the `Marco Silva owes you $61.44` row → the row reads
`Marco Silva is settled up`, the badge reads `2`, and the summary reads
`Total: you owe $67.01` → Groups tab → `Tahoe Trip` reads `You owe $188.88` and
`Ski Weekend` reads `You are owed $8.22` → Settings tab → `Total owed to you: $16.37` and
`Total you owe: $83.38` → turn on `Hide settled members` → Balances tab → the
`Marco Silva` row is gone → Settings tab → Balances tab → still gone.
