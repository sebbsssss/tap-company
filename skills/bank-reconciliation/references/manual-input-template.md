# Bank Reconciliation — manual input template

Use when you've got a single unreconciled bank line in Xero that you want the agent to triage. The agent applies the canonical 4-step algorithm and returns a tier (🟢/🟡/🔴) + next action.

**Important:** the agent NEVER clicks OK in Xero. It produces a verdict and recommended action; the human does the actual click.

## How to use

1. In Paperclip web UI, new issue assigned to **Finance Lead**
2. Title: `Bank rec triage — <date> <payer> <amount>` (e.g. "Bank rec triage — 9 May LI JIAHUI $2,900")
3. Paste the template below; replace placeholders
4. Submit

For a batch of lines (e.g. "triage all 12 unreconciled lines from yesterday"), use the **batch template** further down instead.

## Single-line template

```markdown
## Bank reconciliation triage

**Account:** UOB 357-316-093-0 (TAP Co-Livings)
**Date:** 9 May 2026
**Payee on bank line:** LI, JIAHUI
**Amount:** 2900.00   (positive = received; use negative for spent)
**Reference field:** PayNow Transfer
**Description field:** PAYNOW-FAST

## Xero auto-match suggestion (if any)

Copy the green box from Xero's Match panel here, e.g.:

> 8 May 2026 — Aermanjiang Abulaiti — Ref: INV-CL-47043 — Received $2,900.00

Or write "no suggestion (Create tab is selected)" if Xero couldn't auto-match.

## What I've already checked (optional but helpful)

- (e.g. "Searched Xero contacts for 'LI JIAHUI' — 5 contacts found, none with $2,900 outstanding")
- (e.g. "Aermanjiang Abulaiti has only one outstanding invoice — INV-CL-47043 for $2,900")
- (e.g. "Her April rent was the same $2,900, paid 8 Apr — cadence matches")

## Question

Please apply the 4-step canonical algorithm and give me:
1. Tier (🟢/🟡/🔴)
2. Which step fired
3. Recommended next action (click OK, ask CM, leave alone, etc.)
```

## Batch template (multiple lines at once)

When you've got several unreconciled lines and want them all triaged in one pass:

```markdown
## Bank reconciliation batch

**Account:** UOB 357-316-093-0 (TAP Co-Livings)
**Date range:** 1 May 2026 to 9 May 2026
**Total lines:** 12

## Lines

> One block per line, separated by `---`. Same fields as the single-line template.

### Line 1
Date: 9 May 2026
Payee: LI, JIAHUI
Amount: 2900.00
Reference: PayNow Transfer
Description: PAYNOW-FAST
Xero auto-match: INV-CL-47043 Aermanjiang Abulaiti $2,900

---

### Line 2
Date: 8 May 2026
Payee: WEN ZHOULINA
Amount: 4600.00
Reference: PayNow Transfer
Description: PAYNOW-FAST
Xero auto-match: (stale 2024 credit note from Kuan Zhan Peng — looks wrong)

---

### Line 3
Date: 5 May 2026
Payee: COZYHOMES MANAGEMENT
Amount: 1324.99
Reference: RD0618
Description: PAYNOW-FAST
Xero auto-match: none (Create tab)

(...more lines...)
```

## What the agent does

For each line:

1. **Step 1** — Does the payer name match a Xero contact AND does the amount match one of their outstanding invoices?
2. **Step 2** — If name doesn't match: extract last 4 digits from reference; query CRM for member ending in those digits; check shared-room scenarios.
3. **Step 3** — If a tenant is identified but paid less than invoiced: recommend Split.
4. **Step 4** — If paid more than invoiced: leave alone (requirements not finalised).

Output:

```markdown
## Bank rec batch verdict — UOB 357-316-093-0 — 1-9 May 2026

**Total:** 12 lines
**🟢 Green (safe to click OK):** 6
**🟡 Amber (CM verification needed):** 4
**🔴 Red (escalate / leave alone):** 2

### 🟢 Green (6) — safe to reconcile in Xero

| Date | Payer | Amount | Match | Xero link |
| --- | --- | --- | --- | --- |
| 9 May | KATE TAN | $2,650 | INV-CL-47120 (Kate Tan) — sole outstanding, cadence matches | https://go.xero.com/AccountsReceivable/View.aspx?invoiceid=... |
| (more rows) |

### 🟡 Amber (4) — need CM check before reconciling

| Date | Payer | Amount | Proposed match | Why amber | CM question |
| --- | --- | --- | --- | --- | --- |
| 9 May | LI JIAHUI | $2,900 | INV-CL-47043 (Aermanjiang Abulaiti) | Name mismatch; sole outstanding + cadence both match but no member code in reference | "Who is LI JIAHUI paying for? Best guess: Aermanjiang Abulaiti at URBANA #12-03 1203B" |
| (more rows) |

### 🔴 Red (2) — do not reconcile

| Date | Payer | Amount | Why red | Recommended action |
| --- | --- | --- | --- | --- |
| 8 May | WEN ZHOULINA | $4,600 | Only Xero candidate is a stale 2024 credit note (Kuan Zhan Peng) | Wait for invoice to be raised, OR ask AR if WEN ZHOULINA is a new tenant we haven't booked yet |
| 5 May | COZYHOMES MGT | $1,324.99 | No Xero contact match; ref "RD0618" doesn't resolve in CRM; no $1,324.99 outstanding invoice anywhere | Ask CM: who is COZYHOMES paying for? Likely employer-paying-for-employee-tenant |

### Next actions

- Click OK on the 6 green lines in Xero (links above)
- I've drafted CM-group questions for the 4 amber + 2 red — want me to forward them via Ops Lead?
```

## Hard rules

1. **Agent never clicks OK** — humans always do
2. **Agent never auto-applies against a credit note older than 6 months** based on amount alone
3. **Agent never creates an overpayment entry** (Step 4 says leave alone)
4. **Agent always cites the step that fired** in the reasoning column

## See also

- `../SKILL.md` — full algorithm + tier definitions
- `./edge-cases.md` — regression log of validated test cases (LI JIAHUI, WEN ZHOULINA, COZYHOMES)
- [Notion — Payment Reconciliation Training (20 May 2026)](https://www.notion.so/366a25ce804f80a98aaccacbcab72e95) — canonical training
