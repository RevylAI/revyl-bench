# Step 2 — habit detail

Tapping a habit row pushes a detail screen, with a back control at the top-left.

1. **Header and summary**: header title is the habit name; then the lines
   `Current streak: <n>`, `Longest streak: <n>` and `Completion: <n>%`.

2. **Longest streak** (root ground rule 4) is the longest run anywhere in the 28-day
   window, which is usually not the current streak: `Meditate` is `Current streak: 0` and
   `Longest streak: 12`; `No sugar` is `Current streak: 0` and `Longest streak: 23`.

3. **Completion %** (root ground rule 5) divides by ACTIVE days — the habit's start day
   through day 28 — not by 28. `No sugar` starts on day 5, so it is `23/24 = 96%`.
   Dividing by 28 would give `82%` and is wrong. `Stretch` starts on day 15: `11/14 = 79%`.

4. **Day log**: a section listing all 28 days in order as `Day <n>: done` or
   `Day <n>: missed`, and `Day <n>: not started` for any day before the habit's start day.

5. **The log scrolls** (root ground rule 13): it is taller than one screen, and the habit
   name and the `Current streak` line stay pinned at the top while it scrolls.

## Observable outcome the hidden test checks

Tapping `No sugar` shows `Current streak: 23`, `Longest streak: 23` and `Completion: 100%`;
the `Day log` shows `Day 4: not started` and `Day 28: missed`; scrolling the log to the
bottom leaves the name and `Current streak: 0` pinned at the top. Back returns to the list.
