# Step 2 — Exercise log and date-grouped history

Make the Log and History tabs real. On the Log tab the user picks one of the five seeded
exercise types, sees the duration and calorie inputs pre-fill with that exercise's
seeded defaults, can edit them, and saves the workout with a one-shot `Save workout`
button. The saved workout appears on the History tab, which lists all workouts (seeded
plus newly logged) grouped under their fixed date labels.

Explore the journey on the device before you consider the step done: select Cycling,
confirm the pre-filled `45` / `400`, save, and find the new entry in History under
`Jul 18`. Try a rapid double-tap on Save — it must not create a second entry.

## Acceptance criteria (binding)

1. The Log tab shows the exercise types `Running`, `Cycling`, `Swimming`, `Yoga`,
   `Strength`.
2. Selecting `Cycling` marks it selected and pre-fills `Duration minutes` with `45` and
   `Calories burned` with `400`.
3. Tapping `Save workout` appends a workout that renders in History under the group
   header `Jul 18` as `Cycling — 45 min, 400 cal`.
4. Save is one-shot (debounced): a rapid double-tap logs exactly one workout — only one
   such Cycling entry may exist afterwards.
