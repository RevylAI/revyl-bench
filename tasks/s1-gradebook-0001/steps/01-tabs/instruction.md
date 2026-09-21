# Step 01 — tab shell + roster + seed data

Scaffold the app with bottom tab navigation, the student roster, and the synthetic seed
data from the root contract. No grade computation yet beyond the screen shells.

## Requirements

1. The app launches without a red screen or runtime error dialog.
2. The bottom tab bar shows exactly three tabs labeled `Students`, `Class`, `Settings`;
   `Students` is the initial tab.
3. Each tab screen renders without crashing and shows its heading text — `Students`,
   `Class`, `Settings` respectively. (These headings are permanent: they must still be
   present when the real UI arrives in steps 02/03, because every submission is graded
   against the full suite.) Any placeholder body content on the Class and Settings tabs
   is your choice and is not asserted.
4. The Students tab lists the six students in roster order — `Aisha`, `Ben`, `Chloe`,
   `Diana`, `Ethan`, `Farah`. (The rows are permanent too: they gain the computed
   overall grade and letter in step 02, but the names must always be visible.)
5. The seed data from the root contract (the roster, the three weighted categories, the
   six assessments with their maxima, and the score table **including which scores are
   not recorded**) is checked into the repo as typed modules — integer scores, no
   clock/random calls, and no derived value stored: every average, grade, letter and
   ranking is computed in steps 02/03.

## Observable outcome the hidden test checks

Launch → tab bar shows `Students` / `Class` / `Settings` and the roster lists the six
student names → tapping each tab renders its screen with its heading, no crash at any
point.
