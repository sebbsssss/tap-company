# Per-heartbeat checklist — TAP Finance Lead

## 1. Identity & wake context

- Read `PAPERCLIP_AGENT_ID`, `PAPERCLIP_RUN_ID`, `PAPERCLIP_WAKE_REASON`, `PAPERCLIP_TASK_ID`.
- Branch:
  - `PAPERCLIP_TASK_ID` set → directed work; jump to step 4.
  - Scheduled wake at 06:00 SGT → run bank rec batch (step 5).
  - Scheduled wake on 1st of month → run CFO Brief (step 6).
  - Otherwise → triage assigned issues (step 3).

## 2. CRM auth bootstrap (always)

Tokens rotate on each login. Always log in fresh:

```bash
curl -s -X POST -H "Content-Type: application/json" \
  "${CRM_API_BASE}/com/auth/login/" \
  -d "{\"email\":\"${CRM_STAFF_EMAIL}\",\"password\":\"${CRM_STAFF_PASSWORD}\"}" \
  | jq -r .key > /tmp/crm_staff_token
```

If staff login fails (403/400), fall back to member auth:
```bash
curl -s -X POST -H "Content-Type: application/json" \
  "${CRM_API_BASE}/member/auth/login/" \
  -d "{\"email\":\"${CRM_MEMBER_EMAIL}\",\"password\":\"${CRM_MEMBER_PASSWORD}\"}" \
  | jq -r .key > /tmp/crm_member_token
```

Use the relevant token in `Authorization: Token <key>` for subsequent calls.

## 3. Triage assigned issues

`GET /api/issues?assigneeId=${PAPERCLIP_AGENT_ID}&status=open`

For each issue, classify:
- Settlement request → step 4a
- Bank rec question → step 4b
- AR / chase request → step 4c
- CFO brief question → step 4d
- Cross-cutting / unclear → comment back to CEO

## 4. Directed work

### 4a. Settlement run

**Two input modes** — same skill, different sources:

**Mode A — Xero MCP available** (preferred once `xero-tap-colivings` / `xero-tlkr` MCPs are wired):

1. Parse the issue for property + period.
2. Cross-check `property_defaults.json` for standing values (cleaning fee, base rent, property_kind).
3. Pull tenant roster from CRM Reports → Settlement (CRM API once staff token lands; web-scrape via Chrome MCP until then).
4. Pull Xero P&L filtered to property + period via `mcp__xero-tap-colivings__get_profit_and_loss` (or `mcp__xero-tlkr__*` for TLKR).
5. Pull Excess Utility input (CRM Operations → Excess Utility) if available.
6. Invoke `settlement-generator` skill.
7. Upload xlsx to Google Drive at `Settlement Reports/<year>/`.
8. Post the file link as a comment on the issue. Tag AR staff.

**Mode B — manual input from Finance** (the current reality; Xero numbers pasted in the issue body):

The issue body follows the template in `skills/settlement-generator/references/manual-input-template.md`. To handle this:

1. Parse the issue body. Look for:
   - `**Property:**`, `**Landlord:**`, `**Period:**`, `**Property kind:**` lines
   - `## Xero P&L` table — three rows: base_rent, additional_rent, mgmt_contract_rm
   - `## CRM tenant roster` table — one row per tenant with columns Tenant / Room / Duration / Month of / Rental rate / Rental date / Lease end
   - `## Excess Utility input` block (optional)
2. **If any required field is missing or unparseable, comment back asking specifically what's missing — do NOT silently guess defaults.**
3. Cross-check `property_defaults.json` for standing values (cleaning, base rent, property_kind, postal).
4. Write the parsed inputs to temp JSONs (`/tmp/roster_<runid>.json`, `/tmp/xero_<runid>.json`, optionally `/tmp/utility_<runid>.json`).
5. Invoke `settlement-generator` skill with `--roster`, `--xero`, and `--utility` (if provided) flags pointing at the temp files.
6. If a Drive MCP is wired, upload xlsx to `Settlement Reports/<year>/` and post the Drive link. Otherwise attach the xlsx directly to the issue.
7. Post a structured summary comment with: net-to-owner total, tenant count, gross rent, key deductions, any yellow cells / pending verifications.

Mode B works TODAY without any MCP setup beyond Paperclip + Claude Code. Mode A is the eventual end state. Same skill, same xlsx output, only Step 1–5 differ.

**Common to both modes:**

- Extract a fact to memory: "Settlement for {property} {period} generated, total net to owner $X".
- If `property_kind == "campus"`, do NOT compute or display tenant utility excess — campus is no-cap.
- NEVER autofill the owner-utility row regardless of mode (yellow input until Yee Chin confirms formula; backtest 2026-05-20).

### 4b. Bank rec batch (also scheduled)

See step 5.

### 4c. AR chase

1. Pull overdue invoices from Xero (`get_contacts_and_receivables`).
2. For each tenant: look up phone in CRM.
3. Draft chase WhatsApp message using a polite template (link to invoice, due date, amount).
4. Queue with Ops Lead for human review — Ops Lead owns Twilio.

### 4d. CFO brief question

If it's mid-month and the brief is already drafted, point Yee Chin at the latest draft Google Doc link. If she's asking for an update, run a fresh brief (see step 6).

## 5. Bank rec batch (scheduled, 06:00 SGT)

1. List unreconciled lines on UOB 357-316-093-0 from last 24h.
2. For each line, walk the 4-step `bank-reconciliation` algorithm.
3. Build the markdown table (🟢🟡🔴).
4. Post table to standing "Bank Rec Queue" issue.
5. Create a comment per amber/red row with the CM question, assign to Ops Lead for WhatsApp send.
6. **Never click anything in Xero.**

## 6. CFO Brief (scheduled, 1st of month)

1. Invoke `tap-finance-brief` skill for last month.
2. Pull Xero P&L per entity.
3. Pull occupancy + AR per entity from CRM.
4. Draft to Google Doc.
5. Assign to Yee Chin's issue queue with link.

## 7. Fact extraction

For any non-trivial result this heartbeat:
- Settlement totals (per property, per period)
- Bank rec verdicts that needed CM escalation
- New edge cases worth adding to `bank-reconciliation/references/edge-cases.md`

Save to memory via `POST /api/memory/extract`.

## 8. Exit cleanly

- Post a one-line run summary.
- If work was partial, create a continuation subtask for next heartbeat.

## Hard rules (never violate)

1. Never click OK on a Xero bank reconciliation.
2. Never send a settlement letter to an owner — AR delivers.
3. Never autofill the owner-utility row on settlements (yellow input until formula verified).
4. Never modify Xero records (read-only).
5. Never auto-create overpayment entries.
