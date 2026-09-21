# Step 03 — booking composer, cancellation with promotion, settings totals

Implement the booking composer on the room day screen, the `Cancel` action on the
Bookings tab with the fee and waitlist-promotion rules, and the Settings tab per the
root contract.

## Requirements

1. **Composer** (room day screen, pinned at the bottom): a start input with placeholder
   `HH:MM`, a length input with placeholder `Minutes`, a `Book` button, and a status
   line beneath them. `Book` is one-shot (debounced) and applies ground rule 5 exactly:
   `Outside opening hours` or `You already have a booking at that time` on the status
   line with nothing created **and both inputs cleared** (so the next attempt types into
   empty inputs), else a **confirmed** booking when the room has a free seat
   on every slot of the range, else a **waitlisted** one. A created booking's row is
   visible in the timeline without manual scrolling, both inputs clear, and the status
   line clears. From the seed on `Focus Pod`: `10:30` for `30` is refused with
   `You already have a booking at that time`; then `09:00` for `60` is **waitlisted**
   (it ends exactly when your `10:00` booking starts — not a self-overlap — but Ana Costa
   holds the room), so the timeline gains `09:00 to 10:00 You (waitlisted)`, the
   `Bookings` badge reads `1`, and the Focus Pod Rooms row is unchanged. On `Boardroom`,
   `16:00` for `60` is **confirmed** (it starts exactly when your `15:00 to 16:00` booking
   ends): the timeline gains `16:00 to 17:00 You` and the Rooms row becomes
   `Today: 50% booked`.

2. **Cancel**: tapping a Bookings row pushes the booking screen — header title
   `<room name> <day label> <start> to <end>`, a status line reading what the row's second
   line reads, and for a confirmed or waitlisted booking one button labelled
   `Cancel booking` (a cancelled booking's screen shows no button; rows carry no buttons).
   Tapping `Cancel booking` is one-shot and applies ground rules 6 and 7 on that tap: the
   status line (and the row, on return) becomes `cancelled, Fee $<half the price>` when the
   booking starts 24 hours or less after `NOW` (`start ≤ 2026-04-07 09:00`, the boundary
   itself included), `cancelled, No fee` otherwise, and — for a confirmed booking — the
   room's waitlist for that date is walked in ascending `order`, promoting every entry
   that now fits. From the seed, cancelling `Huddle Mon 6 Apr 11:00 to 12:00` reads
   `cancelled, Fee $10.00` and promotes `Emma Lindqvist` (`11:00 to 12:30`, order 10)
   while `Dev Patel` (order 11) stays waitlisted; the Huddle Rooms row becomes
   `Today: 44% booked` with `Next free: 12:30`, and the Huddle timeline reads
   `11:00 to 12:30 Emma Lindqvist` with no suffix. Cancelling
   `Boardroom Tue 7 Apr 09:00 to 10:00` (exactly 24 hours after `NOW`) reads
   `cancelled, Fee $22.50`; cancelling `Focus Pod Tue 7 Apr 14:00 to 15:00` reads
   `cancelled, No fee`.

3. **Settings tab**: a `Totals` block with `Booked this week: <h>h <mm>m` (the hours of
   your confirmed bookings Monday to Friday) and `Fees charged: $<amount>` (the fees on
   your cancelled bookings) — with the seed alone, `Booked this week: 15h 30m` and
   `Fees charged: $10.00`; after cancelling bk-4 alone, `Booked this week: 14h 30m` and
   `Fees charged: $20.00`. A `Display` section holds one row labelled `Hide cancelled`
   with a toggle switch; turning it on makes the Bookings tab omit every cancelled row,
   and changes nothing else anywhere.

4. Created bookings, cancellations, promotions and the switch persist across
   navigation: leaving a tab and returning shows the same rows, the same totals, and the
   same switch position (store state; no backend, no disk persistence).

## Observable outcome the hidden test checks

Rooms → `Focus Pod` → `10:30` / `30` → `Book` → status line
`You already have a booking at that time` → `09:00` / `60` → `Book` → the row
`09:00 to 10:00 You (waitlisted)` is visible → back → Bookings tab → badge `1`, first row
`Focus Pod Mon 6 Apr 09:00 to 10:00` / `waitlisted` → tap the row
`Huddle Mon 6 Apr 11:00 to 12:00` → booking screen titled `Huddle Mon 6 Apr 11:00 to 12:00`
→ `Cancel booking` → `cancelled, Fee $10.00` → back → the row reads `cancelled, Fee $10.00`
→ Rooms tab → `Huddle`
reads `Today: 44% booked` and `Next free: 12:30` → tap `Huddle` → `11:00 to 12:30
Emma Lindqvist` with no waitlisted suffix, `11:00 to 12:00 Dev Patel (waitlisted)` →
back → Settings → `Booked this week: 14h 30m` and `Fees charged: $20.00` → turn on
`Hide cancelled` → Bookings tab → the Huddle 14:00 row is gone → Settings → Bookings →
still gone.
