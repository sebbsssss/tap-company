# TAP Live Ops Portal

A triage and reply web view for TAP ops staff. Mirrors live CRM ticket state and proxies writes back to the CRM. CRM stays the source of truth.

**Live URL:** https://tap-company.fly.dev/ops-portal

## Access

The portal uses magic-link email auth. Only addresses in the allowlist can sign in.

### Grant access

```bash
fly secrets set OPS_PORTAL_ALLOWED_EMAILS="faisal@example.com,irwan@example.com" --app tap-company
```

The secret is comma-separated. Changing it takes effect on the next machine start (or immediately on the next `fly deploy`).

### Revoke access

Remove the email from the list and redeploy:

```bash
fly secrets set OPS_PORTAL_ALLOWED_EMAILS="remaining@example.com" --app tap-company
```

Existing sessions are validated on every request via the session DB — they expire after 24 hours.

## Audit Log

Every CRM write (comment, status change, draft approval) made through the portal is appended to the audit log on the Fly machine volume:

```
/data/audit/ticket-auto-reply.log
```

Log format (one JSON object per line):

```json
{"timestamp": "2026-06-08T03:00:00Z", "actor": "ops@example.com", "action": "comment", "ticket_id": "12345", "details": {...}}
```

### Reading the audit log

SSH into the machine:

```bash
fly ssh console --app tap-company
cat /data/audit/ticket-auto-reply.log
```

Or tail it live:

```bash
fly ssh console --app tap-company -C "tail -f /data/audit/ticket-auto-reply.log"
```

## Kill Switch

The kill switch disables all bot auto-actions (draft approvals, auto-replies) instantly without a code redeploy:

```bash
# Disable bot
fly secrets set OPS_PORTAL_BOT_ENABLED=false --app tap-company

# Re-enable bot
fly secrets set OPS_PORTAL_BOT_ENABLED=true --app tap-company
```

The kill switch is read on every request — no machine restart required.

Check current state: `GET /ops-portal/health` returns `{"status":"ok","bot_enabled":true|false}`.

## Deployment

The portal is embedded in the `tap-company` Fly app at `/ops-portal`. It runs as a FastAPI process alongside the occupancy dashboard, with nginx routing between them.

### Architecture

```
tap-company.fly.dev
  ├── /          → occupancy dashboard (Python stdlib HTTP)
  ├── /healthz   → occupancy health check
  └── /ops-portal → FastAPI (CRM proxy + auth + audit)
        ├── /health
        ├── /auth/*
        ├── /api/tickets/*
        └── /          (frontend HTML/JS/CSS)
```

### Redeploy

Any push to `main` touching `portals/ops/**`, `Dockerfile`, `nginx.conf`, or `fly.toml` triggers auto-deploy via GitHub Actions.

Manual redeploy from repo root:

```bash
flyctl deploy --config fly.toml --remote-only --app tap-company
```

### Update secrets

```bash
fly secrets set KEY=value --app tap-company
```

Key secrets:
- `OPS_PORTAL_ALLOWED_EMAILS` — comma-separated ops staff emails
- `OPS_PORTAL_BOT_ENABLED` — `true` or `false`
- `CRM_API_KEY` — CRM staff API key
- `SECRET_KEY` — session signing key

## Code Location

```
portals/ops/
  backend/          FastAPI app (CRM proxy, auth, audit, kill switch)
  frontend/         HTML + vanilla JS (three screens: table, detail, bot audit)
  fly.toml          Fly config for the embedded service (via tap-company root fly.toml)
  README.md         This file
```
