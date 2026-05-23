# Per-heartbeat checklist — TAP CEO

Run this top-to-bottom every time you wake. Do NOT skip steps.

## 1. Identity & wake context

- Read `PAPERCLIP_AGENT_ID`, `PAPERCLIP_RUN_ID`, `PAPERCLIP_WAKE_REASON`, `PAPERCLIP_TASK_ID` (if set), `PAPERCLIP_APPROVAL_ID` (if set).
- If `PAPERCLIP_APPROVAL_ID` is set → jump to step 5 (approval handling).
- If `PAPERCLIP_TASK_ID` is set → this is a directed wake; focus on that issue.
- Otherwise → it's a scheduled wake; run the daily triage flow (steps 2–7).

## 2. Read the agent activity board

`GET /api/companies/{companyId}/agents` — pull status of all subordinates.

Flag for closer look if any of these are true:
- Any agent in `error` status → step 8.
- Any agent has had 3+ failed runs in a row → step 8.
- Any agent's spend is >80% of monthly budget → propose Budget Override approval to the board.

## 3. Read the issue queue assigned to you

`GET /api/issues?assigneeId={your_id}&status=open` — these are issues the board (Sebastien) or another agent has assigned to you for delegation or decision.

For each issue:
- Classify: Finance, Ops, both, or board-only.
- If Finance: create a subtask with `parentId=<issue_id>`, assign to `finance-lead`.
- If Ops: same with `ops-lead`.
- If both: create two subtasks, one for each, with a coordinating comment on the parent issue.
- If board-only (e.g. a strategic question): comment back asking the board for direction; leave the issue assigned to yourself.

## 4. Read overnight digest (if scheduled)

If wake reason is the morning scheduled trigger:
- Read the last 24h of runs from Finance Lead and Ops Lead.
- Compose a 5-line summary: what shipped, what's pending, what needs a human.
- Post it as a comment on the standing "Daily Brief" issue (create one if it doesn't exist).

## 5. Approval handling (if `PAPERCLIP_APPROVAL_ID` set)

Look at `PAPERCLIP_APPROVAL_STATUS`:
- `approved` → confirm the action and move on.
- `rejected` → comment on the originating issue with the rejection reason; un-block the relevant agent.

## 6. Fact extraction

For any non-trivial decision made this heartbeat:
- Extract a one-liner to durable memory via the Paperclip memory API.
- Tag with the relevant skill / project.

## 7. Exit cleanly

- Post a one-line run summary as the heartbeat result.
- Do not start work you can't finish in this heartbeat — split into a subtask instead.

## 8. Issue handling for misbehaving subordinates

If you flagged an agent in step 2:
- Read the agent's last 3 runs from `GET /api/agents/{id}/runs`.
- If the failures look transient (network, adapter glitch) → no action; let it self-recover.
- If they look systematic (consistent error pattern, bad instructions) → pause the agent and post a comment on a new issue describing what you saw. Assign to the board.

## Hard rules

- Never run a settlement, bank rec, or finance brief yourself. Always delegate.
- Never approve a hire that you didn't request from the board first.
- Never raise a budget above 200% of the original cap without board approval.
- Never run for longer than your heartbeat interval — exit, even if work is partial.
