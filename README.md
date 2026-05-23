# TAP Automation — Paperclip company package

This folder is a Paperclip-importable company. It contains everything we've built and validated for TAP Automation so far: three agents, seven skills, and a manifest declaring the adapters and environment variables.

## 👋 For the Finance team

If you're Yee Chin, AR staff, or settlements staff — **start here: [`docs/finance-quickstart.md`](./docs/finance-quickstart.md)**. It's a 5-minute read with copy-paste templates for everything you'll commonly want to do.

For administrators wiring up the host machine, read on.

## What's in here

```
tap-company/
├── COMPANY.md                       # Company definition: name, goal, entity map, key people
├── .paperclip.yaml                  # Adapters per agent, env var declarations, approval rules
├── README.md                        # This file
├── docs/
│   ├── finance-quickstart.md        # 🎯 START HERE if you're on the Finance team
│   ├── issue-templates.md           # Full copy-paste templates for every workflow
│   ├── xero-export-guide.md         # Where in Xero each template's numbers come from
│   ├── paperclip-quickstart-setup.md# How to surface the quickstart inside Paperclip's UI
│   ├── deployment-vm.md             # Cloud VM setup (Ubuntu + Paperclip + Claude Code + Xero Custom Connection)
│   └── mcp-setup.md                 # Which MCPs to install + claude mcp add commands
│
├── agents/
│   ├── ceo/                         # Orchestrator — delegates to specialists, watches budgets
│   │   ├── AGENT.md                 # Operating manual (entry file)
│   │   ├── SOUL.md                  # Persona / strategic posture
│   │   ├── HEARTBEAT.md             # Per-wake checklist
│   │   └── TOOLS.md                 # Toolkit (Paperclip API, delegation)
│   │
│   ├── finance-lead/                # Settlements, bank rec, CFO brief, AR
│   │   ├── AGENT.md
│   │   ├── SOUL.md
│   │   ├── HEARTBEAT.md
│   │   └── TOOLS.md
│   │
│   └── ops-lead/                    # Ticket digest, lease renewal, occupancy, all Twilio
│       ├── AGENT.md
│       ├── SOUL.md
│       ├── HEARTBEAT.md
│       └── TOOLS.md
│
├── skills/                          # Company-level skill library
│   ├── bank-reconciliation/         # 4-step algorithm + edge-case log + manual-input template
│   ├── settlement-generator/        # Excess Utility calc + utility backtest + manual-input template (validated to the cent)
│   ├── tap-finance-brief/           # CFO Brief + manual-input template
│   ├── ar-chase-list/               # NEW — polite chase drafts with mass-message safety rail
│   ├── ticket-digest/               # PORTED
│   ├── lease-renewal-reminder/      # PORTED
│   └── occupancy-snapshot/          # PORTED
│
└── projects/                        # Empty — add projects once import lands
```

## Where this runs

**Recommended: a single cloud VM** (Ubuntu 24.04 LTS, 2 vCPU / 4 GB / SG region, ~$24/mo).

Don't install on individual laptops — each install is a silo with its own MCP wiring and its own agent state. One shared VM means: one Xero wiring, 24/7 heartbeats, one issue queue, no per-user setup, survives staff turnover.

Full step-by-step in **[`docs/deployment-vm.md`](./docs/deployment-vm.md)** — covers VM provisioning, Node + Claude Code + Paperclip install, systemd service, HTTPS via Caddy or Tailscale, per-agent cwds, Xero Custom Connection setup (the part that's been hardest), and team onboarding.

## Import command

```bash
# Preview first — always
paperclipai company import ./tap-company \
  --target new \
  --new-company-name "TAP Automation" \
  --dry-run

# Read the preview output carefully. Then for real:
paperclipai company import ./tap-company \
  --target new \
  --new-company-name "TAP Automation"
```

## After import — checklist

Imported agents start with scheduled heartbeats DISABLED. Do not enable them until you've:

1. **Set the environment variables** declared in `.paperclip.yaml`:
   - `XERO_ACCESS_TOKEN`, `XERO_TENANT_ID_TAP_COLIVINGS`, `XERO_TENANT_ID_TLKR`
   - `CRM_API_BASE`, `CRM_STAFF_EMAIL`, `CRM_STAFF_PASSWORD` (pending Tech follow-up task #16)
   - `CRM_MEMBER_EMAIL`, `CRM_MEMBER_PASSWORD` (member fallback)
   - `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_SANDBOX_FROM`
   - `SETTLEMENT_OUTPUT_DIR`, `TWILIO_TEST_TO` (optional)

2. **Set per-agent working directories** (Agent → Configuration → cwd):
   - CEO: `~/paperclip-workspace/ceo`
   - Finance Lead: `~/paperclip-workspace/finance-lead`
   - Ops Lead: `~/paperclip-workspace/ops-lead`
   Distinct cwds keep each agent's `.mcp.json` and skill files isolated.

3. **Wire MCP servers** (one-time per host machine):
   - Follow [`docs/mcp-setup.md`](./docs/mcp-setup.md) — sets up Xero MCP, Notion MCP, etc. at the Claude Code level
   - Finance Lead needs: Xero (×2, one per entity) + Notion
   - Ops Lead needs: Notion (Twilio is via REST + env vars, no MCP needed)
   - CEO doesn't need any MCPs

4. **Set per-agent budgets** (Agent → Budget tab):
   - CEO: ~$50/month (mostly delegation)
   - Finance Lead: $200/month (monthly settlements + daily bank rec)
   - Ops Lead: $100/month (Haiku-class; high frequency but cheap)

5. **Manual test heartbeat per agent** (Agent → Run Heartbeat button):
   - Verify auth bootstrap works (CRM login succeeds)
   - Verify it can hit Xero MCP / Twilio
   - Read the Runs tab transcript to confirm nothing's broken

6. **Skim each AGENT.md / SOUL.md / HEARTBEAT.md / TOOLS.md** — these are good starting points but you'll want to tweak the voice, the cadence, and the escalation rules to match your preferences before the agent goes live.

7. **Then enable heartbeats** (Agent → Configuration → Heartbeat enabled).

## Open questions baked into the agents

These are flagged in the agent instructions so the agents themselves surface them rather than guess:

- **Owner-side Excess Utility formula** — backtest 20 May 2026 showed our per-tenant rule doesn't apply to the owner settlement line. Pending Yee Chin clarifying. Finance Lead leaves that row as yellow input.
- **B05 Zhu Yichen on March 18 Jln Jintan** — CRM has her active, Finance's file omits her. Reason TBC.
- **Staff CRM API token** — currently using member-scope + web-scrape. Tech follow-up task #16 to unlock `/com/auth/login/`.

## Cadences

- CEO: hourly heartbeat (mostly idle, just watching)
- Finance Lead: every 6 hours by default; bump to hourly during month-end (1st–5th of each month)
- Ops Lead: every 2 hours for ticket digest; daily 09:00 SGT for lease renewal scan; Monday 08:00 SGT for occupancy snapshot

## What's NOT in this package

- API keys / Twilio credentials / Xero tokens — set via Paperclip UI per-agent after import
- Notion / Slack / Drive connectors — assume those MCPs are available at the adapter level; not configured here
- Tasks / issues — start fresh; let the agents discover real work
