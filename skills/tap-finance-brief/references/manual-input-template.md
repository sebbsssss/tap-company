# CFO Brief — manual input template

Use when generating the monthly TAP-wide CFO Brief for Yee Chin and you don't have Xero MCP wired (or want to override the MCP-pulled numbers with your own).

## How to use

1. In Paperclip web UI, new issue assigned to **Finance Lead**
2. Title: `Draft CFO Brief — <Month YYYY>` (e.g. "Draft CFO Brief — May 2026")
3. Paste the template below, fill in the per-entity numbers from Xero
4. Submit. The agent drafts a Markdown brief, optionally posts to Google Doc, and tags Yee Chin for review

## Copy-paste template

```markdown
## CFO Brief request

**Period:** May 2026
**Audience:** Yee Chin (final goes to her for review BEFORE sharing with anyone else)
**Output format:** Google Doc draft   (or: "Markdown only", "Slack-ready summary")

## Per-entity Profit & Loss

> Pull from Xero → Reports → Profit and Loss, run separately per entity. The period should match the brief period above.

### TLKR Pte. Ltd. (UEN 201901964D)
| Line | This period | Last period | Variance |
| --- | --- | --- | --- |
| Rental income | 87,500.00 | 85,200.00 | +2,300 (+2.7%) |
| Other operating income | 0 | 0 | — |
| Cost of sales | 8,200.00 | 7,900.00 | +300 |
| Total operating expenses | 28,400.00 | 27,100.00 | +1,300 |
| Net profit | 50,900.00 | 50,200.00 | +700 |
| AR at period end | 18,450.00 | 16,200.00 | +2,250 |

### TAP Co-Livings Pte. Ltd. (UEN 202300680H)
| Line | This period | Last period | Variance |
| --- | --- | --- | --- |
| Rental income | (paste) | | |
| Other operating income | | | |
| Cost of sales | | | |
| Total operating expenses | | | |
| Net profit | | | |
| AR at period end | | | |

### Hotel entity
> Write "n/a — no activity this period" if applicable
(same shape as above)

### Service Apartment entity
(same shape as above)

## Occupancy snapshot
> Optional but recommended — from CRM dashboard or your monthly tracking sheet

| Property | Rooms | Occupied this period | Occupancy % | Δ vs last period |
| --- | --- | --- | --- | --- |
| TLKR Block A | 42 | 40 | 95% | +1 |
| TLKR Block B | 38 | 32 | 84% | -2 |
| 18 Jln Jintan | 6 | 6 | 100% | 0 |
| 18 Penhas | 8 | 7 | 88% | 0 |
| (other properties) | | | | |

## Watch items (optional but valuable)
> Anything notable for the period — one-offs, exceptions, or trends Yee Chin should know about

- (e.g. "TLKR Block B AR climbing 3 months in a row — recommend dunning review")
- (e.g. "One-off legal fee of $X under Co-Livings related to the 51 Middle Rd dispute")
- (e.g. "Aircon servicing capex came in $2k under budget this quarter")

## Comparison context
- Compare to:   prior month   (or: "same month last year", "vs budget")
- YTD context: include / skip

## Specific questions from Yee Chin (optional)
- (e.g. "Wants a deeper view on TLKR Block B's expense climb — what's driving it?")
- (e.g. "Asked for cash flow runway estimate — please include if numbers support it")
```

## What the agent produces

A markdown / Google Doc roughly like:

```markdown
# TAP CFO Brief — May 2026

**Headline.** TAP-wide revenue $X,XXX,XXX (Δ vs Apr +2.1%). Net profit $XXX,XXX. AR $XXX,XXX (up $XX from Apr, mostly TLKR Block B).

## Per-entity summary

| Entity | Revenue | Net profit | AR | Watch |
| --- | --- | --- | --- | --- |
| TLKR | $87,500 | $50,900 (58% margin) | $18,450 | Block B AR climbing |
| Co-Livings | ... | ... | ... | ... |
| Hotel | n/a | | | |
| Service Apt | n/a | | | |

## Drill-downs

### TLKR Pte. Ltd.
- Revenue +2.7% vs April, driven by Block A reaching 95% occupancy
- AR up $2,250 — entirely Block B (3 long-standing tenants)
- Recommendation: dunning review on the 3 stale Block B accounts before they hit 45 days

### TAP Co-Livings
- (similar drill-down)

## Occupancy

(table or chart-ready data)

## Watch items

- TLKR Block B AR — 3 months of climb. Recommend Yee Chin call or escalate to CM.
- Legal fee $X under Co-Livings (51 Middle Rd) — one-off, no impact on operating margin.

## Yee Chin's specific questions

(if she asked for a deeper look on something, address it here)

---
*Draft prepared by Finance Lead agent. Pending Yee Chin review before sharing.*
```

## Workflow after the draft lands

1. Yee Chin opens the Google Doc / reads the comment
2. She edits in place (Google Doc) or comments back on the Paperclip issue with corrections
3. Agent revises if asked, or marks issue done if she's satisfied
4. **She** shares the final version with the rest of the leadership team — agent does NOT auto-share

## Notes

- The agent will NOT publish or share the brief externally — only drafts for Yee Chin's review.
- If Drive MCP is wired, the brief is created as a Google Doc and the link is posted to the issue. Without Drive MCP, the brief is posted as a markdown comment on the issue (or attached as a .md file).
- For monthly briefs, the agent's HEARTBEAT runs this automatically on the 1st of each month — you only need to paste the template if you want an off-cycle brief or want to override MCP-pulled numbers.

## See also

- `../SKILL.md` — full brief structure + scope
- `../../settlement-generator/references/utility-backtest-2026-05-20.md` — the open Finance verification gap that affects net margin numbers slightly
