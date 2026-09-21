# Step 01 — tab shell + seed data

Scaffold the app with bottom tab navigation and the synthetic seed data from the root
contract. No real booking UI yet beyond the screen shells.

## Requirements

1. The app launches without a red screen or runtime error dialog.
2. The bottom tab bar shows exactly three tabs labeled `Rooms`, `Bookings`, `Settings`;
   `Rooms` is the initial tab.
3. Each tab screen renders without crashing and shows its heading text — `Rooms`,
   `Bookings`, `Settings` respectively. (These headings are permanent: they must still
   be present when the real UI arrives in steps 02/03, because every submission is
   graded against the full suite.) Any placeholder body content is your choice and is
   not asserted.
4. The seed data from the root contract (users, rooms with capacity and rate in integer
   cents, bookings with `YYYY-MM-DD` dates, `HH:MM` times, status and integer `order`,
   and the fixed `NOW`) is checked into the repo as typed modules — integer cents,
   integer sort keys, no clock/random calls.

## Observable outcome the hidden test checks

Launch → tab bar shows `Rooms` / `Bookings` / `Settings` → tapping each tab renders
its screen with its heading, no crash at any point.
