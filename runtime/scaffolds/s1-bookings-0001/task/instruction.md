# RoomDesk — build a mobile room-booking app

You are a coding agent building a fresh iOS mobile app from the provided Expo scaffold
(Expo SDK 57, Expo Router, TypeScript). The product is a room-booking app for a small
coworking space: four bookable rooms, a week of reservations in 30-minute slots, a
per-room daily timeline with a booking composer, a waitlist that promotes automatically
when a cancellation frees a slot, a cancellation fee keyed to a fixed clock, and a
settings screen with running totals that persist across navigation.

The work is split into three steps (see `steps/01-tabs`,
`steps/02-rooms-timeline-bookings`, `steps/03-book-cancel-settings`, each with its own
`instruction.md`), followed by a final end-to-end acceptance run. Complete the steps in
order.

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

**These screens do not all fit on one phone.** The Bookings list is longer than the
display, and the tests scroll. Verify your work by looking at the running app on the
device, not by reasoning about the code — layout, scroll position, keyboard behaviour and
badge rendering are graded from screenshots.

## Ground rules (binding — the tests depend on these)

1. **The clock is a constant.** The app's notion of "now" is fixed: `NOW` is
   **Monday 2026-04-06 at 09:00**. Today is `2026-04-06`. The working week is Monday
   `2026-04-06` through Friday `2026-04-10`. No `Date.now()`, `new Date()`,
   `Math.random()` or uuid libraries anywhere in app code. Dates are stored as
   `YYYY-MM-DD` strings and rendered as `Mon 6 Apr`, `Tue 7 Apr`, `Wed 8 Apr`,
   `Thu 9 Apr`, `Fri 10 Apr`. Times are `HH:MM` strings on a 24-hour clock.

2. **Opening hours and slots.** Every room is bookable from `09:00` to `17:00`, in
   30-minute slots: a day has **16 slots** per room. A booking starts on a slot boundary
   (`09:00`, `09:30`, …), lasts a whole number of slots, and ends no later than `17:00`.
   A time range renders as `<start> to <end>` (`10:00 to 11:00`).

3. **Overlap is half-open.** A booking occupies `[start, end)`: it holds every slot from
   `start` up to but **not including** `end`. Two bookings overlap only when one starts
   strictly before the other ends **and** vice versa. A booking ending at `10:00` does
   **not** overlap a booking starting at `10:00`.

4. **Capacity.** Each room has a `capacity`: how many bookings it holds **at the same
   time**. `Focus Pod`, `Huddle` and `Boardroom` hold one; `Open Desks` holds three. A
   range is **free** in a room when every slot in it has fewer than `capacity` confirmed
   bookings; otherwise the room is **full** for that range. Waitlisted and cancelled
   bookings never count toward capacity.

5. **Booking rule (exact, in this order).** Tapping `Book` with a start time `S` and a
   length of `L` minutes:
   - if `S` is not on a slot boundary, `L` is not a positive multiple of 30, `S` is before
     `09:00` or `S + L` is after `17:00` → nothing is created and the status line reads
     `Outside opening hours`;
   - else if the range `[S, S+L)` overlaps **any** of your own confirmed **or waitlisted**
     bookings on that date, in **any** room → nothing is created and the status line reads
     `You already have a booking at that time`;
   - else if the range is free in the room → a **confirmed** booking is created;
   - else → a **waitlisted** booking is created.
   A created booking is yours, for that room and date, with `order = (current maximum) + 1`
   and an id from a counter (`bk-23`, `bk-24`, …). The status line is cleared when a
   booking is created.

6. **Cancellation and the fee (exact).** Every booking has a price: the room's hourly
   rate × its length in hours (`Boardroom` for one hour is `$45.00`; `Focus Pod` for 30
   minutes is `$6.00`). Cancelling a **confirmed** booking charges a fee of **half its
   price** when the booking starts **24 hours or less** after `NOW` — that is, when
   `start ≤ Tuesday 2026-04-07 09:00`. A booking starting at exactly `2026-04-07 09:00`
   is charged. A booking starting later than that is cancelled with **no fee**.
   Cancelling a **waitlisted** booking is always free and never promotes anyone.

7. **Waitlist promotion (exact).** When a confirmed booking is cancelled, walk that
   room's waitlisted bookings **for that date** in ascending `order`. Each one whose range
   is now free (ground rule 4) becomes **confirmed**, and counts toward capacity for the
   ones checked after it. The rest stay waitlisted. Promotion happens on the same tap as
   the cancellation and changes every screen that shows the room: its timeline, its
   Rooms-tab row, and the promoted user's status.

8. **Utilisation (exact).** A room's `Today` figure is its confirmed seat-slots today
   divided by `16 × capacity`, as a percentage **rounded half-up to a whole number**:
   `37.5%` renders as `38%`, `29.17%` as `29%`, `43.75%` as `44%`. A booking of 2 slots
   is 2 seat-slots regardless of who holds it.

9. **Next free (exact).** A room's `Next free` is the earliest slot start today, from
   `09:00` onwards, at which the room has a free seat (fewer than `capacity` confirmed
   bookings on that slot) — `Next free: 09:00` when the first slot is free, and
   `Next free: none today` when no slot is.

10. **Integer cents everywhere.** Prices and fees are integer cents rendered as
    `$<dollars>.<cents>` with exactly two decimals (`$6.00`, `$22.50`). Rates are whole
    dollars, so every price and every half-price fee is an exact number of cents.

11. **Debounced one-shot Book / Cancel booking, applied immediately.** `Book` and the
    booking screen's `Cancel booking` are one-shot: a rapid double-tap performs the action
    **exactly once**.
    Disabling the control briefly after press (≈250–300 ms) is one acceptable
    implementation. `Book` is disabled while either composer input is empty or
    whitespace; a successful booking clears both inputs. Both controls take effect **on
    the single tap that triggers them** — there is no confirmation dialog, alert,
    "are you sure?" step, or intermediate screen, and the app never opens a native
    alert/confirm dialog at any point.

12. **Verbatim text input.** The start input accepts `HH:MM`; the length input accepts
    digits only and is interpreted as minutes (`60` → 60 minutes). Neither input
    auto-corrects or auto-capitalizes.

13. **Textual state summaries.** Every status, percentage, time and total is an exact text
    string (pinned below) — never encoded only in colours, icons, or bar widths.

14. **State survives navigation.** Created bookings, cancellations, promotions and the
    `Hide cancelled` switch persist when the user navigates between tabs and
    pushes/pops screens (module-level/store state is sufficient; no backend, no disk
    persistence — a fresh install starts from the seed below).

15. **Navigation shape.** The app opens directly on the Rooms tab — no login, onboarding,
    or splash gate — and the room list is interactive within two seconds of launch. The
    three tabs are a bottom tab bar. Tapping a room row **pushes** that room's day screen
    for today (native stack header titled with the room's `name` and a back button).
    Back from the day screen returns to the tab bar.

16. **Long lists, and what must stay reachable.** The Bookings tab lists **thirteen**
    bookings at the seed and does **not** fit on one screen; its list scrolls. Within
    that:
    - While either composer input is focused and the on-screen keyboard is up, the start
      input, the length input and the `Book` button all remain visible and tappable (a
      keyboard-avoiding container is the reference approach).
    - After a booking is created, its timeline row is **visible without the user
      scrolling manually**.
    - The status line under the composer is visible whenever it has text.

17. **The Bookings tab carries a badge.** The `Bookings` item in the bottom tab bar shows
    a small numeric badge with the count of your **waitlisted** bookings. With the seed
    alone that count is zero and **no badge is shown**; the badge appears (`1`) as soon
    as one of your bookings is waitlisted and disappears when the count returns to zero.

## Seed data (exact values — copy these verbatim)

Users (`id`, `displayName`). The signed-in user is `u-you`.

| id | displayName |
|---|---|
| u-you | You |
| u-ana | Ana Costa |
| u-ben | Ben Okafor |
| u-chloe | Chloe Martin |
| u-dev | Dev Patel |
| u-emma | Emma Lindqvist |

Rooms (`id`, `name`, `capacity`, hourly rate), listed in this order:

| id | name | capacity | rate |
|---|---|---|---|
| r-focus | Focus Pod | 1 | $12.00 |
| r-huddle | Huddle | 1 | $20.00 |
| r-board | Boardroom | 1 | $45.00 |
| r-desks | Open Desks | 3 | $6.00 |

Bookings (`id`, room, user, `date`, `start`, `end`, `status`, `order`):

| id | room | user | date | start | end | status | order |
|---|---|---|---|---|---|---|---|
| bk-1 | Focus Pod | Ana Costa | 2026-04-06 | 09:00 | 10:00 | confirmed | 1 |
| bk-2 | Focus Pod | You | 2026-04-06 | 10:00 | 11:00 | confirmed | 2 |
| bk-3 | Huddle | Ben Okafor | 2026-04-06 | 09:00 | 11:00 | confirmed | 3 |
| bk-4 | Huddle | You | 2026-04-06 | 11:00 | 12:00 | confirmed | 4 |
| bk-5 | Boardroom | Chloe Martin | 2026-04-06 | 13:00 | 15:00 | confirmed | 5 |
| bk-6 | Boardroom | You | 2026-04-06 | 15:00 | 16:00 | confirmed | 6 |
| bk-7 | Open Desks | Dev Patel | 2026-04-06 | 09:00 | 12:00 | confirmed | 7 |
| bk-8 | Open Desks | Emma Lindqvist | 2026-04-06 | 09:00 | 12:00 | confirmed | 8 |
| bk-9 | Open Desks | You | 2026-04-06 | 12:00 | 13:00 | confirmed | 9 |
| bk-10 | Huddle | Emma Lindqvist | 2026-04-06 | 11:00 | 12:30 | waitlisted | 10 |
| bk-11 | Huddle | Dev Patel | 2026-04-06 | 11:00 | 12:00 | waitlisted | 11 |
| bk-12 | Boardroom | You | 2026-04-07 | 09:00 | 10:00 | confirmed | 12 |
| bk-13 | Focus Pod | You | 2026-04-07 | 14:00 | 15:00 | confirmed | 13 |
| bk-14 | Huddle | Ana Costa | 2026-04-07 | 10:00 | 11:00 | confirmed | 14 |
| bk-15 | Boardroom | You | 2026-04-08 | 10:00 | 12:00 | confirmed | 15 |
| bk-16 | Open Desks | You | 2026-04-08 | 13:00 | 17:00 | confirmed | 16 |
| bk-17 | Focus Pod | You | 2026-04-09 | 09:00 | 09:30 | confirmed | 17 |
| bk-18 | Huddle | Ben Okafor | 2026-04-09 | 15:00 | 16:30 | confirmed | 18 |
| bk-19 | Boardroom | You | 2026-04-10 | 14:00 | 16:00 | confirmed | 19 |
| bk-20 | Open Desks | You | 2026-04-10 | 09:00 | 10:00 | confirmed | 20 |
| bk-21 | Huddle | You | 2026-04-06 | 14:00 | 15:00 | cancelled | 21 |
| bk-22 | Boardroom | You | 2026-04-08 | 15:00 | 16:00 | cancelled | 22 |

The two seeded cancellations already carry their fee by ground rule 6: `bk-21` was
charged `$10.00` (a `Huddle` hour is `$20.00`, it started today), `bk-22` was free.

Defaults: `Hide cancelled` is off. The next `order` for a created booking is 23; the
next created booking id is `bk-23`.

## Derived values (the tests assert these exact strings)

**Rooms tab rows** at the seed (confirmed seat-slots today, the percentage, and the
first slot with a free seat):

| room | seats line | seat-slots today | utilisation | next free |
|---|---|---|---|---|
| Focus Pod | `Seats 1` | 4 of 16 = 25.00% | `Today: 25% booked` | `Next free: 11:00` |
| Huddle | `Seats 1` | 6 of 16 = 37.50% | `Today: 38% booked` | `Next free: 12:00` |
| Boardroom | `Seats 1` | 6 of 16 = 37.50% | `Today: 38% booked` | `Next free: 09:00` |
| Open Desks | `Seats 3` | 14 of 48 = 29.17% | `Today: 29% booked` | `Next free: 09:00` |

**Room day screens** (today, header title = the room's `name`, subtitle `Mon 6 Apr`;
rows in ascending start, confirmed before waitlisted at the same start, then by `order`):

| room | timeline rows |
|---|---|
| Focus Pod | `09:00 to 10:00 Ana Costa`; `10:00 to 11:00 You` |
| Huddle | `09:00 to 11:00 Ben Okafor`; `11:00 to 12:00 You`; `11:00 to 12:30 Emma Lindqvist (waitlisted)`; `11:00 to 12:00 Dev Patel (waitlisted)` |
| Boardroom | `13:00 to 15:00 Chloe Martin`; `15:00 to 16:00 You` |
| Open Desks | `09:00 to 12:00 Dev Patel`; `09:00 to 12:00 Emma Lindqvist`; `12:00 to 13:00 You` |

**Bookings tab** (your bookings, in ascending date then start then `order`; thirteen
rows at the seed). Each row's first line is `<room name> <day label> <start> to <end>`
and its second line is the status text:

| first line | second line |
|---|---|
| `Focus Pod Mon 6 Apr 10:00 to 11:00` | `confirmed` |
| `Huddle Mon 6 Apr 11:00 to 12:00` | `confirmed` |
| `Open Desks Mon 6 Apr 12:00 to 13:00` | `confirmed` |
| `Huddle Mon 6 Apr 14:00 to 15:00` | `cancelled, Fee $10.00` |
| `Boardroom Mon 6 Apr 15:00 to 16:00` | `confirmed` |
| `Boardroom Tue 7 Apr 09:00 to 10:00` | `confirmed` |
| `Focus Pod Tue 7 Apr 14:00 to 15:00` | `confirmed` |
| `Boardroom Wed 8 Apr 10:00 to 12:00` | `confirmed` |
| `Open Desks Wed 8 Apr 13:00 to 17:00` | `confirmed` |
| `Boardroom Wed 8 Apr 15:00 to 16:00` | `cancelled, No fee` |
| `Focus Pod Thu 9 Apr 09:00 to 09:30` | `confirmed` |
| `Open Desks Fri 10 Apr 09:00 to 10:00` | `confirmed` |
| `Boardroom Fri 10 Apr 14:00 to 16:00` | `confirmed` |

**Prices and the fee boundary** for your bookings (rate × hours; the fee is half the
price when `start ≤ 2026-04-07 09:00`):

| booking | price | if cancelled |
|---|---|---|
| bk-2 Focus Pod Mon 10:00 (1 h) | `$12.00` | `Fee $6.00` |
| bk-4 Huddle Mon 11:00 (1 h) | `$20.00` | `Fee $10.00` |
| bk-9 Open Desks Mon 12:00 (1 h) | `$6.00` | `Fee $3.00` |
| bk-6 Boardroom Mon 15:00 (1 h) | `$45.00` | `Fee $22.50` |
| bk-12 Boardroom Tue 09:00 (1 h) — starts **exactly** 24 hours after `NOW` | `$45.00` | `Fee $22.50` |
| bk-13 Focus Pod Tue 14:00 (1 h) | `$12.00` | `No fee` |
| bk-15 Boardroom Wed 10:00 (2 h) | `$90.00` | `No fee` |
| bk-16 Open Desks Wed 13:00 (4 h) | `$24.00` | `No fee` |
| bk-17 Focus Pod Thu 09:00 (30 min) | `$6.00` | `No fee` |
| bk-19 Boardroom Fri 14:00 (2 h) | `$90.00` | `No fee` |
| bk-20 Open Desks Fri 09:00 (1 h) | `$6.00` | `No fee` |

**Settings totals** at the seed: `Booked this week: 15h 30m` (the hours of your
**confirmed** bookings Monday to Friday: 1 + 1 + 1 + 1 + 1 + 1 + 2 + 4 + 0.5 + 2 + 1) and
`Fees charged: $10.00` (the fees on your cancelled bookings — a different aggregation;
cancelling a booking lowers the first and may raise the second).

**Worked example — booking.** On the `Focus Pod` day screen, `10:30` for `30` minutes
overlaps your own `10:00 to 11:00` booking, so nothing is created and the status line
reads `You already have a booking at that time`. Then `09:00` for `60` minutes: it ends
at `10:00`, exactly when your booking starts, so by ground rule 3 it is **not** a
self-overlap; but `Ana Costa` holds `09:00 to 10:00` and the room seats one, so the room
is full and the booking is **waitlisted**: a new row `09:00 to 10:00 You (waitlisted)`
appears in the timeline (between Ana's row and your `10:00 to 11:00` row), the status
line is cleared, the Bookings tab gains the row `Focus Pod Mon 6 Apr 09:00 to 10:00` /
`waitlisted` at the top, and the `Bookings` tab badge reads `1`. The Focus Pod Rooms row
is unchanged (`Today: 25% booked`, `Next free: 11:00`). On the `Boardroom` day screen,
`16:00` for `60` minutes starts exactly when your `15:00 to 16:00` booking ends — not a
self-overlap — and the room is free until `17:00`, so it is **confirmed**: the timeline
gains `16:00 to 17:00 You`, the Boardroom Rooms row becomes `Today: 50% booked`
(8 of 16) with `Next free: 09:00` unchanged, and the Bookings tab gains
`Boardroom Mon 6 Apr 16:00 to 17:00` / `confirmed`.

**Worked example — cancelling with promotion.** From the seed, opening the
`Huddle Mon 6 Apr 11:00 to 12:00` booking (bk-4, today, within 24 hours) and tapping
`Cancel booking` makes its status, and the row, read `cancelled, Fee $10.00`. The Huddle waitlist for today is walked in `order`: `bk-10`
(`Emma Lindqvist`, `11:00 to 12:30`, order 10) now fits and is **confirmed**; `bk-11`
(`Dev Patel`, `11:00 to 12:00`, order 11) then overlaps Emma's booking and **stays
waitlisted**. The Huddle timeline becomes `09:00 to 11:00 Ben Okafor`,
`11:00 to 12:30 Emma Lindqvist`, `11:00 to 12:00 Dev Patel (waitlisted)`; the Huddle
Rooms row becomes `Today: 44% booked` (7 of 16 = 43.75%) with `Next free: 12:30`.
Settings becomes `Booked this week: 14h 30m` and `Fees charged: $20.00`.

**Worked example — the 24-hour boundary.** Cancelling `Boardroom Tue 7 Apr 09:00 to
10:00` (bk-12), which starts exactly 24 hours after `NOW`, reads `cancelled, Fee $22.50`.
Cancelling `Focus Pod Tue 7 Apr 14:00 to 15:00` (bk-13) reads `cancelled, No fee`.
Neither promotes anyone (no one is waitlisted on those rooms that day).

**Worked example — the whole final journey** (book the waitlisted Focus Pod slot, book
the Boardroom hour, cancel bk-4, bk-12 and bk-13): Settings reads
`Booked this week: 13h 30m` and `Fees charged: $42.50`; the badge reads `1`; with
`Hide cancelled` on, the Bookings tab shows ten rows and none reads `cancelled`.

## Pinned UI text (tests match these exactly — render them verbatim)

- Tab bar labels: `Rooms`, `Bookings`, `Settings`. Each tab screen shows its heading
  text: `Rooms`, `Bookings`, `Settings`. The `Bookings` tab item carries the numeric
  badge from ground rule 17.
- **Rooms tab**: one row per room in seed order showing the room `name`, the text
  `Seats <capacity>`, the text `Today: <n>% booked`, and `Next free: <HH:MM>` or
  `Next free: none today`.
- **Room day screen**: header title is the room's `name`; a subtitle `Mon 6 Apr`; a
  timeline with one row per confirmed or waitlisted booking today reading
  `<start> to <end> <displayName>` (`You` for your own), with the suffix ` (waitlisted)`
  on waitlisted rows; nothing for cancelled bookings. A composer is pinned at the
  bottom: a start input with placeholder `HH:MM`, a length input with placeholder
  `Minutes`, a button labelled `Book`, and a status line beneath them that is empty
  until a booking is refused, then reads `You already have a booking at that time` or
  `Outside opening hours`.
- **Bookings tab**: one row per booking of yours in the order above; first line
  `<room name> <day label> <start> to <end>`, second line `confirmed`, `waitlisted`,
  `cancelled, Fee $<amount>` or `cancelled, No fee`. Rows carry no buttons; tapping a row
  pushes the **booking screen**.
- **Booking screen**: header title `<room name> <day label> <start> to <end>` (the row's
  first line), a status line reading exactly what the row's second line reads, and — for a
  confirmed or waitlisted booking only — one button labelled `Cancel booking`. Tapping it
  applies ground rules 6 and 7 on that tap: the status line becomes `cancelled, Fee
  $<amount>` or `cancelled, No fee`, the button disappears, and the screen stays open (the
  back button at the top-left returns to the list, whose row now reads the same status).
  A cancelled booking's screen shows no button.
- **Settings tab**: a `Totals` block with the two lines `Booked this week: <h>h <mm>m`
  and `Fees charged: $<amount>`; a `Display` section with one row labelled
  `Hide cancelled` with a toggle switch. When that switch is on, the Bookings tab omits
  every cancelled row (it changes nothing else anywhere).

## Final acceptance

The final e2e journey: launch → Rooms tab lists the four rooms with `Focus Pod` reading
`Today: 25% booked` and `Next free: 11:00`, and `Huddle` reading `Today: 38% booked`
and `Next free: 12:00` → tap `Focus Pod` → type `10:30` and `30` → `Book` → the status
line reads `You already have a booking at that time` → type `09:00` and `60` → `Book`
→ the row `09:00 to 10:00 You (waitlisted)` is visible without scrolling → back → tap
`Boardroom` → type `16:00` and `60` → `Book` → the row `16:00 to 17:00 You` is visible
→ back → `Boardroom` reads `Today: 50% booked` → Bookings tab → the badge reads `1`
and the first row reads `Focus Pod Mon 6 Apr 09:00 to 10:00` / `waitlisted` → tap the
row `Huddle Mon 6 Apr 11:00 to 12:00` → the booking screen is titled
`Huddle Mon 6 Apr 11:00 to 12:00` → `Cancel booking` → the status reads
`cancelled, Fee $10.00` → back → the row reads `cancelled, Fee $10.00` → Rooms
tab → `Huddle` reads `Today: 44% booked` and `Next free: 12:30` → tap `Huddle` → the
timeline reads `11:00 to 12:30 Emma Lindqvist` with no waitlisted suffix and
`11:00 to 12:00 Dev Patel (waitlisted)` → back → Bookings tab → scroll to and tap the
row `Boardroom Tue 7 Apr 09:00 to 10:00` → `Cancel booking` → `cancelled, Fee $22.50` →
back → tap the row `Focus Pod Tue 7 Apr 14:00 to 15:00` → `Cancel booking` →
`cancelled, No fee` → back → Settings tab →
`Booked this week: 13h 30m` and `Fees charged: $42.50` → turn on `Hide cancelled` →
Bookings tab → no row reads `cancelled`. It must complete without manual intervention.
