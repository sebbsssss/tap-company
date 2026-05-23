---
name: ar-chase-list
description: >
  Use when generating chase messages for overdue tenant rent. Pulls overdue invoices (from Xero MCP if available, or from a list pasted in the issue body), cross-references CRM for tenant contact, drafts polite personalised WhatsApp / email messages for each. Drafts ONLY — Ops Lead sends after human (CM/AR) review. Do NOT use for owner-side AR (chasing landlords for amounts owed); that's a different conversation.
---

# AR Chase List

Produces a vetted batch of draft chase messages for tenants past due on rent. Two input modes — same skill, different sources.

## When to invoke

Run this when:
- AR staff requests a weekly chase batch ("draft chases for everyone overdue ≥7 days")
- Yee Chin asks for a one-off chase ahead of month-end
- Finance Lead's daily heartbeat detects a new overdue invoice it hasn't surfaced yet

Do NOT run for:
- First-overdue-day reminders (these tend to resolve themselves; chase from day 7+ unless Yee Chin says otherwise)
- Owner-side AR (we don't chase landlords through this; that's a phone call from Yee Chin)
- Tenants whose CM has flagged "leave alone" (check CM-group notes first)

## Two input modes

### Mode A — Xero + CRM MCPs available

1. Call `mcp__xero-tap-colivings__get_contacts_and_receivables` (and `xero-tlkr` similarly) — pull every contact with `overdueAmount > 0`
2. For each tenant, look up their CRM contact for phone + lease context (CRM API once staff auth lands)
3. Filter to overdue ≥ 7 days (or whatever threshold the issue specifies)
4. Apply skip-list from the issue notes
5. Draft messages

### Mode B — manual paste (today's reality)

AR staff pastes the overdue list into the issue body using the template in `references/manual-input-template.md`. Agent parses, drafts messages.

## What the agent produces

A markdown table — one row per tenant — with the draft message in the last column. Drafts ONLY; nothing is sent until a human approves.

```
| Tenant | Property | Amount | Days overdue | Phone | Channel | Draft message |
| --- | --- | --- | --- | --- | --- | --- |
| Wang Xiao Ming | 18 Jln Jintan B02 | $2,800 | 14 | +65 9123 4567 | WhatsApp | Hi Wang Xiao Ming, friendly reminder — your March rent of $2,800 for 18 Jln Jintan B02 is now 14 days overdue. Could you please settle via PayNow to UEN 202300680H or let us know if there's an issue? Reply STOP to opt out. — TAP Co-Livings |
| Tan Lee Hua | 51 Middle Rd 03 | $2,600 | 11 | +65 8234 5678 | WhatsApp | (similar polite draft) |
```

After AR / CM approves the drafts, Finance Lead creates a subtask assigned to Ops Lead with the approved messages — Ops Lead sends via Twilio.

## Message tone rules

- **Default tone: polite, warm, Singapore English ok.** "Hi [name], friendly reminder — your March rent..." beats "Dear sir/madam, this is to inform you...".
- **Address by name** (not "Dear Tenant"). Use the name the tenant goes by in CRM, not necessarily the legal name on the invoice (e.g. "Aermanjiang" not "Erman Jiang Abulati").
- **Include the property + room** so the tenant doesn't have to look it up.
- **State the amount and payment method.** Don't make them guess.
- **Always include opt-out language** ("Reply STOP to opt out") — required for WhatsApp business messaging compliance.
- **Don't threaten or imply consequences** unless the user explicitly asks for a firm tone. First chase is warm; escalation comes from a human.
- **Match channel to tenant.** WhatsApp for SG-local tenants. Email for overseas / corporate payers (COZYHOMES-style). When in doubt, both.

## Mass-message safety rail

**Maximum 5 tenants in a single send batch without explicit board approval.** Paperclip flags any send to >5 recipients as a `mass_tenant_message` approval. This isn't a Twilio limit — it's a protection against bulk-send mistakes.

If AR needs to chase 20 tenants in one go, split into batches of 5 and process them sequentially with approval per batch.

## Skip-list logic

Common reasons to skip a tenant from this batch:
- CM has flagged "resolving this week" in CRM notes or the issue's `## Notes` section
- Tenant is in a payment-plan agreement (check Xero invoice has been split or part-paid)
- Tenant is moving out and amount will be deducted from deposit (CM flag)
- Tenant has already been chased this calendar week — don't re-chase same week unless escalating tone

When skipping, include the reason in the output table:
```
| Wang Xiao Ming | ... | SKIPPED — CM flag: "resolving today, leave alone" |
```

## Escalation logic

If the agent notices any of these patterns, surface separately at the top of the output as **needs human escalation**, not just a chase draft:

- Tenant overdue ≥30 days → escalate to Yee Chin, NOT a polite chase
- Tenant has 3+ unpaid invoices stacked → escalate to CM (root cause likely not just forgetfulness)
- Tenant's payment-on-deposit balance won't cover the overdue amount + remaining lease → escalate to Yee Chin (write-off territory)

## Output format the agent posts back

```markdown
## AR Chase batch — 23 May 2026

**Threshold:** overdue ≥ 7 days
**Total tenants in queue:** 12
**Drafts ready for review:** 9
**Skipped:** 2 (CM flag)
**Needs escalation:** 1 (40 days overdue, see below)

### 🚨 Escalation needed

- **Tan Wei Ling** — 18 Penhas Rd 04 — $5,200 — **40 days overdue** — recommend Yee Chin call directly.

### ✏️ Drafts for review

(table here)

### 🚫 Skipped

| Tenant | Reason |
| --- | --- |
| Wang Xiao Ming | CM flag: "resolving today" |
| (next) | (reason) |

After review, please reply with: "approved" + list of any drafts to remove/edit. I'll then create a subtask for Ops Lead to send.
```

## See also

- `references/manual-input-template.md` — copy-paste template for Mode B
- [Notion — Lease Renewal Management discussion (5 May 2026)](https://www.notion.so/357a25ce804f80a08c18d20f746f612f) — broader tenant comms context
