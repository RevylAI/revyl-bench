# SwiftRide — build a mobile ride-booking app

You are a coding agent building a fresh iOS mobile app from the provided Expo scaffold
(Expo SDK 57, Expo Router, TypeScript). The product is a ride-booking app: a
destination search with mocked map labels, tiered fare selection with a price + ETA
cascade, ride confirmation with a synthetic ride ID and driver assignment, a
progressing trip-status timeline, and a persistent preferred-fare-tier preference.

The work is split into three steps (see `steps/01-tabs`, `steps/02-search-fare`,
`steps/03-trip-status-preference`, each with its own `instruction.md`), followed by a
final end-to-end acceptance run. Complete the steps in order.

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

## Ground rules (binding — the tests depend on these)

1. **Integer cents; dollars only at render.** Fare prices live as integer cents and
   render as `$<dollars>.<2-digit cents>` (1250 → `$12.50`, 2400 → `$24.00`,
   3600 → `$36.00`). ETAs are fixed integer minutes rendered as `ETA <n> min`.
2. **Deterministic data — no clocks, no randomness, no GPS.** No `Date.now()`,
   `new Date()`, `Math.random()`, or location APIs anywhere in app code. Destinations
   are fixed names; the pickup label is always `Current Location`; fares are fixed
   per tier (not distance-dependent); the ride ID and driver are fixed values; the
   trip status advances only through explicit user action. Every value on screen must
   be computable from this contract alone.
3. **Debounced one-shot mutation controls.** Fare-card selection, **Confirm ride**,
   **Advance status**, and the preferred-fare selector are one-shot: a rapid
   double-tap must have the same effect as a single tap (a fare stays selected — never
   toggles off; the ride is confirmed once; the status advances exactly one step per
   press; the preference is set once). Disabling the control briefly after press is
   one acceptable implementation.
4. **Textual state summaries.** The selected fare, ride ID, driver, current status,
   and preferred fare are exact text strings (pinned below) — never encoded only in
   colors, badges, or highlight positions. (Highlights may accompany the text.)
5. **State survives tab navigation.** The selected destination, selected fare, the
   confirmed ride (including its status), and the preferred-fare preference persist
   when the user navigates between tabs (module-level/store state is sufficient; no
   backend, no disk persistence).
6. **Em dash separator.** Where this contract shows ` — ` (space, em dash U+2014,
   space) render exactly that character.

## Seed data (exact values — copy these verbatim)

Destinations (`id`, `name`, `distanceMeters` — distance never affects fares; showing
it is optional and no test asserts it, e.g. `5.2 km` is fine):

| id | name | distanceMeters |
|---|---|---|
| downtown | Downtown Office | 5200 |
| airport | Airport Terminal | 18000 |
| riverside | Riverside Park | 3400 |
| library | City Library | 6700 |
| stadium | Stadium East | 9200 |

Fare tiers (`id`, `label`, `baseCents`, `etaMinutes`), in this order:

| id | label | baseCents | etaMinutes | renders as |
|---|---|---|---|---|
| economy | Economy | 1250 | 5 | $12.50 — ETA 5 min |
| premium | Premium | 2400 | 3 | $24.00 — ETA 3 min |
| xl | XL | 3600 | 4 | $36.00 — ETA 4 min |

Assigned driver (always this one): name `Sarah`, vehicle `Toyota Camry`, plate
`WSH-1423`. **The ride ID is the plate string `WSH-1423`.**

Trip statuses, fixed order (integer index 0..3; index 3 is terminal):

| index | label |
|---|---|
| 0 | Matching |
| 1 | Driver assigned |
| 2 | En route |
| 3 | Arriving |

Defaults: no destination selected; no fare selected; ride not confirmed; preferred
fare tier `economy`.

Derived values (the tests assert these exact strings):

- Fare cascade: selecting a tier renders `<Label>: <price> — ETA <n> min` from that
  tier's row — `Economy: $12.50 — ETA 5 min`; switching to Premium →
  `Premium: $24.00 — ETA 3 min`.
- Confirming the ride renders `Ride ID: WSH-1423`, `Driver: Sarah — Toyota Camry`,
  `Status: Matching` (index 0).
- Each **Advance status** press moves the index by exactly one:
  `Status: Driver assigned` → `Status: En route` → `Status: Arriving`; at index 3 the
  advance control is disabled and reads `Arrived`.
- Preferred fare summary: `Preferred fare: Economy` by default;
  `Preferred fare: Premium` after selecting Premium.

## Pinned UI text (tests match these exactly — render them verbatim)

- Tab bar labels: `Search`, `Fare`, `Trip`. Each tab screen shows its heading text:
  `Search`, `Fare`, `Trip`.
- Search screen: a mocked map-labels area with `Pickup: Current Location` and
  `Dropoff: Select a destination` (no selection) / `Dropoff: <destination name>`
  (after tapping a destination); a `Destinations` list label (rendered upper-case:
  `DESTINATIONS`) above one row per destination showing its name; the selected row
  visually highlighted.
- Fare screen: a `Selected fare` label (rendered upper-case: `SELECTED FARE`) above
  the summary text — `Select a fare tier` when nothing is selected, otherwise
  `<Label>: <price> — ETA <n> min`; three fare cards in seed order, each showing the
  tier label and `<price> — ETA <n> min`; the selected card visually highlighted and
  showing the badge text `Selected`.
- Trip screen: before confirmation, a `Confirm ride` button that is **always enabled** —
  it requires no destination or fare to have been selected (the ride ID and driver are
  fixed values, independent of any selection). After confirmation:
  `Ride ID: WSH-1423`, `Driver: Sarah — Toyota Camry`, `Status: <label>`; a
  `Trip status` timeline label (rendered upper-case: `TRIP STATUS`) listing the four
  statuses in order with the current one visibly marked; an `Advance status` button
  that at the terminal status is disabled and reads `Arrived`. Always: a
  `Preferred fare tier` label (rendered upper-case: `PREFERRED FARE TIER`) with the
  three tier options (selected one highlighted) and the summary line
  `Preferred fare: <Label>`.

## Final acceptance

The final e2e journey: launch → Search shows the destinations → tap Downtown Office →
`Pickup: Current Location` / `Dropoff: Downtown Office` → Fare tab shows the three
cards → tap Economy → `Economy: $12.50 — ETA 5 min` → tap Premium →
`Premium: $24.00 — ETA 3 min` → Trip tab → Confirm ride → `Ride ID: WSH-1423`,
`Driver: Sarah — Toyota Camry`, `Status: Matching` → Advance status three times →
`Status: Arriving` with the control disabled reading `Arrived` → select Premium as
preferred fare → `Preferred fare: Premium` → navigate to Search and back to Trip →
preference and ride state (still `Status: Arriving`, `Ride ID: WSH-1423`) persisted.
It must complete without manual intervention.
