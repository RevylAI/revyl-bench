# TaskBoard — build a mobile project-tracker app

You are a coding agent building a fresh iOS mobile app from the provided Expo scaffold
(Expo SDK 57, Expo Router, TypeScript). The product is a project tracker: a board of
tickets grouped into three status columns with per-column ticket and story-point totals,
a pushed ticket detail screen where a ticket can be moved between statuses or assigned to
you, a "My Work" inbox of everything assigned to you, and a settings screen with
completion totals that persist across navigation.

The work is split into three steps (see `steps/01-tabs`, `steps/02-board-mywork`,
`steps/03-move-assign-settings`, each with its own `instruction.md`), followed by a final
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

1. **Integer story points.** Every ticket carries an integer `points` value. All totals
   are integer sums. No floating-point arithmetic anywhere.

2. **The ordering rule (exact).** Within any list of tickets, order by **priority
   descending** (`High`, then `Medium`, then `Low`), and break ties by **ticket number
   ascending**. This applies to every board column and to the My Work list. A ticket that
   changes status is re-sorted into its new column by this rule — it does **not** simply
   append to the end.

3. **The percentage rule (exact).** `Complete` is the Done point total as a percentage of
   the overall point total, **rounded half-up to a whole number** — no decimal places, and
   a trailing `%`. Worked example: `11` of `45` points is `24.444…%`, which renders as
   `24%`.

4. **Deterministic data — no clocks, no randomness.** No `Date.now()`, `new Date()`,
   `Math.random()`, or uuid libraries anywhere in app code. No dates or time-of-day text
   is rendered anywhere. Every value on screen must be computable from this contract alone.

5. **Moving a ticket moves its points.** Changing a ticket's status changes both the
   source and the destination column's ticket count and point total, and (when Done is
   involved) the `Complete` percentage. The overall `Total points` never changes.

6. **Assigning has no side effects beyond My Work and the ticket itself.** Assigning a
   ticket to you changes the ticket's assignee and the My Work list, and **nothing else** —
   no column header, no total, and no percentage changes, because assignment moves no
   points between columns.

7. **Debounced one-shot actions.** The status buttons and `Assign to me` are one-shot: a
   rapid double-tap performs the action **exactly once**. Disabling the control briefly
   after press (≈250–300 ms) is one acceptable implementation. They take effect **on the
   single tap that triggers them** — there is no confirmation dialog, alert, or
   intermediate screen, and the app never opens a native alert dialog at any point.
   Moving a ticket to the status it already has, or assigning a ticket already assigned to
   you, is a no-op that changes nothing. **The detail screen stays open after either
   action** — it does not pop back on its own; the user returns with the back button.

8. **Textual state summaries.** Column headers, the totals, and the completion percentage
   are exact text strings (pinned below) — never encoded only in colours, icons, or bar
   widths. (Icons and bars may accompany the text.)

9. **State survives navigation.** Status changes and assignments persist when the user
   navigates between tabs and pushes/pops screens (module-level/store state is sufficient;
   no backend, no disk persistence — a fresh install starts from the seed below).

10. **Navigation shape.** The app opens directly on the Board tab — no login, onboarding,
    or splash gate — and the board is interactive within two seconds of launch. The three
    tabs are a bottom tab bar. Tapping any ticket row **pushes** its detail screen (native
    stack header titled `Ticket` with a back button). Back returns to where you came from.
    Every ticket row, on the Board and in My Work, is tappable to open its detail.

11. **Everything the user must reach stays on screen.** The Board tab is a single
    vertically scrollable view containing all three column sections in status order, so
    the `Done` section is reachable by scrolling down (it sits below roughly nine rows of
    content). A ticket row's detail screen shows the status buttons and `Assign to me`
    without horizontal scrolling.

12. **The column heading you are inside stays visible.** While the Board is scrolled, the
    status name of the section currently under the top of the list stays **pinned at the
    top of the screen**, above the rows. Scrolled to the very bottom of the board the
    viewport still begins inside `In Progress` (there are not enough `Done` rows below it
    to fill a screen), so `In Progress` is what stays pinned there, with the `Done` section
    visible beneath it. Without pinning, the top of the screen would show ticket rows with
    no status name above them.

13. **The My Work tab carries a badge.** The `My Work` item in the bottom tab bar shows a
    small numeric badge with the number of tickets assigned to `You`. With the seed alone
    that badge reads `3`. It updates when a ticket is assigned, and shows no badge at all
    when the count is zero.

## Seed data (exact values — copy these verbatim)

Members (`id`, `displayName`). The signed-in user is `u-you`.

| id | displayName |
|---|---|
| u-you | You |
| u-rhea | Rhea Kapoor |
| u-tomas | Tomas Lindqvist |
| u-ada | Ada Okonkwo |

Statuses, in this order: `To Do`, `In Progress`, `Done`.
Priorities, highest first: `High`, `Medium`, `Low`.

Tickets (`number`, `title`, `status`, `assignee`, `points`, `priority`):

| # | title | status | assignee | points | priority |
|---|---|---|---|---|---|
| 101 | Fix login redirect loop | To Do | Rhea Kapoor | 3 | High |
| 102 | Add CSV export to reports | To Do | You | 5 | Medium |
| 103 | Upgrade image pipeline | To Do | Tomas Lindqvist | 8 | Low |
| 104 | Crash on empty search | To Do | Ada Okonkwo | 2 | High |
| 105 | Dark mode audit | In Progress | You | 3 | Medium |
| 106 | Rate limit the public API | In Progress | Rhea Kapoor | 5 | High |
| 107 | Migrate settings storage | In Progress | Tomas Lindqvist | 8 | Medium |
| 108 | Retire legacy feature flags | Done | Ada Okonkwo | 2 | Low |
| 109 | Onboarding copy pass | Done | You | 1 | Medium |
| 110 | Cache warm on deploy | Done | Rhea Kapoor | 5 | High |
| 111 | Fix flaky checkout test | Done | Tomas Lindqvist | 3 | Medium |

## Derived values (the tests assert these exact strings and orders)

**Board columns**, with their header lines and their rows in the order of ground rule 2:

| column | header | rows, in order |
|---|---|---|
| `To Do` | `4 tickets, 18 points` | #101, #104, #102, #103 |
| `In Progress` | `3 tickets, 16 points` | #106, #105, #107 |
| `Done` | `4 tickets, 11 points` | #110, #109, #111, #108 |

Note the tie-breaks: in `To Do`, #101 and #104 are both `High` so #101 comes first; in
`In Progress`, #105 and #107 are both `Medium` so #105 comes first; in `Done`, #109 and
#111 are both `Medium` so #109 comes first.

**My Work** (assigned to `You`, ordered by status in seed order, then by the rule in
ground rule 2): #102 (`To Do`), #105 (`In Progress`), #109 (`Done`).

**Settings totals**: `Total points: 45`, `Done points: 11`, `Complete: 24%`.

**Ticket detail — worked example.** Opening #105 `Dark mode audit` from the seed renders
`Status: In Progress`, `Priority: Medium`, `Points: 3` and `Assignee: You`. Opening #101
`Fix login redirect loop` renders `Status: To Do`, `Priority: High`, `Points: 3` and
`Assignee: Rhea Kapoor`.

**Worked example — moving a ticket.** Moving #105 `Dark mode audit` (3 points) from
`In Progress` to `Done`:

- `In Progress` becomes `2 tickets, 13 points`; `Done` becomes `5 tickets, 14 points`;
  `To Do` is unchanged at `4 tickets, 18 points`.
- The `Done` column re-sorts to #110, **#105**, #109, #111, #108 — #105 is `Medium`, so it
  lands **between** #110 (`High`) and #109 (`Medium`, higher number). It does not go last.
- `Done points: 14` and `Complete: 31%` (`14` of `45` is `31.111…%`).
- In My Work, #105 now appears in the `Done` group.

**Worked example — assigning a ticket.** Assigning #101 `Fix login redirect loop` to you
adds it to My Work at the **top** (it is `To Do` and `High`), giving #101, #102, #105,
#109. Every column header, every total and the percentage are unchanged.

## Pinned UI text (tests match these exactly — render them verbatim)

- Tab bar labels: `Board`, `My Work`, `Settings`. Each tab screen shows its heading text:
  `Board`, `My Work`, `Settings`. The `My Work` tab item carries the numeric badge from
  ground rule 13.
- **Board tab**: three column sections in status order, each showing the status name
  (`To Do`, `In Progress`, `Done`) and beneath it the header line
  `<n> ticket(s), <p> point(s)` — singular `1 ticket` / `1 point` when the count is one.
  Each ticket row shows `#<number>`, the `title`, the `priority`, and `<p> pts`.
- **Ticket detail screen** (pushed): header title `Ticket`; the `#<number>` and `title` at
  the top, then the lines `Status: <status>`, `Priority: <priority>`, `Points: <points>`
  and `Assignee: <displayName>`; a `Move to` section with three buttons labelled
  `To Do`, `In Progress`, `Done`; and a button labelled `Assign to me`.
- **My Work tab**: the tickets assigned to `You`, grouped under the status names in seed
  order, each row showing `#<number>` and the `title`. When empty, the text
  `Nothing assigned to you.`.
- **Settings tab**: a `Totals` block with the three lines `Total points: <n>`,
  `Done points: <n>` and `Complete: <n>%`.

## Final acceptance

The final e2e journey: launch → Board tab shows `To Do` `4 tickets, 18 points`,
`In Progress` `3 tickets, 16 points`, `Done` `4 tickets, 11 points` → tap the `#105`
row → detail shows `Status: In Progress` and `Points: 3` → tap `Done` in the `Move to`
section → back → `In Progress` reads `2 tickets, 13 points` and `Done` reads
`5 tickets, 14 points`, with `#105` shown second in the `Done` column → tap the `#101`
row → `Assign to me` → back → the column headers are unchanged → `My Work` tab lists
`#101` first, then `#102`, `#105`, `#109` → `Settings` tab shows `Total points: 45`,
`Done points: 14`, `Complete: 31%`. It must complete without manual intervention.
