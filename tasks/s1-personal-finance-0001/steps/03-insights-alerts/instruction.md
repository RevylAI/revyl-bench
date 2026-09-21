# Step 03 — spending insights + persistent weekly-alert preference

Implement the Insights tab per the root contract: top spending category, the weekly
spending trend, and a persistent weekly-alert preference with a textual summary.

## Requirements

1. **Top category**: `Top category: <Name>` computed from the live per-category
   expense totals (with the seed data: `Top category: Rent`, before and after any
   re-categorization in the graded journeys).
2. **Weekly trend**: a `Weekly spending` section rendering exactly the four fixed
   weekly rows from the root contract — `Week of Jul 1` `$2,135.00`, `Week of Jul 8`
   `$185.00`, `Week of Jul 15` `$265.00`, `Week of Jul 22` `$75.00`. These totals are
   fixed values and must not move when a transaction is re-categorized.
3. **Weekly-alert preference**: an `Alert preferences` section with a toggle row
   labeled `Weekly spending alert` whose state renders as text `On` / `Off` (enabled
   row visually distinct, e.g. green background), plus a summary line
   `Weekly alert: On` / `Weekly alert: Off`. Default: `Off`.
4. The toggle is **one-shot (debounced)**: a rapid double-tap enables it exactly once
   — it must not bounce back to `Off`.
5. The preference persists across tab navigation (store state; no backend needed).

## Observable outcome the hidden test checks

Open `Insights` → `Top category: Rent` + the four weekly rows verified → summary reads
`Weekly alert: Off` → **double-tap** the `Weekly spending alert` row → row shows `On`
(visually distinct) and summary reads `Weekly alert: On` (no bounce-back) → navigate
to `Accounts` and back to `Insights` → still `On` / `Weekly alert: On`.
