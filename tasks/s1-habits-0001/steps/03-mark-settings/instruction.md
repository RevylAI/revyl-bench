# Step 3 — marking today, and Settings

1. **Today tab**: one row per habit in seed order showing the habit name and a control
   labelled `Mark done` when day 28 is not completed and `Done today` when it is.

   **The control must be individually addressable**: its accessibility label carries the
   habit name (`Mark done, No sugar`, `Done today, Morning run`) because six controls share
   the same visible text and nothing could otherwise say which one is meant. Visible text
   stays exactly `Mark done` / `Done today`.

2. **Marking recomputes immediately** (root ground rule 7). Marking `No sugar` completes
   its day 28, which is its only incomplete active day, so it goes to 24 of 24:
   `Current streak: 23` → `Current streak: 24`, longest `23` → `24`, `Completion: 100%` →
   `Completion: 100%`. The Habits tab shows the new streak without further navigation.

   The `0` → `24` jump is the check on ground rule 3. An implementation that reported the
   most recent run would move from `23` to `24` instead.

3. **Debounced one-shot** (root ground rule 8): one tap takes effect exactly once. No
   confirmation dialogs.

4. **Settings tab**: a `Totals` block with `Habits tracked: 6`, `Done today: <n>` and
   `Longest streak overall: <n>`. At the seed: `Done today: 4`, `Longest streak overall: 23`.
   After marking `No sugar`: `Done today: 5`, `Longest streak overall: 24`.

5. **State survives navigation** (root ground rule 9): leaving a tab and returning shows
   the same values.

## Observable outcome the hidden test checks

Today tab → tap `Mark done` on the `No sugar` row → it reads `Done today` → Habits tab →
`No sugar` shows `Current streak: 24` → Settings tab → `Done today: 5` and
`Longest streak overall: 24` → Habits tab → Settings tab again → unchanged.
