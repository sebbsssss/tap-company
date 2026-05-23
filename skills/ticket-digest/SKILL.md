---
name: ticket-digest
description: Pulls open maintenance and housekeeping tickets from the TAP CRM and sends a formatted WhatsApp summary to operations staff. Use when the user says "send the ticket digest", "summarise open tickets", "what's in the maintenance queue", "ticket roundup for Faisal", or "show me what ops needs to act on today". Includes counts by service, priority, area, category, property; flags oldest unresolved tickets and tickets with no staff reply.
---

# Ticket Digest

A read-only summary of open tickets in the TAP CRM, delivered via WhatsApp on demand or on a 2-hourly schedule.

## When to invoke

Run this skill when the user asks for any of:

- A snapshot of open tickets ("what's open?", "ticket roundup")
- The 2-hourly digest send to ops ("send the digest", "trigger the digest now")
- Status of the digest schedule ("is the digest still running?", "when did the last digest fire?")
- Adjusting the digest cadence or recipient list

## What it does NOT do

This is **Tier A** of the ticket automation. The agent:

- Reads tickets only — no replies, no status changes, no comment posts
- Does not modify tenant-facing data in the CRM
- Does not interact with WhatsApp ingestion (some TAP divisions use WhatsApp-only tickets — those are out of scope until a later phase)

Tier B (AI drafts replies for Faisal/Irwan to copy-paste) and Tier C (AI posts replies with approval) are separate workflows, not in this skill.

## Required environment variables

Either:
- `CRM_STAFF_TOKEN` — token for a /com/ scope account (preferred for production; covers all tenants and all properties)

Or:
- `CRM_MEMBER_TOKEN` — token for a /member/ scope tenant account (validation only; sees just one tenant's tickets)

Plus:
- `CRM_API_BASE` — defaults to `https://crm-api.theassemblyplace.com`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_SANDBOX_FROM` — usually `whatsapp:+14155238886` (Twilio shared sandbox)
- `TAP_DIGEST_TO` — recipient WhatsApp in `whatsapp:+65XXXXXXXX` format

The script auto-prefers the staff token when both are set.

## How to run it

Locate the digest script in this plugin's `scripts/` directory (after installation it lives at `${CLAUDE_PLUGIN_ROOT}/scripts/digest.py`).

```bash
# Send a real digest right now
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/digest.py --source api --send whatsapp

# Dry-run (print the digest to stdout, do not send)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/digest.py --source api --send dry

# Use bundled sample data (for first-install demo before token lands)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/digest.py --source sample --send dry
```

Successful runs end with a line like `✓ Sent. SID: SM<…>  Status: queued`.

## Recommended cadence

Every 2 hours during waking hours, fed by the Cowork `schedule` skill or by a GitHub Actions cron once the workflow moves into TAP infrastructure.

Cron expression: `0 */2 * * *` (every 2 hours on the hour, local SGT).

To pause the digest: disable the scheduled task in the Cowork sidebar, or reply `STOP` from the recipient WhatsApp number.

## Failure modes and what to do

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `HTTP 401/403` from CRM | Token expired or revoked | Re-issue via `POST /com/auth/login/` (staff) or `/member/auth/login/` (member); update env |
| Twilio responds with non-queued status | Recipient not joined to Sandbox, or Sandbox session expired (~3 days) | Have the recipient re-send the join code from their WhatsApp |
| Digest shows zeros even though tickets exist | Wrong scope (member token sees only one tenant; need staff token) | Set `CRM_STAFF_TOKEN` instead |
| Schedule doesn't fire | Cowork app closed (scheduled tasks need the app open) | Open Cowork; next run fires on launch |

## Validation plan (first week of install)

Day 1–2: only the installer receives the digest. Eyeball each digest against the CRM ticket list to confirm counts match.

Day 3–4: compare digest aging buckets to actual ticket ages. Adjust thresholds if helpful.

Day 5–7: tune the formatting based on what's actually useful when reading at 1am vs 9am. Decide on top-N counts.

End of week 1: review with Faisal in the working session, then add him + Irwan as recipients.

## See also

- `references/digest-architecture.md` — the data flow, schema mapping, and digest format
- `references/runbook.md` — week-1 validation steps and tuning knobs
- `references/digest.py` — reference copy of the actual script
