# Step 01 — tab shell, roster, and the seeded timesheet

Scaffold the app with bottom tab navigation, the roster, and the seeded shifts from the
root contract rendered as data. No derived hours or pay yet beyond what is listed here.

## Requirements

1. The app launches without a red screen or runtime error dialog.
2. The bottom tab bar shows exactly three tabs labeled `Team`, `Payroll`, `Settings`;
   `Team` is the initial tab.
3. Each tab screen renders without crashing and shows its heading text — `Team`,
   `Payroll`, `Settings` respectively. (These headings are permanent: they must still be
   present when the real UI arrives in steps 02/03, because every submission is graded
   against the full suite.) Any placeholder body content on `Payroll` and `Settings` is
   your choice and is not asserted.
4. **Team tab**: one row per employee in roster order — `Ava Torres`, `Ben Okafor`,
   `Chloe Nguyen`, `Dev Patel` — showing the rate as `$<rate>/h` (`$22.50/h`, `$18.50/h`,
   `$27.50/h`, `$16.00/h`) and the text `<n> shifts` (`6 shifts`, `5 shifts`, `5 shifts`,
   `4 shifts`).
5. Tapping a roster row **pushes** the employee's timesheet screen (native stack header
   titled with the employee name, back button). At this step it must show the employee's
   shifts in weekday order as `<Day> <start>-<end>` — for Ava that is `Mon 07:00-16:30`,
   `Tue 07:00-16:00`, `Wed 07:00-15:30`, `Thu 07:00-16:30`, `Fri 07:00-17:00`,
   `Sat 08:00-13:00`. The daily lines and the Week block arrive in step 02.
6. The seed data from the root contract (the roster with rates, and the 20 shifts as
   weekday index + `HH:MM` strings) is checked into the repo as typed modules — integer
   minutes for derivation, no clock/random calls.

## Observable outcome the hidden test checks

Launch → tab bar shows `Team` / `Payroll` / `Settings` → tapping each tab renders its
screen with its heading, no crash at any point → Team lists the four employees with rates
and shift counts → tapping `Ava Torres` pushes a screen titled `Ava Torres` listing her
six shifts with their exact times.
