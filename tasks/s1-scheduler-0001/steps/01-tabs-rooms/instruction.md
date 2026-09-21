# Step 01 — tab shell, the room list, and the seeded schedule

Scaffold the app with bottom tab navigation, the seed data from the root contract, the
Rooms tab and the pushed room detail with its seeded schedule. No booking form and no
derived availability/utilization yet beyond the screen shells.

## Requirements

1. The app launches without a red screen or runtime error dialog.
2. The bottom tab bar shows exactly three tabs labeled `Rooms`, `Book`, `Settings`;
   `Rooms` is the initial tab.
3. Each tab screen renders without crashing and shows its heading text — `Rooms`, `Book`,
   `Settings` respectively. (These headings are permanent: they must still be present
   when the real UI arrives in steps 02/03, because every submission is graded against
   the full suite.) Placeholder body content on `Book` and `Settings` is your choice and
   is not asserted.
4. **Rooms tab**: one row per room in seed order (`Aurora`, `Boardroom`, `Fern`,
   `Huddle`, `Lumen`) showing the room name, `Seats <n>` (`Seats 12`, `Seats 20`,
   `Seats 6`, `Seats 4`, `Seats 8`), the equipment tags joined with a comma and a space
   (`Screen, VC`, `Screen, VC, Whiteboard`, `Whiteboard`, `Screen`, `VC, Whiteboard`),
   and the text `<n> bookings` (`3 bookings` for every room except `Lumen`, which shows
   `2 bookings`).
5. **Room detail** (pushed, header title = the room name, native back button): the text
   `Seats <n>`, the equipment line, and a `Schedule` section listing the room's seeded
   bookings sorted by start time as `<start>-<end> <title> (<attendees>)` — for `Aurora`
   that is `08:30-09:45 Design Review (8)`, `11:00-12:30 Sprint Planning (10)`,
   `14:15-15:05 Client Call (3)`, in that order.
6. The seed data from the root contract (the five rooms and the fourteen bookings) is
   checked into the repo as typed modules, with every time held as integer minutes from
   `08:00`. No `Date` objects, no clock or random calls (ground rules 1 and 9).

## Observable outcome the hidden test checks

Launch → tab bar shows `Rooms` / `Book` / `Settings` with the five room rows and their
seat counts → tap `Aurora` → detail shows `Seats 12` and the three seeded schedule rows
in start order → back → tapping each remaining tab renders its screen with its heading,
no crash at any point.
