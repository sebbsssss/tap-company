# Skill: meter-reading-intake

Inbound meter-reading pipeline for TAP. Helmy WhatsApps a meter photo + caption
to the Zernio number; this service receives the webhook, extracts the reading with
Claude vision, logs the row to an xlsx, and replies with confirmation.

## Flow

```
Helmy → WhatsApp → Zernio (+1 856-447-1082)
  → POST /webhook/zernio (tap-meter-intake on Fly)
  → caption parsed (property / utility_type / date)
  → if incomplete: reply asking for missing fields
  → image downloaded from Zernio CDN
  → MeterReadingCalculator (Claude claude-sonnet-4-6 vision) → reading
  → utility_log.append_reading() → /data/utility-logs/utility_log_YYYY-MM.xlsx
  → reply: "Logged: <property> <type> +<delta>"
```

18:00 SGT daily: `python3 daily_digest.py --send live` → digest to Erwan via Zernio

## Scripts

| File | Purpose |
|------|---------|
| `meter_intake.py` | FastAPI app — Zernio webhook receiver |
| `zernio_client.py` | Zernio REST API wrapper (webhooks, inbox reply, image download) |
| `caption_parser.py` | Parses WhatsApp captions → property / utility_type / date |
| `meter_calculator.py` | Claude vision → `{reading, meter_id, confidence}` |
| `utility_log.py` | xlsx writer — one workbook per month, one sheet per property |
| `daily_digest.py` | 18:00 SGT digest to Erwan (route vs. logged comparison) |

## Inputs

Caption format: `<property> <utility_type> <date>`

Property aliases: `18JJ` / `18Penhas` / `51MR` / `TLKR` / `BlockA` / `BlockB`
Utility types: `elec` / `electricity` / `water` / `gas`
Date: ISO `2026-06-11`, `DD/MM`, `DD Mon`, or `today`

## Outputs

### xlsx (utility log)

Path: `UTILITY_LOG_DIR/utility_log_<YYYY-MM>.xlsx` (default `/data/utility-logs/`)

Columns: `date, property, meter_id, utility_type, reading, prev_reading, delta, days_elapsed, reader, notes`

### WhatsApp confirmation

`Logged: 18 JALAN JINTAN electricity +44.0 (reading: 12389.0)`

## Env vars

| Var | Required | Notes |
|-----|----------|-------|
| `ZERNIO_API_KEY` | Yes | Never logged — sealed Fly secret |
| `ANTHROPIC_API_KEY` | Yes | Used by meter_calculator.py |
| `METER_INTAKE_DRY_RUN` | No | `true` (default) — set `false` to enable live sends |
| `UTILITY_LOG_DIR` | No | Override xlsx storage dir (default `/data/utility-logs`) |
| `WEBHOOK_CALLBACK_URL` | No | Used by `/admin/register-webhook` |
| `ERWAN_CONTACT_ID` | For digest | Zernio contact ID for Erwan |
| `ERWAN_INBOX_ID` | For digest | Zernio inbox ID |

## Deploy

```bash
# Create app (first time)
fly apps create tap-meter-intake --org personal

# Set secrets
fly secrets set -a tap-meter-intake \
  ZERNIO_API_KEY=<value> \
  ANTHROPIC_API_KEY=<value> \
  METER_INTAKE_DRY_RUN=false \
  ERWAN_CONTACT_ID=<zernio_contact_id> \
  ERWAN_INBOX_ID=<zernio_inbox_id> \
  WEBHOOK_CALLBACK_URL=https://tap-meter-intake.fly.dev/webhook/zernio

# Create volume
fly volumes create meter_data -a tap-meter-intake -r sin --size 1

# Deploy
fly deploy --config skills/meter-reading-intake/fly.toml

# Register Zernio webhook (once, after deploy)
curl -X POST https://tap-meter-intake.fly.dev/admin/register-webhook \
  -H "Content-Type: application/json" \
  -d '{"callback_url":"https://tap-meter-intake.fly.dev/webhook/zernio"}'
```

## New dependencies

`fastapi`, `uvicorn`, `anthropic` added beyond the existing allowlist
(`openpyxl`, `requests`, `pytest`). Justified by the FastAPI service requirement
and Claude vision extraction per THE-17390.

## Not yet implemented (follow-up)

- Per-property utility cap table from Finance → `vs cap` excess column feeding settlement
- Production WhatsApp Business API (currently uses Zernio sandbox/first account)
- Digest cron scheduling via Fly Machines process groups
