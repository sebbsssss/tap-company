# TAP Live Ops Portal

Dark-themed web portal for the TAP ops team to view, triage, and reply to CRM maintenance tickets. Powered by a FastAPI backend proxying the TAP CRM, with magic-link auth and an audit log.

- **Production:** https://tap-ops-portal.fly.dev
- **Staging:** https://tap-ops-portal-staging.fly.dev

---

## Access: grant or revoke

Access is controlled by a comma-separated list of allowed emails in the `OPS_PORTAL_ALLOWED_EMAILS` Fly secret.

**Grant access** (add an email):

```bash
# Get current list
fly secrets list -a tap-ops-portal | grep OPS_PORTAL_ALLOWED_EMAILS

# Set the full updated list (replaces the existing value)
fly secrets set -a tap-ops-portal \
  OPS_PORTAL_ALLOWED_EMAILS="faisal@theassemblyplace.com,newperson@theassemblyplace.com"
```

**Revoke access** — same command, omit the person's email from the list.

After updating secrets, the app hot-reloads the env var on the next request — no redeploy needed (the allowed-emails check reads `os.environ` at request time).

---

## Reading the audit log

Every write action (comment, status change, draft approval) is logged to `/data/audit/ticket-auto-reply.log` on the Fly volume. Each line is:

```
2026-06-08T10:30:00Z actor=faisal@theassemblyplace.com action=comment ticket=1234 status=200
```

**Tail the live log:**

```bash
fly ssh console -a tap-ops-portal -C "tail -f /data/audit/ticket-auto-reply.log"
```

**Download the full log:**

```bash
fly ssh console -a tap-ops-portal -C "cat /data/audit/ticket-auto-reply.log" > ops-audit.log
```

The portal also exposes the last 50 entries via `/api/audit/recent` (authenticated) and in the Bot Audit dock on the right side of the UI.

---

## Kill switch: disable bot actions

To immediately stop all bot-gated actions (approve_draft, edit_and_send) across all sessions without a redeploy:

```bash
fly secrets set -a tap-ops-portal OPS_PORTAL_BOT_ENABLED=false
```

The portal returns `503 Bot actions disabled` on those endpoints instantly. Manual comment posting and status changes are unaffected.

**Re-enable:**

```bash
fly secrets set -a tap-ops-portal OPS_PORTAL_BOT_ENABLED=true
```

---

## Redeploying after a config change

Most secret changes take effect without a redeploy (the app reads env vars at request time). Only code changes need a full deploy:

```bash
# From the portals/ops/ directory:
fly deploy --app tap-ops-portal --config backend/fly.toml

# Or for staging:
fly deploy --app tap-ops-portal-staging --config backend/fly.staging.toml
```

The build context is `portals/ops/` (set in fly.toml), so the Dockerfile can access both `backend/` and `frontend/` during the build.

---

## Secrets reference

| Secret | Required | Description |
|---|---|---|
| `CRM_API_KEY` | Yes | TAP staff CRM API key (x-api-key header) |
| `OPS_PORTAL_ALLOWED_EMAILS` | Yes | Comma-separated list of allowed email addresses |
| `SECRET_KEY` | Yes | JWT signing key for magic-link tokens |
| `OPS_PORTAL_BOT_ENABLED` | No | Set to `false` to disable bot actions (default: `true`) |
| `SMTP_HOST` | No | SMTP server for magic-link email delivery |
| `SMTP_PORT` | No | SMTP port (default: 587) |
| `SMTP_USER` | No | SMTP username |
| `SMTP_PASS` | No | SMTP password |
| `OPS_PORTAL_FROM_EMAIL` | No | From address for magic-link emails |

Without `SMTP_HOST`, magic links are logged to stderr and printed in the `/auth/magic-link` response — useful for staging.

---

## Architecture

```
portals/ops/
├── backend/          FastAPI app (CRM proxy, auth, audit)
│   ├── main.py       API routes
│   ├── auth.py       Magic-link + session (SQLite, /data/auth.db)
│   ├── audit.py      Append-only audit log (/data/audit/*)
│   ├── crm_client.py CRM API wrapper (60s cache)
│   ├── models.py     Pydantic request models
│   ├── Dockerfile    Build context: portals/ops/ (includes frontend/)
│   ├── fly.toml      Production Fly config
│   └── fly.staging.toml  Staging Fly config
└── frontend/         Vanilla HTML/CSS/JS (no build step)
    ├── index.html
    ├── styles.css
    └── app.js
```
