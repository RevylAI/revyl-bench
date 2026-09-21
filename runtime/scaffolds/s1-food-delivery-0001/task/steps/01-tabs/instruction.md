# Step 01 — tab shell + seed data

Scaffold the app with bottom tab navigation and the synthetic seed data from the root
contract. No real food-delivery UI yet beyond the screen shells.

## Requirements

1. The app launches without a red screen or runtime error dialog.
2. The bottom tab bar shows exactly three tabs labeled `Restaurants`, `Cart`,
   `Checkout`; `Restaurants` is the initial tab.
3. Each tab screen renders without crashing and shows its heading text —
   `Restaurants`, `Cart`, `Checkout` respectively. (These headings are permanent: they
   must still be present when the real UI arrives in steps 02/03 — including in the
   empty-cart and empty-checkout states — because every submission is graded against
   the full suite.) Any other placeholder body content is your choice and is not
   asserted.
4. The seed data from the root contract (restaurants, per-restaurant menus, delivery
   addresses) is checked into the repo as typed modules — integer cents, fixed
   integer ETAs, no clock/random/location calls.

## Observable outcome the hidden test checks

Launch → tab bar shows `Restaurants` / `Cart` / `Checkout` → tapping each tab renders
its screen with its heading, no crash at any point.
