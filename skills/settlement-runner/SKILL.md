---
name: settlement-runner
description: Run the monthly TAP owner settlements end-to-end. Generates per-property settlement letters (per-tenant for co-livings, per-block for TLKR), and auto-fills every line — excess utility (CRM), security deposits (Xero Deposits Received), base/additional rent (Xero), and cleaning/furniture/servicing (Andrey's SETTLEMENT INPUT email to jarvis.ai@theassemblyplace) — then recomputes and drafts to owners for review. Use when the user says run the settlements for a month, generate the settlement for a property and month, run all co-living settlements, or settle TLKR Campus for a month.
---

# Settlement Runner

End-to-end monthly settlement. Produces Finance's exact xlsx, with nothing routine left manual.

## Triggers
- `run all co-living settlements for <month>`
- `generate the settlement for <property>, <month>`
- `run TLKR Campus settlement for <month>`
- `partial settlement for <property>, <start>–<end>`

## Inputs
A **month** (e.g. `2026-06`) and either **one property** or **all**. Resolve the property → CRM record and owner automatically; never ask the user for IDs.

## Connectors required (already on the TAP Paperclip agents)
- **CRM** — `x-api-key` (William's staff token). Properties: `GET /com/property/properties/?limit=1000`; bookings: `/com/booking/bookings/`; excess utility: `/com/billing/expenses/`.
- **Xero** — Custom Connection per entity (client_credentials) for base/additional rent + **Deposits Received** transactions.
- **jarvis Gmail MCP** — to read Andrey's `[SETTLEMENT INPUT]` emails.

## ⚠ Correctness rules (dispute THE-17475 — verified against Finance's file; do not skip)
- **Rent = full monthly rate. NO proration.** Use each tenant's full contractual monthly rate. The "rental date" column is the **billing date, not move-in** — tenants are mid-lease and bill a full month (even a mid-month break-lease bills full). (An earlier prorated version was wrong.)
- **Real landlord.** Address to the property's `rental_detail_landlord_name` + its address/attention (e.g. Suites @ Sophia → *AV Venture Pte. Ltd., 105 Eunos Ave 3, Attn: Ms Susan Goh*), NOT `default_landlord`.
- **Utilities = SP Bill Amount per stack** (NOT member-excess). From the CRM excess-utility export / `GET /com/billing/expenses/` use the `sp_bill_amount` **per unit/stack** for the prior **15th–14th** cycle (e.g. May settlement → 15 Apr–14 May), itemized one line per stack.
- **Itemize** payment-on-behalf (one line per Xero vendor invoice) and servicing (one line per item, with date). Cleaning from Andrey's `[SETTLEMENT INPUT]` email.

## Workflow (per property)
1. **Base letter** — pull the roster from CRM (each tenant's **full** monthly rate, no proration), set the owner = `rental_detail_landlord_name` (+ address/attention), and generate with the `settlement-generator` script (management fee 15% + commission = rent ÷ 24; base/additional rent from Xero). Picks per-tenant vs per-block from `property_kind`.
2. **Utilities** → "Less: Utilities", **itemized per stack** = `sp_bill_amount` per unit from `/com/billing/expenses/` for the 15th–14th cycle. (NOT member-excess. Properties with no bill that cycle → 0 and flag.)
3. **Security deposits** → fill "Add: Security deposits received/(refunded)". Source: **Xero → Transactions → Deposits Received** for the property/period (net received − refunded).
4. **Cleaning / furniture / servicing** → run `scripts/settlement_inputs.py`:
   - `fetch_email_body(month)` searches jarvis Gmail for `subject:"SETTLEMENT INPUT" subject:"<month>"` (or pass the body straight from the Gmail MCP),
   - `parse_settlement_input(body)` → per-property amounts,
   - `apply_inputs_to_settlement(xlsx, month, property, parsed)` → fills cleaning ("Less: Cleaning charges") and furniture+servicing ("Servicing items"). See `Settlement Email Intake — Format` for the email spec.
5. **Recompute & verify** — run `xlsx/scripts/recalc.py`; require **zero formula errors**; check Net amount due.
6. **Draft to owner** — draft the email in Gmail with the xlsx attached. **Do NOT auto-send** — leave for human review (per the rollout rule).

## What stays manual / gets flagged (never guessed)
- Any `[SETTLEMENT INPUT]` line the parser can't match (unknown property name, missing amount).
- Properties with no excess-utility bill in the cycle (e.g. 117 Killiney, 257 Outram in May).
- Straight-lease base/additional rent if Xero hasn't booked it yet (typical mid-month).

## Output
Save to `The Assembly Place/Settlements <Month>/`. One xlsx per property (3 tabs: letter, CRM roster raw, Xero P&L raw). For an all-properties run, also write a `_Bulk-Manifest-<Month>.xlsx`.

## Notes / gotchas
- If CRM `/com/report/settlement/` returns 500, fall back to `/com/booking/bookings/` (roster) — handled automatically.
- Excess utility uses the **member-excess** figure (per Sebastien). To switch to total SP+Senoko bill, say so.
- See companion docs: `Settlement Report - Finance Team Guide (Paperclip).md`, `Settlement Email Intake - Format for Andrey & Finance.md`.
