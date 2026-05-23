---
name: TAP Automation
description: AI control plane for The Assembly Place — finance, operations, and reporting automation across four entities (TLKR, Co-Livings, Hotel, Service Apartment).
goal: >
  Reduce manual Finance and Operations workload at TAP. Specifically: automate monthly settlement letter generation for property owners, daily bank reconciliation triage, weekly AR and ticket digests, and TAP-wide CFO briefs. Surface decisions that require human judgement (CM identification of payers, owner-side utility formula verification, settlement sign-off) rather than auto-executing them.
---

# TAP Automation

The Assembly Place (TAP) is a Singapore-based property management company operating four entities:

| Entity | UEN | Properties |
| --- | --- | --- |
| TAP Co-Livings Pte. Ltd. | 202300680H | 18 Jln Jintan, 18 Penhas, 51 Middle Rd, and other co-livings |
| TLKR Pte. Ltd. | 201901964D | TLKR Campus — Block A (116 Lor J), Block B (119 Lor K) — student housing |
| Hotel entity | (TBC) | Hotel operations |
| Service Apartment entity | (TBC) | Service apartment operations |

## Key people the agents will reference

- **Yee Chin** — CFO. Audience for the monthly CFO Brief and any escalations needing financial judgement.
- **Faisal** + **Erwan / Muhammad / Thomas** — Operations. Faisal owns the ticket queue; technicians cover electrical / plumbing.
- **Community Managers (CMs)** — Tenant relationship owners. ~300 tenants per CM. Authoritative source when a payer's identity is ambiguous on a PayNow line.
- **Tech team** — Owns the CRM (Django backend at `crm-api.theassemblyplace.com` with `/member/` and `/com/` API surfaces) and grants staff API tokens.

## Data sources

- **Xero** — One organisation per entity. Read-only MCP available with 7 tools (P&L, receivables, cash position, financial year, contacts). Web UI fallback for invoice / contact lookups.
- **CRM** — Two API surfaces: `/member/` (tenant-scope, 51 paths) confirmed working; `/com/` (staff-scope, 215 paths) pending staff auth flow (Tech follow-up in progress).
- **Twilio** — WhatsApp Sandbox for ticket digests and lease renewal reminders.
- **Google Drive** — Final settlement xlsx files land in `Settlement Reports/<year>/`.
- **Notion** — Meeting minutes (Property Management Settlement, Payment Reconciliation Training) — canonical source for the calculation rules the agents follow.

## Operating principles

1. **Human in the loop for irreversible actions.** Agents never click OK on bank reconciliations, never send final settlement letters to owners, never send mass tenant messages without human approval.
2. **Surface uncertainty.** When the canonical rules say "verify with CM" or "Finance to fill", agents flag the work and stop rather than guess.
3. **Audit trail by default.** Every settlement xlsx includes raw CRM + Xero source sheets. Every bank rec decision includes the reasoning (which rule fired, which candidates were considered).
4. **Cite sources.** When following a Notion-documented rule, link the Notion page in the agent's output.
