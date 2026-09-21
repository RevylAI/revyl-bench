# Step 02 — the recipe list, recipe detail, and selection

Implement the Recipes tab and the pushed recipe detail screen per the root contract's
seed data, ground rules, and pinned UI text.

## Requirements

1. **Recipes tab**: one row per recipe in seed order showing the recipe name and the text
   `<n> ingredients` (`Tomato Pasta` 6, `Chicken Risotto` 6, `Garlic Bread` 3,
   `Tomato Soup` 5, `Herb Chicken` 4, `Potato Gratin` 6, `Mushroom Risotto` 7,
   `Lemon Spinach` 5), plus a toggle control reading `Selected` when the recipe is in the
   plan and `Add to plan` when it is not. At a fresh install `Tomato Pasta`,
   `Garlic Bread`, `Potato Gratin` and `Mushroom Risotto` are `Selected`.

2. **Recipe detail** (pushed, header title = the recipe name, native back button): the
   text `Serves 2`, then an `Ingredients` section listing every ingredient
   **alphabetically** as `<name> <qty><unit>`, with a bare count rendering no unit. For
   `Tomato Pasta` that is `Basil 15g`, `Garlic 2`, `Olive oil 25ml`, `Parmesan 45g`,
   `Pasta 200g`, `Tomatoes 400g`.

3. **Selecting** is one-shot (debounced) and takes effect on the single tap, with no
   confirmation step. Toggling a recipe flips its control between `Selected` and
   `Add to plan`.

4. The selection persists across navigation (store state; no backend needed).


**The toggle must be individually addressable**: its accessibility label carries the recipe
name (`Add to plan, Tomato Soup`, `Selected, Tomato Pasta`) because up to eight toggles
share the same two words of visible text. Visible text stays exactly `Add to plan` /
`Selected`.

## Observable outcome the hidden test checks

Launch → Recipes lists the eight recipes with their ingredient counts, `Tomato Pasta`,
`Garlic Bread`, `Potato Gratin` and `Mushroom Risotto` showing `Selected` → tap `Tomato Soup` → detail shows `Serves 2` and the
alphabetical ingredients including `Tomatoes 600g` → back → tap its `Add to plan` toggle →
the row now reads `Selected`.
