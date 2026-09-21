# Step 03 — the derived shopping list, servings scaling, and settings

Implement the List tab and the Settings tab per the root contract.

## Requirements

1. **List tab**: a `Servings` row with buttons `2`, `3`, `4`; the line
   `<n> recipes, <m> items`; then the combined ingredients alphabetically as
   `<name> <qty><unit>`. Empty state text: `No recipes selected.`.

2. **Combine, then scale, then subtract the pantry** (ground rules 2, 3 and 4) — three
   steps, in that order. Sum each ingredient across every selected recipe **first**, then
   scale that combined total **once** by `servings / 2` rounding half-up, and **only then**
   subtract the pantry, which does **not** scale. An ingredient the pantry fully covers is
   removed from the list and not counted.

   With the seed selection at 2 servings the list is 13 items: `Basil 10g`, `Cream 250ml`,
   `Garlic 3`, `Mushrooms 375g`, `Olive oil 10ml`, `Onion 1`, `Parmesan 165g`,
   `Pasta 200g`, `Potatoes 800g`, `Rice 175g`, `Stock 650ml`, `Thyme 13g`,
   `Tomatoes 400g` — `Butter` combines to `80g`, the pantry holds `100g`, so it is gone.

   At 3 servings the list becomes 14 items: `Butter` scales to `120g` against the same
   unscaled `100g` pantry and reappears as `Butter 20g`; `Parmesan` becomes `248g`,
   `Olive oil 45ml`, `Basil 20g`, `Garlic 7`.

   Two things that would be wrong: scaling each recipe separately and adding afterwards
   gives `Parmesan 249g` and `Olive oil 106ml` before the pantry; and scaling the pantry,
   or subtracting it before scaling, leaves `Butter` covered so the list stays at 13 items
   instead of growing to 14.

3. **The list is fully derived** (ground rule 5): selecting or deselecting a recipe, or
   changing servings, rewrites it immediately. The servings buttons are one-shot and take
   effect on the single tap.

4. **Settings tab**: a `Plan` block with `Recipes selected: <n>` and `Servings: <n>`, then
   a `Pantry` block listing the four pantry lines alphabetically: `Basil 10g`,
   `Butter 100g`, `Garlic 5`, `Olive oil 60ml`.

5. The selection and the servings choice persist across navigation: leaving a tab and
   returning shows the same list and the same servings (store state; no backend, no disk
   persistence).

## Observable outcome the hidden test checks

List tab shows `4 recipes, 13 items` with no `Butter` line; the list scrolls, and scrolling
to the bottom shows `Tomatoes 400g` → tap the `3` servings button → the list becomes
`4 recipes, 14 items`, `Butter 20g` appears, `Olive oil 45ml` and `Parmesan 248g` → Recipes
tab → add `Tomato Soup` to the plan → List tab → `5 recipes, 14 items` with `Basil 28g` and
`Olive oil 83ml` → Settings tab → `Recipes selected: 5`, `Servings: 3` and a `Pantry` block
→ List tab → Settings tab again → unchanged.
