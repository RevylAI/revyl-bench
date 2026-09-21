# Step 01 — tab shell + product seed data

Scaffold the app with bottom tab navigation and the synthetic product seed data from
the root contract. No real shopping UI yet beyond the screen shells.

## Requirements

1. The app launches without a red screen or runtime error dialog.
2. The bottom tab bar shows exactly three tabs labeled `Home`, `Cart`, `Checkout`;
   `Home` is the initial tab.
3. Each tab screen renders without crashing and shows its heading text — `Shop` on the
   Home tab, `Cart` on the Cart tab, `Checkout` on the Checkout tab. (These headings
   are permanent: they must still be present when the real UI arrives in steps 02/03,
   in every state of the screen — empty cart included — because every submission is
   graded against the full suite.) Any other placeholder body content is your choice
   and is not asserted.
4. The product seed data from the root contract (eight products with `id`, `title`,
   whole-dollar `price`, `description`, in the given order) is checked into the repo as
   a typed module, plus the tax rate constant `0.08` — no clock/random calls.

## Observable outcome the hidden test checks

Launch → tab bar shows `Home` / `Cart` / `Checkout` → tapping each tab renders its
screen with its heading (`Shop`, `Cart`, `Checkout`), no crash at any point.
