# Settlement run — manual input template (no Xero MCP required)

Use this when the agent can't pull Xero directly (no MCP wired yet, or you want to run a settlement against numbers you've already verified by hand). The agent reads the pasted numbers from the Paperclip issue body, runs `settlement.py`, and posts the xlsx back.

## How Finance creates the issue

In Paperclip web UI:

1. New issue
2. Assignee: **Finance Lead**
3. Title: `Generate <Month YYYY> settlement for <PROPERTY>` (e.g. "Generate March 2026 settlement for 18 Jln Jintan")
4. Paste the template below into the body, replacing the placeholders with values from Xero + CRM
5. Submit. The agent picks it up on its next heartbeat (within ~6 hours by default; click "Run Heartbeat" to fire immediately).

## Copy-paste template

```markdown
## Settlement request

**Property:** 18 JALAN JINTAN
**Landlord:** Yeoh Joe Wei Evelyn
**Entity:** TAP Co-Livings Pte. Ltd.
**Period:** March 2026  (or: 2026-03-01 to 2026-03-31 for partial)
**Property kind:** co_living  (or: campus — for TLKR)

## Xero P&L (from Reports → Profit and Loss, Location filter = property, period above)

| Line | Amount (SGD) |
| --- | --- |
| Straight Lease - Rental of premises (base_rent) | 6000.00 |
| Rental of premises (additional_rent) | 10798.83 |
| Management Contract - Repairs and maintenance (mgmt_contract_rm) | 38.00 |

## CRM tenant roster (from Reports → Settlement, property + period above)

| Tenant | Room | Duration | Month of | Rental rate | Rental date | Lease end |
| --- | --- | --- | --- | --- | --- | --- |
| Guan Mingjun   | B01 | Extend 1 months  | 1/1  | 2800.00 | 1 Mar 26  | 31 Mar 26 |
| Xu Jia         | B02 | Extend 12 months | 1/12 | 3000.00 | 27 Mar 26 | 26 Mar 27 |
| Wan Ying Zhang | B03 | Extend 1 months  | 1/1  | 2600.00 | 11 Mar 26 | 10 Apr 26 |
| An Qi          | B04 | 12 months        | 1/12 | 3100.00 | 25 Mar 26 | 24 Mar 27 |
| Drishti Sehgal | B06 | Extend 8 months  | 1/8  | 3100.00 | 23 Mar 26 | 22 Nov 26 |

## Excess Utility input (optional — leave blank if SP bill not yet downloaded)

Unit: Whole shophouse  cap_mode: per_room
Actual SP bill: $850.00  (period: 1–31 Mar 2026)

Per-tenant caps:
- Guan Mingjun   B01: 100.00
- Xu Jia         B02: 100.00
- Wan Ying Zhang B03: 100.00
- An Qi          B04: 100.00
- Drishti Sehgal B06: 100.00

## Notes (optional)

- Cleaning: use property default ($180 × 4 = $720). Override if Finance says different.
- Owner-side utility row: leave yellow (pending Yee Chin's formula verification per backtest 2026-05-20).
- Special handling: <any one-off context for this run>
```

## What the agent does with this

1. **Parses** the template — extracts property, period, Xero numbers, roster, utility (if present)
2. **Looks up** standing defaults from `property_defaults.json` (cleaning, base rent, property_kind, landlord postal)
3. **Builds** the inputs:
   - Writes roster JSON to `/tmp/roster_<runid>.json`
   - Writes Xero JSON to `/tmp/xero_<runid>.json`
   - Writes utility JSON to `/tmp/utility_<runid>.json` if utility data provided
4. **Runs** `settlement.py`:
   ```bash
   python3 ${SKILLS_ROOT}/settlement-generator/scripts/settlement.py \
     --property "<PROPERTY>" --landlord "<LANDLORD>" \
     --period <YYYY-MM> \
     --roster /tmp/roster_<runid>.json \
     --xero /tmp/xero_<runid>.json \
     --utility /tmp/utility_<runid>.json \
     --output /tmp/settlement_<runid>.xlsx
   ```
5. **Posts back** on the issue with: xlsx attached (or Drive link if Drive MCP wired), the net-to-owner total, and a 3-line summary that includes any caveats (yellow cells, pending verifications)

## What Finance gets back

A comment on the issue like:

> Settlement for **18 Jalan Jintan — March 2026** generated.
>
> - **Net to owner: $16,798.83** (straight-lease block: $6,000 base + $10,798.83 additional rent)
> - 5 tenants, $14,600 gross rent, $2,798.34 mgmt + commission deducted
> - Cleaning $720 auto-filled from property defaults
> - Utility row: $250.00 tenant-side excess computed (see Tenant Excess Utility sheet), owner-side row left yellow per the formula-verification gap with Yee Chin (Notion backtest 2026-05-20)
>
> [settlement_18jntn_mar26.xlsx](attachment_or_drive_link)
>
> AR staff: please review the yellow cells (utility, deposits, servicing) before sending to owner.

## Why this is OK as the interim

- **5 minutes of Finance time** vs maybe 60 minutes the way it's done today (manually building the xlsx from scratch)
- **Same precision as the MCP path** — we validated the skeleton ties to the cent against Finance's actual Feb / Mar 2026 files
- **Same outputs** — the xlsx Finance gets is identical whether the numbers came from MCP or paste
- **One change later** — when Xero MCP lands, the agent stops needing the Xero section from Finance, but the template otherwise stays the same. Finance won't have to relearn anything.

## When the agent CAN'T parse the template

The agent's `HEARTBEAT.md` for Finance Lead handles common failure modes:

- Missing required field (property, period, Xero numbers) → agent comments back asking specifically what's missing
- Roster table doesn't parse (column missing, weird formatting) → agent posts the parsed roster back for Finance to confirm
- Period format ambiguous → agent asks: "March 2026 or 2026-03-01 to 2026-03-31?"

Never silently guesses — always asks.

## Generalising to other settlements

Same template, different values. For TLKR Campus settlements, set `property_kind: campus` and skip the utility section entirely (TLKR has no utility caps — company absorbs).

For partial-period (mid-month closeout), use the date range form of `period`: `2026-05-01 to 2026-05-11`. Agent passes `--start` and `--end` to `settlement.py` instead of `--period`.
