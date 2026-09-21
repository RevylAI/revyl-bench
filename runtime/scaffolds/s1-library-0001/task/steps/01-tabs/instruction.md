# Step 01 — tab shell + catalog, members and ledger from the seed

Scaffold the app with bottom tab navigation and render the seed data from the root
contract on the Catalog, Members and Loans tabs. No flows yet — the Desk and Settings
tabs need only their headings.

## Requirements

1. The app launches without a red screen or runtime error dialog.
2. The bottom tab bar shows exactly five tabs labeled `Catalog`, `Members`, `Loans`,
   `Desk`, `Settings`; `Catalog` is the initial tab.
3. Each tab screen renders without crashing and shows its heading text — `Catalog`,
   `Members`, `Loans`, `Desk`, `Settings` respectively. (These headings are permanent:
   they must still be present when the real UI arrives in steps 02/03, because every
   submission is graded against the full suite.) The Desk and Settings body content is
   your choice at this step and is not asserted.
4. **Catalog tab**: one row per title in seed order showing the title name and
   `<available> of <copies> available`, with availability derived from the seed ledger:
   `The Glass Harbor` `1 of 3 available`, `Salt and Circuit` `1 of 2 available`,
   `A Field Guide to Nowhere` `1 of 2 available`, `Paper Mountains` `1 of 3 available`,
   `Winter Arithmetic` `0 of 2 available`, `The Lighthouse Codex` `1 of 2 available`.
5. **Members tab**: one row per member in seed order showing the member name and tier —
   `Maya Chen` (`Plus`), `Marcus Webb` (`Standard`), `Priya Raman` (`Basic`),
   `Theo Alvarez` (`Standard`), `Elif Kaya` (`Plus`). The `Loans:` and `Fines owed:`
   lines arrive with step 02's derivations and are not asserted at this step, but
   rendering them already is fine.
6. **Loans tab**: the seed ledger renders as a section headed `Out (9)` and a section
   headed `Returned (8)`, each entry showing at least `<title>, <member>` in the orders
   pinned by ground rule 15. Status lines arrive with step 02 and are not asserted at
   this step.
7. The seed data from the root contract (titles with copies, members with tiers, and
   all seventeen loans with their day numbers) is checked into the repo as typed
   modules — integer days, integer cents, no clock/random calls.

## Observable outcome the hidden test checks

Launch → tab bar shows `Catalog` / `Members` / `Loans` / `Desk` / `Settings`, Catalog
listing the six titles with their availability → Members tab lists the five members →
Loans tab shows `Out (9)` and `Returned (8)` → Desk and Settings each render their
heading, no crash at any point.
