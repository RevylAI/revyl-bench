# Step 03 — place a bid, settings totals

Implement bidding from the lot screen, and the Settings tab, per the root contract.

## Requirements

1. **Place a bid**: the composer pinned at the bottom of the lot screen (amount input
   with placeholder `0.00`, button `Place bid`) places a proxy bid by ground rules 2–3
   with `bidOrder = (current maximum) + 1`. It is one-shot (debounced), takes effect on
   the single tap, opens no dialog or alert, and clears the input whether the bid is
   accepted or refused (ground rule 7). The input and the button stay visible and tappable
   while the keyboard is up (ground rule 12).

2. **A refused bid** (max below the standing bid plus its increment) shows the text
   `Minimum bid is $<amount>` beneath the composer and changes nothing else. From the seed,
   bidding `325.00` on `Private chef dinner` shows `Minimum bid is $330.00`.

3. **An accepted bid** re-resolves the lot and updates **every** screen that shows it: the
   lot screen's header block and history (the new row visible without manual scrolling),
   the Lots row and the `Lots` badge, the My Bids row, and the Settings totals. From the
   seed, bidding `600.00` on `Private chef dinner` gives `Standing bid $330.00`,
   `You are winning`, `below reserve`, `Next bid from $340.00`, history row `You $330.00`,
   badge `3`, and My Bids `Your max $600.00`, `Standing bid $330.00`, `winning`. The
   status stays `below reserve` because the **standing bid** is below the `$500.00`
   reserve, whatever your max (ground rule 4).

4. **Settings tab**: a `Totals` block with `Reserve-met standing bids: $<amount>` (the sum
   of standing bids over lots whose status is `reserve met`, any bidder) and
   `Your exposure: $<amount>` (the sum of standing bids over lots where you are the
   standing bidder, any status). With the seed alone: `Reserve-met standing bids: $700.00`
   and `Your exposure: $670.00`; after the `600.00` bid above:
   `Reserve-met standing bids: $700.00` and `Your exposure: $1000.00`.

5. Placed bids persist across navigation: leaving the lot screen and returning, or
   switching tabs, shows the same resolved state (store state; no backend, no disk
   persistence).

## Observable outcome the hidden test checks

Tap `Private chef dinner` → the header reads `Standing bid $320.00`,
`Omar Haddad is winning`, `Next bid from $330.00` → type `325.00` → `Place bid` → the text
`Minimum bid is $330.00` is shown and the header still reads `Standing bid $320.00` → type
`600.00` → `Place bid` → the header reads `Standing bid $330.00`, `You are winning`,
`below reserve`, `Next bid from $340.00`, and the row `You $330.00` is visible without
scrolling → back → the `Private chef dinner` row reads `Standing bid $330.00` and
`below reserve`, and the `Lots` badge reads `3` → My Bids → `Private chef dinner` reads
`Your max $600.00`, `Standing bid $330.00`, `winning` → Settings →
`Reserve-met standing bids: $700.00` and `Your exposure: $1000.00` → Lots → tap
`Private chef dinner` → still `Standing bid $330.00` and `You are winning`.
