# Step 03 — recording a result, re-sorting, and the season totals

Implement the `Record a result` form and the Settings tab per the root contract.

## Requirements

1. **Record a result**: below the fixtures list, a section with a home-team selector, an
   away-team selector, two score inputs (placeholders `0`, digits only) and a button
   labelled `Record`. Recording is one-shot (debounced), takes effect on the single tap
   with no confirmation step, and `Record` is disabled while either score input is empty.

2. **Recording recomputes and re-sorts** (ground rule 5): the new result is appended to
   the fixtures list, both teams' rows are recomputed, and the whole table is re-sorted by
   the ordering rule. Example from the seed: recording `Calder 3 - 0 Ashford` makes
   `Calder` read `5 2 1 2 10 9 1 7` and `Ashford` read `5 2 0 3 8 9 -1 6`, and
   the table order becomes `Brightwell`, `Holloway`, `Fenwick`, `Calder`, `Garrick`, `Ingleton`, `Ashford`, `Eastvale`, `Jarrow`, `Dunmore`.

3. **Settings tab**: a `Season` block with `Matches played: <n>` (the number of results)
   and `Goals scored: <n>` (every goal in every result). With the seed alone that is
   `Matches played: 20` and `Goals scored: 70`.

4. Recorded results persist across navigation: leaving a tab and returning shows the same
   table, the same fixtures and the same totals (store state; no backend, no disk
   persistence).

**A newly recorded result is appended as the LAST row of the fixtures list** (root
contract, Fixtures tab). The list is longer than one screen, so reaching it means scrolling
to the bottom.

## Observable outcome the hidden test checks

Fixtures tab → record `Calder` `3` – `0` `Ashford` → the fixtures list gains
`Calder 3 - 0 Ashford` → Table tab → the order is now
`Brightwell`, `Holloway`, `Fenwick`, `Calder`… with `Calder` reading
`5 2 1 2 10 9 1 7` → Settings tab → `Matches played: 21` and
`Goals scored: 73` → Table tab → Settings tab again → the totals are unchanged.
