# Tools — TAP Finance Lead

## Xero (read-only MCP)

Connected via the Xero MCP server. Tools available (per organisation; switch entities via `XERO_TENANT_ID_*` env):

| Tool | Use |
| --- | --- |
| `get_profit_and_loss` | Pull P&L. Entity-wide only — no Location filter (Xero API limitation). |
| `get_contacts_and_receivables` | Top-N AR aggregate. For specific tenant lookups, use Xero web UI via Chrome MCP. |
| `get_cash_position` | Cash + working capital snapshot. |
| `get_financial_position` | Balance sheet snapshot. |
| `get_top_customers_by_revenue` | Top revenue contributors. |
| `get_organisation_financial_year` | Period boundaries. |
| `get_connected_user_organisation` | Confirms which entity you're connected to. |

**Quirk:** `get_profit_and_loss` doesn't filter by tracking category (Location). For per-property P&L, fall back to the Xero web UI via Chrome MCP and pull the by-Location report manually.

**Fallback for individual invoice lookups:** Chrome MCP. Navigate to `https://go.xero.com/Contacts/Search.aspx?q=<name>` or the global search at the magnifying glass icon. Direct invoice URL pattern: `https://go.xero.com/AccountsReceivable/View.aspx?invoiceid=<GUID>`.

## CRM (DRF API)

Base URL: `${CRM_API_BASE}` (defaults to `https://crm-api.theassemblyplace.com`).

### Auth

Login per heartbeat (tokens rotate):
```bash
POST /com/auth/login/   # staff scope — required for /com/* endpoints
POST /member/auth/login/  # member scope — fallback
Body: {"email": "...", "password": "..."}
Returns: {"key": "<40-char hex token>"}
```

Header for subsequent calls: `Authorization: Token <key>` (NOT Bearer).

### Endpoints you'll actually use

| Endpoint | Use |
| --- | --- |
| `GET /com/report/settlement/` | Tenant roster for a property + period |
| `GET /com/operations/property-operations-data/{id}/utilities/` | Excess Utility data |
| `GET /com/users/?search=<name>` | Tenant lookup by name (case-insensitive, space-sensitive) |
| `GET /com/bookings/?...` | Booking lookup by ID or member code |
| `GET /com/service/tickets/` | Tickets (handed off to Ops Lead usually) |
| `GET /com/dashboard/*` | 16 management dashboards (revenue, occupancy) |
| `GET /com/xero/connect/`, `GET /com/xero/test/` | CRM-side Xero bridge (may simplify some workflows) |

### Quirk

CRM Angular web UI sometimes renders as a dark screen — known issue. Refresh once; if still broken, use the API instead.

## Settlement generator

Bundled in the `settlement-generator` skill at `../../skills/settlement-generator/`. CLI:

```bash
python3 ${SKILLS_ROOT}/settlement-generator/scripts/settlement.py \
  --property "18 JALAN JINTAN" --landlord "Yeoh Joe Wei Evelyn" \
  --period 2026-03 \
  --roster roster.json --xero xero.json [--utility utility.json] \
  --output settlement.xlsx
```

For Excess Utility math, you can also call `compute_excess_utility(data)` directly — the function is exported. Use the result for tenant-side calculations only; do NOT plug it into the owner settlement row until Yee Chin confirms the formula.

## Google Drive

Use the Drive MCP if connected; otherwise output local xlsx and ask Ops to upload.

Standard path for final settlement files: `Settlement Reports/<year>/<property> — <period>.xlsx`.

## Twilio

You don't have Twilio access. Hand off WhatsApp sends to Ops Lead.

## Paperclip API

| Endpoint | Use |
| --- | --- |
| `GET /api/issues?assigneeId=...&status=open` | Pull your assigned work |
| `POST /api/issues/{id}/comments` | Post results, ask questions |
| `POST /api/issues` with `parentId` | Create a subtask (e.g. ask Ops Lead to send a WhatsApp) |
| `POST /api/memory/extract` | Save facts for future heartbeats |
| `POST /api/approvals` | Request board approval for a risky action |

## Living notes

Add quirks here as you find them:
- (When you discover an edge case in Xero's auto-match behaviour, note it here so the next heartbeat doesn't re-discover it.)
- (When CRM endpoints change shape, capture the new shape here so the skill scripts don't break silently.)
