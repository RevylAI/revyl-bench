# Ledgerline — build a mobile invoicing app

You are a coding agent building a fresh iOS mobile app from the provided Expo scaffold
(Expo SDK 57, Expo Router, TypeScript). The product is a freelancer's invoicing app: a
client list with what each client still owes, an invoice list with a status filter, a
pushed invoice screen with the full line-by-line arithmetic (subtotal, discount, tax,
total, paid, balance), a one-tap way to record a payment against an invoice, and a
settings screen with running totals that persist across navigation.

The work is split into three steps (see `steps/01-tabs`,
`steps/02-clients-invoices-detail`, `steps/03-payments-settings`, each with its own
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

**These screens do not all fit on one phone.** The invoice list and several invoice
screens are longer than the display, and the tests scroll. Verify your work by looking at
the running app on the device, not by reasoning about the code — layout, scroll position,
keyboard behaviour and badge rendering are graded from screenshots.

## Ground rules (binding — the tests depend on these)

1. **Integer cents everywhere, thousands grouped.** Every monetary value is stored as an
   integer number of cents and rendered as `$<dollars>.<cents>` with exactly two decimal
   places and a comma every three digits of the dollar part (`$7.53`, `$330.60`,
   `$1,486.94`, `$10,665.42`). Never use floating-point arithmetic for money. A rendered
   amount is **never** negative and never carries a minus sign — a negative balance is
   expressed in words as a credit (`Credit $14.05`), never by a sign or a colour alone.

2. **Round half up, per line.** The only rounding operation in the app is
   `rhu(x, pct) = floor((x × pct + 50) / 100)` on integer cents — "round half up to the
   cent". It is applied **per line**, never to a subtotal. Worked example:
   `rhu(67545, 10)` = `floor((675450 + 50) / 100)` = `6755` → `$67.55`.

3. **The invoice arithmetic (exact, in this order).** For every line:
   `net = qty × unitPrice`; `lineDiscount = rhu(net, discountPct)`;
   `lineTax = rhu(net − lineDiscount, taxPct)`. The discount is applied **before** tax,
   and tax is computed **on each line's discounted net**, at that line's own rate. Then
   for the invoice: `subtotal = Σ net`; `discount = Σ lineDiscount`; `tax = Σ lineTax`;
   `total = subtotal − discount + tax`; `paid = Σ payments`; `balance = total − paid`.
   Three readings that look reasonable and are **wrong** here: rounding the discount once
   on the subtotal (`INV-1002` would show `$245.07` instead of `$245.08`); computing tax
   before the discount (`INV-1002` would show `$312.57` instead of `$281.32`); taxing the
   discounted subtotal at one rate. The derived table below is the ground truth.

4. **A fixed today: `2026-03-14`.** There is no clock. Dates are `YYYY-MM-DD` strings and
   compare as strings. An invoice is **overdue** when its due date is strictly earlier
   than `2026-03-14` and its balance is greater than zero; `INV-1007` (due `2026-03-14`)
   is not overdue.

5. **Status (exactly one, derived — never stored).** In this order of precedence:
   `Draft` when the invoice has not been sent; otherwise `Paid` when `balance ≤ 0`;
   otherwise `Overdue` when the due date is earlier than today; otherwise `Partial` when
   `paid > 0`; otherwise `Sent`. `Overdue` beats `Partial`: an overdue invoice with a
   partial payment is `Overdue`.

6. **Outstanding excludes drafts and ignores credits.** A client's outstanding figure is
   the sum of the **positive** balances of that client's **sent** invoices. A draft
   contributes nothing however large. A credit (a paid invoice with `balance < 0`)
   contributes nothing — it does **not** reduce the figure. `Total collected` is the sum
   of every payment recorded against a sent invoice (drafts cannot receive payments).
   `Overdue invoices` is the count of invoices whose status is `Overdue`.

7. **Deterministic data — no clocks, no randomness.** No `Date.now()`, `new Date()`,
   `Math.random()`, or uuid libraries anywhere in app code. Every payment carries an
   integer `tsOrder`; a recorded payment gets `tsOrder = (current maximum) + 1` and the
   id from a counter (`pay-8`, `pay-9`, …). Invoices are listed in ascending invoice
   number everywhere. No time-of-day text is rendered anywhere.

8. **Debounced one-shot Record payment, applied immediately.** The payment composer's
   `Record payment` button is one-shot: a rapid double-tap records the payment **exactly
   once**. Disabling the control briefly after press (≈250–300 ms) is one acceptable
   implementation. It is disabled while the amount input is empty. It takes effect **on
   the single tap that triggers it** — there is no confirmation dialog, alert, "are you
   sure?" step, or intermediate screen, and the app never opens a native alert/confirm
   dialog at any point. A payment larger than the balance is accepted and produces a
   credit.

9. **Verbatim amount input.** The amount input accepts digits and at most one `.` and is
   interpreted as dollars-and-cents (`600.00` → 60000 cents; `600` → 60000 cents).
   Recording clears it.

10. **Textual state summaries.** Every balance, total, status and count is an exact text
    string (pinned below) — never encoded only in colours, icons, or bar widths.

11. **State survives navigation.** Recorded payments and the `Hide paid invoices` switch
    persist when the user navigates between tabs and pushes/pops screens (module-level/
    store state is sufficient; no backend, no disk persistence — a fresh install starts
    from the seed below).

12. **Navigation shape.** The app opens directly on the Clients tab — no login, onboarding,
    or splash gate — and the client list is interactive within two seconds of launch. The
    three tabs are a bottom tab bar. Tapping an invoice row on the Invoices tab **pushes**
    the invoice screen (native stack header titled with the invoice number, e.g.
    `INV-1004`, and a back button). Back from the invoice screen returns to the Invoices
    tab with the same filter still selected.

13. **Long lists, and what must stay reachable.** The Invoices tab lists fourteen invoices
    and does **not** fit on one screen; it scrolls. Within that:
    - The filter row stays **pinned at the top and visible while the list scrolls**.
    - On an invoice screen the payment composer is pinned at the bottom; while its input
      is focused and the on-screen keyboard is up, the input and the `Record payment`
      button remain visible and tappable (a keyboard-avoiding container is the reference
      approach).
    - After recording a payment, the totals block (`Paid` and the balance line) is
      **visible without the user scrolling manually** — the screen brings it into view.

14. **The Invoices tab carries a badge.** The `Invoices` item in the bottom tab bar shows a
    small numeric badge with the count of invoices whose status is `Overdue`. With the
    seed alone that badge reads `5`. It updates as payments change statuses, and shows no
    badge at all when the count is zero.

## Seed data (exact values — copy these verbatim)

Clients (`id`, `name`), listed in this order everywhere:

| id | name |
|---|---|
| c-harbor | Harbor Books |
| c-north | Northwind Studio |
| c-pine | Pinecrest Dental |
| c-lumen | Lumen Analytics |
| c-sol | Solstice Cafe |

Invoices (`id`, `number`, client, `issued`, `due`, `sent`, invoice-level `discount`
percent). `sent = no` is a draft:

| id | number | client | issued | due | sent | discount |
|---|---|---|---|---|---|---|
| inv-1 | INV-1001 | Harbor Books | 2026-01-12 | 2026-02-11 | yes | 0% |
| inv-2 | INV-1002 | Northwind Studio | 2026-01-20 | 2026-02-19 | yes | 10% |
| inv-3 | INV-1003 | Pinecrest Dental | 2026-01-28 | 2026-02-27 | yes | 0% |
| inv-4 | INV-1004 | Lumen Analytics | 2026-02-02 | 2026-03-04 | yes | 15% |
| inv-5 | INV-1005 | Solstice Cafe | 2026-02-05 | 2026-03-07 | yes | 0% |
| inv-6 | INV-1006 | Harbor Books | 2026-02-09 | 2026-03-11 | yes | 10% |
| inv-7 | INV-1007 | Northwind Studio | 2026-02-12 | 2026-03-14 | yes | 0% |
| inv-8 | INV-1008 | Pinecrest Dental | 2026-02-16 | 2026-03-18 | yes | 15% |
| inv-9 | INV-1009 | Lumen Analytics | 2026-02-19 | 2026-03-21 | yes | 0% |
| inv-10 | INV-1010 | Solstice Cafe | 2026-02-23 | 2026-03-25 | yes | 10% |
| inv-11 | INV-1011 | Harbor Books | 2026-02-26 | 2026-03-28 | no | 0% |
| inv-12 | INV-1012 | Northwind Studio | 2026-03-01 | 2026-03-31 | yes | 0% |
| inv-13 | INV-1013 | Lumen Analytics | 2026-03-04 | 2026-04-03 | no | 15% |
| inv-14 | INV-1014 | Pinecrest Dental | 2026-03-08 | 2026-04-07 | yes | 0% |

Lines (per invoice, in this order; `qty`, `unitPrice` in cents, per-line `taxRate`):

| invoice | description | qty | unit price | tax rate |
|---|---|---|---|---|
| INV-1001 | Catalogue design | 1 | $1,200.00 | 13% |
| INV-1001 | Stock photography | 12 | $35.00 | 13% |
| INV-1002 | Brand workshop | 2 | $850.00 | 13% |
| INV-1002 | Logo refinements | 3 | $225.15 | 13% |
| INV-1002 | Print proofs | 5 | $15.05 | 5% |
| INV-1003 | Website copy | 6 | $140.00 | 13% |
| INV-1003 | Appointment form | 1 | $475.00 | 13% |
| INV-1004 | Dashboard mockups | 5 | $300.00 | 13% |
| INV-1004 | Icon set | 26 | $11.55 | 13% |
| INV-1004 | Usability review | 3 | $410.10 | 0% |
| INV-1005 | Menu redesign | 1 | $680.00 | 13% |
| INV-1005 | Table tents | 40 | $3.75 | 5% |
| INV-1006 | Newsletter template | 1 | $525.00 | 13% |
| INV-1006 | Author photos | 7 | $41.25 | 13% |
| INV-1006 | Social banners | 9 | $22.25 | 13% |
| INV-1007 | Motion sting | 1 | $920.00 | 13% |
| INV-1007 | Colour grade | 2 | $187.50 | 13% |
| INV-1008 | Recall postcards | 250 | $1.45 | 5% |
| INV-1008 | Front desk signage | 3 | $89.00 | 13% |
| INV-1008 | Reminder emails | 6 | $62.50 | 13% |
| INV-1008 | Review response pack | 1 | $335.00 | 0% |
| INV-1009 | Quarterly report layout | 4 | $212.50 | 13% |
| INV-1009 | Chart templates | 11 | $19.75 | 13% |
| INV-1010 | Loyalty card | 500 | $0.65 | 5% |
| INV-1010 | Window decal | 2 | $145.00 | 13% |
| INV-1010 | Seasonal menu insert | 3 | $98.75 | 13% |
| INV-1011 | Spring catalogue | 1 | $1,350.00 | 13% |
| INV-1012 | Pitch deck | 1 | $740.00 | 13% |
| INV-1012 | Presenter notes | 5 | $33.00 | 0% |
| INV-1013 | Annual report | 1 | $2,100.00 | 13% |
| INV-1013 | Infographics | 8 | $77.50 | 13% |
| INV-1014 | Hygiene guide | 300 | $2.15 | 5% |
| INV-1014 | Poster series | 4 | $56.00 | 13% |

Payments (`id`, invoice, amount, `tsOrder`):

| id | invoice | amount | tsOrder |
|---|---|---|---|
| pay-1 | INV-1001 | $1,500.00 | 1 |
| pay-2 | INV-1002 | $1,000.00 | 2 |
| pay-3 | INV-1003 | $1,500.00 | 3 |
| pay-4 | INV-1005 | $400.00 | 4 |
| pay-5 | INV-1007 | $1,463.35 | 5 |
| pay-6 | INV-1009 | $500.00 | 6 |
| pay-7 | INV-1010 | $250.00 | 7 |

Defaults: `Hide paid invoices` is off; the Invoices tab opens on the `All` filter. Next
`tsOrder` for a recorded payment is 8; the next payment id is `pay-8`.

## Derived values (the tests assert these exact strings)

**Every invoice at the seed** (ground rules 2–5; the balance line and status are pinned
strings):

| number | subtotal | discount | tax | total | paid | balance line | status |
|---|---|---|---|---|---|---|---|
| INV-1001 | $1,620.00 | $0.00 | $210.60 | $1,830.60 | $1,500.00 | `Balance due $330.60` | `Overdue` |
| INV-1002 | $2,450.70 | $245.08 | $281.32 | $2,486.94 | $1,000.00 | `Balance due $1,486.94` | `Overdue` |
| INV-1003 | $1,315.00 | $0.00 | $170.95 | $1,485.95 | $1,500.00 | `Credit $14.05` | `Paid` |
| INV-1004 | $3,030.60 | $454.60 | $198.93 | $2,774.93 | $0.00 | `Balance due $2,774.93` | `Overdue` |
| INV-1005 | $830.00 | $0.00 | $95.90 | $925.90 | $400.00 | `Balance due $525.90` | `Overdue` |
| INV-1006 | $1,014.00 | $101.41 | $118.64 | $1,031.23 | $0.00 | `Balance due $1,031.23` | `Overdue` |
| INV-1007 | $1,295.00 | $0.00 | $168.35 | $1,463.35 | $1,463.35 | `Paid in full` | `Paid` |
| INV-1008 | $1,339.50 | $200.93 | $86.35 | $1,224.92 | $0.00 | `Balance due $1,224.92` | `Sent` |
| INV-1009 | $1,067.25 | $0.00 | $138.74 | $1,205.99 | $500.00 | `Balance due $705.99` | `Partial` |
| INV-1010 | $911.25 | $91.13 | $83.22 | $903.34 | $250.00 | `Balance due $653.34` | `Partial` |
| INV-1011 | $1,350.00 | $0.00 | $175.50 | $1,525.50 | $0.00 | `Balance due $1,525.50` | `Draft` |
| INV-1012 | $905.00 | $0.00 | $96.20 | $1,001.20 | $0.00 | `Balance due $1,001.20` | `Sent` |
| INV-1013 | $2,720.00 | $408.00 | $300.56 | $2,612.56 | $0.00 | `Balance due $2,612.56` | `Draft` |
| INV-1014 | $869.00 | $0.00 | $61.37 | $930.37 | $0.00 | `Balance due $930.37` | `Sent` |

**Line breakdowns** (net, then the per-line discount and per-line tax that sum to the
invoice's `discount` and `tax`):

| invoice | line | net | discount | tax |
|---|---|---|---|---|
| INV-1001 | Catalogue design `1 × $1,200.00` | $1,200.00 | $0.00 | $156.00 |
| INV-1001 | Stock photography `12 × $35.00` | $420.00 | $0.00 | $54.60 |
| INV-1002 | Brand workshop `2 × $850.00` | $1,700.00 | $170.00 | $198.90 |
| INV-1002 | Logo refinements `3 × $225.15` | $675.45 | $67.55 | $79.03 |
| INV-1002 | Print proofs `5 × $15.05` | $75.25 | $7.53 | $3.39 |
| INV-1003 | Website copy `6 × $140.00` | $840.00 | $0.00 | $109.20 |
| INV-1003 | Appointment form `1 × $475.00` | $475.00 | $0.00 | $61.75 |
| INV-1004 | Dashboard mockups `5 × $300.00` | $1,500.00 | $225.00 | $165.75 |
| INV-1004 | Icon set `26 × $11.55` | $300.30 | $45.05 | $33.18 |
| INV-1004 | Usability review `3 × $410.10` | $1,230.30 | $184.55 | $0.00 |
| INV-1005 | Menu redesign `1 × $680.00` | $680.00 | $0.00 | $88.40 |
| INV-1005 | Table tents `40 × $3.75` | $150.00 | $0.00 | $7.50 |
| INV-1006 | Newsletter template `1 × $525.00` | $525.00 | $52.50 | $61.43 |
| INV-1006 | Author photos `7 × $41.25` | $288.75 | $28.88 | $33.78 |
| INV-1006 | Social banners `9 × $22.25` | $200.25 | $20.03 | $23.43 |
| INV-1007 | Motion sting `1 × $920.00` | $920.00 | $0.00 | $119.60 |
| INV-1007 | Colour grade `2 × $187.50` | $375.00 | $0.00 | $48.75 |
| INV-1008 | Recall postcards `250 × $1.45` | $362.50 | $54.38 | $15.41 |
| INV-1008 | Front desk signage `3 × $89.00` | $267.00 | $40.05 | $29.50 |
| INV-1008 | Reminder emails `6 × $62.50` | $375.00 | $56.25 | $41.44 |
| INV-1008 | Review response pack `1 × $335.00` | $335.00 | $50.25 | $0.00 |
| INV-1009 | Quarterly report layout `4 × $212.50` | $850.00 | $0.00 | $110.50 |
| INV-1009 | Chart templates `11 × $19.75` | $217.25 | $0.00 | $28.24 |
| INV-1010 | Loyalty card `500 × $0.65` | $325.00 | $32.50 | $14.63 |
| INV-1010 | Window decal `2 × $145.00` | $290.00 | $29.00 | $33.93 |
| INV-1010 | Seasonal menu insert `3 × $98.75` | $296.25 | $29.63 | $34.66 |
| INV-1011 | Spring catalogue `1 × $1,350.00` | $1,350.00 | $0.00 | $175.50 |
| INV-1012 | Pitch deck `1 × $740.00` | $740.00 | $0.00 | $96.20 |
| INV-1012 | Presenter notes `5 × $33.00` | $165.00 | $0.00 | $0.00 |
| INV-1013 | Annual report `1 × $2,100.00` | $2,100.00 | $315.00 | $232.05 |
| INV-1013 | Infographics `8 × $77.50` | $620.00 | $93.00 | $68.51 |
| INV-1014 | Hygiene guide `300 × $2.15` | $645.00 | $0.00 | $32.25 |
| INV-1014 | Poster series `4 × $56.00` | $224.00 | $0.00 | $29.12 |

**Worked example — `INV-1004` (15% discount, one untaxed line).** `Dashboard mockups`
`5 × $300.00 = $1,500.00`, discount `rhu(150000, 15) = $225.00`, tax
`rhu(127500, 13) = $165.75`. `Icon set` `26 × $11.55 = $300.30`, discount
`rhu(30030, 15) = floor((450450 + 50)/100) = 4505 = $45.05`, tax
`rhu(25525, 13) = $33.18`. `Usability review` `3 × $410.10 = $1,230.30`, discount
`rhu(123030, 15) = $184.55`, tax `0%` → `$0.00`. Subtotal `$3,030.60`, discount
`$454.60` (rounding once on the subtotal would give `$454.59`), tax `$198.93`, total
`$2,774.93`, paid `$0.00`, `Balance due $2,774.93`, status `Overdue` (due `2026-03-04`).

**Worked example — `INV-1003` is a credit.** Total `$1,485.95`, paid `$1,500.00`, so the
balance line reads `Credit $14.05` and the status is `Paid`. That credit does **not**
reduce Pinecrest Dental's outstanding figure, which counts only `INV-1008` and
`INV-1014`: `$1,224.92 + $930.37 = $2,155.29`.

**Clients tab rows** (name, outstanding line, overdue line — ground rule 6):

| client | outstanding | overdue |
|---|---|---|
| Harbor Books | `Outstanding $1,361.83` | `2 overdue` |
| Northwind Studio | `Outstanding $2,488.14` | `1 overdue` |
| Pinecrest Dental | `Outstanding $2,155.29` | `0 overdue` |
| Lumen Analytics | `Outstanding $3,480.92` | `1 overdue` |
| Solstice Cafe | `Outstanding $1,179.24` | `1 overdue` |

Harbor Books is `$330.60 + $1,031.23`: its draft `INV-1011` is excluded. Lumen Analytics
is `$2,774.93 + $705.99`: its draft `INV-1013` is excluded.

**Invoices tab filters** (rows in ascending number; each row shows the number, the
client name, `Due <date>`, the total and the status):

- `All` (14): `INV-1001` … `INV-1014`
- `Unpaid` (10): `INV-1001`, `INV-1002`, `INV-1004`, `INV-1005`, `INV-1006`, `INV-1008`,
  `INV-1009`, `INV-1010`, `INV-1012`, `INV-1014`
- `Overdue` (5): `INV-1001`, `INV-1002`, `INV-1004`, `INV-1005`, `INV-1006`
- `Paid` (2): `INV-1003`, `INV-1007`
- `Drafts` (2): `INV-1011`, `INV-1013`

**Settings totals** (two different aggregations of the same data — the outstanding
figure and the collected figure are not complements of each other):
`Total outstanding: $10,665.42`, `Total collected: $6,613.35`, `Overdue invoices: 5`.
The `Invoices` tab badge reads `5`.

**Worked example — recording a payment that overpays.** From the seed, open `INV-1005`
(`Overdue`, `Balance due $525.90`, `Paid $400.00`) and record `600.00`. The invoice
becomes `Paid` with `Paid $1,000.00` and `Credit $74.10`. Solstice Cafe's row becomes
`Outstanding $653.34` and `0 overdue` (only `INV-1010` remains). Settings becomes
`Total outstanding: $10,139.52`, `Total collected: $7,213.35`, `Overdue invoices: 4`;
the badge reads `4`. The `Paid` filter now lists `INV-1003`, `INV-1005`, `INV-1007`.
With `Hide paid invoices` on, the `All` filter lists the other eleven invoices
(`INV-1001`, `INV-1002`, `INV-1004`, `INV-1006`, `INV-1008`, `INV-1009`, `INV-1010`,
`INV-1011`, `INV-1012`, `INV-1013`, `INV-1014`) and the `Paid` filter is unchanged.

**Worked example — a partial payment.** From the seed, open `INV-1009` (`Partial`,
`Balance due $705.99`, `Paid $500.00`) and record `300.00`. It stays `Partial` with
`Paid $800.00` and `Balance due $405.99`; Lumen Analytics becomes
`Outstanding $3,180.92` and `1 overdue`. Recording the `INV-1005` payment above after
that gives Settings `Total outstanding: $9,839.52`, `Total collected: $7,513.35`,
`Overdue invoices: 4`.

## Pinned UI text (tests match these exactly — render them verbatim)

- Tab bar labels: `Clients`, `Invoices`, `Settings`. Each tab screen shows its heading
  text: `Clients`, `Invoices`, `Settings`. The `Invoices` tab item carries the numeric
  badge from ground rule 14.
- **Clients tab**: one row per client in seed order showing the client `name`, the
  outstanding line — `Outstanding $<amount>`, or `Nothing outstanding` when it is zero —
  and the overdue line `<n> overdue` (`0 overdue` when none).
- **Invoices tab**: a filter row pinned at the top with the five options `All`, `Unpaid`,
  `Overdue`, `Paid`, `Drafts` (`All` selected on launch); then one row per matching
  invoice in ascending number showing the `number`, the client `name`, `Due <due>`
  (e.g. `Due 2026-03-04`), the total (e.g. `$2,774.93`) and the status word (`Draft`,
  `Sent`, `Partial`, `Paid`, `Overdue`).
- **Invoice screen**: header title is the `number`; then the client `name`,
  `Issued <issued>`, `Due <due>` and the status word; then one row per line showing the
  `description`, `<qty> × $<unitPrice>` and the line net `$<net>`; then a totals block
  with the lines `Subtotal $<amount>`, `Discount (<pct>%) $<amount>` (always shown, e.g.
  `Discount (0%) $0.00`), `Tax $<amount>`, `Total $<amount>`, `Paid $<amount>`, and the
  balance line — `Balance due $<amount>`, `Paid in full`, or `Credit $<amount>`. For a
  sent invoice, a composer is pinned at the bottom: an amount input with placeholder
  `0.00` and a button labelled `Record payment`. A draft shows the text
  `Drafts cannot receive payments` instead of the composer.
- **Settings tab**: a `Totals` block with the three lines `Total outstanding: $<amount>`,
  `Total collected: $<amount>` and `Overdue invoices: <n>`; a `Display` section with one
  row labelled `Hide paid invoices` with a toggle switch. When that switch is on, the
  Invoices tab's `All` filter omits every invoice whose status is `Paid` (the `Paid`
  filter still lists them; it changes nothing else anywhere).

## Final acceptance

The final e2e journey: launch → Clients tab lists the five clients with their outstanding
and overdue lines → Invoices tab → the badge reads `5` and the list starts with
`INV-1001` `Overdue` `$1,830.60` → scroll to the bottom → `INV-1014` `Sent` `$930.37` →
tap `Overdue` in the filter row → exactly five rows, `INV-1001` through `INV-1006` without
`INV-1003` → tap `INV-1004` → `Subtotal $3,030.60`, `Discount (15%) $454.60`,
`Tax $198.93`, `Total $2,774.93`, `Balance due $2,774.93` → back → tap `All` → tap
`INV-1009` → `Balance due $705.99` → type `300.00` → `Record payment` → `Paid $800.00`
and `Balance due $405.99` visible without scrolling manually, status `Partial` → back →
tap `INV-1005` → type `600.00` → `Record payment` → `Paid $1,000.00`, `Credit $74.10`,
status `Paid` → back → the badge reads `4` → Clients tab → `Solstice Cafe` reads
`Outstanding $653.34` and `0 overdue`; `Lumen Analytics` reads `Outstanding $3,180.92`
→ Settings tab → `Total outstanding: $9,839.52`, `Total collected: $7,513.35`,
`Overdue invoices: 4`. It must complete without manual intervention.
