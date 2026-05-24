---
name: tap-finance-brief
description: Generates the monthly TAP-wide CFO Brief covering revenue, expenses, occupancy and AR across all four TAP entities (TLKR, Co-Livings, Hotel, Service Apartment). Use when the user says "draft the CFO brief", "update the finance brief", "monthly leadership summary", "TAP-wide P&L for [month]", or "prep the brief for Yee Chin". Pulls from Xero (per entity) and CRM, produces a Google Doc draft for human review before sharing.
---

# TAP Finance Brief

Cross-entity monthly summary for TAP leadership. Generates a Google Doc draft from Xero + CRM data; never shares automatically.

## When to invoke

Run this skill when the user asks for any of:

- The monthly leadership brief ("draft the May 2026 brief")
- An updated CFO brief after a data correction ("refresh the brief with the new Xero export")
- A specific section ("just give me the AR + occupancy section for May")

## What it does NOT do

- **Does not auto-share.** Output is a draft Google Doc in the installer's Drive — Sebastien / Yee Chin reviews before sharing with the CFO.
- **Does not modify any source data.** Read-only across Xero, CRM, and historical briefs.
- **Does not project forward.** Backwards-looking summary; forecasting is a separate workflow.

## Required environment variables

- `CRM_STAFF_TOKEN`
- `XERO_ACCESS_TOKEN` + tenant IDs for each entity:
  - `XERO_TENANT_TLKR` — TLKR Pte Ltd (201901964D)
  - `XERO_TENANT_COLIVINGS` — TAP Co-Livings (202300680H)
  - `XERO_TENANT_HOTEL` — pending entity name
  - `XERO_TENANT_SERVICE_APT` — pending entity name
- `BRIEF_OUTPUT_FOLDER` — Google Drive folder ID for drafts

## What's in the brief (v4 target)

The brief is structured around the four entities, not consolidated. Each entity gets:

1. **Headline P&L** — revenue, total expenses, net margin for the period vs prior period
2. **Occupancy** — total rooms, occupied, vacant, booked, reserved (from CRM)
3. **AR snapshot** — aged receivables (Current / <30d / 30-60d / 60-90d / >90d)
4. **Top movers** — biggest expense increases vs prior month, biggest revenue contributors

Plus a cross-entity TL;DR at the top: TAP-wide revenue, TAP-wide cost-of-sales, TAP-wide net.

## v1–v3 history (TLKR-only, deprecated)

- **v1** (10 May 2026): First TLKR-only CFO Brief, descriptive of the YTD P&L.
- **v2** (11 May 2026): Added the Unassigned bucket reallocation finding.
- **v3** (11 May 2026): Concise version after meeting note feedback.
- **v4** (in progress): Rework for TAP-wide scope after the 12 May entity reframe discovery (TLKR is only one of four TAP entities). v3 is misleading without this rework — do not share v3 with leadership.

The v4 rework is the gating dependency for sharing the brief with Yee Chin and the CEO.

## How to run it

```bash
# Generate the latest brief for a given month
python3 ./scripts/finance_brief.py \
  --month 2026-05 \
  --output-folder "drive:CFO Briefs"

# Generate only one entity's section (faster for iteration)
python3 ./scripts/finance_brief.py \
  --month 2026-05 --entity tlkr --output-folder "drive:CFO Briefs"

# Use cached Xero exports (if you've already downloaded them to Drive)
python3 ./scripts/finance_brief.py \
  --month 2026-05 --xero-cache "drive:Xero Exports/2026-05" \
  --output-folder "drive:CFO Briefs"
```

## Validation history

- v1–v3 produced and shared with Sebastien for review (none sent to leadership yet — v3 is wrong because it pre-dates the TAP entity reframe).
- TAP Co-Livings Xero access landed 12 May 2026. Hotel + Service Apt entities still pending.
- **v4 generator built 18 May 2026** (this skill). Renders TAP-wide Markdown brief from bundled sample data (TLKR + Co-Livings real numbers; Hotel + Service Apt placeholders). One-line swap to live Xero exports once those API integrations land.

## Status: working

This skill now bundles a working `finance_brief.py` script (`./scripts/finance_brief.py`) that produces a real Markdown brief from the bundled `sample_finance_entities.json`. Run it as documented above — you get a brief ready to paste into Google Docs.

To use live data: replace `sample_finance_entities.json` with a freshly-pulled per-entity data file (same schema). When the CRM + Xero MCP servers ship, this becomes an automatic pull.

## See also

- `references/brief-template-v4.md` — the structure of the v4 output Google Doc
- `references/entity-mapping.md` — which TAP entities exist and their Xero tenant IDs
- `references/v3-to-v4-deltas.md` — what's changing from v3 to v4 (scope + section structure)
