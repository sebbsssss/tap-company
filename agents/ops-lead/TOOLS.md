# Tools — TAP Ops Lead

## CRM (DRF API)

Base: `${CRM_API_BASE}` (defaults to `https://crm-api.theassemblyplace.com`).

### Auth (per heartbeat)

```bash
# Staff scope (preferred — unlocks /com/* endpoints)
curl -s -X POST -H "Content-Type: application/json" \
  "${CRM_API_BASE}/com/auth/login/" \
  -d "{\"email\":\"${CRM_STAFF_EMAIL}\",\"password\":\"${CRM_STAFF_PASSWORD}\"}" \
  | jq -r .key

# Member scope (fallback)
curl -s -X POST -H "Content-Type: application/json" \
  "${CRM_API_BASE}/member/auth/login/" \
  -d "{\"email\":\"${CRM_MEMBER_EMAIL}\",\"password\":\"${CRM_MEMBER_PASSWORD}\"}" \
  | jq -r .key
```

Header: `Authorization: Token <key>` (NOT Bearer).

### Endpoints

| Endpoint | Use |
| --- | --- |
| `GET /com/service/tickets/` (or `/member/service/tickets/`) | Ticket digest |
| `GET /com/users/?search=<name>` | Tenant lookup |
| `GET /com/bookings/?...` | Active leases, renewal-eligible tenants |
| `GET /com/operations/property-operations-data/{id}/` | Property-level ops data |

### Quirk

Tickets API returns nested structure — flatten before grouping. Sample response shape in `../../skills/ticket-digest/references/` once auth lands.

## Twilio (WhatsApp Sandbox)

Env: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_SANDBOX_FROM` (e.g. `whatsapp:+14155238886`).

### Send a message

```bash
curl -s -X POST -u "${TWILIO_ACCOUNT_SID}:${TWILIO_AUTH_TOKEN}" \
  "https://api.twilio.com/2010-04-01/Accounts/${TWILIO_ACCOUNT_SID}/Messages.json" \
  --data-urlencode "From=${TWILIO_SANDBOX_FROM}" \
  --data-urlencode "To=whatsapp:+65XXXXXXXX" \
  --data-urlencode "Body=Your message here"
```

### Quirks

- Sandbox numbers must have opted in once via the sandbox join code (one-time setup per recipient).
- Rate limits: stay under 1 msg/sec to a given number.
- WhatsApp 24h template window: if you haven't messaged a tenant in 24h, only template messages work.

### Test number

`TWILIO_TEST_TO` env var (if set) overrides recipient — use it for dry-run digest sends.

## Skill scripts

| Skill | CLI entrypoint |
| --- | --- |
| `ticket-digest` | `python3 ${SKILLS_ROOT}/ticket-digest/scripts/digest.py` |
| `lease-renewal-reminder` | `python3 ${SKILLS_ROOT}/lease-renewal-reminder/scripts/*.py` |
| `occupancy-snapshot` | `python3 ${SKILLS_ROOT}/occupancy-snapshot/scripts/*.py` |

## Xero (read-only, limited use)

You don't usually need Xero directly — Finance Lead owns that. The exception is occupancy snapshot, where you pull YTD revenue + AR per entity via the Xero MCP `get_profit_and_loss` + `get_contacts_and_receivables` tools.

## Paperclip API

Same set as Finance Lead. Common patterns:
- Get assigned issues, comment with results
- Create subtasks back to Finance Lead when something needs financial validation
- Save memory: digest counts, renewal messages sent, occupancy deltas

## Living notes

- (Record Twilio rate-limit surprises here.)
- (Record CRM ticket field shape changes here.)
- (Record CM-group response patterns — which questions get fast replies, which need re-pinging.)
