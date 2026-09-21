# Step 01 — tab shell + seed data

Scaffold the app with bottom tab navigation and the synthetic seed data from the root
contract. No real ride-booking UI yet beyond the screen shells.

## Requirements

1. The app launches without a red screen or runtime error dialog.
2. The bottom tab bar shows exactly three tabs labeled `Search`, `Fare`, `Trip`;
   `Search` is the initial tab.
3. Each tab screen renders without crashing and shows its heading text — `Search`,
   `Fare`, `Trip` respectively. (These headings are permanent: they must still be
   present when the real UI arrives in steps 02/03, because every submission is
   graded against the full suite.)
4. The seed data from the root contract (destinations, fare tiers, assigned driver,
   trip statuses) is checked into the repo as typed modules — integer cents, fixed
   integer ETAs, fixed status order, no clock/random/location calls.

## Observable outcome the hidden test checks

Launch → tab bar shows `Search` / `Fare` / `Trip` → tapping each tab renders its
screen with its heading, no crash at any point.
