# Finance Quickstart — TAP Automation

**Read this first.** If you're on the Finance team (Yee Chin, AR, settlements) and someone just gave you a Paperclip login, this is your starting page.

## What this is

You now have an AI assistant ("Finance Lead") that does the repetitive parts of your job: monthly settlements, daily bank rec triage, AR chase lists, and the monthly CFO Brief. It works in two modes:

- **Today**: you paste a small amount of data into a Paperclip issue. The agent does the calculation, drafting, and formatting. Saves ~50 minutes of work per settlement, ~30 minutes per CFO brief.
- **Soon (once Xero MCP is wired)**: you don't even paste — the agent pulls Xero directly. You only review.

Either way, you stay in control. **The agent never sends anything to owners, never clicks OK in Xero, never sends tenant messages without your approval.** It produces drafts; you approve.

## "I want to..." lookup

| If you want to... | Open this template | Where the numbers come from | Time |
| --- | --- | --- | --- |
| **Generate a monthly settlement letter** for a property | [Settlement template](#settlement) | [Xero P&L by Location + CRM roster](./xero-export-guide.md#for-settlement-template) | ~5 min |
| **Triage today's unreconciled bank lines** in Xero | [Bank rec template](#bank-rec) | [Xero Bank rec page](./xero-export-guide.md#for-bank-reconciliation-template) | ~3 min per line |
| **Draft the monthly CFO Brief** for Yee Chin | [CFO brief template](#cfo-brief) | [Xero P&L + Aged Receivables, per entity](./xero-export-guide.md#for-cfo-brief-template) | ~5 min |
| **Get a chase-list for overdue tenant rent** | [AR chase template](#ar-chase) | [Xero Awaiting-Payment invoices](./xero-export-guide.md#for-ar-chase-list-template) | ~3 min |
| **See the operations ticket digest** | Ops Lead handles this automatically every 2h | (CRM) | 0 min |
| **Run something I don't see here** | Just create an issue and assign Finance Lead — describe what you need in plain English | — | — |

📍 **Where to find the data in Xero:** see [`docs/xero-export-guide.md`](./xero-export-guide.md) — click-by-click for every template above.

## How Paperclip works (30-second tour)

1. **Issues** are where work happens. Every request is an issue.
2. **Assignee** controls who works on it. For Finance things, assign Finance Lead.
3. **Comment thread** is the conversation. The agent comments back with results, questions, or files.
4. **Run Heartbeat** button (top right of the agent page) fires the agent immediately if you don't want to wait for the next scheduled run.
5. **Approve / Reject** buttons appear on requests that need human sign-off (budget overrides, hire requests, etc.). Read these carefully before clicking.

## The four templates (copy-paste from here)

### Settlement

Use when generating a monthly owner settlement letter. The agent produces an xlsx in your existing template format.

```markdown
## Settlement request

**Property:** 18 JALAN JINTAN
**Landlord:** Yeoh Joe Wei Evelyn
**Period:** March 2026
**Property kind:** co_living   (use "campus" for TLKR)

## Xero P&L (Reports → Profit and Loss, Location filter = property, period above)

| Line | Amount (SGD) |
| --- | --- |
| Straight Lease - Rental of premises | 6000.00 |
| Rental of premises | 10798.83 |
| Management Contract - Repairs and maintenance | 38.00 |

## CRM tenant roster (Reports → Settlement, property + period above)

| Tenant | Room | Duration | Month of | Rental rate | Rental date | Lease end |
| --- | --- | --- | --- | --- | --- | --- |
| Guan Mingjun   | B01 | Extend 1 months  | 1/1  | 2800.00 | 1 Mar 26  | 31 Mar 26 |
| Xu Jia         | B02 | Extend 12 months | 1/12 | 3000.00 | 27 Mar 26 | 26 Mar 27 |
```

(See `docs/issue-templates.md` for the full settlement template including the optional Excess Utility block.)

### Bank rec

Use when Xero shows a PayNow/FAST line that Xero's auto-match can't confidently identify. The agent walks the canonical 4-step algorithm and gives you a 🟢/🟡/🔴 verdict.

```markdown
## Bank reconciliation triage

**Account:** UOB 357-316-093-0 (TAP Co-Livings)
**Date:** 9 May 2026
**Payee on bank line:** LI, JIAHUI
**Amount:** $2,900.00
**Reference:** PayNow Transfer
**Description:** PAYNOW-FAST
**Xero auto-match suggestion (if any):** INV-CL-47043 Aermanjiang Abulaiti $2,900

What I've already checked:
- (e.g. "Searched Xero contacts for LI JIAHUI — no exact match")
- (or leave blank if you haven't checked anything)

Question for the agent: please advise tier + next step.
```

### CFO brief

Use when drafting the monthly TAP-wide CFO Brief for Yee Chin. Cover all four entities.

```markdown
## CFO Brief request

**Period:** May 2026

## Per-entity numbers (Xero Reports → Profit and Loss per entity)

### TLKR Pte. Ltd. (UEN 201901964D)
| Line | Amount |
| --- | --- |
| Rental income | (paste from Xero) |
| Cost of sales | |
| Total expenses | |
| Net profit | |
| AR at period end | |

### TAP Co-Livings Pte. Ltd. (UEN 202300680H)
| Line | Amount |
| --- | --- |
| Rental income | |
| Cost of sales | |
| Total expenses | |
| Net profit | |
| AR at period end | |

### Hotel
(same shape, or write "n/a — no activity this month")

### Service Apartment
(same shape, or write "n/a — no activity this month")

## Operational context

- Occupancy this month: (paste from CRM dashboard or skip)
- Anything Yee Chin specifically asked about: (e.g. "she wants a deeper look at the TLKR Block B AR climb")
```

### AR chase

Use when you want a chase-list for tenants past due. The agent drafts polite WhatsApp/email messages — you review and send.

```markdown
## AR Chase list request

**Period:** as of 23 May 2026
**Tone:** polite (Singapore English ok)
**Send channel:** WhatsApp via Ops Lead (or "email" if preferred)

## Overdue invoices (Xero → Sales → Invoices → filter Status=Awaiting Payment, Due date < today)

| Invoice | Tenant | Amount | Days overdue | Tenant phone (if known) |
| --- | --- | --- | --- | --- |
| INV-CL-46991 | Wang Xiao Ming | 2,800.00 | 14 | +65 9123 4567 |
| INV-CL-47002 | Tan Lee Hua    | 2,600.00 | 11 | +65 8234 5678 |

## Notes
- (Optional context — e.g. "skip Wang Xiao Ming, his CM said he's resolving today")
- Always include opt-out language ("Reply STOP to opt out")
```

## What happens after you submit an issue

Within a few minutes (or on the next scheduled heartbeat — within 6 hours by default for Finance Lead, sooner if you click "Run Heartbeat"):

1. The agent reads your issue
2. Pulls in standing values from `property_defaults.json` (cleaning fees, base rents, property kinds)
3. Does the calculation / drafting
4. Comments back with: the file (xlsx for settlements, Drive link or attached), a structured summary, and any open questions
5. If anything is ambiguous, it asks before guessing. Don't be surprised if it comes back with "I need to confirm: is the period March 2026 or 2026-03-01 to 2026-03-11?"

If the agent doesn't respond within a few minutes, click **Run Heartbeat** on the Finance Lead agent page. That fires it immediately.

## Things the agent will refuse to do

It's not being stubborn — these are deliberate safety rails:

- **Click OK on a Xero bank reconciliation.** You always do the actual click.
- **Send a settlement letter to an owner.** AR staff sends.
- **Autofill the owner-side utility row on settlements.** Pending Yee Chin's formula verification (the math doesn't match Feb/Mar Finance files — see backtest doc).
- **Modify Xero records** (invoices, contacts, deposits). Read-only.
- **Send mass tenant messages without per-message human approval.** Ops Lead drafts; CM group approves.

If you really want it to do something it's refusing, talk to Sebastien — the rails can be loosened with board approval, but the default is "draft, don't do."

## Where to find more detail

- **Settlement template (full version):** `docs/issue-templates.md` → settlement section
- **Bank rec algorithm (the 4 steps):** `skills/bank-reconciliation/SKILL.md`
- **Why the owner-utility row is yellow:** `skills/settlement-generator/references/utility-backtest-2026-05-20.md`
- **What the agent's persona/safety rules are:** `agents/finance-lead/AGENT.md` and `SOUL.md`
- **What other agents exist:** the CEO (just orchestrates) and the Ops Lead (tickets / lease renewals / occupancy). Mostly the CEO routes things; you'll mostly interact with Finance Lead.

## Help / questions

- **Something's wrong with a generated xlsx** — comment on the same issue describing what's off. The agent re-runs.
- **You want a new kind of report we don't have a template for** — create an issue, describe what you need in plain English, assign Finance Lead. Worst case: it comes back asking clarifying questions. Best case: it just does it.
- **You're not sure if the agent is even alive** — open the Finance Lead agent page; the Runs tab shows you every heartbeat. Recent ones with green ticks = healthy.
- **You need to escalate to Sebastien** — comment `@sebastien` on the issue (if Paperclip supports mentions in your install) or assign the issue to the CEO agent who'll surface it.
