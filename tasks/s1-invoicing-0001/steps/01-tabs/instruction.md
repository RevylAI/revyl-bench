# Step 01 — tab shell + seed data

Scaffold the app with bottom tab navigation and the synthetic seed data from the root
contract. No real invoicing UI yet beyond the screen shells.

## Requirements

1. The app launches without a red screen or runtime error dialog.
2. The bottom tab bar shows exactly three tabs labeled `Clients`, `Invoices`,
   `Settings`; `Clients` is the initial tab.
3. Each tab screen renders without crashing and shows its heading text — `Clients`,
   `Invoices`, `Settings` respectively. (These headings are permanent: they must still
   be present when the real UI arrives in steps 02/03, because every submission is
   graded against the full suite.) Any placeholder body content is your choice and is
   not asserted.
4. The seed data from the root contract (clients, invoices with their lines in order,
   integer cent unit prices, per-line tax rates, invoice-level discount percentages,
   `YYYY-MM-DD` date strings, the sent flag, and the seeded payments with integer
   `tsOrder`) is checked into the repo as typed modules — integer cents, integer sort
   keys, no clock/random calls, and the fixed today `2026-03-14` as a constant.

## Observable outcome the hidden test checks

Launch → tab bar shows `Clients` / `Invoices` / `Settings` → tapping each tab renders
its screen with its heading, no crash at any point.
