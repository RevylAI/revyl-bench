# Step 02 — destination search + tiered fare selection with price/ETA cascade

Implement the Search tab and the Fare tab per the root contract's seed data, pinned
formats, and pinned UI text.

## Requirements

1. **Search screen**: mocked map labels `Pickup: Current Location` and
   `Dropoff: Select a destination`; a `Destinations` list of the five seeded
   destinations by name. Tapping a destination selects it (row highlighted) and the
   dropoff label becomes `Dropoff: <name>` (e.g. `Dropoff: Downtown Office`). Pickup
   never changes.
2. **Fare screen**: a `Selected fare` summary — `Select a fare tier` initially — and
   three fare cards in seed order (Economy, Premium, XL), each showing the label and
   `<price> — ETA <n> min` (`$12.50 — ETA 5 min`, `$24.00 — ETA 3 min`,
   `$36.00 — ETA 4 min`).
3. Tapping a card selects that tier: the card is highlighted with the badge text
   `Selected`, and the summary reads `<Label>: <price> — ETA <n> min`. Selecting a
   different tier moves the selection and cascades price + ETA into the summary
   (Economy → Premium: `Economy: $12.50 — ETA 5 min` → `Premium: $24.00 — ETA 3 min`).
4. Fare selection is **one-shot (debounced)** and idempotent: a rapid double-tap on a
   card leaves that tier selected — it must never deselect.
5. Selected destination and fare persist across tab navigation.

## Observable outcome the hidden test checks

Launch → Search shows Downtown Office / Airport Terminal / Riverside Park with
`Pickup: Current Location` and `Dropoff: Select a destination` → tap Downtown Office →
`Dropoff: Downtown Office` → Fare tab shows the three cards and `Select a fare tier` →
tap Economy → `Economy: $12.50 — ETA 5 min` + `Selected` badge → tap Premium →
`Premium: $24.00 — ETA 3 min` + badge moves → double-tap Premium → summary still
`Premium: $24.00 — ETA 3 min`.
