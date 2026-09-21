# Step 01 — tab shell + seed data

Scaffold the app with bottom tab navigation and the synthetic seed data from the root
contract. No real chat UI yet beyond the screen shells.

## Requirements

1. The app launches without a red screen or runtime error dialog.
2. The bottom tab bar shows exactly three tabs labeled `Channels`, `Mentions`,
   `Settings`; `Channels` is the initial tab.
3. Each tab screen renders without crashing and shows its heading text — `Channels`,
   `Mentions`, `Settings` respectively. (These headings are permanent: they must still
   be present when the real UI arrives in steps 02/03, because every submission is
   graded against the full suite.) Any placeholder body content is your choice and is
   not asserted.
4. The seed data from the root contract (users, channels with unread counts, messages
   with integer `tsOrder`, author, `@mention` refs derived from the body, and thread
   `parentId` refs) is checked into the repo as typed modules — integer sort keys, no
   clock/random calls.

## Observable outcome the hidden test checks

Launch → tab bar shows `Channels` / `Mentions` / `Settings` → tapping each tab renders
its screen with its heading, no crash at any point.
