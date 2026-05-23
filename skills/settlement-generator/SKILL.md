---
name: settlement-generator
description: Generates owner settlement letters for TAP-managed properties — per-tenant for co-livings, per-block for TLKR Campus. Use when the user says "generate the settlement for [property] [month]", "build settlement letter for [owner]", "run the monthly settlement", "draft settlement for 18 Jln Jintan", or "settle TLKR Campus for [month]". Pulls tenant roster from CRM, financial data from Xero, and produces an xlsx in Finance's preferred format with a comparison sheet against the prior month.
---

# Settlement Generator

Generates owner settlement letters in Finance's exact xlsx format, sourced from CRM tenant rosters and Xero P&L data.

## When to invoke

Run this skill when the user asks for any of:

- A new monthly settlement letter for a specific property + owner
- A partial-month settlement (e.g. mid-month closeout when a tenancy ends)
- A re-run of an existing settlement after Xero data lands
- A comparison between TAP's draft and Finance's prior-month file (validation mode)

## Two settlement formats supported

| Format | Used for | Logic |
| --- | --- | --- |
| **Per-tenant (Co-livings)** | TAP Co-Livings properties (18 Jln Jintan, 18 Penhas, 51 Middle Rd, etc.) | One letter per property per month, listing each commissioned tenant's contribution + deductions (cleaning, utilities, deposits, payment-on-behalf, servicing) |
| **Per-block (TLKR Campus)** | 116 LOR J + 119 LOR K (Telok Kurau student housing) | Building-level P&L sharing — one settlement per block per month |

The skill picks the right format from the property's `property_kind` field in the CRM.

## Required environment variables

- `CRM_STAFF_TOKEN` — required (this is staff-scope work; member token won't see cross-tenant rosters)
- `CRM_API_BASE` — defaults to `https://crm-api.theassemblyplace.com`
- `XERO_ACCESS_TOKEN` + `XERO_TENANT_ID` — for the entity being settled (TAP Co-Livings is UEN 202300680H; TLKR is 201901964D)
- Output destination: `SETTLEMENT_OUTPUT_DIR` — Google Drive folder ID (or local path for testing)

## Inputs the user provides

When invoking, the user names a **property** and a **period**. Examples:

- "Generate the settlement for 18 Jln Jintan, March 2026"
- "Run TLKR Campus Block A for April 2026"
- "Partial settlement for 18 Jln Jintan 1–11 May 2026"

The skill resolves the property to a CRM property ID, the owner from the property's default_landlord, and the period boundaries automatically.

## How to run it

Locate the generator scripts in this plugin's `scripts/` directory.

```bash
# Standard monthly run
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/settlement.py \
  --property "18 Jln Jintan" \
  --period 2026-03 \
  --output-dir "drive:Settlement Reports/2026"

# Partial period
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/settlement.py \
  --property "18 Jln Jintan" \
  --start 2026-05-01 --end 2026-05-11 \
  --output-dir "drive:Settlement Reports/2026"

# Comparison mode (against an existing reference file)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/settlement.py \
  --property "18 Jln Jintan" --period 2026-03 \
  --compare-to "drive:fileId/abc123" \
  --output-dir "drive:Settlement Reports/2026"
```

Output is an xlsx with these sheets:
- **Settlement [Period]** — the actual letter, matches Finance's template exactly
- **Comparison vs Finance** (when `--compare-to` given) — line-by-line deltas
- **CRM Roster (raw)** — what the CRM returned, for audit
- **Xero P&L** — what Xero returned for the period, for audit

## What's auto-extracted vs left manual

| Item | Source | Auto? |
| --- | --- | --- |
| Tenant roster (name, room, rate, lease dates) | CRM Reports → Settlement | ✅ |
| Management fee (15%) + commission (1 month / 24) | Computed | ✅ |
| Base rent + additional rent to owner | Xero P&L (Straight Lease - Rental of premises, Rental of premises) | ✅ |
| Cleaning charges | property_defaults.json (when standing) or Finance email | ✅ for 18 Jln Jintan; ⏳ yellow cell otherwise |
| **Utilities (Excess Utility rule)** | CRM Operations → Excess Utility | ✅ when `--utility` JSON supplied; auto-zero for `property_kind=campus`; ⏳ yellow cell otherwise |
| Security deposits net | Xero Deposit Received Transactions | ⏳ Pending Xero MCP integration |
| Payment on behalf (Whiz subscriptions etc.) | Xero Account Transactions filtered to Location | ✅ partial — current month only; back-bill window pending |
| Servicing items | Maintenance ticket system | ⏳ Manual — yellow cell |

## Excess Utility — calculation rule

Source: [Notion meeting 12 May 2026 — Property Management Settlement & Automation Discussion](https://www.notion.so/35da25ce804f81969a1cc207cdd50e83). Each booking carries a utility cap, viewable in CRM under booking details. Two cap modes:

- **per_room** — unit allowance = sum of per-room caps (e.g. 6 rooms × $100 = $600)
- **per_unit** — unit allowance = highest cap among bookings in that unit

Excess = `max(0, actual_bill − unit_allowance)`, split evenly across all tenants in the unit.

**Campus branch:** TLKR Campus tenants have NO utility caps — the company absorbs all utility costs. When `property_kind == "campus"` (from `property_defaults.json` or `--property-kind campus`), the utility row is auto-zeroed with a "N/A (Campus)" note.

**Utility input JSON shape** (see `scripts/sample_utility_18jntn_mar26.json`):

```json
{
  "_source": "CRM Operations → Excess Utility export",
  "units": [
    {
      "unit_id": "Whole shophouse",
      "cap_mode": "per_room",
      "actual_bill": 850.00,
      "bookings": [
        {"tenant": "Guan Mingjun", "room": "B01", "cap": 100.00}
      ]
    }
  ]
}
```

The generated xlsx includes a **Utility Excess Detail** audit sheet showing per-unit allowance math + per-tenant split — lets Finance trace the deducted amount back to the SP bill and CRM caps.

Run with utility auto-fill:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/settlement.py \
  --property "18 JALAN JINTAN" --landlord "Yeoh Joe Wei Evelyn" \
  --period 2026-03 \
  --roster crm_mar.json --xero xero_mar.json \
  --utility crm_utility_mar.json \
  --output settlement_mar26.xlsx
```

## Validation history

- **March 2026 — 18 Jln Jintan**: Generated and compared against Finance's actual file. **Straight-lease net to owner matched to the cent ($16,798.83).** Discovered B05 (Zhu Yichen) discrepancy: CRM shows her active; Finance's file omits her. Open question to confirm with Finance.
- **May 1–11 2026 — 18 Jln Jintan**: Partial-period preview generated. Correctly identified no new commission events in the window; Xero base rent + additional rent not yet booked (typical mid-month state).
- **TLKR Campus — YTD FY2026**: Block A + Block B sheets generated with P&L + sample roster from CRM.

## Status: working

This skill now bundles a working `settlement.py` script (`${CLAUDE_PLUGIN_ROOT}/scripts/settlement.py`) plus two demo configurations. Output is an xlsx in Finance's exact template with 33 formulas, all yellow input cells for the manual items (cleaning, utilities, deposits, servicing), and the straight-lease summary block at the bottom.

Run it with bundled samples to see the exact format Finance expects:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/settlement.py --sample 18jln_jintan-mar26 --output ./mar.xlsx
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/settlement.py --sample 18jln_jintan-may1-11 --output ./may_partial.xlsx
```

To use your own data, supply `--roster` (CRM tenant roster as JSON) and `--xero` (P&L data as JSON). The schemas are documented in `settlement.py` and matched against samples bundled at `scripts/sample_roster_*.json` + `scripts/sample_xero_*.json`.

## Running without Xero MCP (manual input mode)

The skill doesn't depend on the Xero MCP. The script accepts `--roster`, `--xero`, `--utility` as JSON file paths — those JSONs can be generated from Xero MCP output OR from numbers Finance pastes into a Paperclip issue.

See **`references/manual-input-template.md`** for the copy-paste template Finance uses. The agent parses the template, writes the JSONs to temp files, and invokes the skill identically. The xlsx output is the same whether the inputs came from MCP or paste.

This is the recommended workflow until Xero Custom Connection is provisioned (~$10/month per entity) and the official Xero MCP is wired into Claude Code on the heartbeat host.

## See also

- `references/settlement-format.md` — full breakdown of the xlsx structure Finance uses
- `references/validation-march-jln-jintan.md` — the comparison findings + B05 question
- `references/property-kind-routing.md` — how the skill decides per-tenant vs per-block format
- `references/manual-input-template.md` — copy-paste template for the no-Xero-MCP path
- `references/utility-backtest-2026-05-20.md` — why the owner-utility row is yellow-input
