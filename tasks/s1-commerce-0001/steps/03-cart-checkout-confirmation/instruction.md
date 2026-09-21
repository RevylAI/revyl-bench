# Step 03 — add to cart, quantity stepper, checkout summary, order confirmation

Implement the cart, the checkout summary and the order-confirmation screen per the
root contract: whole-dollar prices with `$` + plain-number rendering, 8% tax rounded
to cents, and a deterministic per-launch order counter.

## Requirements

1. **Add to cart**: the product detail screen has an `Add to cart` button. Each tap
   adds exactly one unit of that product to the cart (merging into the product's
   existing row — never a second row) and gives visible feedback (the label reads
   `Added to cart` briefly, about 1.5 s, then reverts). The detail screen stays open
   after the tap — no automatic navigation to the cart.
2. **Cart tab** (heading `Cart`): `Your cart is empty.` when empty; otherwise one row
   per product with the title, `$<price> each`, a stepper `−` `<qty>` `+`, and the line
   subtotal `$<price×qty>`; a `Subtotal` row below with the cart subtotal. `+` adds one
   unit, `−` removes one unit, and `−` at quantity 1 removes the row. Subtotals update
   immediately (`$24` → `$48` after one `+` on Cobalt Travel Mug; back to `$24` after
   one `−`).
3. **Checkout tab** (heading `Checkout`): `Your cart is empty. Add a product to start
   checkout.` when empty; otherwise one line per product `<title> × <qty>` with its
   line subtotal; always a totals card with `Subtotal`, `Tax (8%)`, `Total` (rounded to
   cents: two mugs → `$48` / `$3.84` / `$51.84`); a `Place order` button, disabled
   while the cart is empty.
4. **Order confirmation**: tapping `Place order` assigns the next order ID
   (`ORD-000001` for the first order since launch), clears the cart, and opens a
   stack screen (header title `Order confirmed`) with the heading `Order placed`, the
   line `Thanks — your order has been confirmed.`, and rows `Order ID` / `ORD-000001`,
   `Items` / `<total quantity>` (`2`), `Total charged` / `<total>` (`$51.84`).
5. Cart state persists across tab navigation and into/out of the detail and
   confirmation screens (store state; no backend, no disk persistence).

## Observable outcome the hidden test checks

Launch → tap the Cobalt Travel Mug card → detail shows `Cobalt Travel Mug`, `$24`,
`Add to cart` → tap Add to cart once → back → Cart tab → one row `Cobalt Travel Mug`,
`$24 each`, quantity `1`, line `$24`, `Subtotal` `$24` → tap `+` once → quantity `2`,
`$48`, `Subtotal` `$48` → tap `−` once → quantity `1`, `$24`, `Subtotal` `$24` → tap
`+` once → quantity `2`, `$48`, `Subtotal` `$48` → Checkout tab → line
`Cobalt Travel Mug × 2` `$48`, `Subtotal` `$48`, `Tax (8%)` `$3.84`, `Total` `$51.84`,
`Place order` enabled → tap Place order → `Order placed`, `Order ID` `ORD-000001`,
`Items` `2`, `Total charged` `$51.84`.
