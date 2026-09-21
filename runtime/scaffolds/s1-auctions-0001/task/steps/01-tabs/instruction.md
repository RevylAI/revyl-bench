# Step 01 — tab shell + seed data

Scaffold the app with bottom tab navigation and the synthetic seed data from the root
contract. No real auction UI yet beyond the screen shells.

## Requirements

1. The app launches without a red screen or runtime error dialog.
2. The bottom tab bar shows exactly three tabs labeled `Lots`, `My Bids`, `Settings`;
   `Lots` is the initial tab.
3. Each tab screen renders without crashing and shows its heading text — `Lots`,
   `My Bids`, `Settings` respectively. (These headings are permanent: they must still be
   present when the real UI arrives in steps 02/03, because every submission is graded
   against the full suite.) Any placeholder body content is your choice and is not
   asserted.
4. The seed data from the root contract (bidders, lots with integer cent starting and
   reserve prices and integer `closesAt`, and bids with integer cent maxes and integer
   `bidOrder`) is checked into the repo as typed modules — integer cents, integer sort
   keys, no clock/random calls.

## Observable outcome the hidden test checks

Launch → tab bar shows `Lots` / `My Bids` / `Settings` → tapping each tab renders its
screen with its heading, no crash at any point.
