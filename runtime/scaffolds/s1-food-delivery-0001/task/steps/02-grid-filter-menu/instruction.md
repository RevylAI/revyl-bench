# Step 02 — restaurant grid, live cuisine filter, restaurant menu screen

Implement the Restaurants tab and the restaurant menu route per the root contract's
seed data, pinned formats, and pinned UI text.

## Requirements

1. **Restaurant grid**: below the `Restaurants` heading and the filter input, a grid of
   the six seeded restaurants in seed order; each card shows the restaurant name, its
   cuisine, and `<deliveryEtaMinutes> min` (Nonna Lucia / Italian / `28 min`, …).
2. **Cuisine filter**: a text input with placeholder
   `Filter by cuisine (e.g. ital, mex, jap)`, with auto-capitalization and
   auto-correct disabled (typed text is taken literally). Filtering is a case-insensitive
   substring match on `cuisine`, applied live as the user types (no submit action):
   `ital` → exactly Nonna Lucia and Pasta Vesuvio; `mex` → exactly Casa Verde and
   Taqueria del Sol; no match → `No restaurants match your filter.`; empty → all six.
3. **Menu screen**: tapping a restaurant card opens a pushed screen with a back control
   at the top-left of the header (returns to the grid; the tab bar need not be visible
   on the menu screen). It shows the restaurant name as the title, the line
   `<cuisine> · <eta> min` (`Italian · 28 min`), and one row per menu item in seed
   order with the item name and its price (`Margherita Pizza` `$14.99`,
   `Spaghetti Carbonara` `$16.99`, `Tiramisu` `$8.99`). The `Add to cart` button per
   row may be present already but is only required by step 03.
4. The filter text and the grid state survive opening a menu and coming back
   (navigation must not reset the Restaurants tab).

## Observable outcome the hidden test checks

Launch → grid shows the restaurant cards (Nonna Lucia, Pasta Vesuvio, Casa Verde, …) →
type `ital` in the filter → only Nonna Lucia and Pasta Vesuvio remain → tap Nonna Lucia
→ menu screen shows `Nonna Lucia`, `Italian`, `28 min`, and the three items with their
prices `$14.99`, `$16.99`, `$8.99`.
