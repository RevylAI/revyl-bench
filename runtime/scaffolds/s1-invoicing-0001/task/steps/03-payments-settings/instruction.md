# Step 03 — record payment, settings totals, hide paid

Implement the payment composer on the invoice screen, and the Settings tab, per the root
contract.

## Requirements

1. **Record payment**: on every **sent** invoice's screen, a composer is pinned at the
   bottom with an amount input (placeholder `0.00`) and a button labelled
   `Record payment`. A draft shows the text `Drafts cannot receive payments` and no
   composer. Tapping the button is one-shot (debounced) and applies immediately with no
   dialog (ground rule 8): it appends a payment of the typed amount to that invoice with
   `tsOrder = max + 1`, clears the input, and re-derives everything — the `Paid` line,
   the balance line, the status word, the invoice list row, the client's outstanding and
   overdue lines, the Settings totals and the tab badge. An amount larger than the balance
   is accepted and renders as `Credit $<amount>`.

2. **Worked cases the tests use** (both from a fresh install): recording `600.00` on
   `INV-1005` makes it `Paid` with `Paid $1,000.00` and `Credit $74.10`; `Solstice Cafe`
   becomes `Outstanding $653.34` and `0 overdue`; the badge reads `4`; Settings reads
   `Total outstanding: $10,139.52`, `Total collected: $7,213.35`, `Overdue invoices: 4`.
   Recording `300.00` on `INV-1009` keeps it `Partial` with `Paid $800.00` and
   `Balance due $405.99`; `Lumen Analytics` becomes `Outstanding $3,180.92`.

3. **After recording**, the `Paid` line and the balance line are visible without the user
   scrolling manually, and while the amount input is focused with the keyboard up, the
   input and the `Record payment` button remain visible and tappable (ground rule 13).

4. **Settings tab**: a `Totals` block with `Total outstanding: $<amount>` (the sum of the
   clients' outstanding figures), `Total collected: $<amount>` (the sum of every payment on
   a sent invoice) and `Overdue invoices: <n>` — with the seed alone,
   `Total outstanding: $10,665.42`, `Total collected: $6,613.35`, `Overdue invoices: 5`.
   A `Display` section holds one row labelled `Hide paid invoices` with a toggle switch;
   turning it on makes the Invoices tab's `All` filter omit every `Paid` invoice (the
   `Paid` filter still lists them) and changes nothing else anywhere.

5. Payments and the `Hide paid invoices` switch persist across navigation: leaving the
   tab and returning shows the same rows, the same totals, and the same switch position
   (store state; no backend, no disk persistence).

## Observable outcome the hidden test checks

Invoices tab → tap `INV-1005` → `Overdue`, `Paid $400.00`, `Balance due $525.90` → type
`600.00` into the amount input → tap `Record payment` → `Paid $1,000.00` and
`Credit $74.10` visible without scrolling, status `Paid` → back → the badge reads `4` →
Clients tab → `Solstice Cafe` reads `Outstanding $653.34` and `0 overdue` → Settings tab
→ `Total outstanding: $10,139.52`, `Total collected: $7,213.35`, `Overdue invoices: 4` →
turn on `Hide paid invoices` → Invoices tab → `All` no longer lists `INV-1005` and still
lists `INV-1004` and `INV-1006` → tap `Paid` → `INV-1003`, `INV-1005`, `INV-1007` →
Settings tab → Invoices tab → still on `Paid`, still three rows.
