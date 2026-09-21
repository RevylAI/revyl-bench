# Step 02 — product grid, title search, product detail

Implement the Home tab and the product detail route per the root contract's seed
data, price format, and pinned UI text.

## Requirements

1. **Product grid** on the Home tab under the `Shop` heading: a two-column grid of
   all eight seeded products in seed order, each card showing the product title and
   its price rendered as `$<price>` (`$24`, `$58`, `$9`, `$142`, `$68`, `$46`, `$32`,
   `$38`). Keep it compact: at least six cards visible without scrolling.
2. **Search input** above the grid with placeholder `Search products`, auto-capitalization
   and auto-correct disabled. Typing filters the grid live (no debounce) by
   case-insensitive substring match on the product title (`travel` →
   only Cobalt Travel Mug; `a` → every title containing an "a"). Clearing the input
   restores all eight cards. When nothing matches show `No products match your
   search.`
3. **Product detail route**: tapping a card pushes a detail screen (stack screen over
   the tabs, back control at the top-left, header title = product title) showing the
   product title, its price (`$24` for Cobalt Travel Mug), and its full description
   text verbatim from the seed data — title, price, description and the `Add to cart`
   button (step 03) all on one screen without scrolling. (The `Add to cart` button arrives in step 03; adding it
   now is fine.)
4. Search state may reset when leaving the tab; it is not asserted across navigation.

## Observable outcome the hidden test checks

Launch → Home shows the `Search products` input and a grid of at least six product
cards including Cobalt Travel Mug, Linen Throw Blanket, Cedar Pocket Notebook (each
with its price) → type `travel` → the grid shows only the Cobalt Travel Mug card
(`$24`) → tap it → the detail screen shows `Cobalt Travel Mug`, `$24`, and the text
`Vacuum-sealed 16oz mug with a matte cobalt finish and a leak-resistant lid.`
