# Step 02 — the board, ticket detail, and My Work

Implement the Board tab, the pushed ticket detail screen, and the My Work tab per the root
contract's seed data, ground rules, and pinned UI text.

## Requirements

1. **Board** (Board tab): three column sections in status order — `To Do`,
   `In Progress`, `Done` — each showing beneath its name the header line
   `<n> ticket(s), <p> point(s)`. With the seed alone: `4 tickets, 18 points`,
   `3 tickets, 16 points`, `4 tickets, 11 points`.

2. **Column ordering**: within each column the rows follow ground rule 2 — priority
   descending (`High`, `Medium`, `Low`), ties broken by ticket number ascending. With the
   seed alone: `To Do` is #101, #104, #102, #103; `In Progress` is #106, #105, #107;
   `Done` is #110, #109, #111, #108. Each row shows `#<number>`, the `title`, the
   `priority`, and `<p> pts`.

3. **Ticket detail** (pushed, header title `Ticket`, native back button): tapping any
   ticket row opens it, showing `#<number>` and `title` at the top, then `Status: …`,
   `Priority: …`, `Points: …` and `Assignee: …`.

4. **My Work tab**: the tickets assigned to `You`, grouped under the status names in seed
   order, each row showing `#<number>` and the `title`. With the seed alone this is #102
   under `To Do`, #105 under `In Progress`, #109 under `Done`. Empty state text:
   `Nothing assigned to you.`.

5. Every ticket row, on the Board and in My Work, is tappable and pushes the same detail
   screen.

## Observable outcome the hidden test checks

Launch → Board shows the three columns with their header lines → the `To Do` column lists
#101 before #104 (both `High`, tie broken by number) → tap the `#105` row → detail shows
`Status: In Progress`, `Points: 3`, `Assignee: You` → back → `My Work` tab lists #102,
#105 and #109 grouped under their statuses.
