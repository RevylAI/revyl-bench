# Step 01 — tab shell + catalog + seed data

Scaffold the app with bottom tab navigation, the catalog rendered from seed data, and
the seed data from the root contract checked in. No movement, stocktake, reorder or
settings UI yet beyond the screen shells.

## Requirements

1. The app launches without a red screen or runtime error dialog.
2. The bottom tab bar shows exactly five tabs labeled `Items`, `Movements`, `Stocktake`,
   `Reorder`, `Settings`; `Items` is the initial tab.
3. Each tab screen renders without crashing and shows its heading text — `Items`,
   `Movements`, `Stocktake`, `Reorder`, `Settings` respectively. (These headings are
   permanent: they must still be present when the real UI arrives in steps 02/03,
   because every submission is graded against the full suite.) Any placeholder body
   content on the other four tabs is your choice and is not asserted.
4. The Items tab shows the catalog in **catalog order** (categories alphabetically,
   items alphabetically within each): a header per category showing at least the
   category name — `Fasteners`, `Packaging`, `Safety` — and one row per item showing at
   least the item name, all 12 items. The catalog is longer than one screen and scrolls.
   The full row format (`On hand`, the `Low` marker) arrives in step 02 and is not
   asserted yet.
5. The seed data from the root contract (the 12-item catalog table, the 11-entry seed
   ledger, the count sheet and the restock buffer) is checked into the repo as typed
   modules — integer units and cents, no clock/random calls.

## Observable outcome the hidden test checks

Launch → tab bar shows `Items` / `Movements` / `Stocktake` / `Reorder` / `Settings`
with the Items catalog listing the category headers and item names → tapping each other
tab renders its screen with its heading, no crash at any point.
