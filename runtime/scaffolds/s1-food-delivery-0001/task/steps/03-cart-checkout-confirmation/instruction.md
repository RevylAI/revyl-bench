# Step 03 — single-restaurant cart, quantity steppers, checkout, order confirmation

Implement add-to-cart, the Cart tab, the Checkout tab and the confirmation screen per
the root contract.

## Requirements

1. **Add to cart** (menu screen): each menu row has an `Add to cart` button
   (one-shot, debounced). Tapping it adds that item to the cart with quantity 1; the
   row button then reads `In cart (<qty>)` (`In cart (1)`) and is disabled. Adding
   sets the cart's restaurant. Adding does not navigate away: the user stays on the
   menu screen and the row button updates in place.
2. **Single-restaurant constraint**: if the cart already holds items from a different
   restaurant, tapping `Add to cart` shows the confirmation dialog titled
   `Clear cart and add this item?` with body `Your cart has items from <current
   restaurant name>. Adding <item name> from <new restaurant name> will clear your
   existing cart.` and buttons `Cancel` / `Clear & add`. **Cancel** leaves the cart
   exactly as it was; **Clear & add** replaces the cart with the new item (quantity 1).
   Either way the user stays on the menu screen (no navigation), and the row button
   reflects the outcome in place.
3. **Cart tab**: heading `Cart`; `Your cart is empty` when empty; otherwise one row
   per item with the item name, `$<unit> each · line: $<unit × qty>`, and a `−` /
   quantity / `+` stepper (one-shot, debounced: exactly one step per press), plus a
   `Subtotal` line. `+` on a Margherita Pizza row at 1 → quantity `2`, line
   `$29.98`, `Subtotal` `$29.98`. Decrementing to 0 removes the row.
4. **Checkout tab**: heading `Checkout`; `Add items to your cart to checkout.` when
   the cart is empty; otherwise `Deliver to` with the three address rows
   (`Home` 123 Test Ave, `Work` 456 Office Blvd, `Other` 789 Hotel St; selected row
   visibly marked), then `Subtotal`, `Delivery fee` (`$3.99`), `Tax (8%)`
   (round(subtotal × 0.08)), `Total`, and a `Place order` button (one-shot,
   debounced) that is disabled until an address is selected. For two Margherita
   Pizzas: `$29.98` / `$3.99` / `$2.40` / `$36.37`.
5. **Confirmation**: **Place order** clears the cart and pushes a screen titled
   `Order placed` showing `Order placed`, the order id (`ORDER-000001` for the first
   order after launch — six-digit zero-padded per-launch counter, no randomness),
   `Arriving in ~<eta> min` for the order's restaurant (`~28 min` for Nonna Lucia),
   and `from <restaurant name>`.
6. The cart persists across tab navigation and menu visits (store state; no backend,
   no disk persistence).

## Observable outcome the hidden test checks

Launch → tap Nonna Lucia → menu with `Add to cart` buttons → tap Add to cart on
Margherita Pizza → `In cart (1)` → back → Cart tab → one row, Margherita Pizza,
quantity 1, `Subtotal` `$14.99` → tap `+` once → quantity 2, `Subtotal` `$29.98` →
Checkout tab → Deliver to (Home / Work / Other), `Subtotal` `$29.98`, `Delivery fee`
`$3.99`, `Tax (8%)` `$2.40`, `Total` `$36.37`, `Place order` disabled → tap Home →
Home selected, `Place order` enabled → tap Place order → `Order placed`,
`ORDER-000001`, `Arriving in ~28 min`, `from Nonna Lucia`.
