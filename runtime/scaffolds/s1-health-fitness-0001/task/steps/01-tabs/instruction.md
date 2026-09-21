# Step 1 — App shell: tabs and seed data

Set up the product skeleton. Turn the scaffold into a three-tab app — `Log`, `History`,
`Progress` — and put all the seed data from the root contract (`/task/instruction.md`)
in place as typed TypeScript modules, together with the formatting helpers
(`<n> min` / `<n> cal`) and the shared state the later steps will build on. No real
fitness UI yet: each tab renders its title text (placeholder body content is your choice).

Explore the result on the device: launch the app and tap through each of the three tabs.
That journey is what gets verified.

## Acceptance criteria (binding)

1. The app launches without a red screen or runtime error.
2. The bottom tab bar shows `Log`, `History`, and `Progress`.
3. The Log tab shows the title text `Log`; the History tab shows `History`; the
   Progress tab shows `Progress`. Tapping between tabs never crashes. These titles are
   permanent — they must still be present after steps 2 and 3 replace the placeholder
   content, because every submission is graded against the full suite.
