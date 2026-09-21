# Step 01 — tab shell + catalog + the seeded till

Scaffold the app with bottom tab navigation, the catalog rendered from seed data, and
the opening drawer rendered on the Till tab. No sale, refund, reconciliation or report
mechanics yet beyond the screen shells — and no audit lines yet (the first audited
actions arrive in step 02).

## Requirements

1. The app launches without a red screen or runtime error dialog.
2. The bottom tab bar shows exactly four tabs labeled `Sale`, `Refunds`, `Till`,
   `Report`; `Sale` is the initial tab.
3. Each tab screen renders without crashing and shows its heading text — `Sale`,
   `Refunds`, `Till`, `Report` respectively. (These headings are permanent: they must
   still be present when the real UI arrives in steps 02/03, because every submission
   is graded against the full suite.) Any other body content on the Refunds and Report
   tabs is your choice at this step and is not asserted.
4. The Sale tab shows the catalog in **catalog order** (categories alphabetically,
   products alphabetically within each): a header per category — `Drinks`, `Food`,
   `Merch` — and one row per product showing the product name and its price
   (`Americano` with `$3.20`, `Tote bag` with `$12.50`), all 8 products. The sale
   panel, tender input and their mechanics arrive in step 02 and are not asserted yet.
5. The Till tab shows the line `Opening float: $84.00` and the `Drawer at open` block
   with the seven float lines from the root contract (`1 x $20` through `100 x 1c`).
   The `Reconciliation` figures and the `Transactions` list arrive in steps 02/03.
6. The seed data from the root contract (the 8-product catalog, the drawer float, the
   4 seed transactions and the reason codes) is checked into the repo as typed modules
   — integer cents, no clock/random calls.

## Observable outcome the hidden test checks

Launch → tab bar shows `Sale` / `Refunds` / `Till` / `Report` with the Sale catalog
listing the category headers, product names and prices → the Till tab shows
`Opening float: $84.00` and the drawer lines → tapping each other tab renders its
screen with its heading, no crash at any point.
