# Step 02 — group list, expense list, composer, pairwise balances

Implement the Groups tab, the pushed group screen, and the Balances tab per the root
contract's seed data, ground rules, and pinned UI text.

## Requirements

1. **Group list** (Groups tab): one row per seeded group, in seed order, showing the
   group `name`, the text `<n> members`, and the net line for that group computed from
   that group's expenses **and that group's settlements** (`Tahoe Trip` → `You owe
   $193.63`, `Lunch Crew` → `You are owed $3.74`, `Apartment` → `You are owed $99.99`,
   `Ski Weekend` → `You are owed $84.33`). Tapping a row pushes that group's screen.

2. **Group screen** (pushed, header title = the group's `name`, native back button): the
   group's expenses in ascending `tsOrder`, each row showing the `description`, the
   amount, `<payer displayName> paid` (or `You paid`), and the secondary text
   `you lent $<amount>` / `you borrowed $<amount>` per the root contract's table. A
   composer is pinned at the bottom: a description input (placeholder
   `What was it for?`, verbatim input — no auto-capitalization/auto-correct), an amount
   input (placeholder `0.00`), and an `Add` button.

3. **Add** is one-shot (debounced) and idempotent: a rapid double-tap adds exactly one
   expense. Adding appends an expense to that group paid by `You`, with
   `tsOrder = max + 1` (so it appears at the bottom, exactly once), split equally among
   all the group's members by the root contract's split rule, and clears both inputs.
   `Add` is disabled while either input is empty.

4. **Balances tab**: a summary line **pinned at the top and visible while the rows scroll**,
   then one row per other member in seed order showing the **pairwise** balance between you
   and that member across every group (ground rule 4). With the seed alone this is
   `Priya Nair owes you $16.37`, `Marco Silva owes you $61.44`,
   `You owe Elena Vasquez $83.38`, and the summary `Total: you owe $5.57`. The `Balances`
   tab item carries a numeric badge with the count of non-zero balances — `3` at the seed.

6. **The `Ski Weekend` group does not fit on one screen.** Its twelve expenses scroll. The
   composer stays usable with the keyboard up, and a newly added expense is brought into
   view without the user scrolling manually (ground rule 12).

5. Added expenses persist across navigation (store state; no backend needed), and they
   update both the group's Groups tab net line and the affected Balances rows.

## Observable outcome the hidden test checks

Launch → Groups lists the four groups with their `<n> members` and net lines → tap
`Ski Weekend` → the list scrolls; `Lift passes` reads `you borrowed $156.00` and, after
scrolling down, `Hot tub fee` reads `you borrowed $13.13` → type `Boba` and `26.00` →
`Add` → the new row is visible without manual scrolling, reading `You paid` and
`you lent $19.50` → back → Balances tab shows the badge `3`, the pinned summary, and
`Marco Silva owes you $67.94`.
