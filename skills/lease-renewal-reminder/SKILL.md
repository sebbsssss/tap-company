---
name: lease-renewal-reminder
description: Sends WhatsApp lease renewal reminders to TAP tenants whose leases expire within a configurable window. Use when the user says "send renewal reminders", "ping tenants about expiring leases", "lease renewal queue for next 30/60 days", "draft renewal message for [tenant]", or "show me whose lease is up next month". Pulls tenant + lease data from the CRM, drafts the message with each tenant's specific renewal options (1mo, 3mo, 6mo, 12mo) and current rate, and queues sends via Twilio.
---

# Lease Renewal Reminder

Pulls tenants with leases expiring soon, drafts a personalised renewal message, sends via WhatsApp on explicit per-send approval.

## When to invoke

Run this skill when the user asks for any of:

- The queue of upcoming renewals ("what leases expire next month?")
- Drafted messages for review ("draft renewal reminders for everyone expiring in 60 days")
- An immediate send to a specific tenant ("send the renewal reminder to An Qi")
- A bulk approve-and-send for the validated queue

## What it does NOT do

- **Does not auto-send without approval.** Every batch is queued for the user to approve before WhatsApp delivers.
- **Does not negotiate.** The reminder offers standard renewal options + asks tenants to reply with a choice or contact the property manager.
- **Does not modify lease records in the CRM.** Replies + decisions still go through the existing CRM workflow.

## Required environment variables

- `CRM_STAFF_TOKEN` — to read across all tenants
- `CRM_API_BASE` — defaults to `https://crm-api.theassemblyplace.com`
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_SANDBOX_FROM` (or production WhatsApp Business number)
- `RENEWAL_WINDOW_DAYS` — default 60. Controls how far ahead the skill looks.

## How to run it

```bash
# Build the queue of upcoming renewals (no sends)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/renewals.py --window 60 --dry-run

# Draft personalised messages for everyone in the queue (no sends)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/renewals.py --window 60 --draft-only --output-dir "drive:Renewal Queue/$(date +%Y-%m)"

# Send to one specific tenant by booking ID
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/renewals.py --booking-id 12345 --send

# Send the validated batch (requires --batch-file from a prior --draft-only run)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/renewals.py --batch-file ./drafts.json --send
```

## Message template

Stored in `references/templates/renewal-reminder.md`. The current draft offers:

- Tenant's current lease end date
- Current monthly rate
- Renewal options: 1 month, 3 months, 6 months, 12 months (with TAP's standard rate adjustments per duration)
- A reply prompt to confirm choice or request a call

Templates are pre-approved with Meta as **Utility** category (not Marketing) so they comply with WhatsApp Business policy.

## Approval flow (Tier B model)

1. Skill builds the queue (e.g. 30 tenants expiring in next 60 days).
2. Drafts each personalised message; writes the batch to a Google Sheet for human review.
3. User reviews, marks rows as approved / skip / edit, then re-invokes with `--send`.
4. Each send returns a Twilio SID; failures get logged for retry.

## Validation history

- Initial CRM lease extract working (Task #53 done).
- Twilio Sandbox proven end-to-end (Task #52 done).
- Reminder content + Meta-approved template + Sheet-based approval flow: **not yet built**. This is the next implementation block.

## See also

- `references/templates/renewal-reminder.md` — Meta-approved message template
- `references/queue-format.md` — schema of the renewal queue Sheet
- `references/twilio-production-migration.md` — how to swap Sandbox for a TAP-owned WhatsApp Business number
