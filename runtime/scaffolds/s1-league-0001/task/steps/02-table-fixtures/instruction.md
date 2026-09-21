# Step 02 — the computed table, team detail, and fixtures

Implement the Table tab, the pushed team detail screen, and the Fixtures list per the root
contract's seed data, ground rules, and pinned UI text.

## Requirements

1. **Table tab**: a header row with the column labels `Team`, `P`, `W`, `D`, `L`, `GF`,
   `GA`, `GD`, `Pts`, then one row per team showing its position number, name and those
   nine values — every one of them **computed** from the result list (ground rule 1), with
   3 points for a win and 1 for a draw.

2. **Ordering** follows ground rule 3 exactly: points descending, then goal difference
   descending, then goals for descending, then name A–Z. With the seed alone the order is
   `Brightwell`, `Holloway`, `Fenwick`, `Garrick`, `Ingleton`, `Ashford`, `Calder`, `Eastvale`, `Jarrow`, `Dunmore` — and all four levels decide one of those
   adjacent pairs, so all four must be implemented. **The table is longer than one screen
   and scrolls.**

3. **Signed goal difference** per ground rule 4: negative differences render with a
   leading minus (`-5` for `Dunmore`), and a zero difference renders
   `0` with no sign.

4. **Team detail** (pushed, header title = the team name, native back button): the lines
   `Played:`, `Won:`, `Drawn:`, `Lost:`, `Goals for:`, `Goals against:`,
   `Goal difference:` and `Points:` with that team's computed values. For `Eastvale` that
   is `Played: 4`, `Won: 1`, `Drawn: 0`, `Lost: 3`,
   `Goals for: 6`, `Goals against: 7`,
   `Goal difference: -1`, `Points: 3`.

5. **Fixtures tab**: one row per result in fixture order, reading
   `<home> <home goals> - <away goals> <away>`, for example `Ashford 3 - 4 Brightwell`.

## Observable outcome the hidden test checks

Launch → the Table lists `Brightwell` first with `4 3 0 1 8 6 2 9` → scroll down → `Dunmore` is
last with `4 0 2 2 4 9 -5 2` → tap the `Eastvale` row → detail shows
`Goals for: 6` and `Points: 3` → back → Fixtures tab lists
`Ashford 0 - 2 Brightwell`.
