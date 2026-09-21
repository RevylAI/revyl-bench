# Step 01 — tab shell + seed data

Scaffold the app with bottom tab navigation and the synthetic seed data from the root
contract. No real finance UI yet beyond the screen shells.

## Requirements

1. The app launches without a red screen or runtime error dialog.
2. The bottom tab bar shows exactly three tabs labeled `Accounts`, `Budget`,
   `Insights`; `Accounts` is the initial tab.
3. Each tab screen renders without crashing and shows its heading text —
   `Accounts`, `Budget`, `Insights` respectively. (These headings are permanent:
   they must still be present when the real UI arrives in steps 02/03, because every
   submission is graded against the full suite.)
4. The seed data from the root contract (accounts, categories, budgets, transactions,
   weekly totals) is checked into the repo as typed modules — integer cents, fixed
   `dateLabel`/`weekLabel` strings, integer `tsOrder` sort keys, no clock calls.

## Observable outcome the hidden test checks

Launch → tab bar shows `Accounts` / `Budget` / `Insights` → tapping each tab renders
its screen with its heading, no crash at any point.
