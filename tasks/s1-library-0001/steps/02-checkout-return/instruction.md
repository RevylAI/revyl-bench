# Step 02 — fines and allowances, the return flow, and the checkout flow

Implement the ledger derivations and both desk flows per the root contract: per-loan
overdue days and fines with the cap, per-member allowances and `Fines owed`, the member
detail screen, returns from the Loans tab, and checkouts from a member detail —
including the at-limit block.

## Requirements

1. **Ledger status lines** (Loans tab, ground rules 5–7): every `Out` entry carries
   `Out Day <a>, due Day <b>` and either `Overdue <k> days, fine $<x>` or
   `Not overdue`; every `Returned` entry carries `Returned Day <r>, on time` or
   `Returned Day <r>, <k> days late, fine $<x>`. At the seed the `Out` section is
   topped by `A Field Guide to Nowhere`, `Priya Raman` with
   `Overdue 12 days, fine $4.00` (the cap), and `Winter Arithmetic`, `Elif Kaya` reads
   `Overdue 11 days, fine $3.85` (under it).

2. **Members tab rows** gain `Loans: <out> of <limit>` and `Fines owed: $<x>` — at the
   seed `Marcus Webb` is `Loans: 3 of 3` with `Fines owed: $2.80` and `Priya Raman` is
   `Loans: 1 of 2` with `Fines owed: $8.00` (her two past returns do not count against
   the limit).

3. **Member detail** (pushed, header title = the member name, native back button): the
   pinned lines `Tier: <tier>`, `Loan limit: <k> books`, `Loan period: <d> days`,
   `Loans out: <out> of <limit>`, `Fines owed: $<x>`; a `Books out` section (due day
   ascending, each loan as `<title>, due Day <n>` plus its status line); and a
   `Check out` section listing every title with at least one available copy in catalog
   order, each with a `Check out` control (accessibility label `Check out, <title>`).
   For a member at their limit the section shows exactly
   `At loan limit: <k> of <k> books out. Return a book first.` and no controls —
   `Marcus Webb` at the seed.

4. **Return** (Loans tab, one-shot, no confirmation): each `Out` entry has a `Return`
   control (accessibility label `Return, <title>, <member>`). Returning happens on
   Day 40: the loan moves to the `Returned` section with its charge fixed at return
   time, the section counts move, availability and the member's allowance and
   `Fines owed` recompute immediately. Returning `A Field Guide to Nowhere` for
   `Priya Raman` yields `Out (8)`, `Returned (9)` and a row reading
   `Returned Day 40, 12 days late, fine $4.00`; her row drops to `Loans: 0 of 2`.

5. **Check out** (member detail, one-shot, no confirmation): tapping `Check out` creates
   a loan out Day 40, due `40 + the member's tier period`, visible in `Books out`
   without scrolling. Checking out `Salt and Circuit` for `Theo Alvarez` creates
   `Salt and Circuit, due Day 54` with `Not overdue`, moves him to `Loans out: 3 of 3`,
   and his `Check out` section is replaced by
   `At loan limit: 3 of 3 books out. Return a book first.`. `Salt and Circuit` drops to
   `0 of 2 available` on the Catalog tab and leaves every `Check out` list.

6. All derived numbers stay consistent across tabs after every action (ground rule 11),
   and the selection of screens from step 01 keeps rendering — headings, catalog rows,
   and both ledger sections.

## Observable outcome the hidden test checks

Launch → Loans tab shows the seed status lines including the `$4.00`/`$3.85` cap pair →
Members tab shows `Marcus Webb` `Loans: 3 of 3` and `Priya Raman` `Loans: 1 of 2` →
Marcus's detail shows `Fines owed: $2.80` and the at-limit message with no `Check out`
controls → back → Loans tab → return `A Field Guide to Nowhere` → `Out (8)` with
`Winter Arithmetic`, `Elif Kaya` now on top → Theo Alvarez's detail → check out
`Salt and Circuit` → `Loans out: 3 of 3`, the new loan due Day 54, the at-limit
message → Catalog shows `Salt and Circuit` `0 of 2 available` and
`A Field Guide to Nowhere` `2 of 2 available`.
