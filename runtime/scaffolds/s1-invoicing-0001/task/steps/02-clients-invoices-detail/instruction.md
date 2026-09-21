# Step 02 — client list, invoice list with filters, invoice screen

Implement the Clients tab, the Invoices tab with its filter row, and the pushed invoice
screen per the root contract's seed data, ground rules, and pinned UI text.

## Requirements

1. **Client list** (Clients tab): one row per seeded client, in seed order, showing the
   client `name`, the outstanding line and the overdue line computed per ground rule 6
   (`Harbor Books` → `Outstanding $1,361.83` and `2 overdue`, `Northwind Studio` →
   `Outstanding $2,488.14` and `1 overdue`, `Pinecrest Dental` → `Outstanding $2,155.29`
   and `0 overdue`, `Lumen Analytics` → `Outstanding $3,480.92` and `1 overdue`,
   `Solstice Cafe` → `Outstanding $1,179.24` and `1 overdue`). Drafts are excluded and a
   credit contributes nothing.

2. **Invoice list** (Invoices tab): a filter row with `All`, `Unpaid`, `Overdue`, `Paid`,
   `Drafts`, pinned at the top and visible while the list scrolls; `All` is selected on
   launch. Below it, one row per matching invoice in ascending number showing the number,
   the client name, `Due <due>`, the total and the derived status word (ground rule 5).
   With the seed, `All` lists all fourteen (`INV-1001` `Overdue` `$1,830.60` first,
   `INV-1014` `Sent` `$930.37` last, reached by scrolling), `Overdue` lists exactly
   `INV-1001`, `INV-1002`, `INV-1004`, `INV-1005`, `INV-1006`, and `Paid` lists
   `INV-1003` and `INV-1007`. Tapping a row pushes the invoice screen; back returns with
   the same filter still selected.

3. **Invoice screen** (pushed, header title = the invoice number, native back button): the
   client name, `Issued <issued>`, `Due <due>`, the status word; one row per line with the
   `description`, `<qty> × $<unitPrice>` and the line net; then the totals block
   `Subtotal`, `Discount (<pct>%)`, `Tax`, `Total`, `Paid` and the balance line, all per
   ground rules 2–3 and the derived table. From the seed, `INV-1004` shows
   `Subtotal $3,030.60`, `Discount (15%) $454.60`, `Tax $198.93`, `Total $2,774.93`,
   `Paid $0.00`, `Balance due $2,774.93`; `INV-1003` shows `Total $1,485.95`,
   `Paid $1,500.00`, `Credit $14.05`; `INV-1007` shows `Paid in full`.

4. **The `Invoices` tab item carries a badge** with the count of `Overdue` invoices — `5`
   at the seed (ground rule 14).

5. **The invoice list does not fit on one screen.** Its fourteen rows scroll under the
   pinned filter row (ground rule 13). A long invoice screen (`INV-1008` has four lines)
   also scrolls; its totals block must be reachable by scrolling.

## Observable outcome the hidden test checks

Launch → Clients lists the five clients with their outstanding and overdue lines →
Invoices tab → the badge reads `5`; `INV-1001` reads `Overdue` and `$1,830.60` → scroll
to the bottom → `INV-1014` reads `Sent` and `$930.37` → tap `Overdue` → exactly five rows
(`INV-1001`, `INV-1002`, `INV-1004`, `INV-1005`, `INV-1006`), the filter row still visible
→ tap `INV-1004` → `Subtotal $3,030.60`, `Discount (15%) $454.60`, `Tax $198.93`,
`Total $2,774.93`, `Balance due $2,774.93` → back → `Overdue` is still selected → tap
`Paid` → `INV-1003` and `INV-1007` → tap `INV-1003` → `Paid $1,500.00` and
`Credit $14.05`.
