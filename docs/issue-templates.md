# Issue Templates — TAP Automation

Copy-paste templates for every common Finance + Ops workflow. Each template is the **full version** with all optional sections; the quickstart shows the minimal version.

When using these, replace **bold placeholders** with your actual values. Comment lines starting with `>` are agent-readable hints — keep them or delete them, the agent treats them as optional context.

---

## Settlement (full version)

```markdown
## Settlement request

**Property:** 18 JALAN JINTAN
**Landlord:** Yeoh Joe Wei Evelyn
**Entity:** TAP Co-Livings Pte. Ltd.
**Period:** March 2026
> For partial month, use date range instead: 2026-05-01 to 2026-05-11
**Property kind:** co_living
> Use "campus" for TLKR Block A / Block B — no utility section needed for campus

## Xero P&L
> From Xero → Reports → Profit and Loss → Filter Location = property, period = above

| Line | Amount (SGD) |
| --- | --- |
| Straight Lease - Rental of premises | 6000.00 |
| Rental of premises | 10798.83 |
| Management Contract - Repairs and maintenance | 38.00 |

## CRM tenant roster
> From CRM → Reports → Settlement → property + period above

| Tenant | Room | Duration | Month of | Rental rate | Rental date | Lease end |
| --- | --- | --- | --- | --- | --- | --- |
| Guan Mingjun   | B01 | Extend 1 months  | 1/1  | 2800.00 | 1 Mar 26  | 31 Mar 26 |
| Xu Jia         | B02 | Extend 12 months | 1/12 | 3000.00 | 27 Mar 26 | 26 Mar 27 |
| Wan Ying Zhang | B03 | Extend 1 months  | 1/1  | 2600.00 | 11 Mar 26 | 10 Apr 26 |
| An Qi          | B04 | 12 months        | 1/12 | 3100.00 | 25 Mar 26 | 24 Mar 27 |
| Drishti Sehgal | B06 | Extend 8 months  | 1/8  | 3100.00 | 23 Mar 26 | 22 Nov 26 |

## Deposits (optional — add lines as needed)
> From Xero → "Deposit Received Transactions" report, period above

| Description | Amount |
| --- | --- |
| Deposit received from An Qi for 18 JALAN JINTAN - Rm B04 | 3150.00 |
| Deposit received from Wu Xintong for 18 JALAN JINTAN - Rm B01 | 2850.00 |

## Payment on behalf (optional — Whiz subscriptions, etc.)
> From Xero → Account Transactions → filter Location, expense accounts paid by TAP for the owner

| Description | Amount |
| --- | --- |
| Whiz Communications monthly subscription - Nov 2025 | 38.00 |
| Whiz Communications monthly subscription - Jan 2026 | 38.00 |
| Whiz Communications monthly subscription - Feb 2026 | 38.00 |
| Whiz Communications monthly subscription - Mar 2026 | 38.00 |

## Servicing items (optional — maintenance under threshold)

| Description | Amount |
| --- | --- |
| 20/3/26: Fixing of loose toilet seat for B06 | 45.00 |

## Excess Utility (optional — only if you've downloaded the SP bill)

Unit: Whole shophouse  cap_mode: per_room
Actual SP bill: $850.00  (period: 1–31 Mar 2026)

Per-tenant caps:
- Guan Mingjun   B01: 100.00
- Xu Jia         B02: 100.00
- Wan Ying Zhang B03: 100.00
- An Qi          B04: 100.00
- Drishti Sehgal B06: 100.00

## Notes (optional)

- Cleaning: use property default ($180 × 4 = $720).
- Owner-side utility row: leave yellow per the formula-verification gap with Yee Chin.
- Special handling: (any one-off context)
```

---

## Bank reconciliation triage

```markdown
## Bank reconciliation triage

**Account:** UOB 357-316-093-0 (TAP Co-Livings)
**Date:** 9 May 2026
**Payee on bank line:** LI, JIAHUI
**Amount:** 2900.00
**Reference field:** PayNow Transfer
**Description field:** PAYNOW-FAST
**Xero auto-match suggestion (if any):** INV-CL-47043 Aermanjiang Abulaiti $2,900 issued 8 May 26 due 11 May 26

## What I've already checked (optional)

- Searched Xero contacts for "LI JIAHUI" — 5 contacts found (Janna Tee Jiahui, Keok Jia Hui, Tang Jiahui, Wang Jiahui, Yu Jiahui), none with $2,900 outstanding
- Aermanjiang Abulaiti has only one outstanding invoice ($2,900)
- Her April rent was the same $2,900, paid on time

## Question for the agent

Please apply the 4-step canonical algorithm and give me a tier (🟢/🟡/🔴) + next action.
```

The agent will respond with a tier, the reasoning that fired (which of the 4 steps applies), and the next concrete action — usually one of:
- 🟢 "Safe to click OK in Xero on INV-CL-47043. Direct link: …"
- 🟡 "Verify with CM group: who is [payer name] paying for? Suggested message to send: …"
- 🔴 "Do not reconcile. Recommended action: post to CM group asking …, OR wait for the matching invoice to be raised."

---

## CFO Brief (monthly)

```markdown
## CFO Brief request

**Period:** May 2026
**Audience:** Yee Chin (final draft will land as Google Doc for her review)

## Per-entity Profit & Loss
> From Xero → Reports → Profit and Loss, run separately per entity

### TLKR Pte. Ltd. (UEN 201901964D)
| Line | Amount (SGD) |
| --- | --- |
| Rental income | |
| Other operating income | |
| Cost of sales | |
| Total operating expenses | |
| Net profit | |
| AR at period end | |

### TAP Co-Livings Pte. Ltd. (UEN 202300680H)
| Line | Amount (SGD) |
| --- | --- |
| Rental income | |
| Other operating income | |
| Cost of sales | |
| Total operating expenses | |
| Net profit | |
| AR at period end | |

### Hotel entity
> Write "n/a — no activity this period" if applicable
| Line | Amount (SGD) |
| --- | --- |
| Rental income | |
| Total operating expenses | |
| Net profit | |
| AR at period end | |

### Service Apartment entity
| Line | Amount (SGD) |
| --- | --- |
| Rental income | |
| Total operating expenses | |
| Net profit | |
| AR at period end | |

## Occupancy snapshot
> Optional but recommended — from CRM dashboard or your monthly tracking sheet

| Property | Rooms | Occupied | Occupancy % |
| --- | --- | --- | --- |
| TLKR Block A | 42 | | |
| TLKR Block B | 38 | | |
| 18 Jln Jintan | 6 | | |

## Operational notes
- Anything Yee Chin specifically asked about for this period:
- Any one-off items worth calling out (e.g. one-off legal fees, deposit refunds, exceptional repairs):
- Comparison context (vs prior month / vs budget / vs same month last year):
```

The agent drafts a Markdown / Google Doc covering: TAP-wide P&L roll-up, per-entity drill-down, occupancy summary, AR aging, and a "watch items" section flagging anything outside normal ranges. **Goes to Yee Chin for review BEFORE sharing.**

---

## AR chase list

```markdown
## AR Chase list request

**As of date:** 23 May 2026
**Tone:** polite, Singapore English ok
**Send channel:** WhatsApp via Ops Lead

## Overdue invoices
> From Xero → Sales → Invoices → filter Status=Awaiting Payment, Due date < today

| Invoice | Tenant | Property | Amount (SGD) | Days overdue | Tenant phone |
| --- | --- | --- | --- | --- | --- |
| INV-CL-46991 | Wang Xiao Ming | 18 Jln Jintan B02 | 2800.00 | 14 | +65 9123 4567 |
| INV-CL-47002 | Tan Lee Hua    | 51 Middle Rd 03   | 2600.00 | 11 | +65 8234 5678 |

## Notes
- (Optional context per tenant — e.g. "Wang Xiao Ming's CM said he's resolving today, skip")
- (Or any tone overrides — e.g. "second-time reminder for Tan Lee Hua, slightly firmer please")

## Hard rules
- Always include opt-out language ("Reply STOP to opt out")
- Never message more than 5 tenants in a batch without explicit board approval
- Drafts go to AR / CM for review before Ops Lead sends
```

---

## Ticket digest (Ops Lead handles automatically)

You don't normally need to create this issue — Ops Lead sends a digest every 2 hours to the operations WhatsApp group. But if you want an ad-hoc one (e.g. for a board meeting):

```markdown
## Ad-hoc ticket digest

**As of:** 23 May 2026 14:00 SGT
**Audience:** (e.g. "Faisal only", "ops group", "include Yee Chin")
**Scope:** (e.g. "all properties", "TLKR Campus only", "urgent only")

Anything special you want called out:
```

---

## Occupancy snapshot (Ops Lead handles automatically)

Refreshed weekly Monday 08:00 SGT to `Property Dashboards/TLKR Campus.xlsx`. For an ad-hoc refresh or to add a new property:

```markdown
## Ad-hoc occupancy snapshot

**Property:** TLKR Campus  (or other property)
**As of:** 23 May 2026
**Compare against:** (e.g. "last week", "start of year", or leave blank)

Specific question to surface in the summary:
```

---

## A note on how the agent reads these

The agent is fairly forgiving — you don't have to match the format pixel-for-pixel. Specifically:

- Headers (`## ...`) help it find sections, but if you write `Settlement request:` instead the agent usually figures it out
- Tables don't have to be markdown — bullet lists work too. The agent tries Markdown table parsing first, then bullet-list parsing, then a final "ask Finance to clarify" if neither works
- Numbers can have commas, currency symbols, parentheses — the agent strips formatting before parsing
- If the agent ever guesses something rather than asking you, that's a bug — flag it on the issue with `@sebastien` and the AGENT.md gets tightened

## When the template doesn't fit your case

Just write the request in plain English and assign to Finance Lead. Worst case: it asks clarifying questions. The templates are for speed, not for restriction.
