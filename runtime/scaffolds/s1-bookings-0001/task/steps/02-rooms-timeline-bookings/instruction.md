# Step 02 — room list with utilisation, the room day screen, the bookings list

Implement the Rooms tab, the pushed room day screen (read-only in this step), and the
Bookings tab per the root contract's seed data, ground rules, and pinned UI text.

## Requirements

1. **Room list** (Rooms tab): one row per seeded room, in seed order, showing the room
   `name`, `Seats <capacity>`, `Today: <n>% booked` (ground rule 8: confirmed seat-slots
   today over `16 × capacity`, rounded half-up) and `Next free: <HH:MM>` (ground rule 9).
   At the seed: `Focus Pod` → `Seats 1`, `Today: 25% booked`, `Next free: 11:00`;
   `Huddle` → `Seats 1`, `Today: 38% booked`, `Next free: 12:00`; `Boardroom` →
   `Seats 1`, `Today: 38% booked`, `Next free: 09:00`; `Open Desks` → `Seats 3`,
   `Today: 29% booked`, `Next free: 09:00`. Tapping a row pushes that room's day screen.

2. **Room day screen** (pushed, header title = the room's `name`, native back button,
   subtitle `Mon 6 Apr`): today's confirmed and waitlisted bookings for that room, one
   row each reading `<start> to <end> <displayName>` (`You` for yours) with the suffix
   ` (waitlisted)` on waitlisted rows, in ascending start, confirmed before waitlisted at
   the same start, then by `order`. Cancelled bookings are not shown. From the seed the
   `Huddle` screen reads `09:00 to 11:00 Ben Okafor`, `11:00 to 12:00 You`,
   `11:00 to 12:30 Emma Lindqvist (waitlisted)`, `11:00 to 12:00 Dev Patel (waitlisted)`.
   The composer described in step 03 may be present but is not exercised in this step.

3. **Bookings tab**: your bookings in ascending date, then start, then `order` — thirteen
   rows at the seed, exactly the table in the root contract's derived values. Each row
   shows the first line `<room name> <day label> <start> to <end>` and the second line
   `confirmed`, `waitlisted`, `cancelled, Fee $<amount>` or `cancelled, No fee`. The
   first row reads `Focus Pod Mon 6 Apr 10:00 to 11:00` / `confirmed`; the fourth reads
   `Huddle Mon 6 Apr 14:00 to 15:00` / `cancelled, Fee $10.00`; the last reads
   `Boardroom Fri 10 Apr 14:00 to 16:00` / `confirmed`.

4. **The Bookings list does not fit on one screen.** Thirteen rows scroll (ground rule
   16); the last row is reachable by scrolling. The `Bookings` tab item shows no badge at
   the seed (ground rule 17: zero waitlisted bookings of yours).

5. The seed state is the same on every launch (store state; no backend, no disk
   persistence).

## Observable outcome the hidden test checks

Launch → Rooms lists the four rooms with their `Seats`, `Today` and `Next free` lines →
tap `Huddle` → the day screen shows its four timeline rows with the two `(waitlisted)`
rows → back → Bookings tab → the first row reads `Focus Pod Mon 6 Apr 10:00 to 11:00`
and `confirmed`, `Huddle Mon 6 Apr 14:00 to 15:00` reads `cancelled, Fee $10.00`, and
after scrolling down the last row reads `Boardroom Fri 10 Apr 14:00 to 16:00`.
