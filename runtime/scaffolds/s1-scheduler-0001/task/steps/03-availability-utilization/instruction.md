# Step 03 — derived availability, utilization, and settings totals

Implement the availability and utilization derivations per the root contract. All of it
is derived state (ground rule 6): every figure below recomputes immediately when a
booking is made in step 02's form.

## Requirements

1. **Availability on the room detail** (ground rule 7): below the `Schedule` section, an
   `Availability` section listing the free gaps between `08:00`, the sorted bookings and
   `18:00` as `<start>-<end> (<n> min)`, rendering only gaps longer than 0 minutes.

   At the seed: `Aurora` shows `08:00-08:30 (30 min)`, `09:45-11:00 (75 min)`,
   `12:30-14:15 (105 min)`, `15:05-18:00 (175 min)`; `Fern` shows exactly three gaps —
   `08:00-10:00 (120 min)`, `11:45-15:30 (225 min)`, `16:15-18:00 (105 min)` — with
   **no** row between its touching `11:00` bookings; `Huddle` shows exactly two —
   `08:25-12:15 (230 min)`, `13:05-17:10 (245 min)` — with **no** gap starting at
   `08:00` or ending at `18:00`.

2. **The booked line on the room detail**: `Booked <m> min (<p>%)` above the `Schedule`
   section, with the percentage per ground rule 8 (integer tenths, rounded half-up,
   always one decimal). At the seed: `Booked 215 min (35.8%)` on `Aurora`,
   `Booked 125 min (20.8%)` on `Huddle`, `Booked 160 min (26.7%)` on `Lumen` — `26.7`,
   not the truncated `26.6`.

3. **Settings tab**: an `Office` block with `Rooms: 5`, `Bookings: <n>`,
   `Booked: <m> min`, `Utilization: <p>%`, then a `By room` block with one line per room
   in seed order as `<name>: <m> min, <p>%`. At the seed the office lines read
   `Bookings: 14`, `Booked: 935 min`, `Utilization: 31.2%` and the room lines read
   `Aurora: 215 min, 35.8%`, `Boardroom: 285 min, 47.5%`, `Fern: 150 min, 25.0%`,
   `Huddle: 125 min, 20.8%`, `Lumen: 160 min, 26.7%`.

4. **Coupling to bookings.** After booking `Aurora` `09:45-11:00` (the root contract's
   worked example, 12 attendees — exactly capacity, allowed) the 75-minute gap disappears
   (three gaps remain), Aurora's booked line reads `Booked 290 min (48.3%)`, and Settings
   reads `Bookings: 15`, `Booked: 1010 min`, `Utilization: 33.7%`,
   `Aurora: 290 min, 48.3%` — `33.7`, not the truncated `33.6`.

5. Everything remains integer arithmetic (ground rules 2 and 8) and every figure
   persists across navigation (ground rule 13).

## Observable outcome the hidden test checks

`Aurora` detail shows `Booked 215 min (35.8%)` and its four availability gaps → `Fern`
detail shows exactly three gaps with none between the touching bookings → Settings shows
the seed `Office` block and all five `By room` lines → book `Aurora` `09:45-11:00` for 12
→ `Booked Aurora 09:45-11:00 for 12` → Settings now shows `Bookings: 15`,
`Booked: 1010 min`, `Utilization: 33.7%` and `Aurora: 290 min, 48.3%`.
