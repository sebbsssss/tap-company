# AR Chase List — manual input template

Use when there's no Xero MCP wired and you want to request a chase batch by pasting the overdue list yourself.

## How to use

1. In Paperclip web UI, create a new issue assigned to **Finance Lead**
2. Title: `Generate AR chase batch — <date>` (e.g. "Generate AR chase batch — 23 May 2026")
3. Paste the template below into the body, replacing placeholders
4. Submit. The agent drafts the messages and posts them back for your review

## Copy-paste template

```markdown
## AR Chase list request

**As of date:** 23 May 2026
**Threshold:** overdue ≥ 7 days   (or specify a different cutoff)
**Tone:** polite   (or: "firm — second reminder", "final notice")
**Send channel:** WhatsApp via Ops Lead   (or: "email", "both")

## Overdue invoices

> Export from Xero → Sales → Invoices → filter Status=Awaiting Payment + Due date < today.
> Paste relevant columns into the table below. Add tenant phone from CRM if you have it handy
> (otherwise the agent will look it up via CRM API once that's wired, or leave blank for AR to fill in later).

| Invoice | Tenant | Property | Amount (SGD) | Days overdue | Tenant phone |
| --- | --- | --- | --- | --- | --- |
| INV-CL-46991 | Wang Xiao Ming | 18 Jln Jintan B02 | 2800.00 | 14 | +65 9123 4567 |
| INV-CL-47002 | Tan Lee Hua    | 51 Middle Rd 03   | 2600.00 | 11 | +65 8234 5678 |
| INV-CL-47015 | Aermanjiang Abulaiti | URBANA #12-03 1203B | 2900.00 | 7 | (unknown) |

## Skip list (optional)

| Tenant | Reason to skip |
| --- | --- |
| (e.g. Wang Xiao Ming | CM flagged "resolving today, leave alone") |

## Notes (optional)

- Anything Yee Chin specifically wants flagged
- Per-tenant tone overrides ("Tan Lee Hua is a second-reminder, slightly firmer please")
- Channel preferences ("Aermanjiang prefers WeChat, but agent's restricted to WhatsApp — note it")
```

## What the agent does

1. Parses the table
2. For each non-skipped tenant: generates a personalised draft message (polite, named, includes amount + property + opt-out)
3. Detects escalation cases (≥30 days overdue, multiple stacked invoices) and flags them separately
4. Posts the result back on the same issue with three sections: 🚨 escalations (need Yee Chin), ✏️ drafts (need AR/CM review), 🚫 skipped

## What you do next

Reply on the issue: `approved` + any draft IDs to edit/remove. Finance Lead then creates a subtask for Ops Lead to actually send the approved batch via Twilio.

If the batch is >5 messages, Paperclip will require board approval (Sebastien) before sending. Plan accordingly — split big batches into 5-message chunks for faster turnaround.

## Common gotchas

- **Phone numbers without country code** — agent rejects with "+65 needed for SG numbers". Always include `+65`.
- **Amounts with commas** — agent strips commas before parsing, so "2,800.00" and "2800.00" both work.
- **Tenant name spelling** — agent will draft using whatever name you provide. If a CM tells you the tenant goes by a different name, use that one in the template — the message goes to the tenant, not the legal record.
- **Mixed entities in one batch** — fine. Agent sorts by entity in the output for AR's convenience.
