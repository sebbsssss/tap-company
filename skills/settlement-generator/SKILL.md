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
- `ANTHROPIC_API_KEY` — required when `--gmail-search` is used (Claude Haiku inference per email)

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
python3 ./scripts/settlement.py \
  --property "18 Jln Jintan" \
  --period 2026-03 \
  --output-dir "drive:Settlement Reports/2026"

# Partial period
python3 ./scripts/settlement.py \
  --property "18 Jln Jintan" \
  --start 2026-05-01 --end 2026-05-11 \
  --output-dir "drive:Settlement Reports/2026"

# Comparison mode (against an existing reference file)
python3 ./scripts/settlement.py \
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
| **Cleaning charges** | Gmail (jarvis.ai inbox) when `--gmail-search` used; `property_defaults.json` fallback; else yellow | ✅ with `--gmail-search`; $0 if not found in inbox (not yellow) |
| **Servicing items** | Gmail (jarvis.ai inbox) when `--gmail-search` used | ✅ with `--gmail-search`; $0 if not found in inbox (not yellow) |
| **Utilities (Excess Utility rule)** | CRM Operations → Excess Utility | ✅ when `--utility` JSON supplied; auto-zero for `property_kind=campus`; ⏳ yellow cell otherwise |
| Security deposits net | Xero Deposit Received Transactions | ⏳ Pending Xero MCP integration |
| Payment on behalf (Whiz subscriptions etc.) | Xero Account Transactions filtered to Location | ✅ partial — current month only; back-bill window pending |

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
python3 ./scripts/settlement.py \
  --property "18 JALAN JINTAN" --landlord "Yeoh Joe Wei Evelyn" \
  --period 2026-03 \
  --roster crm_mar.json --xero xero_mar.json \
  --utility crm_utility_mar.json \
  --output settlement_mar26.xlsx
```

## Gmail auto-source — cleaning + servicing

**Architecture (Sebastien, THE-17480):** This is an **always-on inbox watcher + classifier → structured store** system. Settlement runs read from the store — they do NOT scan email at xlsx-build time.

```
jarvis.ai Gmail inbox
       │
       ▼  (every 15 min)
inbox_watcher.py ──→ email_classifier.py (Claude Haiku)
       │                    │
       │                    ├── Finance email → actuals_store.py → Notion DB
       │                    ├── Ops email     → ops_routing_stub() [v1: log only]
       │                    └── Neither       → skip
       │
settlement.py ──→ gmail_search.py ──→ actuals_store.py ──→ Notion DB query
```

**Not found → `$0.00`, never yellow.** Yellow is reserved for "source not yet searched at all".

### Setup

#### 1. OAuth credentials (jarvis.ai@theassemblyplace.com)

```
JARVIS_GOOGLE_CLIENT_ID     = 588437766403-...
JARVIS_GOOGLE_CLIENT_SECRET = GOCSPX-...
JARVIS_GOOGLE_REFRESH_TOKEN = 1//...   (minted for jarvis.ai@theassemblyplace.com)
```

See [THE-17484](/THE/issues/THE-17484) for OAuth mint instructions (William / delegation).

#### 2. Notion actuals DB

Create a Notion database with these properties:

| Property | Type | Notes |
| --- | --- | --- |
| Name | title | auto: "PROPERTY MONTH TYPE" |
| Property | rich_text | property address |
| Month | rich_text | "2026-06" |
| Line Item Type | select | cleaning / servicing / stock / deposits / excess_utility / pob / other |
| Amount | number | SGD |
| Description | rich_text | detail text |
| Source Email ID | rich_text | Gmail message ID |
| Source Email Subject | rich_text | |
| Source Email Date | date | |
| Confidence | number | 0.0–1.0 |
| Processed At | date | when watcher processed it |

Then set:
```
NOTION_API_KEY         = secret_...   (Notion integration token)
NOTION_ACTUALS_DB_ID   = <database-id-from-URL>
```

Falls back to a local JSON file at `ACTUALS_STORE_PATH` (default `/data/actuals_store.json`) if Notion env vars are absent.

#### 3. Watcher routine

The inbox watcher runs as a Paperclip routine assigned to Finance Lead, firing every 15 min. See [THE-17492](/THE/issues/THE-17492) — Finance Lead creates this routine for themselves.

### Scripts

| Script | Role |
| --- | --- |
| `scripts/inbox_watcher.py` | Polling orchestrator — runs every 15 min via routine |
| `scripts/email_classifier.py` | Claude Haiku: classify + extract line items per email |
| `scripts/actuals_store.py` | Notion DB interface (+ JSON fallback) |
| `scripts/gmail_search.py` | Store reader — called by settlement.py at xlsx time |

### Run with actuals auto-source

```bash
# Standard run — cleaning + servicing auto-populated from Notion store
python3 ./scripts/settlement.py \
  --property "18 JALAN JINTAN" \
  --landlord "Yeoh Joe Wei Evelyn" \
  --period 2026-05 \
  --roster crm_may.json --xero xero_may.json \
  --gmail-search \
  --output settlement_may26.xlsx
```

The `--gmail-search` flag still works — it now reads from the Notion store instead of scanning Gmail at xlsx time.

### Classifier — line item types

| Type | Maps to | Examples |
| --- | --- | --- |
| `cleaning` | Cleaning row | "cleaning charge", "cleaner fee", "housekeeping" |
| `servicing` | Servicing row(s) | "aircon service", "pest control", "plumbing repair" |
| `stock` | Stock taken row | "stock vouchers", "supplies" |
| `deposits` | Deposit rows (settlement.py handles separately) | "security deposit" |
| `excess_utility` | Utility row (settlement.py handles separately) | "excess utility" |
| `pob` | POB row (settlement.py handles separately) | "Whiz subscription", "payment on behalf" |
| `other` | Servicing row (with Finance description) | anything Finance-relevant not fitting above |

### Manual watcher test

```bash
# Dry-run: classify but don't write to store
python3 ./scripts/inbox_watcher.py --dry-run --verbose

# Backfill: process all emails since a given timestamp
python3 ./scripts/inbox_watcher.py --since 2026-06-01T00:00:00Z --verbose

# Read what's in the store for a property+month
python3 ./scripts/gmail_search.py "18 JALAN JINTAN" 2026-05
```

### Required env vars (full list)

```
JARVIS_GOOGLE_CLIENT_ID
JARVIS_GOOGLE_CLIENT_SECRET
JARVIS_GOOGLE_REFRESH_TOKEN
ANTHROPIC_API_KEY
NOTION_API_KEY
NOTION_ACTUALS_DB_ID
WATCHER_STATE_PATH    (default: /data/watcher_state.json)
ACTUALS_STORE_PATH    (default: /data/actuals_store.json — JSON fallback only)
```

## Validation history

- **March 2026 — 18 Jln Jintan**: Generated and compared against Finance's actual file. **Straight-lease net to owner matched to the cent ($16,798.83).** Discovered B05 (Zhu Yichen) discrepancy: CRM shows her active; Finance's file omits her. Open question to confirm with Finance.
- **May 1–11 2026 — 18 Jln Jintan**: Partial-period preview generated. Correctly identified no new commission events in the window; Xero base rent + additional rent not yet booked (typical mid-month state).
- **TLKR Campus — YTD FY2026**: Block A + Block B sheets generated with P&L + sample roster from CRM.

## Status: working

This skill now bundles a working `settlement.py` script (`./scripts/settlement.py`) plus two demo configurations. Output is an xlsx in Finance's exact template with 33 formulas, all yellow input cells for the manual items (cleaning, utilities, deposits, servicing), and the straight-lease summary block at the bottom.

Run it with bundled samples to see the exact format Finance expects:

```bash
python3 ./scripts/settlement.py --sample 18jln_jintan-mar26 --output ./mar.xlsx
python3 ./scripts/settlement.py --sample 18jln_jintan-may1-11 --output ./may_partial.xlsx
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
