# Step 01 — tab shell + seed data

Scaffold the app with bottom tab navigation and the synthetic seed data from the root
contract. No real table UI yet beyond the screen shells.

## Requirements

1. The app launches without a red screen or runtime error dialog.
2. The bottom tab bar shows exactly three tabs labeled `Table`, `Fixtures`, `Settings`;
   `Table` is the initial tab.
3. Each tab screen renders without crashing and shows its heading text — `Table`,
   `Fixtures`, `Settings` respectively. (These headings are permanent: they must still be
   present when the real UI arrives in steps 02/03, because every submission is graded
   against the full suite.) Any placeholder body content is your choice and is not
   asserted.
4. The seed data from the root contract (the ten teams and the twenty results, with integer
   goal counts) is checked into the repo as typed modules — no clock/random calls, and no
   standings stored: the table is computed in step 02.

## Observable outcome the hidden test checks

Launch → tab bar shows `Table` / `Fixtures` / `Settings` → tapping each tab renders its
screen with its heading, no crash at any point.
