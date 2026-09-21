# Step 02 — the booking form and conflict detection

Implement the Book tab per the root contract's ground rules 3, 4, 5, 10, 11, 12 and 15,
and couple it back into step 01's views: a successful booking appears on its room's
schedule and in the Rooms-tab counts immediately.

## Requirements

1. **Book tab**: five room chips labelled with the room names, `Aurora` selected at
   launch, the current selection echoed as the line `Room: <name>`; text inputs with the
   hint texts `Meeting title`, `Start (HH:MM)`, `End (HH:MM)` and `Attendees`; a
   `Request booking` button; and a result line rendered after each request. Tapping an
   already-selected chip is harmless, and changing the room never changes the inputs.

2. **Validation order — capacity first, then overlap** (ground rule 4, binding):
   - If the attendee count exceeds the room's capacity the result line is
     `Rejected: <attendees> attendees exceeds capacity <capacity>` — even when the slot
     also overlaps. Requesting `Huddle` `12:00-13:00` with 6 attendees shows
     `Rejected: 6 attendees exceeds capacity 4`, not an overlap message, although the
     slot overlaps `Coaching`. An attendee count **equal** to capacity is allowed.
   - Otherwise, if the slot overlaps an existing booking in the same room
     (`start < existing.end` AND `end > existing.start`; touching endpoints are legal),
     the result line is `Rejected: overlaps <title> (<start>-<end>)`, naming the
     earliest-starting overlapped booking. Requesting `Aurora` `12:00-13:00` shows
     `Rejected: overlaps Sprint Planning (11:00-12:30)`.
   - Otherwise the booking is created and the result line is
     `Booked <room> <start>-<end> for <attendees>`. Requesting `Aurora` `09:45-11:00`
     with 6 attendees — touching `Design Review`'s end and `Sprint Planning`'s start,
     conflicting with neither — shows `Booked Aurora 09:45-11:00 for 6`.

3. **A rejection changes nothing**; a success inserts the booking into its room's
   schedule **in start-time order** and bumps the room's `<n> bookings` row text (after
   the example above `Aurora` reads `4 bookings`). No confirmation dialog, no native
   alert, ever; `Request booking` is one-shot (debounced).

4. **Inputs** clear on focus, keep their values after a rejection, and reset to empty
   after a success (ground rule 11). An empty title books as `Booking`. The
   `Request booking` button and the result line stay visible while the keyboard is open;
   requesting dismisses the keyboard.

## Observable outcome the hidden test checks

Book tab shows the chips, `Room: Aurora`, the four hint inputs and `Request booking` →
select `Huddle`, request `12:00-13:00` for 6 → `Rejected: 6 attendees exceeds capacity 4`
→ select `Aurora` (inputs kept) and request → `Rejected: overlaps Sprint Planning
(11:00-12:30)` → change the times to `09:45`-`11:00` and request →
`Booked Aurora 09:45-11:00 for 6` → Rooms tab shows `Aurora` at `4 bookings`.
