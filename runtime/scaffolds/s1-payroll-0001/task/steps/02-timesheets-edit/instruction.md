# Step 02 — the derived timesheet and the shift edit

Implement the full timesheet screen — daily lines, the Week block, gross pay — and the
Edit shift flow, per the root contract's pay pipeline, rounding rules, and pinned UI text.

## Requirements

1. **Daily lines.** Every shift row on a timesheet shows `<Day> <start>-<end>` and its
   daily line `Reg <r>h, OT <o>h, Eve <e>h` (2-decimal hours), computed by R1 (break),
   R2 (daily split) and R4 (evening window) only — **R3's weekly conversion never
   appears in a daily line**. Boundary rows that must come out exactly as the root
   contract's Derived values section lists them: `Ava Wed 07:00-15:30` pays exactly 8h
   (`OT 0.00h`), `Chloe Fri 12:00-18:00` spans exactly 6h (no break) and ends at exactly
   18:00 (`Eve 0.00h`), `Dev Sun 11:00-16:35` is 335 minutes (`Reg 5.58h`), and
   `Dev Mon` and `Dev Wed` both read `Reg 6.00h` by different routes.

2. **The Week block**, above the shift rows and visible without scrolling: `Regular <r>h`,
   `Overtime <o>h`, `Evening <e>h`, `Paid <p>h`, `Gross $<g>` — weekly figures summed in
   **minutes** then converted once (Chloe's regular week is `27.75h`, not the `27.76` her
   rounded daily lines add to), R3 applied at week level (Ava: `Regular 40.00h`,
   `Overtime 9.00h`; Ben: `Regular 39.25h`, `Overtime 2.50h` — not 1.75 and not 4.25),
   and pay priced per the root contract's ground rule 5 (Ben's gross is `$798.51`, with
   both of his components landing on a half-cent and rounding up).

3. **Edit shift** (pushed from a shift row; the row's accessibility label starts with
   `<Day> <start>-<end>`): header `Edit shift`; the employee name; the current
   `<Day> <start>-<end>` and current daily line; a `New end time` row with exactly the
   three buttons `18:00`, `19:30`, `22:00`. Tapping one applies immediately — one-shot,
   debounced, no confirmation dialog — and the screen now shows the updated times and
   updated daily line. Back returns to the timesheet, whose Week block has already
   recomputed.

4. The asserted sequence on `Dev Thu 09:00-16:30` (`Reg 7.00h, OT 0.00h, Eve 0.00h`,
   week `Regular 24.58h`, `Gross $393.28`): end `18:00` gives `Reg 8.00h, OT 0.50h,
   Eve 0.00h` and gross `$421.28`; then end `19:30` crosses the daily-OT boundary —
   `Reg 8.00h, OT 2.00h, Eve 1.50h`, week `Regular 25.58h`, `Overtime 2.00h`,
   `Evening 1.50h`, `Gross $461.78`.

5. An applied edit persists across navigation (store state; no backend, no disk
   persistence — a fresh install starts from the seed).

## Observable outcome the hidden test checks

Team → `Ben Okafor` → Week block `Regular 39.25h`, `Overtime 2.50h`, `Evening 1.00h`,
`Gross $798.51`, with `Mon 08:30-17:15` reading `Reg 8.00h, OT 0.25h, Eve 0.00h` → back →
`Ava Torres` → `Regular 40.00h`, `Overtime 9.00h`, `Gross $1203.75` while her daily lines
show only daily overtime → back → `Dev Patel` → `Gross $393.28` → tap `Thu 09:00-16:30` →
Edit shift shows the three end-time buttons → tap `18:00` → `Reg 8.00h, OT 0.50h,
Eve 0.00h` → tap `19:30` → `Reg 8.00h, OT 2.00h, Eve 1.50h` → back → Week block
`Overtime 2.00h`, `Evening 1.50h`, `Gross $461.78`.
