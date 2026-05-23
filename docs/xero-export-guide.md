# Xero export guide — where to find the numbers each template needs

Click-by-click walkthrough for getting the data the agent asks for in each template. Bookmark this page — it's the companion to `docs/issue-templates.md`.

**Convention used:** Xero menu paths are shown as `Top menu → Sub-item → Sub-sub-item`. Most reports have an **Export** button (top-right corner of the report) that gives you xlsx / PDF / CSV — for the agent you generally don't need to export anything, just **read the 3-6 numbers** off the screen and paste them.

---

## For Settlement template

The agent needs **3 numbers from one Xero report** + optional supporting lines.

### Main report — Profit and Loss by Location

1. Switch to the right entity at the top-left dropdown:
   - **TAP Co-Livings Pte. Ltd.** (UEN 202300680H) for 18 Jln Jintan, 18 Penhas, 51 Middle Rd, etc.
   - **TLKR Pte. Ltd.** (UEN 201901964D) for TLKR Block A (116 Lor J), Block B (119 Lor K)

2. Navigate: **Accounting → Reports → Profit and Loss** (or click the ⭐ star to favourite it)

3. Set the parameters at the top of the report:
   - **Date range:** the settlement month (e.g. 1 Mar 2026 → 31 Mar 2026). For partial periods (e.g. 1–11 May), use the custom range.
   - **Compare with:** leave blank for settlements (you compare in the CFO Brief, not here)
   - **Click "More" → enable "Tracking categories"** — this reveals the Location filter
   - **Filter by tracking category → Location → pick the property** (e.g. "18 Jalan Jintan")
   - Click **Update**

4. Read these three line items off the report — they are the only three the agent needs:

| Xero line item label | Where it appears | Template field |
| --- | --- | --- |
| **Straight Lease - Rental of premises** | Under Income | `base_rent` |
| **Rental of premises** | Under Income (usually right above Straight Lease) | `additional_rent` |
| **Management Contract - Repairs and maintenance** | Under Expenses (sometimes under "Operating expenses") | `mgmt_contract_rm` |

If any of these lines isn't showing, check that:
- The Location filter is correctly set
- The period covers when the rent was booked
- Xero hasn't been re-categorised since (rare — ask Finance if a line that was there in March isn't there in April)

### Optional — Deposit Received Transactions (for the deposits section)

Only needed if there were new deposits received or refunded in the period.

1. **Accounting → Reports → All Reports** → search "Deposit"
2. Pick **Deposit Received Transactions** (or whatever TAP calls it — Yee Chin's saved version may have a different name)
3. Date range: the settlement period
4. Filter by Location (same as above)
5. List shows: one row per deposit movement with the tenant name, room, and amount
6. Paste relevant rows into the template's `## Deposits` section

### Optional — Account Transactions (for payment-on-behalf items like Whiz)

Only needed if TAP paid third-party expenses on the owner's behalf during the period (e.g. Whiz internet subscription).

1. **Accounting → Reports → Account Transactions**
2. **Account:** filter to "Management Contract - Repairs and Maintenance" (or whichever account is used)
3. **Date range:** the settlement period (sometimes back-bill 2-4 months to catch missed entries — Finance's existing practice on 18 Jln Jintan is 4 months of Whiz)
4. **Location:** same property filter
5. Paste each line into the template's `## Payment on behalf` section

### Optional — Excess Utility (NOT a Xero report)

This data is in the **CRM**, not Xero:
- CRM → Operations → Excess Utility → property + month → download CSV
- Or just read the unit's actual SP bill amount + each booking's cap and paste into the template

---

## For Bank Reconciliation template

You don't actually export anything. You're already looking at the bank rec page when you create the issue.

1. **Switch to the right entity** (top-left dropdown). Bank rec is per entity.
2. **Accounting → Bank accounts → click the account** (e.g. UOB 357-316-093-0 for TAP Co-Livings)
3. The **Reconcile (XX)** tab shows unreconciled lines. Click **More details** on a specific line — that opens the Statement Details popup showing all the fields the template asks for:
   - Date
   - Payee
   - Reference
   - Description
   - Amount
   - Transaction Type
4. If Xero is showing a suggested match (the green box on the right side of the line), copy that text too — the agent uses it as input.

---

## For CFO Brief template

You need P&L per entity + AR per entity. So 2-3 reports × 4 entities = 8-12 numbers total per brief.

### P&L per entity

For EACH entity (TLKR, TAP Co-Livings, Hotel, Service Apartment):

1. Switch to that entity (top-left dropdown)
2. **Accounting → Reports → Profit and Loss**
3. **No Location filter this time** — you want the whole entity rollup
4. **Date range:** the brief period (e.g. May 2026)
5. **Compare with:** previous month (so the variance column is auto-calculated)
6. Read these summary lines:
   - **Total Income** (or "Total Revenue")
   - **Cost of sales** (if present)
   - **Total Operating Expenses**
   - **Net profit** (bottom line)

### AR per entity

For EACH entity:

1. Same entity selected
2. **Accounting → Reports → Aged Receivables Summary**
3. **Date:** last day of the brief period (e.g. 31 May 2026)
4. Read the **Total** row (or specifically "30+ days overdue" if Yee Chin wants the aging breakdown)

### Time-saver

If Yee Chin's been running this for a while, ask her — she probably has all these as **"Saved" reports** in Xero already, named like "TLKR P&L Monthly" and "Co-Livings AR Aging". Saved reports keep your filters/period and let you re-run in one click.

---

## For AR Chase List template

### The main report — Awaiting Payment invoices

1. Switch to the entity (TAP Co-Livings for most tenant rent; TLKR for student housing)
2. **Business → Sales → Invoices**
3. Filter:
   - **Status:** Awaiting Payment
   - **Due date:** is **before** today
4. Sort by **Due Date ascending** (oldest first — those are the most overdue)
5. Click **Export → Summary (CSV)** to get a spreadsheet — or just eyeball the screen if it's a short list
6. For each row, copy: Invoice number, Tenant name, Property/Room (from the Reference field), Amount, Days overdue (Xero shows this in the second-to-last column)

### Tenant phone numbers

Xero doesn't always have the tenant's phone. Two places to find it:

- **CRM → Members → search tenant** → Profile → Phone
- Or ask the CM group — they know

If you don't have the phone handy, leave it blank in the template — the agent will skip that row's draft and ask AR to fill in phone numbers before sending.

---

## For Ticket Digest (Ops Lead handles, not Finance — included for reference)

Not a Finance task, but if you want to see the data the digest is built from:

1. **CRM → Operations → Tickets** (or Service → Tickets, depending on TAP's CRM UI)
2. Filter: Status = Open or Acknowledged
3. Group by Property / Priority / Category

Ops Lead pulls this automatically every 2 hours; you don't need to do anything.

---

## Common gotchas

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| "I see Rental of premises but not Straight Lease - Rental of premises" | Wrong entity selected, OR the property isn't on a straight-lease arrangement | Confirm with Yee Chin — not all properties have both lines |
| "Total in the report doesn't match what I expect" | Location filter is off — report is showing all properties | Re-apply Location filter and click Update |
| "Export button doesn't show xlsx, only PDF" | Some Xero report types are PDF-only | Use the on-screen numbers — paste manually, you only need 3-6 of them per settlement |
| "I see the line item but the amount is $0" | Period range is wrong, or no transactions were booked that month | Check the date range; ask Finance if the income should have been booked |
| "Aged Receivables Summary shows different totals on TLKR vs Co-Livings" | Each entity has its own AR — by design | This is correct. CFO Brief covers each separately. |

---

## What the agent does with these numbers

Pastes them into a JSON file, runs `settlement.py` (or `finance_brief.py`, or the bank rec rules engine), and produces an xlsx or markdown draft. **All math is repeated on its side** — you don't need to compute totals; just give it the raw inputs.

If the agent ever produces a number that doesn't match what you computed by hand, comment on the issue with both numbers — that's how we catch parser bugs.

## See also

- `./finance-quickstart.md` — what to do once you have the numbers
- `./issue-templates.md` — full templates these numbers slot into
- `../skills/settlement-generator/SKILL.md` — what the agent does with the data
