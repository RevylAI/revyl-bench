# Step 1 — tab shell and the habits list

Build the three-tab shell and the Habits tab per the root contract.

1. **Tabs**: bottom tab bar with `Habits`, `Today`, `Settings`. Each screen shows its own
   heading text (`Habits`, `Today`, `Settings`). The app opens on Habits — no login,
   onboarding or splash. Switching tabs must not crash.

2. **Habits list**: one row per habit, in the SEED ORDER from the root contract (not
   alphabetical), showing the habit name and the line `Current streak: <n>`.

3. **The current-streak rule** (root ground rule 3) is what this step is really testing:
   the streak is the run ending exactly at day 28, so a habit whose day 28 is not completed
   reads `Current streak: 0` no matter how long its most recent run was.

## Observable outcome the hidden test checks

The three tabs are present and each selects without a crash; the Habits tab lists the six
habits in seed order; `Morning run` shows `Current streak: 9`, `Meditate` shows
`Current streak: 0` and `No sugar` shows `Current streak: 0`.
