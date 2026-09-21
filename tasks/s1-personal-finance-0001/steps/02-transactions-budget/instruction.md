# Step 02 — account overview, grouped transactions, re-categorization, budget warnings

Implement the Accounts tab, the transaction detail screen, and the Budget tab per the
root contract's seed data, pinned formats, and pinned UI text.

## Requirements

1. **Accounts screen**: the two account cards — `Everyday Checking` `$2,450.00` and
   `Rainy Day Savings` `$8,000.00` (balances displayed as-is, never derived) — above a
   `Transactions` list grouped under `dateLabel` group headers (`Jul 1` … `Jul 23`),
   ordered by `tsOrder`. Each row: label, category name (or `Income`), and the signed
   amount — income green with leading `+` (`+$1,500.00`), expenses with leading `-`.
2. **Transaction detail** (tap a row): label, signed amount, `dateLabel`; a `Category`
   picker of the five categories with the current selection visibly marked
   (checkmark); `Apply category` button that applies the new category exactly once
   (debounced one-shot) and then reads `Category updated`; a `Back to Accounts`
   button. Income transactions show `Income is not categorized.` instead of a picker.
3. **Budget screen**: one row per category, `<Name>: <spent> of <budget>`, where
   `<spent>` is that category's live expense total (recalculated after any
   re-categorization). Over-budget categories additionally show
   `Over budget: <Name> +<overage>`.
4. Re-categorization moves **exactly one** transaction between categories and
   persists across tab navigation.

## Observable outcome the hidden test checks

Launch → account cards + grouped list verified (seeded state: `Dining: $180.00 of
$200.00`, `Entertainment: $100.00 of $100.00` at budget, no warnings) → open
`Pizza Night` (`-$60.00`, `Jul 18`, `Entertainment` selected) → pick `Dining` →
`Apply category` → button reads `Category updated`, `Dining` shows the checkmark →
`Back to Accounts` → `Budget` tab shows `Dining: $240.00 of $200.00` with
`Over budget: Dining +$40.00`, and `Entertainment: $40.00 of $100.00` with no
warning.
