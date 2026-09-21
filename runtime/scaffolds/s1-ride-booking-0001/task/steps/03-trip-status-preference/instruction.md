# Step 03 — trip confirmation, status timeline, persistent preferred fare

Implement the Trip tab per the root contract: ride confirmation, a progressing status
timeline, and a persistent preferred-fare-tier preference with a textual summary.

## Requirements

1. **Confirm ride**: a `Confirm ride` button (one-shot, debounced, **always enabled —
   no destination or fare selection is required first**) that creates the
   ride with `Ride ID: WSH-1423`, `Driver: Sarah — Toyota Camry`, and
   `Status: Matching`, replacing the button with the ride details.
2. **Status timeline**: a `Trip status` section listing Matching / Driver assigned /
   En route / Arriving in order with the current status visibly marked, plus the
   `Status: <label>` text. An `Advance status` button (one-shot, debounced) moves the
   status by exactly one step per press; at `Arriving` it is disabled and reads
   `Arrived`.
3. **Preferred fare tier**: a `Preferred fare tier` section with the three tier
   options (one-shot debounced selector, selected option highlighted) and the summary
   `Preferred fare: <Label>` — `Preferred fare: Economy` by default.
4. Both the confirmed ride (including its current status) and the preferred-fare
   setting persist across tab navigation (store state; no backend needed).

## Observable outcome the hidden test checks

Open Trip → `Confirm ride` button + `Preferred fare: Economy` → tap Confirm ride →
`Ride ID: WSH-1423`, `Driver: Sarah — Toyota Camry`, `Status: Matching` → Advance →
`Status: Driver assigned` → Advance → `Status: En route` → Advance →
`Status: Arriving`, control disabled reading `Arrived` → tap Premium option →
`Preferred fare: Premium` → navigate to Search and back → still
`Preferred fare: Premium`, `Status: Arriving`, `Ride ID: WSH-1423`.
