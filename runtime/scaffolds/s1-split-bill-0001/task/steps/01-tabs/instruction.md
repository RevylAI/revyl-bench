# Step 01 — tab shell + seed data

Scaffold the app with bottom tab navigation and the synthetic seed data from the root
contract. No real expense UI yet beyond the screen shells.

## Requirements

1. The app launches without a red screen or runtime error dialog.
2. The bottom tab bar shows exactly three tabs labeled `Groups`, `Balances`,
   `Settings`; `Groups` is the initial tab.
3. Each tab screen renders without crashing and shows its heading text — `Groups`,
   `Balances`, `Settings` respectively. (These headings are permanent: they must still
   be present when the real UI arrives in steps 02/03, because every submission is
   graded against the full suite.) Any placeholder body content is your choice and is
   not asserted.
4. The seed data from the root contract (members, groups with their ordered member
   lists, expenses with integer cent amounts and integer `tsOrder`, and the seeded
   settlement) is checked into the repo as typed modules — integer cents, integer sort
   keys, no clock/random calls.

## Observable outcome the hidden test checks

Launch → tab bar shows `Groups` / `Balances` / `Settings` → tapping each tab renders
its screen with its heading, no crash at any point.
