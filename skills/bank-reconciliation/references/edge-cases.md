# Bank reconciliation — test cases and outcomes

A growing log of real bank lines we've walked through. Use these as regression cases when iterating the skill.

## Case 1: LI JIAHUI → Aermanjiang Abulaiti ($2,900, 9 May 2026)

**Bank line.** Date 9 May 2026, payee LI JIAHUI, reference "PayNow Transfer", description PAYNOW-FAST, received $2,900.00 into UOB 357-316-093-0 (TAP Co-Livings).

**Xero auto-match suggested.** INV-CL-47043 for Aermanjiang Abulaiti, $2,900, issued 8 May 2026, due 11 May 2026, awaiting payment. Reference field: `7645/URBANA - #12-03 Rm 1203B`. Aermanjiang's only outstanding invoice. April INV-CL-44002 was the same $2,900 paid on time.

**Algorithm walk.**
- Step 1 (name match): fail — LI JIAHUI ≠ Aermanjiang Abulaiti.
- Step 2 (last-4-digit code in reference): no digits in the PayNow reference; can't query CRM by code. Tried Xero global search for "Jiahui": 5 contacts found (Janna Tee, Keok Jia Hui, Tang, Wang, Yu) — none has a $2,900 outstanding obligation. Tried shared-room hypothesis — would need CM to confirm.
- Result: **amber → CM check.**

**Outcome.** Sebastien confirmed (20 May 2026): the strong cadence + sole-outstanding-invoice evidence is NOT sufficient. Name mismatch + no code = always CM identification before any match.

**Lesson encoded in skill.** "Even with strong cadence + sole-outstanding evidence, name mismatch + no member code in the PayNow ref requires CM identification of the payer."

---

## Case 2: WEN ZHOULINA $4,600 PayNow (date TBC)

**Bank line.** PayNow received $4,600.

**Xero auto-match suggested.** Stale 2024 credit note from Kuan Zhan Peng (different person, different year).

**Algorithm walk.**
- Step 1 (name match): fail — WEN ZHOULINA not in Xero contacts.
- Step 2 (code): no member code apparent in reference.
- Exhaustive search: all 3,665 Xero receivables checked for $4,600 — ONLY the stale 2024 Kuan Zhan Peng credit appears. No valid current invoice.
- Result: **red.**

**Outcome.** Bank line stays unreconciled. Either WEN ZHOULINA is a new tenant whose invoice hasn't been raised, or the payment needs manual investigation.

**Lesson encoded in skill.** "Never reconcile against a credit note older than 6 months based on amount alone — these are almost always Xero reaching for stale credits."

---

## Case 3: COZYHOMES MANAGEMENT $1,324.99 PayNow ref RD0618 (5 May 2026)

**Bank line.** Date 5 May 2026, payee COZYHOMES MANAGEMENT, reference RD0618, description PAYNOW-FAST, received $1,324.99.

**Xero auto-match suggested.** None — Xero put it on the Create tab (no Match candidates).

**Algorithm walk.**
- Step 1 (name match): fail — COZYHOMES MANAGEMENT not in Xero contacts (corporate payer).
- Step 2a (full reference "RD0618" search in Xero): 0 results.
- Step 2b (just digits "0618" search): 5 invoices found whose numbers END in 0618 (Yeo Puay Yin INV-0618 $4,216, Lee Yi Han INV-CL-40618 $1,521.50, Yu Mengyuan INV-CL-30618 $5,500, Morrone Cesare INV-CL-20618 $44.52, Joey Lianda Claronino INV-CL-10618 $2,200). None matches the $1,324.99 amount — they share trailing digits by coincidence of Xero's sequential numbering.
- Step 2c (exact amount "1324.99" search): 0 results anywhere in Xero.
- Result: **red.**

**Outcome.** Bank line stays unreconciled. Question for CM: who is COZYHOMES MANAGEMENT paying for, and should we expect a $1,324.99 invoice to be raised?

**Lesson encoded in skill.** "The agent must not auto-match to the closest-looking 0618 invoice (Lee Yi Han at $1,521.50). Red tier fires when name + last-4-code + exact-amount all fail."

---

## Adding new cases

When the agent encounters a new edge case, add a section here using the same structure: bank line → Xero auto-match → algorithm walk → outcome → lesson. This file is the regression suite — keep it tight and current.
