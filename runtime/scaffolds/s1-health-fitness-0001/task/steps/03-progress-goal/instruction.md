# Step 3 — Progress summary and persistent daily goal

Make the Progress tab real. It aggregates the seeded workout history into a weekly
active-minutes total and a top exercise, and hosts a `Daily goal` section where the user
picks a daily active-minutes goal (`30 min` or `60 min`, default 30) with a one-shot
selector. The chosen goal and its textual summary must survive navigating away to
another tab and back.

Explore the journey on the device: open Progress, confirm the aggregate texts, switch
the goal to `60 min`, double-tap it to check the debounce, then hop to Log and back and
confirm the goal stuck.

## Acceptance criteria (binding)

1. The Progress tab shows `Weekly total: 190 min` and `Top exercise: Running`.
2. Selecting the `60 min` daily-goal option marks it selected and updates the summary
   to `Daily goal: 60 min`.
3. The goal survives navigation: after going to the Log tab and back to Progress, the
   summary still reads `Daily goal: 60 min` and `60 min` remains selected.
4. The goal selector is one-shot (debounced): a rapid double-tap does not bounce the
   setting back to `30 min`.
