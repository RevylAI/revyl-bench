# Step 03 — moving tickets, assigning, and the totals

Implement the status and assignment actions on the ticket detail screen, and the Settings
tab, per the root contract.

## Requirements

1. **Move to**: the ticket detail screen has a `Move to` section with three buttons
   labelled `To Do`, `In Progress`, `Done`. Tapping one sets the ticket's status. It is
   one-shot (debounced), takes effect on that single tap with no confirmation step, and
   moving to the status the ticket already has is a no-op.

2. **Moving moves points** (ground rule 5): the source column loses the ticket and its
   points, the destination gains them, and the ticket is re-sorted into the destination by
   the ordering rule — **not** appended at the end. Example from the seed: moving #105
   (`Medium`, 3 points) from `In Progress` to `Done` makes `In Progress` read
   `2 tickets, 13 points` and `Done` read `5 tickets, 14 points`, with #105 second in the
   `Done` column (after #110, before #109).

3. **Assign to me**: a button of that label on the detail screen sets the ticket's
   assignee to `You` and adds it to My Work in the right position. It is one-shot, and
   assigning a ticket already assigned to you is a no-op. Per ground rule 6 it changes
   **nothing else** — no column header, no total, no percentage.

4. **Settings tab**: a `Totals` block with `Total points: <n>` (every ticket's points),
   `Done points: <n>` (the `Done` column's points) and `Complete: <n>%` (Done points as a
   percentage of the total, rounded half-up per ground rule 3). With the seed alone:
   `Total points: 45`, `Done points: 11`, `Complete: 24%`.

5. Status changes and assignments persist across navigation: leaving a tab and returning
   shows the same columns, the same My Work list and the same totals (store state; no
   backend, no disk persistence).

## Observable outcome the hidden test checks

Tap the `#105` row → `Move to` → `Done` → back → `In Progress` reads `2 tickets, 13 points`
and `Done` reads `5 tickets, 14 points` with #105 second in `Done` → `Settings` shows
`Done points: 14` and `Complete: 31%` → back to `Board` → tap `#101` → `Assign to me` →
back → column headers unchanged → `My Work` lists #101 first → `Settings` → `Board` →
`Settings` again → the totals are still `Done points: 14`, `Complete: 31%`.
