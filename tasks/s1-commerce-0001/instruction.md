# Marlow Goods — build a mobile shopping app

You are a coding agent building a fresh iOS mobile app from the provided Expo scaffold
(Expo SDK 56, Expo Router with NativeTabs, TypeScript). The product is a small
shopping app: a product grid with title search, a product detail screen, a cart with
per-row quantity steppers and a subtotal, a checkout summary with subtotal / tax /
total, and an order-confirmation screen with a generated order ID.

The work is split into three steps (see `steps/01-tabs`, `steps/02-grid-search-detail`,
`steps/03-cart-checkout-confirmation`, each with its own `instruction.md`), followed by
a final end-to-end acceptance run. Complete the steps in order.

## How your work is verified

After each submission, **hidden device tests** run your app on a real cloud iOS
simulator and grade journeys with screenshot validations. You never see the test
definitions. Every submission is graded against the **full suite** — all step tests
plus the final e2e — so a change that breaks an earlier step's behavior is caught
immediately. If a run fails, you receive the run report (failed-criteria text,
per-step verdicts, screenshots); fix your code and resubmit. Every requirement the
tests check is stated in this contract and the step contracts; nothing hidden is
required beyond what is written here.

The tests run a **baked-JS Release build** of your app, built by the benchmark from the
source you submit (`./submit.sh`) — you never build or upload a binary yourself. Code
changes are only visible to the verifier after a new submission. Iterate cheaply in the
dev-client session first; submit when you believe the JS is finished.

## Ground rules (binding — the tests depend on these)

1. **Whole-dollar prices; `$` + plain number at render.** Product prices are whole US
   dollars stored as numbers. Every money value renders as `$` immediately followed by
   the number exactly as JavaScript prints it — no thousands separator, no forced
   decimals: 24 → `$24`, 48 → `$48`, 3.84 → `$3.84`, 51.84 → `$51.84`, 0 → `$0`.
   Tax and total are rounded to cents: `tax = Math.round(subtotal × 0.08 × 100) / 100`,
   `total = Math.round((subtotal + tax) × 100) / 100`. (Do not reformat to two fixed
   decimals — `$24.00` is wrong.)
2. **Deterministic data — no clocks, no randomness.** No `Date.now()`, `new Date()`,
   `Math.random()`, or network calls anywhere in app code. The order ID is a
   per-launch counter, not a timestamp or random string (format below). Every value on
   screen must be computable from this contract alone.
3. **One unit per tap, with visible feedback.** `Add to cart`, `+` and `−` are plain
   controls: each tap changes the quantity by exactly one (Add to cart on the same
   product merges into its existing cart row — it never creates a second row).
   Tapping `Add to cart` must give visible feedback (the fixture flips the button label
   to `Added to cart` for about 1.5 s); the tests tap it exactly once and then assert
   that the row quantity reads `1`, so silently swallowed or doubled taps both fail.
4. **Textual state.** Quantities, subtotals, tax, total, item count and the order ID are
   exact text strings (pinned below) — never encoded only in colors or icons.
5. **State survives tab navigation.** The cart persists when the user navigates between
   tabs and into/out of the product detail and confirmation screens (module-level
   store state is sufficient; no backend, no disk persistence — a fresh install starts
   with an empty cart and the order counter at 0).
6. **Special characters.** Where this contract shows ` — ` (space, em dash U+2014,
   space), ` × ` (multiplication sign U+00D7) or `−` (minus sign U+2212), render
   exactly that character.

## Seed data (exact values — copy these verbatim)

Products (`id`, `title`, `price` in whole dollars, `description`), in this order —
this is also the grid order:

| id | title | price | renders as | description |
|---|---|---|---|---|
| p_001 | Cobalt Travel Mug | 24 | $24 | Vacuum-sealed 16oz mug with a matte cobalt finish and a leak-resistant lid. |
| p_002 | Linen Throw Blanket | 58 | $58 | Lightweight stonewashed linen throw, 50x70 inches, with hand-finished edges. |
| p_003 | Cedar Pocket Notebook | 9 | $9 | Pack of three cedar-bound A6 notebooks with 96 dot-grid pages each. |
| p_004 | Brass Desk Lamp | 142 | $142 | Adjustable brass arm with a dimmable warm-white LED head and a weighted base. |
| p_005 | Slate Pour-Over Kettle | 68 | $68 | Gooseneck stainless kettle with a slate matte finish and a 1.0L capacity. |
| p_006 | Walnut Cutting Board | 46 | $46 | End-grain walnut cutting board, 12x18 inches, with finger grooves on both ends. |
| p_007 | Indigo Canvas Tote | 32 | $32 | Heavyweight 18oz canvas tote with reinforced straps and an interior pocket. |
| p_008 | Terracotta Planter Set | 38 | $38 | Set of three glazed terracotta planters in matching cream with drainage trays. |

Tax rate: `0.08` (rendered in the checkout label as `Tax (8%)`).

Order ID: `ORD-` followed by a six-digit zero-padded per-launch sequence number —
the first order placed after launch is `ORD-000001`, the next `ORD-000002`. The
counter never resets while the app is running (placing an order clears the cart but
not the counter); it starts at 0 on every fresh launch.

Defaults: empty cart; no order placed; search query empty (all products shown).

Derived values (the tests assert these exact strings — Cobalt Travel Mug is the
journey product):

- Search: case-insensitive substring match on the product **title** (`travel` →
  only Cobalt Travel Mug; empty query → all eight). No matches →
  `No products match your search.`
- One Cobalt Travel Mug in the cart: row quantity `1`, `$24 each`, line subtotal
  `$24`, cart `Subtotal` `$24`; checkout `Subtotal` `$24`, `Tax (8%)` `$1.92`,
  `Total` `$25.92`.
- Two Cobalt Travel Mugs (after one `+`): quantity `2`, line subtotal `$48`, cart
  `Subtotal` `$48`; checkout line `Cobalt Travel Mug × 2` `$48`, `Subtotal` `$48`,
  `Tax (8%)` `$3.84` (round(48 × 0.08 × 100)/100 = 3.84), `Total` `$51.84`.
- Placing that order: confirmation shows `Order ID` `ORD-000001`, `Items` `2`,
  `Total charged` `$51.84`; the cart is empty afterwards.
- `−` on a row with quantity 1 removes the row; an empty cart shows `Your cart is
  empty.` and checkout shows `$0` / `$0` / `$0` with `Place order` disabled.

## Pinned UI text (tests match these exactly — render them verbatim)

- Tab bar labels: `Home`, `Cart`, `Checkout` (`Home` is the initial tab). Screen
  headings: the Home tab's heading is **`Shop`** (not "Home"); the Cart tab's heading is
  `Cart`; the Checkout tab's heading is `Checkout`. Headings are visible in every state
  of the screen (empty and non-empty).
- Home: a text input with placeholder `Search products` above a two-column product grid;
  each card shows the product title and its price (`$24`, `$58`, …). The grid is compact
  enough that at least six cards are visible at once without scrolling (the reference
  layout shows all eight). Typing filters the grid live — no debounce — and the input
  has auto-capitalization and auto-correct disabled (`autoCapitalize="none"`,
  `autoCorrect={false}`) so `travel` is matched exactly as typed; clearing the input
  restores all eight cards.
- Product detail (a stack screen pushed over the tabs, with a back control at the
  top-left and the product title as the header title): the product title, its price
  (`$24`), its full description text (not truncated), and a button labeled
  `Add to cart` (label `Added to cart` briefly after a tap) — all four fit on one screen
  without scrolling. Tapping it does **not** navigate anywhere —
  the detail screen stays open; the user returns via the back control and opens the
  Cart tab themselves.
- Cart: heading `Cart`; when empty the text `Your cart is empty.`; otherwise one row per
  product showing the title, `$<price> each`, a stepper `−` `<qty>` `+`, and the line
  subtotal `$<price×qty>`; below the rows a `Subtotal` row with the cart subtotal.
- Checkout: heading `Checkout`; when empty `Your cart is empty. Add a product to start
  checkout.`; otherwise one line per product `<title> × <qty>` with its line subtotal;
  always a totals card with rows `Subtotal`, `Tax (8%)`, `Total`; and a `Place order`
  button (disabled while the cart is empty). Tapping `Place order` places the order,
  clears the cart, and opens the confirmation screen.
- Order confirmation (a stack screen; header title `Order confirmed`): heading
  `Order placed`, the line `Thanks — your order has been confirmed.`, and rows
  `Order ID` / `ORD-000001`, `Items` / `2`, `Total charged` / `$51.84` (values for the
  journey order). Optional: hiding the back control here.

## Final acceptance

The final e2e journey: launch → Home shows the `Search products` input and the eight
product cards → type `travel` → the grid shows only Cobalt Travel Mug → tap it → detail
shows `Cobalt Travel Mug`, `$24`, `Add to cart` → tap Add to cart once → back → Cart
tab → one row, quantity `1`, `$24`, subtotal `$24` → tap `+` once → quantity `2`,
`$48`, subtotal `$48` → Checkout tab → `Cobalt Travel Mug × 2`, `Subtotal` `$48`,
`Tax (8%)` `$3.84`, `Total` `$51.84` → tap Place order → confirmation with
`Order placed`, `Order ID` `ORD-000001`, `Items` `2`, `Total charged` `$51.84`. It must
complete without manual intervention.
