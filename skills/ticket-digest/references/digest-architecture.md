# Ticket Digest Architecture

## Data flow

```
CRM staff API  →  digest.py  →  formatter  →  twilio_send.sh  →  WhatsApp
   (/com/service/         (flatten         (markdown-          (Sandbox or
    tickets/)              nested →         style for           Business API)
                           flat)            WhatsApp)
```

Until staff token lands, the script falls back to the member API (`/member/service/tickets/`) which only sees one tenant's tickets — sufficient for pipeline validation, not for real ops use.

## Schema mapping

The CRM API returns deeply nested objects. The script's `_flatten_ticket()` function maps them to a flat shape the formatter consumes:

| Flat field | Source path in API response |
| --- | --- |
| `ticket_id` | `id` |
| `service` | `category.service` ("Housekeeping" \| "Maintenance") |
| `category` | `category.name` (e.g. "Aircon", "Plumbing", "WiFi Down") |
| `ticket_priority` | `priority.name` ("Low" \| "Mid" \| "High") |
| `area` | `room.unit.prop.area` ("North" \| "South" \| "East" \| "West" \| "Central") |
| `property` | `room.unit.prop.name` (e.g. "96 OWEN", "SOPHIA VIEW") |
| `unit` | `room.unit.name` (e.g. "#03-01") |
| `room` | `room.number` (e.g. "304", "Studio", "Lobby") |
| `created_at` | `created` |
| `ticket_status` | Most recent entry in `statuses[]`, by `created` timestamp |
| `last_staff_reply_at` | Max `created` across `statuses[]` |
| `comment_count` | `len(statuses)` |
| `remarks` | `remarks` (the description text) |
| `raised_by` | `raised_by.name` |

## Status values

Open (still need attention): `Open`, `Acknowledged`, `In Progress`, `Scheduled`
Closed (terminal): `Completed`, `Rejected`, `Duplicate`

Confirmed from the live Ticket Status dropdown 14 May 2026.

## Digest sections (in order)

1. **Headline**: total open, new in last 2h, activity in last 30d
2. **Age buckets**: <24h, 1-7d, 1-4w, >1mo
3. **By service**: Housekeeping vs Maintenance
4. **By priority**: High (emphasized), Mid, Low, unset
5. **By area**: North/South/East/West/Central
6. **By category** (top 6 most common)
7. **Top properties** (top 5)
8. **Top priorities**: 7 oldest-within-highest-priority
9. **Oldest unresolved**: 5 oldest across any priority

When `total open == 0`, the script falls back to "recent activity (last 30d)" or "all-time accessible tickets" so the digest still has signal.

## Formatting conventions

- WhatsApp markdown: `*bold*`, `_italic_`, no `**double-asterisk**`.
- Each line stays under ~80 chars to avoid awkward wraps on mobile.
- Total digest length typically 1-2 KB — well under WhatsApp's 4096-char message limit.
- No emojis (keeps it scannable; staff can re-introduce later).

## Cost economics

The digest itself uses zero LLM calls — pure aggregation. Twilio Sandbox costs nothing; production WhatsApp Business charges ~$0.005/message. Even at 12 sends/day (every 2h), that's <$2/month.

## Failure handling

The script halts on any API error. Failures fall into three buckets:

| HTTP status | Likely cause | Recovery |
| --- | --- | --- |
| 401, 403 | Token expired or revoked | Re-issue via `POST /com/auth/login/`; update env |
| 5xx | CRM transient outage | Schedule's next run will retry automatically |
| Network timeout | Cowork sandbox network blip | Same; retry on schedule |

Twilio failures (non-`queued` status) bubble up to the schedule runner, which notifies the user via Cowork.
