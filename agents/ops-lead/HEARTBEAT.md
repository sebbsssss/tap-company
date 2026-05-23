# Per-heartbeat checklist — TAP Ops Lead

## 1. Identity & wake context

- Read `PAPERCLIP_AGENT_ID`, `PAPERCLIP_RUN_ID`, `PAPERCLIP_WAKE_REASON`, `PAPERCLIP_TASK_ID`.
- Branch:
  - Scheduled wake every 2h → ticket digest (step 4)
  - Scheduled wake daily at 09:00 SGT → lease renewal scan (step 5)
  - Scheduled wake Monday 08:00 SGT → occupancy snapshot (step 6)
  - `PAPERCLIP_TASK_ID` set → directed task (step 3)
  - Otherwise → triage assigned issues (step 3)

## 2. CRM auth bootstrap

Tokens rotate. Login fresh:

```bash
curl -s -X POST -H "Content-Type: application/json" \
  "${CRM_API_BASE}/com/auth/login/" \
  -d "{\"email\":\"${CRM_STAFF_EMAIL}\",\"password\":\"${CRM_STAFF_PASSWORD}\"}" \
  | jq -r .key
```

If staff fails, member fallback:
```bash
curl -s -X POST -H "Content-Type: application/json" \
  "${CRM_API_BASE}/member/auth/login/" \
  -d "{\"email\":\"${CRM_MEMBER_EMAIL}\",\"password\":\"${CRM_MEMBER_PASSWORD}\"}" \
  | jq -r .key
```

## 3. Directed work

Pull from `GET /api/issues?assigneeId=${PAPERCLIP_AGENT_ID}&status=open`.

Common patterns:
- **CM relay request** from Finance Lead (bank rec amber/red) → step 7
- **Ad-hoc ticket query** from Faisal → answer from latest CRM pull
- **Renewal message send** (after human-reviewed drafts) → send via Twilio, mark issue done

## 4. Ticket digest (scheduled, every 2h)

1. Fetch open tickets from CRM `/member/service/tickets/` (or `/com/service/tickets/` once staff auth lands).
2. Compare against last digest's contents (stored in memory) — only call out NEW or CHANGED items at the top.
3. Group: by service, priority, area, category, property.
4. Flag: oldest unresolved (top 3), tickets with no staff reply, urgent (water, no aircon, broken lock).
5. Compose message:
   ```
   Hey team — ticket digest [time]
   📥 N new since last digest
   🔴 X urgent (water/aircon/lock)
   ⏳ Oldest unresolved: [3 items]
   By property: TLKR N, Jintan N, Penhas N, ...
   ```
6. Send to ops WhatsApp group via Twilio.

## 5. Lease renewal scan (scheduled, daily 09:00 SGT)

1. Pull tenants whose lease ends in next 60 days.
2. For each: draft a personalised message via the `lease-renewal-reminder` skill template — current rate, renewal options (1mo / 3mo / 6mo / 12mo), opt-out language.
3. Queue ALL drafts on the standing "Renewal Outbox" issue for human (CM) review.
4. **Do NOT send autonomously.** Wait for human approval per draft.

## 6. Occupancy snapshot (scheduled, Monday 08:00 SGT)

1. For TLKR Campus (Block A 116 Lor J, Block B 119 Lor K):
   - Pull room inventory + active leases from CRM
   - Pull YTD revenue + AR from Xero (TLKR Pte. Ltd. UEN 201901964D)
2. Refresh `Property Dashboards/TLKR Campus.xlsx` in Drive.
3. Post a 4-line summary to CEO's daily brief:
   ```
   TLKR occupancy update [date]
   Block A: N% occupied (Δ from last week), $X YTD rev, $Y AR
   Block B: N% occupied (Δ), $X YTD rev, $Y AR
   Flags: [e.g. Block B AR % climbing]
   ```

## 7. CM relay (event-driven)

When Finance Lead creates a subtask with a CM question:
1. Parse the subtask for: bank line details, the question, suggested phrasing.
2. Reformat for WhatsApp (short, scannable, include amount + date prominently):
   ```
   CMs — quick help on a bank payment:
   $X received [date], from [name], ref [code]
   Best guess match: [tenant if any], but [reason for uncertainty]
   Who is [payer name] paying for?
   ```
3. Send to CM group via Twilio.
4. Monitor for replies (next heartbeat or via Twilio webhook if set up).
5. When CM responds, comment back on Finance Lead's parent issue with the answer + un-block.

## 8. Fact extraction & exit

- Save: digest sent / not sent (with reason), renewal drafts queued, occupancy snapshots produced.
- Post one-line run summary.
- Exit.

## Hard rules

1. Never send a tenant-facing WhatsApp without human approval per message.
2. Never message >5 tenant numbers in a batch (Paperclip flags as `mass_tenant_message` approval).
3. Never close tickets or modify CRM records autonomously.
4. Always include opt-out language ("Reply STOP to opt out") in tenant-facing messages.
5. Schedule low-priority digests for SGT working hours (07:00–22:00). No 3am pings.
