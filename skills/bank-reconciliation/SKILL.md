---
name: bank-reconciliation
description: >
  Use when reconciling unmatched bank lines in Xero — specifically PayNow / FAST / direct credits where Xero's auto-match is uncertain or wrong. Walks the canonical 4-step TAP algorithm (per Finance training, 20 May 2026): name+amount match → last-4-digit code → CRM lookup → CM escalation. NEVER clicks OK to reconcile autonomously — always surfaces decisions for human approval. Do NOT use for outbound payments, supplier bills, or transfer reconciliations.
---

# Bank Reconciliation

Procedure for triaging unreconciled bank lines on TAP entities (start with UOB account 357-316-093-0 for TAP Co-Livings). Produces a vetted match queue with confidence flags and reasoning — never auto-reconciles.

## Canonical algorithm (4 steps)

Source: [Notion — Payment Reconciliation Training (20 May 2026)](https://www.notion.so/366a25ce804f80a98aaccacbcab72e95)

### Step 1 — Name + amount both match → 🟢 OK to reconcile

If the bank line's payer name matches a Xero contact AND the amount exactly matches one of that contact's outstanding invoices, surface as **green / safe**. Human still clicks OK in Xero; the agent just queues it with the proposed invoice ID.

### Step 2 — Name doesn't match → last-4-digit code lookup

Extract the last 4 digits from the bank line. Try fields in this order:
1. PayNow / FAST transaction reference (long UTR/UEN string)
2. The reference text field (where tenants type a code when sending)

For each candidate 4-digit code, query CRM for a member whose code ends in those digits.

- **If CRM returns one member** → check whether that member has an outstanding invoice matching the bank amount (exact first, then nearest; date window: payment_date − 1 month for late payments). If yes → 🟡 **amber**, queue with the proposed match + the tenant's invoice context.
- **If CRM returns zero or multiple** → check for shared-room scenario (e.g. 4 tenants in a room, one pays for everyone). Reconcile to the share-key holder (representative). Requires CM confirmation → escalate.
- **If still unidentified** → 🔴 **red / CM escalation**. Post a question to the CM group with the bank line details, asking who the payer is.

### Step 3 — Name found, paid < invoiced → split

Use Xero's Split function. The balance carries forward on the invoice. Outstanding amount is eventually deducted from the tenant's deposit on refund.

### Step 4 — Name found, paid > invoiced → leave alone

Requirements not yet finalised. Do **not** auto-create overpayments. Flag and wait.

## Tier definitions (for the agent's output)

| Tier | Trigger | Action |
| --- | --- | --- |
| 🟢 Green | Name + amount + cadence all match a sole outstanding invoice | Queue with "OK candidate" label; human still clicks |
| 🟡 Amber | Member code resolves to a tenant whose invoice matches, OR shared-room scenario likely | Queue with CM-verification question included |
| 🔴 Red | Payer unidentified after exhausting name + code + amount searches, OR only Xero candidate is a stale credit note 6+ months old | Escalate to CM group with full context. Do NOT match. |

## Edge cases (from real test cases)

- **LI JIAHUI / Aermanjiang Abulaiti, $2,900 received 9 May 2026** — name mismatch but Xero auto-matched INV-CL-47043 for Aermanjiang at URBANA #12-03 Rm 1203B. Single outstanding invoice, cadence matched April's $2,900. **Verdict: amber → CM check.** Even with strong cadence + sole-outstanding evidence, name mismatch + no member code in the PayNow ref requires CM identification of the payer.
- **WEN ZHOULINA $4,600 PayNow** — Xero auto-match suggested a stale 2024 credit note from Kuan Zhan Peng (different person). Searched all 3,665 Xero receivables for $4,600 — only the stale credit appears. **Verdict: red. Never apply amount-only matches against credit notes older than 6 months.**
- **COZYHOMES MANAGEMENT $1,324.99 PayNow ref RD0618** — corporate payer, not in Xero contacts. Searched "RD0618" / "0618" / "1324.99" globally: 5 invoices end in 0618 but none match the amount; exact amount returns 0 results anywhere. **Verdict: red → CM. Likely an employer paying for an employee tenant.**

## Output format

When the agent surfaces a bank-rec batch, produce a markdown table for the human reviewer:

| Tier | Bank line | Proposed match | Confidence reasoning | Action |
| --- | --- | --- | --- | --- |
| 🟢 | 9 May, JANE SMITH, $2,800, PAYNOW | INV-CL-47200 (Jane Smith) | Sole outstanding $2,800; cadence matches Apr | OK to click |
| 🟡 | 9 May, LI JIAHUI, $2,900, PAYNOW | INV-CL-47043 (Aermanjiang) | Cadence + sole-outstanding strong, but name mismatch with no code in ref | Ask CM: who is LI JIAHUI paying for? |
| 🔴 | 5 May, COZYHOMES MGT, $1,324.99, PAYNOW ref RD0618 | None | No Xero contact; 0618 doesn't resolve in CRM; $1,324.99 has no outstanding invoice | Ask CM: who is COZYHOMES paying for? |

After the table, include direct Xero deep-links for green and amber rows so the human can act in one click:
`https://go.xero.com/AccountsReceivable/View.aspx?invoiceid=<GUID>`

## Hard rules (never violate)

1. **Never click OK in Xero autonomously.** Surface the proposed match; the human approves and clicks.
2. **Never reconcile against a credit note older than 6 months** based on amount alone — these are almost always Xero reaching for stale credits.
3. **Never auto-create an overpayment.** Step 4 says leave alone.
4. **Always include the rule citation** in the reasoning (e.g. "Step 2, no code in reference → CM check per Notion training 20 May").

## Two input modes

### Mode A — Xero MCP available

The agent queries Xero directly via `mcp__xero-*__get_contacts_and_receivables` and the bank-feed endpoint. Walks the 4-step algorithm autonomously. Posts a daily batch verdict.

### Mode B — manual paste (today's reality)

AR pastes one or more bank lines into a Paperclip issue using `references/manual-input-template.md`. The agent applies the same 4-step algorithm — the only difference is the input came from a paste rather than an MCP call. Same output format, same Xero deep-links, same tier verdicts.

Mode B works TODAY with no MCP setup beyond Paperclip + Claude Code. Mode A is the eventual end state once Xero Custom Connection is provisioned.

## See also

- [Notion — Payment Reconciliation Training (20 May 2026)](https://www.notion.so/366a25ce804f80a98aaccacbcab72e95) — canonical training
- `references/edge-cases.md` — full log of test cases walked through with outcomes
- `references/manual-input-template.md` — copy-paste template for Mode B (single + batch)
