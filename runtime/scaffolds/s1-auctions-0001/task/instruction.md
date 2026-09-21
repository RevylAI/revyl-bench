# GalaBid — build a mobile silent-auction app

You are a coding agent building a fresh iOS mobile app from the provided Expo scaffold
(Expo SDK 57, Expo Router, TypeScript). The product is a silent-auction app for a charity
gala: a list of lots in closing order, each with a standing bid and a reserve status, a
pushed lot screen with the resolved bid history and a bid composer, a tab of your own
bids showing whether you are winning or outbid, and a settings screen with two running
totals. Bids are proxy (maximum) bids resolved by a pinned increment rule, and the standing
bid on a lot is almost never the amount anyone typed.

The work is split into three steps (see `steps/01-tabs`, `steps/02-lots-detail-mybids`,
`steps/03-bidding-settings`, each with its own `instruction.md`), followed by a final
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

**These screens do not all fit on one phone.** The lot list and one lot's bid history are
longer than the display, and the tests scroll. Verify your work by looking at the running
app on the device, not by reasoning about the code — layout, scroll position, keyboard
behaviour and badge rendering are graded from screenshots.

## Ground rules (binding — the tests depend on these)

1. **Integer cents everywhere.** Every monetary value is stored as an integer number of
   cents and rendered as `$<dollars>.<cents>` with exactly two decimal places and **no
   thousands separator** (`$45.50`, `$210.00`, `$1000.00`, `$1420.00`). Never use
   floating-point arithmetic for money. A rendered amount is never negative.

2. **The minimum increment is a step function of the standing bid.** The increment that
   applies to a lot is decided by the lot's current standing bid (or by its starting price
   while it has no bids):

   | standing bid | increment |
   |---|---|
   | below `$100.00` | `$5.00` |
   | `$100.00` up to but not including `$500.00` | `$10.00` |
   | `$500.00` and above | `$25.00` |

   The boundaries belong to the higher band: a standing bid of exactly `$100.00` carries a
   `$10.00` increment, and exactly `$500.00` carries `$25.00`.

3. **Every bid is a maximum (a proxy bid), and bids resolve in `bidOrder`.** A bid carries
   the most its bidder is willing to pay, `maxCents`. Bids are processed one at a time in
   ascending `bidOrder`. Each lot has a **standing bidder**, that bidder's **max**, and a
   **standing bid** (the amount displayed). The resolution rule, exactly:
   - **First bid on a lot:** the bidder becomes the standing bidder with that max, and the
     standing bid is the lot's **starting price** — never the max.
   - **A later bid is accepted only if its max is at least the standing bid plus the
     increment that applies to the standing bid.** Otherwise it is refused and changes
     nothing.
   - **Accepted, and the new max is higher than the standing bidder's max:** the new
     bidder takes the lot. The standing bid becomes the **previous standing bidder's max
     plus the increment that applies to that max**, capped at the new max. The new max
     itself is never revealed.
   - **Accepted, but the new max is less than or equal to the standing bidder's max:**
     the standing bidder keeps the lot (a tie goes to the **earlier** bid). The standing bid
     rises to the **new bid's max plus the increment that applies to that max**, capped at
     the standing bidder's max.

   Worked example, the `Signed team jersey` (starting price `$45.50`): Dana bids a max of
   `$60.00` → standing bid `$45.50`, Dana winning. You bid a max of `$95.50` → the standing
   bid becomes `$60.00 + $5.00 = $65.00`, you winning. Ken bids `$80.00` → below your max, so
   you keep the lot and the standing bid rises to `$80.00 + $5.00 = $85.00`. Omar bids
   `$91.00` → standing bid `min($95.50, $91.00 + $5.00) = $95.50`. Lucia bids `$120.00` →
   she takes the lot at `$95.50 + $5.00 = $100.50`. The full resolved history of every lot is
   tabled below.

4. **Status is decided by the standing bid, never by any max.** A lot with no bids is
   `no bids`; with a standing bid below its reserve price it is `below reserve`; with a
   standing bid at or above its reserve it is `reserve met`. A bidder whose max covers the
   reserve does **not** make the lot `reserve met` until the standing bid itself reaches it.

5. **Deterministic data — no clocks, no randomness.** No `Date.now()`, `new Date()`,
   `Math.random()`, or uuid libraries anywhere in app code. Every lot carries an integer
   `closesAt`; the Lots tab and the My Bids tab list lots in ascending `closesAt`. Every bid
   carries an integer `bidOrder`; a newly placed bid gets `bidOrder = (current maximum) + 1`
   and its id from a counter (`bid-30`, `bid-31`, …). No time-of-day or date text is rendered
   anywhere.

6. **Only your own maxes are ever shown.** Other bidders' maxes exist in the data and drive
   the resolution rule, but the only max the app displays is yours, on the My Bids tab.
   Bid history rows show the standing bid **after** that bid resolved, never the max.

7. **Debounced one-shot `Place bid`, applied immediately, no dialogs.** `Place bid` is
   one-shot: a rapid double-tap places exactly one bid. Disabling the control briefly after
   press (≈250–300 ms) is one acceptable implementation. It takes effect on the single tap
   that triggers it — there is no confirmation dialog, alert, "are you sure?" step, or
   intermediate screen, and the app never opens a native alert/confirm dialog at any point.
   A refused bid shows its refusal as text on the lot screen (pinned below), never as an
   alert. `Place bid` is disabled while the input is empty or whitespace; both an accepted
   and a refused bid clear the input.

8. **Verbatim amount input.** The amount input accepts digits and at most one `.` and is
   interpreted as dollars-and-cents (`600.00` → 60000 cents; `325` → 32500 cents).

9. **Textual state summaries.** Every standing bid, status, winning/outbid state and total
   is an exact text string (pinned below) — never encoded only in colours, icons, or bar
   widths.

10. **State survives navigation.** Placed bids persist when the user navigates between tabs
    and pushes/pops screens (module-level/store state is sufficient; no backend, no disk
    persistence — a fresh install starts from the seed below).

11. **Navigation shape.** The app opens directly on the Lots tab — no login, onboarding, or
    splash gate — and the lot list is interactive within two seconds of launch. The three
    tabs are a bottom tab bar. Tapping a lot row **pushes** a lot screen (native stack header
    titled with the lot's `title` and a back button). Back from the lot screen returns to the
    tab bar.

12. **Long lists, and what must stay reachable.** Eleven lots do **not** fit on one screen;
    the Lots list scrolls. The `Signed team jersey` has twelve bids; its history scrolls
    within the lot screen while the bid composer stays pinned at the bottom. Within that:
    - While the amount input is focused and the on-screen keyboard is up, the input and the
      `Place bid` button remain visible and tappable (a keyboard-avoiding container is the
      reference approach).
    - After a bid is accepted, its new history row is **visible without the user scrolling
      manually** — the list brings it into view.
    - The lot screen's header block (standing bid, winner line, status, next-bid line) stays
      **pinned at the top and visible while the history rows scroll beneath it**.

13. **The Lots tab carries a badge.** The `Lots` item in the bottom tab bar shows a small
    numeric badge with the count of lots on which you have placed at least one bid **and are
    not the standing bidder**. With the seed alone that badge reads `4`. It updates as bids
    resolve, and shows no badge at all when the count is zero.

## Seed data (exact values — copy these verbatim)

Bidders (`id`, `displayName`). The signed-in user is `b-you`.

| id | displayName |
|---|---|
| b-you | You |
| b-dana | Dana Whitfield |
| b-omar | Omar Haddad |
| b-lucia | Lucia Ferreira |
| b-ken | Ken Tanaka |

Lots (`id`, `title`, starting price, reserve price, `closesAt`). Ids are **not** in closing
order; every lot list renders in ascending `closesAt`:

| id | title | starting price | reserve | closesAt |
|---|---|---|---|---|
| lot-1 | Signed team jersey | $45.50 | $90.00 | 2 |
| lot-2 | Weekend cabin stay | $300.00 | $450.00 | 6 |
| lot-3 | Private chef dinner | $200.00 | $500.00 | 4 |
| lot-4 | Vintage film camera | $80.00 | $120.00 | 1 |
| lot-5 | Wine cellar tour | $120.00 | $250.00 | 8 |
| lot-6 | Pottery workshop | $40.00 | $60.00 | 5 |
| lot-7 | Season ski pass | $500.00 | $700.00 | 10 |
| lot-8 | Landscape painting | $150.00 | $300.00 | 7 |
| lot-9 | Guitar lesson bundle | $90.00 | $150.00 | 3 |
| lot-10 | Espresso machine | $250.00 | $350.00 | 9 |
| lot-11 | Charity gala table | $800.00 | $900.00 | 11 |

Bids (`id`, lot, bidder, `maxCents`, `bidOrder`) — every one of these is accepted when
processed in this order:

| id | lot | bidder | max | bidOrder |
|---|---|---|---|---|
| bid-1 | Signed team jersey | Dana Whitfield | $60.00 | 1 |
| bid-2 | Signed team jersey | You | $95.50 | 2 |
| bid-3 | Private chef dinner | Omar Haddad | $320.00 | 3 |
| bid-4 | Weekend cabin stay | Lucia Ferreira | $420.00 | 4 |
| bid-5 | Signed team jersey | Ken Tanaka | $80.00 | 5 |
| bid-6 | Wine cellar tour | You | $180.00 | 6 |
| bid-7 | Vintage film camera | Dana Whitfield | $90.00 | 7 |
| bid-8 | Weekend cabin stay | You | $480.00 | 8 |
| bid-9 | Private chef dinner | You | $320.00 | 9 |
| bid-10 | Signed team jersey | Omar Haddad | $91.00 | 10 |
| bid-11 | Wine cellar tour | Ken Tanaka | $210.00 | 11 |
| bid-12 | Season ski pass | Lucia Ferreira | $720.00 | 12 |
| bid-13 | Vintage film camera | You | $95.00 | 13 |
| bid-14 | Signed team jersey | Lucia Ferreira | $120.00 | 14 |
| bid-15 | Landscape painting | Omar Haddad | $200.00 | 15 |
| bid-16 | Weekend cabin stay | Dana Whitfield | $510.00 | 16 |
| bid-17 | Signed team jersey | Dana Whitfield | $130.00 | 17 |
| bid-18 | Vintage film camera | Ken Tanaka | $100.00 | 18 |
| bid-19 | Wine cellar tour | Dana Whitfield | $200.00 | 19 |
| bid-20 | Signed team jersey | Ken Tanaka | $140.00 | 20 |
| bid-21 | Landscape painting | You | $260.00 | 21 |
| bid-22 | Signed team jersey | You | $175.00 | 22 |
| bid-23 | Guitar lesson bundle | Lucia Ferreira | $120.00 | 23 |
| bid-24 | Signed team jersey | Omar Haddad | $160.00 | 24 |
| bid-25 | Vintage film camera | Lucia Ferreira | $115.00 | 25 |
| bid-26 | Signed team jersey | Lucia Ferreira | $180.00 | 26 |
| bid-27 | Espresso machine | You | $290.00 | 27 |
| bid-28 | Signed team jersey | You | $220.00 | 28 |
| bid-29 | Signed team jersey | Dana Whitfield | $200.00 | 29 |

Defaults: the next `bidOrder` for a placed bid is 30; the next bid id is `bid-30`.

## Derived values (the tests assert these exact strings)

**Lots tab rows**, in ascending `closesAt`. Each row shows the `title`, the text
`Closing order <closesAt>`, the standing line, and the status text:

| title | closing order | standing line | status |
|---|---|---|---|
| Vintage film camera | `Closing order 1` | `Standing bid $110.00` | `below reserve` |
| Signed team jersey | `Closing order 2` | `Standing bid $210.00` | `reserve met` |
| Guitar lesson bundle | `Closing order 3` | `Standing bid $90.00` | `below reserve` |
| Private chef dinner | `Closing order 4` | `Standing bid $320.00` | `below reserve` |
| Pottery workshop | `Closing order 5` | `Starting at $40.00` | `no bids` |
| Weekend cabin stay | `Closing order 6` | `Standing bid $490.00` | `reserve met` |
| Landscape painting | `Closing order 7` | `Standing bid $210.00` | `below reserve` |
| Wine cellar tour | `Closing order 8` | `Standing bid $210.00` | `below reserve` |
| Espresso machine | `Closing order 9` | `Standing bid $250.00` | `below reserve` |
| Season ski pass | `Closing order 10` | `Standing bid $500.00` | `below reserve` |
| Charity gala table | `Closing order 11` | `Starting at $800.00` | `no bids` |

Lots tab badge: `4` (you are outbid on `Vintage film camera`, `Private chef dinner`,
`Weekend cabin stay` and `Wine cellar tour`).

**Lot screen header block** (standing line, winner line, status, next-bid line — the
next-bid line is the standing bid plus the increment that applies to it):

| title | winner line | next-bid line |
|---|---|---|
| Vintage film camera | `Lucia Ferreira is winning` | `Next bid from $120.00` |
| Signed team jersey | `You are winning` | `Next bid from $220.00` |
| Guitar lesson bundle | `Lucia Ferreira is winning` | `Next bid from $95.00` |
| Private chef dinner | `Omar Haddad is winning` | `Next bid from $330.00` |
| Pottery workshop | `No bids yet` | `Next bid from $40.00` |
| Weekend cabin stay | `Dana Whitfield is winning` | `Next bid from $500.00` |
| Landscape painting | `You are winning` | `Next bid from $220.00` |
| Wine cellar tour | `Ken Tanaka is winning` | `Next bid from $220.00` |
| Espresso machine | `You are winning` | `Next bid from $260.00` |
| Season ski pass | `Lucia Ferreira is winning` | `Next bid from $525.00` |
| Charity gala table | `No bids yet` | `Next bid from $800.00` |

**Resolved bid histories** (every bid, in ascending `bidOrder`; each row reads
`<bidder displayName> $<standing bid after that bid resolved>`):

| lot | history rows, in order |
|---|---|
| Signed team jersey | `Dana Whitfield $45.50`, `You $65.00`, `Ken Tanaka $85.00`, `Omar Haddad $95.50`, `Lucia Ferreira $100.50`, `Dana Whitfield $130.00`, `Ken Tanaka $140.00`, `You $150.00`, `Omar Haddad $170.00`, `Lucia Ferreira $180.00`, `You $190.00`, `Dana Whitfield $210.00` |
| Weekend cabin stay | `Lucia Ferreira $300.00`, `You $430.00`, `Dana Whitfield $490.00` |
| Private chef dinner | `Omar Haddad $200.00`, `You $320.00` |
| Vintage film camera | `Dana Whitfield $80.00`, `You $95.00`, `Ken Tanaka $100.00`, `Lucia Ferreira $110.00` |
| Wine cellar tour | `You $120.00`, `Ken Tanaka $190.00`, `Dana Whitfield $210.00` |
| Season ski pass | `Lucia Ferreira $500.00` |
| Landscape painting | `Omar Haddad $150.00`, `You $210.00` |
| Guitar lesson bundle | `Lucia Ferreira $90.00` |
| Espresso machine | `You $250.00` |

Note the tie on `Private chef dinner`: your max of `$320.00` equals Omar's earlier max, so
Omar keeps the lot and the standing bid rises to exactly `$320.00`. Note `Ken Tanaka
$100.00` on the camera: Ken's `$100.00` beat your `$95.00`, and the standing bid became
`$95.00 + $5.00 = $100.00`, which then sits in the `$10.00` band, so Lucia's `$115.00` set the
standing bid to `$100.00 + $10.00 = $110.00`.

**My Bids tab** (every lot you have bid on, in ascending `closesAt`; each row shows the
`title`, `Your max $<your highest max on that lot>`, the standing line, and `winning` or
`outbid`):

| title | your max line | standing line | state |
|---|---|---|---|
| Vintage film camera | `Your max $95.00` | `Standing bid $110.00` | `outbid` |
| Signed team jersey | `Your max $220.00` | `Standing bid $210.00` | `winning` |
| Private chef dinner | `Your max $320.00` | `Standing bid $320.00` | `outbid` |
| Weekend cabin stay | `Your max $480.00` | `Standing bid $490.00` | `outbid` |
| Landscape painting | `Your max $260.00` | `Standing bid $210.00` | `winning` |
| Wine cellar tour | `Your max $180.00` | `Standing bid $210.00` | `outbid` |
| Espresso machine | `Your max $290.00` | `Standing bid $250.00` | `winning` |

**Settings totals** — two aggregations over two different sets of lots:

- `Reserve-met standing bids: $700.00` — the sum of the standing bids of every lot whose
  status is `reserve met`, whoever is winning it (`Signed team jersey` `$210.00` +
  `Weekend cabin stay` `$490.00`).
- `Your exposure: $670.00` — the sum of the standing bids of every lot on which **you** are
  the standing bidder, whatever its status (`Signed team jersey` `$210.00` +
  `Landscape painting` `$210.00` + `Espresso machine` `$250.00`).

**Worked example — a refused bid.** On `Private chef dinner` the standing bid is
`$320.00`, so the increment is `$10.00` and the next acceptable max is `$330.00`. Placing a
bid of `325.00` is refused: the lot screen shows the text `Minimum bid is $330.00`, the
input clears, and nothing else changes anywhere.

**Worked example — an accepted bid that takes the lot.** Placing a bid of `600.00` on
`Private chef dinner` beats Omar's max of `$320.00`, so you take the lot, and the standing
bid becomes `$320.00 + $10.00 = $330.00` — not `$600.00`. The history gains the row
`You $330.00`, visible without scrolling; the header reads `Standing bid $330.00`,
`You are winning`, `Next bid from $340.00`, and the status stays `below reserve` (your max
covers the `$500.00` reserve, but the standing bid does not). The Lots row reads
`Standing bid $330.00` and `below reserve`; the badge becomes `3`; My Bids shows
`Your max $600.00`, `Standing bid $330.00`, `winning`; Settings becomes
`Reserve-met standing bids: $700.00` (unchanged) and `Your exposure: $1000.00`.

**Worked example — an accepted bid that does not take the lot.** After the example above,
placing a bid of `700.00` on `Season ski pass` is accepted (the standing bid is `$500.00`,
increment `$25.00`, minimum `$525.00`) but does not beat Lucia's max of `$720.00`. Lucia keeps
the lot, and the standing bid rises to `min($720.00, $700.00 + $25.00) = $720.00`. The history
gains `You $720.00`; the header reads `Standing bid $720.00`, `Lucia Ferreira is winning`,
`Next bid from $745.00`, and the status becomes `reserve met`. The Lots row reads
`Standing bid $720.00` and `reserve met`; the badge becomes `4`; My Bids gains
`Season ski pass` with `Your max $700.00`, `Standing bid $720.00`, `outbid`; Settings
becomes `Reserve-met standing bids: $1420.00` and `Your exposure: $1000.00`.

## Pinned UI text (tests match these exactly — render them verbatim)

- Tab bar labels: `Lots`, `My Bids`, `Settings`. Each tab screen shows its heading text:
  `Lots`, `My Bids`, `Settings`. The `Lots` tab item carries the numeric badge from
  ground rule 13.
- **Lots tab**: one row per lot in ascending `closesAt` showing the `title`, the text
  `Closing order <closesAt>`, then `Standing bid $<amount>` (or `Starting at $<starting
  price>` while the lot has no bids), then the status text `no bids`, `below reserve`
  or `reserve met`.
- **Lot screen**: header title is the lot's `title`. A header block pinned at the top:
  `Standing bid $<amount>` (or `Starting at $<starting price>`), then the winner line
  `You are winning` / `<displayName> is winning` / `No bids yet`, then the status text,
  then `Next bid from $<standing bid + its increment>` (or `Next bid from $<starting
  price>` while the lot has no bids). Below it a `Bids` section: the resolved history,
  one row per bid in ascending `bidOrder`, reading `<bidder displayName> $<standing bid
  after that bid>`. A composer is pinned at the bottom: an amount input with placeholder
  `0.00` and a button labelled `Place bid`. A refused bid shows the text
  `Minimum bid is $<amount>` beneath the composer until the next accepted bid or until the
  screen is left.
- **My Bids tab**: one row per lot you have bid on, in ascending `closesAt`, showing the
  `title`, `Your max $<amount>`, `Standing bid $<amount>`, and `winning` or `outbid`.
- **Settings tab**: a `Totals` block with the two lines
  `Reserve-met standing bids: $<amount>` and `Your exposure: $<amount>`.

## Final acceptance

The final e2e journey: launch → the Lots tab lists the eleven lots in closing order with
`Vintage film camera` first reading `Closing order 1`, `Standing bid $110.00`,
`below reserve`, and the badge on `Lots` reading `4` → tap `Signed team jersey` → the
header reads `Standing bid $210.00`, `You are winning`, `reserve met`, `Next bid from
$220.00`; the history begins `Dana Whitfield $45.50`, `You $65.00` → scroll the history to
the bottom → `You $190.00`, `Dana Whitfield $210.00` → back → tap `Private chef dinner` →
type `600.00` → `Place bid` → `Standing bid $330.00`, `You are winning`, `below reserve`,
`Next bid from $340.00`, and the row `You $330.00` is visible without scrolling → back →
the `Private chef dinner` row reads `Standing bid $330.00` and the badge reads `3` → scroll
the lot list down → tap `Season ski pass` → `Standing bid $500.00`,
`Lucia Ferreira is winning`, `Next bid from $525.00` → type `700.00` → `Place bid` →
`Standing bid $720.00`, `Lucia Ferreira is winning`, `reserve met`, `Next bid from
$745.00`, and the row `You $720.00` → back → the badge reads `4` → My Bids → `Season ski
pass` reads `Your max $700.00`, `Standing bid $720.00`, `outbid`, and `Private chef dinner`
reads `Your max $600.00`, `Standing bid $330.00`, `winning` → Settings →
`Reserve-met standing bids: $1420.00` and `Your exposure: $1000.00`. It must complete
without manual intervention.
