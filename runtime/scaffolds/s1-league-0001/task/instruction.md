# LeagueTable — build a mobile league-standings app

You are a coding agent building a fresh iOS mobile app from the provided Expo scaffold
(Expo SDK 57, Expo Router, TypeScript). The product is a league tracker: a standings table
that is **entirely computed** from a list of match results, a fixtures list, a pushed team
detail screen, and a form for recording a new result — which recomputes the affected rows
and re-sorts the whole table.

The work is split into three steps (see `steps/01-tabs`, `steps/02-table-fixtures`,
`steps/03-record-settings`, each with its own `instruction.md`), followed by a final
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

1. **Nothing is stored, everything is computed.** The seed contains **only** teams and
   match results. Every played/won/drawn/lost count, every goals-for and goals-against
   total, every goal difference and every points value is derived from the result list.

2. **The points rule (exact).** A win is `3` points, a draw is `1`, a loss is `0`.

3. **The ordering rule (exact), applied in this order.** Sort teams by **points
   descending**; ties broken by **goal difference descending**; then by **goals for
   descending**; then by **team name A–Z**. All four levels decide a real pair in the seed
   data, so all four must be implemented.

4. **Signed goal difference.** Goal difference renders with a leading minus when negative
   (`-1`, `-7`), as a bare number when positive (`3`), and as `0` when zero. It never
   carries a leading plus.

5. **Recording a result recomputes and re-sorts.** Adding a result updates both teams' rows
   and re-sorts the entire table by the rule in ground rule 3. Rows do not keep their old
   positions.

6. **Deterministic data — no clocks, no randomness.** No `Date.now()`, `new Date()`,
   `Math.random()`, or uuid libraries anywhere in app code. No dates or time-of-day text is
   rendered anywhere. Every value on screen must be computable from this contract alone.

7. **Debounced one-shot recording.** The `Record` button is one-shot: a rapid double-tap
   records **exactly one** result. Disabling it briefly after press (≈250–300 ms) is one
   acceptable implementation. It takes effect on the single tap that triggers it — there is
   no confirmation dialog, alert, or intermediate screen, and the app never opens a native
   alert dialog at any point. `Record` is disabled while either score input is empty.

8. **Verbatim numeric input.** Both score inputs accept digits only and are interpreted as
   whole numbers of goals.

9. **State survives navigation.** Recorded results persist when the user navigates between
   tabs and pushes/pops screens (module-level/store state is sufficient; no backend, no
   disk persistence — a fresh install starts from the seed below).

10. **Navigation shape.** The app opens directly on the Table tab — no login, onboarding,
    or splash gate — and the table is interactive within two seconds of launch. The three
    tabs are a bottom tab bar. Tapping a team row **pushes** its detail screen (native
    stack header titled with the team name and a back button). Back returns to the tab bar.
    Every team row is tappable.

11. **Everything the user must reach stays on screen.** All ten table rows are reachable
    by scrolling the Table tab without horizontal scrolling, and while a score input is
    focused and the on-screen keyboard is up, both inputs and the `Record` button remain
    visible and tappable.

12. **The column labels stay visible.** The header row (`Team`, `P`, `W`, `D`, `L`, `GF`,
    `GA`, `GD`, `Pts`) stays **pinned at the top and visible while the team rows scroll
    beneath it**, so a row's numbers can always be read against their column labels.

13. **After recording, the recorded teams are brought into view.** Recording a result
    re-sorts the table; when the Table tab is next shown, the **home team's row is visible
    without the user scrolling manually**, wherever the re-sort placed it.

## Seed data (exact values — copy these verbatim)

Teams (ten, listed here alphabetically): `Ashford`, `Brightwell`, `Calder`, `Dunmore`,
`Eastvale`, `Fenwick`, `Garrick`, `Holloway`, `Ingleton`, `Jarrow`. **The table is longer
than one screen** — it scrolls, and the tests scroll it.

Results, in this fixture order (`home`, `away`, `home goals`, `away goals`):

| home | away | score (rendered with a plain hyphen) |
|---|---|---|
| Ashford | Brightwell | 0 - 2 |
| Brightwell | Calder | 2 - 0 |
| Calder | Dunmore | 2 - 2 |
| Dunmore | Eastvale | 0 - 3 |
| Eastvale | Fenwick | 0 - 1 |
| Fenwick | Garrick | 1 - 2 |
| Garrick | Holloway | 2 - 1 |
| Holloway | Ingleton | 3 - 2 |
| Ingleton | Jarrow | 3 - 0 |
| Jarrow | Ashford | 0 - 3 |
| Ashford | Dunmore | 4 - 2 |
| Brightwell | Eastvale | 4 - 2 |
| Calder | Fenwick | 1 - 2 |
| Dunmore | Garrick | 0 - 0 |
| Eastvale | Holloway | 1 - 2 |
| Fenwick | Ingleton | 2 - 1 |
| Garrick | Jarrow | 2 - 4 |
| Holloway | Ashford | 2 - 1 |
| Ingleton | Brightwell | 4 - 0 |
| Jarrow | Calder | 3 - 4 |

## Derived values (the tests assert these exact strings and this order)

**The table at the seed**, in order, as `Team P W D L GF GA GD Pts`:

| # | team | P | W | D | L | GF | GA | GD | Pts |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Brightwell | 4 | 3 | 0 | 1 | 8 | 6 | 2 | 9 |
| 2 | Holloway | 4 | 3 | 0 | 1 | 8 | 6 | 2 | 9 |
| 3 | Fenwick | 4 | 3 | 0 | 1 | 6 | 4 | 2 | 9 |
| 4 | Garrick | 4 | 2 | 1 | 1 | 6 | 6 | 0 | 7 |
| 5 | Ingleton | 4 | 2 | 0 | 2 | 10 | 5 | 5 | 6 |
| 6 | Ashford | 4 | 2 | 0 | 2 | 8 | 6 | 2 | 6 |
| 7 | Calder | 4 | 1 | 1 | 2 | 7 | 9 | -2 | 4 |
| 8 | Eastvale | 4 | 1 | 0 | 3 | 6 | 7 | -1 | 3 |
| 9 | Jarrow | 4 | 1 | 0 | 3 | 7 | 12 | -5 | 3 |
| 10 | Dunmore | 4 | 0 | 2 | 2 | 4 | 9 | -5 | 2 |

Every tie-break level decides a real pair here, so all four must work:

- `Brightwell` above `Holloway` — decided by **name A–Z**.
- `Holloway` above `Fenwick` — decided by **goals for** (8 v 6).
- `Fenwick` above `Garrick` — decided by **points** (9 v 7).
- `Garrick` above `Ingleton` — decided by **points** (7 v 6).
- `Ingleton` above `Ashford` — decided by **goal difference** (5 v 2).
- `Ashford` above `Calder` — decided by **points** (6 v 4).
- `Calder` above `Eastvale` — decided by **points** (4 v 3).
- `Eastvale` above `Jarrow` — decided by **goal difference** (-1 v -5).
- `Jarrow` above `Dunmore` — decided by **points** (3 v 2).

**Worked example — recording a result.** Recording the return fixture
`Calder 3 – 0 Ashford` changes exactly two rows:

- `Calder` becomes `5 2 1 2 10 9 1 7`
- `Ashford` becomes `5 2 0 3 8 9 -1 6`

and the table re-sorts to: 1 `Brightwell`, 2 `Holloway`, 3 `Fenwick`, 4 `Calder`, 5 `Garrick`, 6 `Ingleton`, 7 `Ashford`, 8 `Eastvale`, 9 `Jarrow`, 10 `Dunmore`.

## Pinned UI text (tests match these exactly — render them verbatim)

- Tab bar labels: `Table`, `Fixtures`, `Settings`. Each tab screen shows its heading text:
  `Table`, `Fixtures`, `Settings`.
- **Table tab**: a header row with the column labels `Team`, `P`, `W`, `D`, `L`, `GF`,
  `GA`, `GD`, `Pts`; then one row per team in the order of ground rule 3, showing the
  position number, the team name, and those nine values.
- **Team detail screen** (pushed): header title is the team name; the lines
  `Played: <n>`, `Won: <n>`, `Drawn: <n>`, `Lost: <n>`, `Goals for: <n>`,
  `Goals against: <n>`, `Goal difference: <n>` and `Points: <n>`. For `Eastvale` that is
  `Played: 4`, `Won: 1`, `Drawn: 0`, `Lost: 3`,
  `Goals for: 6`, `Goals against: 7`,
  `Goal difference: -1` and `Points: 3`.
- **Fixtures tab**: one row per recorded result in fixture order — the seeded results in
  the order given in the seed table, and **a newly recorded result appended as the last
  row**, so recording one always adds a row at the bottom of the list. (Without this the
  position of a new result is unspecified: an implementation that inserted it anywhere else
  would still satisfy every other line here, and the tests assert where it lands.) Each row
  reads
  `<home> <home goals> - <away goals> <away>` (a plain hyphen between the scores). Below
  them, a `Record a result` section containing: a row labelled `Home` followed by one
  tappable button per team, a row labelled `Away` followed by the same buttons, two score
  inputs with placeholders `0`, and a button labelled `Record`. The team pickers are
  **plain tappable buttons showing the team names**, not a wheel picker, dropdown or
  modal — the selected team in each row is visually marked and its name is readable
  without opening anything. The rows scroll horizontally if the buttons do not fit. The team pickers are **plain tappable buttons showing the team names**, not
  a wheel picker, dropdown or modal — the selected team in each row is visually marked
  and its name is readable without opening anything.
- **Settings tab**: a `Season` block with the two lines `Matches played: <n>` and
  `Goals scored: <n>`.

## Final acceptance

The final e2e journey: launch → Table tab shows `Brightwell` 1st with `4 3 0 1 8 6 2 9`; the table
is longer than one screen, and scrolling to the bottom shows `Dunmore` 10th with
`4 0 2 2 4 9 -5 2` while the column-label header row stays pinned at the top → tap the
`Eastvale` row → detail shows `Goals for: 6`, `Goal difference: -1`
and `Points: 3` → back → Fixtures tab → record `Calder` `3` - `0` `Ashford` →
Table tab → the `Calder` row is visible without further scrolling, the order is now
`Brightwell`, `Holloway`, `Fenwick`, `Calder`, `Garrick`…, and `Calder` reads `5 2 1 2 10 9 1 7` →
Settings tab → `Matches played: 21` and `Goals scored: 73`. It must complete without
manual intervention.
