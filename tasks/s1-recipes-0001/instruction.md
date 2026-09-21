# MealPlan — build a mobile meal-planning app

You are a coding agent building a fresh iOS mobile app from the provided Expo scaffold
(Expo SDK 57, Expo Router, TypeScript). The product is a meal planner: a list of recipes
you can select for the week, a pushed recipe detail screen listing its ingredients, and a
shopping list that is **entirely derived** from your selection — the same ingredient
appearing in several selected recipes is combined into one line, and the whole list scales
to a chosen number of servings.

The work is split into three steps (see `steps/01-tabs`, `steps/02-recipes-select`,
`steps/03-list-scale-settings`, each with its own `instruction.md`), followed by a final
end-to-end acceptance run. Complete the steps in order.

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

1. **Integer quantities.** Every ingredient quantity is an integer in its canonical unit
   (`g`, `ml`, or a bare count). No floating-point arithmetic anywhere; do the scaling in
   integer arithmetic.

2. **Combine first, then scale — in that order.** Building the shopping list is two steps
   and the order is binding: **first** sum each ingredient's quantity across every selected
   recipe, **then** scale that single combined total once. Scaling each recipe's
   contribution separately and adding the results afterwards gives different numbers and is
   wrong. Worked example below shows two lines where the two orders disagree.

3. **The scaling rule (exact).** Every recipe is written for **2 servings**. The shopping
   list is scaled to the chosen servings by multiplying the combined total by
   `servings / 2` and **rounding half-up to a whole unit**. Worked example: a combined
   `45g` at 3 servings is `67.5g`, which renders as `68g`.

4. **The pantry, and the order it applies (binding).** Settings holds a **pantry**: what
   you already own. Building the shopping list is now three steps, and the order is
   binding: **combine** across the selected recipes, **then scale** to the chosen servings,
   **then subtract the pantry**. An ingredient whose scaled total is fully covered by the
   pantry is **removed from the list entirely** — it is not shown as `0`, and it does not
   count towards the item count or the tab badge.

   **The pantry does not scale.** It is a stock level, not a recipe: you own what you own
   regardless of how many servings you are cooking. Scaling the pantry along with the
   recipes, or subtracting it before scaling instead of after, both produce a different
   list — and both produce a different *item count*, which the tests assert.

   Worked example: `Butter` combines to `80g` across the seed selection. At 2 servings that
   is `80g`, the pantry holds `100g`, so `Butter` is fully covered and does not appear. At
   3 servings the combined total scales to `120g`, the pantry still holds `100g` (it did not
   scale), so `Butter 20g` appears and the list grows from 13 items to 14.

5. **Deterministic data — no clocks, no randomness.** No `Date.now()`, `new Date()`,
   `Math.random()`, or uuid libraries anywhere in app code. No dates or time-of-day text is
   rendered anywhere. Every value on screen must be computable from this contract alone.

6. **The list is fully derived.** The shopping list has no independent state: it is always
   exactly the combination of the currently selected recipes at the current servings.
   Selecting or deselecting a recipe rewrites it immediately.

7. **Alphabetical order.** Ingredients are listed alphabetically by name, both on a recipe
   detail screen and on the shopping list.

8. **Debounced one-shot controls.** The recipe select toggle and the servings buttons are
   one-shot: a rapid double-tap performs the action **exactly once**. Disabling the control
   briefly after press (≈250–300 ms) is one acceptable implementation. They take effect on
   the single tap that triggers them — there is no confirmation dialog, alert, or
   intermediate screen, and the app never opens a native alert dialog at any point.

9. **Textual state.** Quantities, the servings selection and the counts are exact text
   strings (pinned below) — never encoded only in colours, icons or bar widths.

10. **State survives navigation.** The recipe selection and the servings choice persist when
   the user navigates between tabs and pushes/pops screens (module-level/store state is
   sufficient; no backend, no disk persistence — a fresh install starts from the seed
   below).

11. **Navigation shape.** The app opens directly on the Recipes tab — no login, onboarding,
    or splash gate — and the recipe list is interactive within two seconds of launch. The
    three tabs are a bottom tab bar. Tapping a recipe row **pushes** its detail screen
    (native stack header titled with the recipe name and a back button). Back returns to
    the tab bar. Every recipe row is tappable to open its detail.

12. **Everything the user must reach stays on screen.** The shopping list is longer than
    one screen and scrolls. The `Servings` row stays **pinned at the top and visible while
    the ingredient rows scroll beneath it**, so the servings buttons are reachable at any
    scroll position without scrolling back up.

13. **The List tab carries a badge.** The `List` item in the bottom tab bar shows a small
    numeric badge with the number of items currently on the shopping list. With the seed
    selection at 2 servings that badge reads `13` — it counts the items actually on the
    list, so an ingredient the pantry fully covers is not counted. It updates as recipes
    are selected or deselected and as servings change, and
    shows no badge at all when nothing is selected.

## Seed data (exact values — copy these verbatim)

Ingredients and their canonical units (a blank unit means a bare count):

| ingredient | unit |
|---|---|
| Basil | g |
| Butter | g |
| Chicken | g |
| Cream | ml |
| Flour | g |
| Garlic | *(count)* |
| Lemon | *(count)* |
| Mushrooms | g |
| Olive oil | ml |
| Onion | *(count)* |
| Parmesan | g |
| Pasta | g |
| Potatoes | g |
| Rice | g |
| Spinach | g |
| Stock | ml |
| Thyme | g |
| Tomatoes | g |

Recipes, in this order. Every recipe is written for **2 servings**.

| recipe | ingredients (alphabetical) |
|---|---|
| Tomato Pasta | Basil 15g, Garlic 2, Olive oil 25ml, Parmesan 45g, Pasta 200g, Tomatoes 400g |
| Chicken Risotto | Chicken 300g, Olive oil 20ml, Onion 1, Parmesan 50g, Rice 175g, Stock 700ml |
| Garlic Bread | Basil 5g, Garlic 4, Olive oil 45ml |
| Tomato Soup | Basil 5g, Olive oil 25ml, Onion 2, Stock 400ml, Tomatoes 600g |
| Herb Chicken | Basil 20g, Chicken 450g, Garlic 3, Olive oil 35ml |
| Potato Gratin | Butter 45g, Cream 250ml, Garlic 2, Parmesan 65g, Potatoes 800g, Thyme 8g |
| Mushroom Risotto | Butter 35g, Mushrooms 375g, Onion 1, Parmesan 55g, Rice 175g, Stock 650ml, Thyme 5g |
| Lemon Spinach | Butter 25g, Flour 15g, Garlic 3, Lemon 2, Spinach 425g |

Defaults: `Tomato Pasta`, `Garlic Bread`, `Potato Gratin` and `Mushroom Risotto` are
selected; servings is `2`. **The resulting shopping list is longer than one screen** — it
scrolls, and the tests scroll it.

### Pantry (exact — what you already own)

These are fixed stock levels, in the canonical unit. They never change and they never
scale with servings.

| ingredient | you own |
|---|---|
| `Basil` | `10g` |
| `Butter` | `100g` |
| `Garlic` | `5` |
| `Olive oil` | `60ml` |

Every other ingredient has a pantry stock of zero.

## Derived values (the tests assert these exact strings and orders)

**Shopping list at the seed selection** (`Tomato Pasta` + `Garlic Bread` +
`Potato Gratin` + `Mushroom Risotto`), **2 servings** — `Basil`, `Butter`, `Garlic`,
`Olive oil`, `Parmesan` and `Thyme` are each combined from more than one recipe:

Combined, then scaled (×1 at 2 servings), then the pantry subtracted. `Butter` combines to
`80g`, the pantry holds `100g`, so it is fully covered and **removed** — the list is
**13 items**, not 14:

`Basil 10g`, `Cream 250ml`, `Garlic 3`, `Mushrooms 375g`, `Olive oil 10ml`, `Onion 1`,
`Parmesan 165g`, `Pasta 200g`, `Potatoes 800g`, `Rice 175g`, `Stock 650ml`, `Thyme 13g`,
`Tomatoes 400g`

The four pantry lines above are the ones to check: `Basil` combines to `20g` and shows
`10g`; `Garlic` combines to `8` and shows `3`; `Olive oil` combines to `70ml` and shows
`10ml`; `Butter` is gone.

**The same selection at 3 servings** (each combined total × 1.5, rounded half-up):

Combined, scaled ×1.5 with half-up rounding, **then** the unscaled pantry subtracted.
`Butter` now scales to `120g` against an unchanged pantry of `100g`, so it reappears and
the list grows to **14 items**:

`Basil 20g`, `Butter 20g`, `Cream 375ml`, `Garlic 7`, `Mushrooms 563g`, `Olive oil 45ml`,
`Onion 2`, `Parmesan 248g`, `Pasta 300g`, `Potatoes 1200g`, `Rice 263g`, `Stock 975ml`,
`Thyme 20g`, `Tomatoes 600g`

The item count moving 13 → 14 is the check that the three steps are in the right order. If
the pantry is scaled with the recipes, or subtracted before scaling instead of after,
`Butter` stays covered and the list stays at 13.

- Rounding cases: `Parmesan` combines to `165g`, × 1.5 = `247.5` → `248g`; `Mushrooms`
  `375 → 562.5 → 563g`; `Rice` `175 → 262.5 → 263g`; `Thyme` `13 → 19.5 → 20g`; `Onion`
  `1 → 1.5 → 2`.
- Order-of-operations cases — combining first then scaling is **required**, and gives
  different answers from scaling each recipe separately and adding. These figures are the
  values **before** the pantry is subtracted, i.e. the result of steps one and two:
  `Olive oil` is `25 + 45 = 70`, × 1.5 = `105ml` (not `38 + 68 = 106`), and the pantry's
  `60ml` then leaves `45ml`; `Basil` is `15 + 5 = 20`, × 1.5 = `30g` (not `23 + 8 = 31`),
  less `10g` leaves `20g`; `Parmesan` is `45 + 65 + 55 = 165`, × 1.5 = `248g` (not
  `68 + 98 + 83 = 249`), and the pantry holds none, so `248g` stands; `Butter` is
  `45 + 35 = 80`, × 1.5 = `120g` (not `68 + 53 = 121`), less `100g` leaves `20g`.

**At 4 servings** (× 2, then the unscaled pantry subtracted) — **14 items**:
`Basil 30g`, `Butter 60g`, `Cream 500ml`, `Garlic 11`, `Mushrooms 750g`,
`Olive oil 80ml`, `Onion 2`, `Parmesan 330g`, `Pasta 400g`, `Potatoes 1600g`,
`Rice 350g`, `Stock 1300ml`, `Thyme 26g`, `Tomatoes 800g`.

**Counts**: with the seed selection at 2 servings the List tab shows `4 recipes, 13 items` — thirteen, because the pantry fully covers `Butter`. Tapping `3` changes it to `4 recipes, 14 items`.

**Adding a fifth recipe.** Selecting `Tomato Soup` as well, at 3 servings, gives
`5 recipes, 14 items` (it introduces no new ingredient): `Basil 28g`, `Butter 20g`,
`Cream 375ml`, `Garlic 7`, `Mushrooms 563g`, `Olive oil 83ml`, `Onion 5`,
`Parmesan 248g`, `Pasta 300g`, `Potatoes 1200g`, `Rice 263g`, `Stock 1575ml`,
`Thyme 20g`, `Tomatoes 1500g`.

## Pinned UI text (tests match these exactly — render them verbatim)

- Tab bar labels: `Recipes`, `List`, `Settings`. Each tab screen shows its heading text:
  `Recipes`, `List`, `Settings`. The `List` tab item carries the numeric badge from ground
  rule 12.
- **Recipes tab**: one row per recipe in seed order showing the recipe name and the text
  `<n> ingredients`, plus a toggle control labelled `Selected` when the recipe is in the
  plan and `Add to plan` when it is not. The toggle is a **separate tap target from the
  rest of the row**: tapping the toggle changes the selection and does not navigate;
  tapping anywhere else on the row pushes the detail screen and does not change the
  selection.

  **The toggle must be individually addressable.** Eight rows means up to eight toggles
  whose visible text is the same two words, so the control's accessibility label must also
  carry the recipe name — `Add to plan, Tomato Soup` and `Selected, Tomato Pasta`. Without
  it nothing can say *which* toggle it means, and neither can the tests. The visible text
  stays exactly `Add to plan` / `Selected`.
- **Recipe detail screen** (pushed): header title is the recipe name; the text
  `Serves 2`; then an `Ingredients` section listing every ingredient alphabetically as
  `<name> <qty><unit>` (a bare count renders with no unit, e.g. `Garlic 2`).
- **List tab**: a `Servings` row with three buttons labelled `2`, `3` and `4`; the line
  `<n> recipes, <m> items`; then the combined ingredients alphabetically as
  `<name> <qty><unit>`. When nothing is selected, the text `No recipes selected.`.
- **Settings tab**: a `Plan` block with the two lines `Recipes selected: <n>` and
  `Servings: <n>`, then a `Pantry` block listing the four pantry lines alphabetically as
  `<name> <qty><unit>`: `Basil 10g`, `Butter 100g`, `Garlic 5`, `Olive oil 60ml`.

## Final acceptance

The final e2e journey: launch → Recipes tab lists the eight recipes with `Tomato Pasta`,
`Garlic Bread`, `Potato Gratin` and `Mushroom Risotto` marked `Selected` → List tab shows
`4 recipes, 13 items` with `Basil 10g`, `Garlic 3`, `Olive oil 10ml`, `Parmesan 165g` and
no `Butter` line at all; the list scrolls, and scrolling to the bottom shows `Thyme 13g`
and `Tomatoes 400g` while the `Servings` row stays pinned at the top → tap the `3` servings
button → the list becomes `4 recipes, 14 items`, `Butter 20g` appears, and `Basil 20g`,
`Olive oil 45ml`, `Parmesan 248g` are shown → Recipes tab → tap `Tomato Soup` → detail
shows `Serves 2` and `Tomatoes 600g` → back → tap its `Add to plan` toggle → List tab →
`5 recipes, 14 items` with `Basil 28g` and `Olive oil 83ml` → Settings tab →
`Recipes selected: 5`, `Servings: 3` and the `Pantry` block showing `Butter 100g`. It must
complete without manual intervention.
