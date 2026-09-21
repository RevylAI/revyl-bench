# SplitBill — build a mobile shared-expense app

You are a coding agent building a fresh iOS mobile app from the provided Expo scaffold
(Expo SDK 57, Expo Router, TypeScript). The product is a shared-expense app: groups of
people who pay for things on each other's behalf, a per-group expense list, an itemized
split breakdown for every expense, pairwise balances telling you who owes whom, a one-tap
settle-up, and a settings screen with running totals that persist across navigation.

The work is split into three steps (see `steps/01-tabs`,
`steps/02-groups-expenses-balances`, `steps/03-detail-settle-settings`, each with its own
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

**These screens do not all fit on one phone.** Several lists are longer than the display,
and the tests scroll. Verify your work by looking at the running app on the device, not by
reasoning about the code — layout, scroll position, keyboard behaviour and badge rendering
are graded from screenshots.

## Ground rules (binding — the tests depend on these)

1. **Integer cents everywhere.** Every monetary value is stored as an integer number of
   cents and rendered as `$<dollars>.<cents>` with exactly two decimal places
   (`$8.22`, `$193.63`, `$624.00`). Never use floating-point arithmetic for money. A
   rendered amount is **never** negative and never carries a minus sign — direction is
   always expressed in words (`owes you` / `you owe`), never by a sign or a colour alone.

2. **The split rule (exact).** An expense is split **equally among all members of its
   group**. If the amount does not divide evenly, the leftover cents are distributed
   **one cent each to the earliest members in the group's member order** (the order in
   the seed table below), until the remainder is exhausted. The shares of an expense
   always sum to exactly the expense amount. Worked example: `$94.25` (9425 cents) across
   the four Ski Weekend members is `9425 = 4 × 2356 + 1`, so the first member gets
   `$23.57` and the other three get `$23.56`.

3. **Deterministic data — no clocks, no randomness.** No `Date.now()`, `new Date()`,
   `Math.random()`, or uuid libraries anywhere in app code. Every expense carries an
   integer `tsOrder`; expense lists render in ascending `tsOrder`. A newly added expense
   gets `tsOrder = (current maximum) + 1`, so it always appears **last** (at the bottom).
   Ids for added expenses come from a counter (`exp-22`, `exp-23`, …). No time-of-day or
   date text is rendered anywhere.

4. **Balances are pairwise, not global.** The Balances tab shows the balance between
   **you and each other member**, computed across every group. An expense creates a debt
   edge **only between its payer and each other participant**: if you paid, every other
   participant owes you their share; if someone else paid, you owe that payer your share.
   An expense paid by a third party in a group you are in creates no edge between you and
   any non-payer. A member's own global net across everyone else is **not** what this tab
   shows.

5. **Settlements belong to groups, and settling clears every group it arose in.** A
   settlement records a payment between you and one member **within one group**. Tapping
   `Settle up` on a member's Balances row clears your balance with that member **in every
   group where you have one**, recording one settlement per affected group. So a single
   settle-up changes: that member's Balances row, the summary, the Settings totals, **and
   the Groups tab row of every affected group**. Worked example below.

6. **A group's net includes its own settlements.** The number on a Groups tab row is your
   net in that group from that group's expenses **and** that group's settlements.

7. **Debounced one-shot Add / Settle up, applied immediately.** The expense composer's
   `Add` and each balance row's `Settle up` are one-shot: a rapid double-tap performs the
   action **exactly once**. Disabling the control briefly after press (≈250–300 ms) is one
   acceptable implementation. `Add` is disabled while either input is empty or whitespace;
   adding trims and clears both inputs. Both controls take effect **on the single tap that
   triggers them** — there is no confirmation dialog, alert, "are you sure?" step, or
   intermediate screen, and the app never opens a native alert/confirm dialog at any point.

8. **Verbatim text input.** The description input has auto-capitalization and auto-correct
   **disabled**, so a description typed as `boba run` is stored and rendered exactly as
   `boba run`. The amount input accepts digits and at most one `.` and is interpreted as
   dollars-and-cents (`26.00` → 2600 cents).

9. **Textual state summaries.** Every balance, total, and settled state is an exact text
   string (pinned below) — never encoded only in colours, icons, or bar widths.

10. **State survives navigation.** Added expenses, recorded settlements, and the
    `Hide settled members` switch persist when the user navigates between tabs and
    pushes/pops screens (module-level/store state is sufficient; no backend, no disk
    persistence — a fresh install starts from the seed below).

11. **Navigation shape.** The app opens directly on the Groups tab — no login, onboarding,
    or splash gate — and the group list is interactive within two seconds of launch. The
    three tabs are a bottom tab bar. Tapping a group row **pushes** a group screen (native
    stack header titled with the group's name and a back button); tapping any expense row
    **pushes** its detail screen (native stack header titled `Expense` with a back button).
    Back from the detail returns to the group; back from the group returns to the tab bar.

12. **Long lists, and what must stay reachable.** The `Ski Weekend` group has twelve
    expenses and does **not** fit on one screen; its list scrolls. Within that:
    - While either composer input is focused and the on-screen keyboard is up, the
      description input, the amount input and the `Add` button all remain visible and
      tappable (a keyboard-avoiding container is the reference approach).
    - After adding an expense, the new row is **visible without the user scrolling
      manually** — the list brings it into view.
    - On the Balances tab the summary line stays **pinned at the top and visible while the
      member rows scroll beneath it**.

13. **The Balances tab carries a badge.** The `Balances` item in the bottom tab bar shows a
    small numeric badge with the count of members whose balance with you is **not** zero.
    With the seed alone that badge reads `3`. It updates as balances change, and shows no
    badge at all when the count is zero.

## Seed data (exact values — copy these verbatim)

Members (`id`, `displayName`). The signed-in user is `m-you`.

| id | displayName |
|---|---|
| m-you | You |
| m-priya | Priya Nair |
| m-marco | Marco Silva |
| m-elena | Elena Vasquez |

Groups (`id`, `name`, members **in this order** — the order that decides remainder cents),
listed in this order:

| id | name | members (in order) |
|---|---|---|
| g-tahoe | Tahoe Trip | You, Priya Nair, Marco Silva, Elena Vasquez |
| g-lunch | Lunch Crew | You, Marco Silva, Elena Vasquez |
| g-apt | Apartment | You, Priya Nair |
| g-ski | Ski Weekend | You, Priya Nair, Marco Silva, Elena Vasquez |

Expenses (`id`, group, `description`, payer, `amountCents`, `tsOrder`):

| id | group | description | payer | amount | tsOrder |
|---|---|---|---|---|---|
| exp-1 | Tahoe Trip | Cabin rental | Elena Vasquez | $480.00 | 1 |
| exp-2 | Tahoe Trip | Groceries | Priya Nair | $87.50 | 2 |
| exp-3 | Tahoe Trip | Gas | You | $61.00 | 3 |
| exp-4 | Tahoe Trip | Lift tickets | Elena Vasquez | $310.00 | 4 |
| exp-5 | Lunch Crew | Ramen | Marco Silva | $52.00 | 5 |
| exp-6 | Lunch Crew | Tacos | You | $41.00 | 6 |
| exp-7 | Lunch Crew | Coffee | Marco Silva | $18.75 | 7 |
| exp-8 | Apartment | Internet | You | $79.99 | 8 |
| exp-9 | Apartment | Cleaning | You | $120.00 | 9 |
| exp-10 | Ski Weekend | Lift passes | Priya Nair | $624.00 | 10 |
| exp-11 | Ski Weekend | Chalet deposit | You | $450.00 | 11 |
| exp-12 | Ski Weekend | Ski hire | Marco Silva | $189.00 | 12 |
| exp-13 | Ski Weekend | Groceries run | Elena Vasquez | $94.25 | 13 |
| exp-14 | Ski Weekend | Fuel | You | $73.50 | 14 |
| exp-15 | Ski Weekend | Lesson fees | Priya Nair | $220.00 | 15 |
| exp-16 | Ski Weekend | Boot fitting | Marco Silva | $66.75 | 16 |
| exp-17 | Ski Weekend | Apres drinks | Elena Vasquez | $81.30 | 17 |
| exp-18 | Ski Weekend | Snow chains | You | $45.50 | 18 |
| exp-19 | Ski Weekend | Locker rental | Priya Nair | $33.00 | 19 |
| exp-20 | Ski Weekend | Trail map | Marco Silva | $8.75 | 20 |
| exp-21 | Ski Weekend | Hot tub fee | Elena Vasquez | $52.50 | 21 |

Settlements (`id`, group, from, to, amount, `tsOrder`):

| id | group | from | to | amount | tsOrder |
|---|---|---|---|---|---|
| set-1 | Tahoe Trip | Marco Silva | You | $20.00 | 22 |

Defaults: `Hide settled members` is off. Next `tsOrder` for an added expense is 23; the
next added expense id is `exp-22`.

## Derived values (the tests assert these exact strings)

**Groups tab rows** (your net in that group — expenses **and** that group's settlements):

| group | members line | net line |
|---|---|---|
| Tahoe Trip | `4 members` | `You owe $193.63` |
| Lunch Crew | `3 members` | `You are owed $3.74` |
| Apartment | `2 members` | `You are owed $99.99` |
| Ski Weekend | `4 members` | `You are owed $84.33` |

**Expense row secondary text.** Each row shows `you lent $<amount − your share>` when
**you** paid, and `you borrowed $<your share>` otherwise:

| group | rows, in ascending tsOrder |
|---|---|
| Tahoe Trip | Cabin rental `you borrowed $120.00`; Groceries `you borrowed $21.88`; Gas `you lent $45.75`; Lift tickets `you borrowed $77.50` |
| Lunch Crew | Ramen `you borrowed $17.34`; Tacos `you lent $27.33`; Coffee `you borrowed $6.25` |
| Apartment | Internet `you lent $39.99`; Cleaning `you lent $60.00` |
| Ski Weekend | Lift passes `you borrowed $156.00`; Chalet deposit `you lent $337.50`; Ski hire `you borrowed $47.25`; Groceries run `you borrowed $23.57`; Fuel `you lent $55.12`; Lesson fees `you borrowed $55.00`; Boot fitting `you borrowed $16.69`; Apres drinks `you borrowed $20.33`; Snow chains `you lent $34.12`; Locker rental `you borrowed $8.25`; Trail map `you borrowed $2.19`; Hot tub fee `you borrowed $13.13` |

**Split breakdowns** (every expense, shares in group member order):

| expense | shares |
|---|---|
| Cabin rental $480.00 | $120.00 / $120.00 / $120.00 / $120.00 |
| Groceries $87.50 | $21.88 / $21.88 / $21.87 / $21.87 |
| Gas $61.00 | $15.25 / $15.25 / $15.25 / $15.25 |
| Lift tickets $310.00 | $77.50 / $77.50 / $77.50 / $77.50 |
| Ramen $52.00 | $17.34 / $17.33 / $17.33 |
| Tacos $41.00 | $13.67 / $13.67 / $13.66 |
| Coffee $18.75 | $6.25 / $6.25 / $6.25 |
| Internet $79.99 | $40.00 / $39.99 |
| Cleaning $120.00 | $60.00 / $60.00 |
| Lift passes $624.00 | $156.00 / $156.00 / $156.00 / $156.00 |
| Chalet deposit $450.00 | $112.50 / $112.50 / $112.50 / $112.50 |
| Ski hire $189.00 | $47.25 / $47.25 / $47.25 / $47.25 |
| Groceries run $94.25 | $23.57 / $23.56 / $23.56 / $23.56 |
| Fuel $73.50 | $18.38 / $18.38 / $18.37 / $18.37 |
| Lesson fees $220.00 | $55.00 / $55.00 / $55.00 / $55.00 |
| Boot fitting $66.75 | $16.69 / $16.69 / $16.69 / $16.68 |
| Apres drinks $81.30 | $20.33 / $20.33 / $20.32 / $20.32 |
| Snow chains $45.50 | $11.38 / $11.38 / $11.37 / $11.37 |
| Locker rental $33.00 | $8.25 / $8.25 / $8.25 / $8.25 |
| Trail map $8.75 | $2.19 / $2.19 / $2.19 / $2.18 |
| Hot tub fee $52.50 | $13.13 / $13.13 / $13.12 / $13.12 |

**Balances tab** (pairwise, in seed member order):

- `Priya Nair owes you $16.37`
- `Marco Silva owes you $61.44`
- `You owe Elena Vasquez $83.38`
- summary line, pinned at the top: `Total: you owe $5.57`
- tab badge: `3`

**Settings totals** (sum of the positive balances, and the absolute sum of the negative
balances — a different aggregation from the net): `Total owed to you: $77.81` and
`Total you owe: $83.38`.

**Worked example — adding an expense.** Adding `Boba` for `26.00` to `Ski Weekend` (paid
by `You`, split four ways) renders the amount as `$26.00` and gives `You $6.50`,
`Priya Nair $6.50`, `Marco Silva $6.50`, `Elena Vasquez $6.50`. The new row renders
`You paid` and `you lent $19.50`. The `Ski Weekend` Groups row becomes
`You are owed $103.83`, and the Balances tab becomes `Priya Nair owes you $22.87`,
`Marco Silva owes you $67.94`, `You owe Elena Vasquez $76.88`, summary
`Total: you are owed $13.93`.

**Worked example — settling up.** From the seed, `Marco Silva owes you $61.44`. That
balance arose in three groups, so tapping `Settle up` on his row records three settlements
and changes **three Groups tab rows**:

| group | before | after |
|---|---|---|
| Tahoe Trip | `You owe $193.63` | `You owe $188.88` |
| Lunch Crew | `You are owed $3.74` | `You are owed $13.66` |
| Apartment | `You are owed $99.99` | `You are owed $99.99` (unchanged — no balance with Marco) |
| Ski Weekend | `You are owed $84.33` | `You are owed $8.22` |

and the Balances tab becomes `Priya Nair owes you $16.37`, `Marco Silva is settled up`,
`You owe Elena Vasquez $83.38`, summary `Total: you owe $67.01`, tab badge `2`. Settings
becomes `Total owed to you: $16.37` and `Total you owe: $83.38`.

## Pinned UI text (tests match these exactly — render them verbatim)

- Tab bar labels: `Groups`, `Balances`, `Settings`. Each tab screen shows its heading text:
  `Groups`, `Balances`, `Settings`. The `Balances` tab item carries the numeric badge from
  ground rule 13.
- **Groups tab**: one row per group in seed order showing the group `name`, the text
  `<n> members`, and the net line — `You owe $<amount>`, `You are owed $<amount>`, or
  `All settled up` when the net is zero.
- **Group screen**: header title is the group's `name`; each expense row shows the
  `description`, the amount, the text `<payer displayName> paid` (`You paid` when you are
  the payer), and the secondary text `you lent $<amount>` / `you borrowed $<amount>`. A
  composer is pinned at the bottom: a description input with placeholder
  `What was it for?`, an amount input with placeholder `0.00`, and a button labelled `Add`.
- **Expense detail screen**: header title `Expense`; the `description` and amount at the
  top, then `<payer displayName> paid`, then a `Split` section listing every group member
  in group order as `<displayName>  $<share>`.
- **Balances tab**: a summary line `Total: you owe $<amount>` / `Total: you are owed
  $<amount>` / `Total: all settled up`, pinned at the top and visible while the rows scroll;
  then one row per other member in seed order. A row reads `<displayName> owes you
  $<amount>`, `You owe <displayName> $<amount>`, or `<displayName> is settled up`. Every
  row with a non-zero balance also shows a button labelled `Settle up`; a settled row shows
  no such button.
- **Settings tab**: a `Totals` block with the two lines `Total owed to you: $<amount>` and
  `Total you owe: $<amount>`; a `Display` section with one row labelled
  `Hide settled members` with a toggle switch. When that switch is on, the Balances tab
  omits every row whose balance is zero (it changes nothing else anywhere).

## Final acceptance

The final e2e journey: launch → Groups tab lists the four groups with their net lines →
tap `Ski Weekend` → its twelve expenses scroll, with `Lift passes` at the top reading
`you borrowed $156.00` → scroll to the bottom → `Hot tub fee` reads `you borrowed $13.13`
→ type `Boba` and `26.00` into the composer → `Add` → the new row is **visible without
scrolling manually**, reading `You paid` and `you lent $19.50` → back → the `Ski Weekend`
row now reads `You are owed $103.83` → tap `Lunch Crew` → tap the `Ramen` row → detail
shows `Marco Silva paid` and the split `You $17.34`, `Marco Silva $17.33`,
`Elena Vasquez $17.33` → back → back → Balances tab → the badge reads `3`, the summary is
pinned at the top reading `Total: you are owed $13.93`, and `Marco Silva owes you $67.94`
→ tap `Settle up` on his row → `Marco Silva is settled up`, badge `2`, summary
`Total: you owe $54.01` → Groups tab → `Tahoe Trip` reads `You owe $188.88`, `Lunch Crew`
reads `You are owed $13.66` and `Ski Weekend` reads `You are owed $21.22` → Settings tab →
`Total owed to you: $22.87` and `Total you owe: $76.88`. It must complete without manual
intervention.
