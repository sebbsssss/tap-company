# Utility backtest — 20 May 2026

Cross-checked the v0.5 Excess Utility auto-fill against Finance's actual February and March 2026 owner settlements for 18 Jln Jintan.

## Headline result

The Notion meeting's "per-unit / per-room cap, excess split across tenants" rule **describes tenant-side invoice math, not the owner-settlement utility line**. The two are different deliverables. v0.5's auto-fill conflated them; v0.5.1 separates them.

## The numbers

| Source | Mar 2026 utility | Feb 2026 utility | Method |
|---|---|---|---|
| v0.5 plugin (sample) | $250.00 (Qty 6 × $41.67) | n/a | per-tenant excess applied to owner row |
| Finance actual file | $85.83 (Qty 1) | $82.30 (Qty 1) | single line, period = SP billing cycle |
| Annual roll-up | Jan $600.00, Feb $82.30, Mar $85.83 | — | Jan = exactly 6 × $100 standing cap |

If v0.5 had been used to generate Finance's March file unattended, the owner would have been **over-deducted by ~$164.17** in that month alone.

## Why the numbers differ

Finance's owner-side line:

- single row, Qty=1
- period spans an SP billing cycle (~30 days, e.g. 12 Feb–13 Mar), not a calendar month
- stable, small (~$82–$86 Feb/Mar)
- January was a one-off $600 (= 6 × $100 standing per-room cap) — suggests methodology changed in Feb

The Notion methodology (per-unit/per-room cap, excess split evenly) clearly describes what tenants are billed above their allowance. It would produce a number on the order of (actual_bill − allowance), divisible by tenant count — not the small stable number Finance puts on the owner letter.

## Three candidate hypotheses for the owner-side formula

Without sight of the actual SP bills, the owner-side number could be any of:

1. **Bill share owner reimburses TAP** — owner pays TAP a specific portion (e.g. common-area meter, service charge); the rest of the SP bill is covered by tenant allowances built into rent + tenant excess invoiced separately.
2. **Net TAP-out-of-pocket** — actual SP bill minus tenant allowance minus tenant excess invoiced. Whatever's left is owner-charged.
3. **A flat property service/regulatory levy** — small stable amount unrelated to actual SP math.

Jan's $600 = 6 × $100 standing cap is too coincidental to ignore — it suggests Jan used one rule and Feb-onwards switched to another.

## What changed in v0.5.1

- Owner-settlement utility row is back to a **yellow input cell** with a "Finance to fill; formula pending verification" note
- The `compute_excess_utility()` function is still here and still correct **for tenant invoicing**
- Audit sheet renamed `Utility Excess Detail` → **`Tenant Excess Utility`** and clearly labelled "for tenant invoicing only; owner formula different"
- When utility data IS supplied, the yellow-input row label mentions the computed tenant-side total for context, so Finance can sanity-check

## Open question for Finance (Yee Chin)

What's the formula for the utility line item on the owner settlement letter? Specifically:

- Why did Jan 2026 = $600 but Feb–Mar 2026 = $82–86?
- Is it (SP bill − tenant collections), a fixed reimbursement, or a property service fee?
- Does the SP billing-cycle date range (e.g. 12 Feb–13 Mar for the Mar letter) carry meaning, or is it just informational?

Once we have an answer we can wire a SECOND auto-fill that's actually correct for the owner row, alongside the tenant-side calculation we already have.

## Files referenced

- Finance Feb file: `Feb'26 settlement for 18 Jln Jintan.xlsx` — row 32, utility = $82.30
- Finance Mar file: `Mar'26 settlement for 18 Jln Jintan.xlsx` — row 31, utility = $85.83
- Cross-property roll-up: `Settlement report for 18 Jln Jintan.xlsx` — confirms monthly pattern
- Source meeting: [Notion — Property Management Settlement & Automation Discussion (12 May 2026)](https://www.notion.so/35da25ce804f81969a1cc207cdd50e83)
