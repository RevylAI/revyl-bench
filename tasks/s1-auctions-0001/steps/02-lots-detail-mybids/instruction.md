# Step 02 — lot list, lot screen with resolved history, My Bids

Implement the Lots tab, the pushed lot screen, and the My Bids tab per the root
contract's seed data, ground rules, and pinned UI text. This step is entirely about
**resolving the seed bids** with the increment and proxy rules (ground rules 2–4) and
rendering the results; placing new bids is step 03.

## Requirements

1. **Lots tab**: one row per lot in ascending `closesAt` (not id order), showing the
   `title`, `Closing order <closesAt>`, then `Standing bid $<amount>` or
   `Starting at $<starting price>`, then the status text. From the seed the list begins
   `Vintage film camera` (`Closing order 1`, `Standing bid $110.00`, `below reserve`) and
   `Signed team jersey` (`Closing order 2`, `Standing bid $210.00`, `reserve met`), and ends
   with `Charity gala table` (`Closing order 11`, `Starting at $800.00`, `no bids`). Eleven
   lots do not fit on one screen; the list scrolls. Tapping a row pushes the lot screen.
   The `Lots` tab item shows the outbid badge — `4` at the seed (ground rule 13).

2. **Lot screen** (pushed, header title = the lot's `title`, native back button): the
   header block pinned at the top — the standing line, the winner line (`You are winning`
   / `<displayName> is winning` / `No bids yet`), the status text, and the next-bid line
   `Next bid from $<amount>` — then a `Bids` section listing the resolved history in
   ascending `bidOrder`, each row `<bidder displayName> $<standing bid after that bid>`.
   The standing bid after each bid follows ground rule 3 exactly; the root contract tables
   every row. From the seed, `Signed team jersey` reads `Standing bid $210.00`,
   `You are winning`, `reserve met`, `Next bid from $220.00`, and its twelve history rows
   begin `Dana Whitfield $45.50`, `You $65.00`, `Ken Tanaka $85.00` and end `You $190.00`,
   `Dana Whitfield $210.00`; that history scrolls beneath the pinned header. The composer
   (an amount input with placeholder `0.00` and a `Place bid` button) is pinned at the
   bottom; it may be inert until step 03.

3. **My Bids tab**: one row per lot you have bid on, in ascending `closesAt`, showing the
   `title`, `Your max $<your highest max on that lot>`, the standing line, and `winning`
   or `outbid` (ground rule 6: only your own max is ever shown). From the seed there are
   seven rows, beginning `Vintage film camera` (`Your max $95.00`, `Standing bid $110.00`,
   `outbid`), `Signed team jersey` (`Your max $220.00`, `Standing bid $210.00`, `winning`),
   `Private chef dinner` (`Your max $320.00`, `Standing bid $320.00`, `outbid` — the tie
   went to Omar's earlier bid).

4. Everything on these screens is derived from the seed at runtime by the resolution
   rules (store state; no backend needed). Do not hard-code the derived strings.

## Observable outcome the hidden test checks

Launch → Lots lists the lots in closing order, `Vintage film camera` first with
`Closing order 1`, `Standing bid $110.00`, `below reserve`, then `Signed team jersey` with
`Standing bid $210.00`, `reserve met`; the `Lots` badge reads `4` → scroll down → the
bottom shows `Charity gala table` reading `Starting at $800.00` and `no bids` → scroll
back to the top → tap `Signed team jersey` → the header reads `Standing bid $210.00`,
`You are winning`, `Next bid from $220.00`; the history begins `Dana Whitfield $45.50`,
`You $65.00`, `Ken Tanaka $85.00` → scroll the history down → the bottom reads
`You $190.00`, `Dana Whitfield $210.00` while the header block is still visible → back →
My Bids tab → `Vintage film camera` reads `Your max $95.00`, `Standing bid $110.00`,
`outbid`; `Private chef dinner` reads `Your max $320.00`, `Standing bid $320.00`, `outbid`;
`Landscape painting` reads `Your max $260.00`, `Standing bid $210.00`, `winning`.
