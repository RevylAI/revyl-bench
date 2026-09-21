# Step 03 — company payroll analytics and settings totals

Implement the Payroll tab and the Settings tab per the root contract. Both are entirely
derived from the current shifts and reprice immediately after a shift edit.

## Requirements

1. **Payroll tab**: a `Company` block with `Total payroll $<t>`, `Top earner <name> $<g>`,
   `Overtime share <s>%`; then an `Employees` section listing `<name> $<gross>` by gross
   descending (roster order breaks a to-the-cent tie).

   Seed state: `Total payroll $3203.43`, `Top earner Ava Torres $1203.75`,
   `Overtime share 11.6%` (373.13 ÷ 3203.43, half-up to 1 decimal), and the rows
   `Ava Torres $1203.75`, `Chloe Nguyen $807.89`, `Ben Okafor $798.51`,
   `Dev Patel $393.28` in that order.

2. **Settings tab**: a `Pay rules` block with the lines `Overtime x1.5`,
   `Evening +$3.00/h after 18:00`, `Unpaid break 30 min over 6h`; then a `Week` block
   with `Employees: 4`, `Shifts: 20`, `Paid hours: <p>`, `Overtime hours: <o>`,
   `Evening hours: <e>` — the hour totals are sums of the per-employee weekly figures.
   Seed state: `Paid hours: 143.08`, `Overtime hours: 11.50`, `Evening hours: 15.92`.

3. **Everything repriced after an edit.** After the `19:30` edit to `Dev Thu` (step 02's
   flow), the Payroll tab reads `Total payroll $3271.93`, `Overtime share 12.9%`
   (421.13 ÷ 3271.93), `Top earner Ava Torres $1203.75` unchanged, and
   `Dev Patel $461.78`; Settings reads `Paid hours: 146.08`, `Overtime hours: 13.50`,
   `Evening hours: 17.42`, with `Employees: 4` and `Shifts: 20` unchanged — an edit
   changes no counts.

4. Both tabs' figures persist across navigation and rewrite with no manual refresh —
   there is no refresh control at all.

## Observable outcome the hidden test checks

Payroll tab shows `Total payroll $3203.43`, `Top earner Ava Torres $1203.75`,
`Overtime share 11.6%` and the four employee rows in gross-descending order → Settings
shows the pay-rules lines and `Paid hours: 143.08`, `Overtime hours: 11.50`,
`Evening hours: 15.92` → Team → `Dev Patel` → `Thu 09:00-16:30` → tap `19:30` → back →
Payroll tab now reads `Total payroll $3271.93`, `Overtime share 12.9%`,
`Dev Patel $461.78` → Settings reads `Paid hours: 146.08`, `Overtime hours: 13.50`,
`Evening hours: 17.42` with `Shifts: 20` unchanged → navigating away and back leaves all
of it in place.
