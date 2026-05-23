---
name: occupancy-snapshot
description: Refreshes the per-block occupancy + financial dashboard for TLKR Campus (and other properties as they're added). Use when the user says "refresh the occupancy dashboard", "TLKR campus occupancy", "what's our occupancy this month?", "block A vs block B comparison", or "update the property dashboard". Pulls room inventory + active leases from CRM and revenue/AR from Xero, produces an xlsx (or live widget) per block.
---

# Occupancy Snapshot

Per-block view of occupancy %, revenue per block, direct expenses, NOI margin, average revenue per room, and AR aging — joining CRM occupancy/roster data with the entity's Xero P&L.

## When to invoke

Run this skill when the user asks for any of:

- A fresh occupancy snapshot for a specific property or block
- A side-by-side comparison of blocks within a property (e.g. TLKR Block A vs Block B)
- A "show me the worst-performing block" / "where's the highest AR" question

## Per-block KPIs computed

For each block:

| Metric | Source |
| --- | --- |
| Total rooms | CRM property inventory |
| Occupied / Booked / Vacant / Reserved | CRM (current state) |
| Occupancy % | Computed |
| Rental income YTD | Xero (Trading Income, filtered by Location) |
| Direct expenses YTD | Xero (Cost of Sales, filtered by Location) |
| Net direct margin + % | Computed |
| Aged receivables (Current, <30d, 30-60d, 60-90d, >90d) | Xero Aged Receivables filtered by Location |
| AR as % of YTD rental | Computed |
| Average rental / room / month YTD | Computed |

## Required environment variables

- `CRM_STAFF_TOKEN`
- `XERO_ACCESS_TOKEN` + `XERO_TENANT_ID` for the relevant entity
- `OCCUPANCY_OUTPUT_FORMAT` — `xlsx` (default) or `artifact` (live Cowork widget)

## How to run it

```bash
# Refresh TLKR Campus (Block A + Block B)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/occupancy.py \
  --property "TLKR Campus" \
  --period YTD \
  --output-dir "drive:Occupancy Dashboards"

# A single block
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/occupancy.py \
  --property "116 LOR J TELOK KURAU" \
  --period YTD

# As a live Cowork artifact instead of xlsx
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/occupancy.py \
  --property "TLKR Campus" --period YTD --format artifact
```

## Validation history

- **TLKR Campus YTD FY2026** dashboard generated 12 May 2026. Block A net direct margin 97.7%, Block B 91.1%. Block B carries higher AR (27% of YTD rental) and ~2× the direct expenses of Block A.
- Co-Livings dashboards not yet built — should fold in once TAP Co-Livings Xero data is fully captured per property.

## See also

- `references/dashboard-format.md` — the xlsx layout used today
- `references/artifact-version.md` — design for the live Cowork widget version
