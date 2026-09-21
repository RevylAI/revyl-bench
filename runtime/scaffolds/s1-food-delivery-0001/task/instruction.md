# Forkly — build a mobile food-delivery app

You are a coding agent building a fresh iOS mobile app from the provided Expo scaffold
(Expo SDK 56, Expo Router with NativeTabs, TypeScript). The product is a food-delivery
app: a restaurant grid with a live cuisine filter, a per-restaurant menu, a
single-restaurant cart with per-row quantity steppers, and a checkout with a
delivery-address picker, delivery fee, tax, total, and an order-confirmation screen.

The work is split into three steps (see `steps/01-tabs`, `steps/02-grid-filter-menu`,
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

1. **Integer cents; dollars only at render.** Every price, fee, tax and total lives as
   integer cents and renders as `$<dollars>.<2-digit cents>` (1499 → `$14.99`,
   399 → `$3.99`, 240 → `$2.40`, 3637 → `$36.37`). No thousands separator is needed
   (no value here reaches $1,000).
2. **Deterministic data — no clocks, no randomness, no location.** No `Date.now()`,
   `new Date()`, `Math.random()`, or location APIs anywhere in app code. Restaurants,
   menus, addresses, the delivery fee, the tax rate and the delivery ETAs are fixed
   values from this contract; the order id is a per-launch counter (below). Every
   value on screen must be computable from this contract alone.
3. **Debounced one-shot mutation controls.** **Add to cart**, the cart `+` / `−`
   steppers, and **Place order** are one-shot: a rapid double-tap must have the same
   effect as a single tap (an item is added once; the quantity moves by exactly one
   per press; exactly one order is placed). Disabling the control briefly after press
   is one acceptable implementation. Mutation buttons must expose a visible disabled
   state when they cannot act (e.g. **Place order** before an address is chosen).
4. **Textual state summaries.** Quantities, line prices, the subtotal, delivery fee,
   tax, total, the selected address, and the order id are exact text strings (pinned
   below) — never encoded only in colors, badges, or highlight positions. (Highlights
   may accompany the text.)
5. **Cart state survives navigation.** The cart (its restaurant and rows) persists
   when the user navigates between tabs and into/out of restaurant menus
   (module-level/store state is sufficient; no backend, no disk persistence — a fresh
   launch starts with an empty cart).
6. **Single-restaurant cart.** A cart holds items from one restaurant at a time.
   Adding an item from a *different* restaurant while the cart is non-empty must show a
   confirmation dialog (pinned text below); **Cancel** leaves the existing cart
   untouched, **Clear & add** replaces the cart with the new item (quantity 1).
   Adding an item, and cancelling the cross-restaurant dialog, do not navigate away:
   the user stays on the menu screen and the row button updates in place.
7. **Middle-dot separator.** Where this contract shows ` · ` (space, middle dot
   U+00B7, space) render exactly that character.

## Seed data (exact values — copy these verbatim)

Restaurants (`id`, `name`, `cuisine`, `deliveryEtaMinutes`), in this order — this is
the grid order:

| id | name | cuisine | deliveryEtaMinutes |
|---|---|---|---|
| rest-001 | Nonna Lucia | Italian | 28 |
| rest-002 | Pasta Vesuvio | Italian | 35 |
| rest-003 | Casa Verde | Mexican | 22 |
| rest-004 | Taqueria del Sol | Mexican | 30 |
| rest-005 | Hanako Ramen | Japanese | 40 |
| rest-006 | Sakura Sushi Bar | Japanese | 32 |

Menus — three items per restaurant, in this order (`id`, `name`, `priceCents`; each
item also has a one-line `description` of your choosing, which no test asserts):

| restaurant | id | name | priceCents | renders as |
|---|---|---|---|---|
| rest-001 | item-001-1 | Margherita Pizza | 1499 | $14.99 |
| rest-001 | item-001-2 | Spaghetti Carbonara | 1699 | $16.99 |
| rest-001 | item-001-3 | Tiramisu | 899 | $8.99 |
| rest-002 | item-002-1 | Lasagna al Forno | 1899 | $18.99 |
| rest-002 | item-002-2 | Penne all’Arrabbiata | 1399 | $13.99 |
| rest-002 | item-002-3 | Caprese Salad | 1099 | $10.99 |
| rest-003 | item-003-1 | Carnitas Tacos (3) | 1299 | $12.99 |
| rest-003 | item-003-2 | Chicken Quesadilla | 1199 | $11.99 |
| rest-003 | item-003-3 | Elote | 599 | $5.99 |
| rest-004 | item-004-1 | Al Pastor Burrito | 1399 | $13.99 |
| rest-004 | item-004-2 | Shrimp Ceviche | 1599 | $15.99 |
| rest-004 | item-004-3 | Churros (4) | 699 | $6.99 |
| rest-005 | item-005-1 | Tonkotsu Ramen | 1599 | $15.99 |
| rest-005 | item-005-2 | Miso Ramen | 1499 | $14.99 |
| rest-005 | item-005-3 | Gyoza (6) | 799 | $7.99 |
| rest-006 | item-006-1 | Omakase Nigiri (8) | 3299 | $32.99 |
| rest-006 | item-006-2 | Spicy Tuna Roll | 1099 | $10.99 |
| rest-006 | item-006-3 | Edamame | 499 | $4.99 |

Delivery addresses (`id`, `label`, `streetLine`), in this order:

| id | label | streetLine |
|---|---|---|
| home | Home | 123 Test Ave |
| work | Work | 456 Office Blvd |
| other | Other | 789 Hotel St |

Checkout constants: `DELIVERY_FEE_CENTS = 399`; `TAX_RATE = 0.08`;
`taxCents = Math.round(subtotalCents × 0.08)`; `totalCents = subtotalCents + 399 +
taxCents`.

Order id: `ORDER-` followed by a six-digit zero-padded per-launch counter —
`ORDER-000001` for the first order placed after launch, `ORDER-000002` for the second,
and so on. State is in-memory only, so a fresh install always yields `ORDER-000001`.

Defaults: cart empty (no restaurant); no delivery address selected; cuisine filter
empty (all six restaurants shown).

Derived values (the tests assert these exact strings):

- Cuisine filter is a case-insensitive substring match on `cuisine`, applied live as
  the user types (no submit action): `ital` → Nonna Lucia and Pasta Vesuvio only;
  `mex` → Casa Verde and Taqueria del Sol only; a filter matching nothing renders
  `No restaurants match your filter.`; clearing the filter restores all six.
- Cart with one Margherita Pizza: quantity `1`, row detail
  `$14.99 each · line: $14.99`, `Subtotal` `$14.99`. After one `+` press: quantity
  `2`, `$14.99 each · line: $29.98`, `Subtotal` `$29.98`.
- Checkout for two Margherita Pizzas: `Subtotal` `$29.98`; `Delivery fee` `$3.99`;
  `Tax (8%)` `$2.40` (round(2998 × 0.08) = round(239.84) = 240); `Total` `$36.37`
  (2998 + 399 + 240 = 3637).
- Confirmation for an order from Nonna Lucia: `Arriving in ~28 min` (that restaurant's
  `deliveryEtaMinutes`) and `from Nonna Lucia`.
- Cross-restaurant add with Nonna Lucia items in the cart, attempting Carnitas Tacos (3)
  from Casa Verde: dialog body `Your cart has items from Nonna Lucia. Adding Carnitas
  Tacos (3) from Casa Verde will clear your existing cart.`

## Pinned UI text (tests match these exactly — render them verbatim)

- Tab bar labels: `Restaurants`, `Cart`, `Checkout`. Each tab screen shows its heading
  text: `Restaurants`, `Cart`, `Checkout` (the heading is present in every state of
  the screen, including the empty cart / empty checkout states).
- Restaurants screen: the heading, a text input with placeholder
  `Filter by cuisine (e.g. ital, mex, jap)` directly below it (auto-capitalization and
  auto-correct disabled, so typed text is taken literally), and a grid of restaurant
  cards in seed order, each card showing the restaurant `name`, its `cuisine`, and
  `<deliveryEtaMinutes> min` (e.g. `28 min`). Tapping anywhere on a card opens that
  restaurant's menu screen.
- Menu screen (a pushed screen over the tabs, with a **back control at the top-left of
  the header** that returns to the Restaurants grid; the tab bar need not be visible
  here): the restaurant name as the screen title, the line `<cuisine> · <eta> min`
  (e.g. `Italian · 28 min`), and one row per menu item in seed order showing the item
  name, its price (`$14.99`), and an `Add to cart` button. Once an item is in the cart
  its row button reads `In cart (<qty>)` (e.g. `In cart (1)`) and is disabled —
  quantity changes happen in the Cart tab. Adding an item, and cancelling the
  cross-restaurant dialog, do not navigate away: the user stays on the menu screen
  and the row button updates in place.
- Cross-restaurant confirmation dialog: a modal dialog (a native `Alert` is fine)
  titled `Clear cart and add this item?` with body `Your cart has items from <current
  restaurant name>. Adding <item name> from <new restaurant name> will clear your
  existing cart.` and exactly two buttons labelled `Cancel` and `Clear & add`.
- Cart screen: heading `Cart`. Empty: the text `Your cart is empty`. Non-empty: one row
  per cart item showing the item name, the detail line `$<unit price> each · line:
  $<unit price × qty>`, and a stepper: a `−` (minus, U+2212) button, the quantity as
  a number, and a `+` button; below the rows, a `Subtotal` label with the subtotal
  amount. Decrementing a quantity to 0 removes the row (an empty cart releases the
  restaurant lock).
- Checkout screen: heading `Checkout`. Empty cart: the text `Add items to your cart to
  checkout.`. Non-empty: a `Deliver to` label above three selectable address rows in
  seed order, each showing the label (`Home`, `Work`, `Other`) and its street line,
  with the selected row visibly marked (radio/highlight); then four summary lines
  labelled `Subtotal`, `Delivery fee`, `Tax (8%)`, `Total` with their amounts; then a
  `Place order` button that is **disabled until an address is selected** (and while
  the cart is empty). Whether the address selection persists across tab navigation is
  unspecified and unasserted — the tests select an address and place the order in one
  visit.
- Confirmation screen (pushed after **Place order**; the cart is cleared): title
  `Order placed`, the text `Order placed`, the order id in large text (`ORDER-000001`
  for the first order), `Arriving in ~<eta> min`, and `from <restaurant name>`.

## Final acceptance

The final e2e journey: launch → Restaurants grid → type `ital` → only Nonna Lucia and
Pasta Vesuvio → tap Nonna Lucia → menu → Add to cart on Margherita Pizza →
`In cart (1)` → back → change the filter to `mex` → tap Casa Verde → Add to cart on
Carnitas Tacos (3) → dialog `Clear cart and add this item?` mentioning Nonna Lucia
with `Cancel` / `Clear & add` → Cancel → back → Cart tab shows only Margherita Pizza,
quantity 1, `Subtotal` `$14.99` → `+` → quantity 2, `$29.98` → Checkout tab →
`$29.98` / `$3.99` / `$2.40` / `$36.37` → tap Home → Place order → confirmation with
`Order placed`, `ORDER-000001`, `Arriving in ~28 min`, `from Nonna Lucia`. It must
complete without manual intervention.
