# MCP setup for TAP Automation agents

Paperclip's `claude_local` adapter inherits Claude Code's MCP client. That means MCP wiring lives at the Claude Code config layer on the **host machine** where the heartbeats run — not in this package or Paperclip itself. This doc lists which MCPs each agent needs and the exact `claude mcp add` commands to set them up.

## How Paperclip + Claude Code + MCP fit together

```
Paperclip control plane  →  Adapter (claude_local)  →  Claude Code runtime  →  MCP JSON-RPC  →  MCP servers
```

The agent never speaks MCP directly — Claude Code does. So:
- Config lives in `~/.claude.json` (user / local scope) or `<agent_cwd>/.mcp.json` (project scope)
- `claude mcp list` (run from the agent's cwd) is your source of truth for what an agent will see
- Removing or replacing an MCP server is a Claude Code action, not a Paperclip action

**Recommendation:** Use **project scope** — each agent has its own working directory (set on the Configuration tab post-import), and a `.mcp.json` lives in that directory. This way, restoring an agent from a fresh machine is just `git pull` of the cwd.

## Per-agent MCP requirements

### Finance Lead

| MCP | What it gives the agent | Scope |
| --- | --- | --- |
| **Xero** (`@anthropic/mcp-xero` or similar) | Read-only access to P&L, AR, contacts, financial position. Needed for: settlement xlsx, CFO brief, bank rec investigation. One Xero org per entity → connect TAP Co-Livings + TLKR Pte Ltd separately. | project |
| **Notion** | Read meeting minutes (canonical source for calculation rules — utility methodology, payment reconciliation training). | project or user |
| **Google Drive** (optional) | Upload finalised settlement xlsx files to `Settlement Reports/<year>/`. If not installed, settlement skill outputs locally and AR staff uploads manually. | project |

### Ops Lead

| MCP | What it gives the agent | Scope |
| --- | --- | --- |
| **WhatsApp / Twilio** | Send digests and tenant-facing messages. If no dedicated MCP, the agent shells out via `curl` using the Twilio REST API — that path already works in the ported `ticket-digest` skill. | project |
| **Google Drive** (optional) | Update the `Property Dashboards/TLKR Campus.xlsx` weekly. | project |

### CEO

The CEO doesn't directly call external services — it orchestrates via the Paperclip API only. No MCPs required.

## Setup commands (run on the host machine, as the OS user that owns the heartbeats)

These assume each agent has its own cwd. Adjust paths to match what you set on the Configuration tab.

### Finance Lead

```bash
# 1. cd into the Finance Lead's working directory
cd ~/paperclip-workspace/finance-lead

# 2. Xero — TAP Co-Livings entity
claude mcp add --transport http --scope project xero-tap-colivings https://mcp.xero.com/sse
# Then complete OAuth once interactively:
claude
> /mcp
# Pick xero-tap-colivings, walk through the OAuth redirect, paste the code back.

# 3. Xero — TLKR entity (separate Xero org → separate MCP connection)
claude mcp add --transport http --scope project xero-tlkr https://mcp.xero.com/sse
# Repeat the OAuth flow for the TLKR Xero org.

# 4. Notion — for meeting minutes
claude mcp add --transport http --scope project notion https://mcp.notion.com/sse
# OAuth once.

# 5. Verify everything loaded
claude mcp list
# Expect: xero-tap-colivings ✓ Connected, xero-tlkr ✓ Connected, notion ✓ Connected
```

### Ops Lead

```bash
cd ~/paperclip-workspace/ops-lead

# Twilio doesn't have an official MCP at time of writing — the ticket-digest skill
# uses the Twilio REST API directly via curl. The Twilio creds come in via env vars
# (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_SANDBOX_FROM) set on the agent's
# Configuration tab. No MCP setup needed unless you add a custom Twilio MCP server.

# Notion (optional — for reading CM-group communication patterns)
claude mcp add --transport http --scope project notion https://mcp.notion.com/sse

claude mcp list
```

### CEO

No MCPs to set up. Just verify the Paperclip API env vars are injected:

```bash
cd ~/paperclip-workspace/ceo
echo $PAPERCLIP_API_URL   # should be set by Paperclip at heartbeat time
echo $PAPERCLIP_API_KEY   # should be set by Paperclip at heartbeat time
```

## Verifying an MCP is wired correctly

The fastest test: assign the agent a one-line task asking it to enumerate its tools.

Create an issue assigned to the agent with body:

> List the MCP tools you have access to. Return a one-line description of each. Do not call any of them — just enumerate.

Watch the run transcript in Paperclip (Agents → <agent> → Runs). The tool list should include the MCPs you just added (namespaced as `mcp__<server>__<tool>`, e.g. `mcp__xero-tap-colivings__get_profit_and_loss`).

If a tool you expect is missing:
1. `claude mcp list` from the agent's cwd — confirms config is loaded
2. `claude mcp get <name>` — shows OAuth status + full transport config
3. If `mcp list` shows it but the agent doesn't call it, the tool description is too vague or the agent's instructions don't mention the capability → add an explicit hint in the agent's `TOOLS.md`

## Per-agent isolation

If you want one MCP server visible to one agent only:
- Use **distinct cwds** per agent (default Paperclip recommendation) and put the MCP in that project's `.mcp.json` — only that agent sees it
- Or use the **local** scope (`--scope local`) and add only on the specific heartbeat host

For TAP Automation, distinct cwds is cleaner: `~/paperclip-workspace/{ceo,finance-lead,ops-lead}` — each with its own `.mcp.json`, each restorable independently.

## Secrets

Never commit OAuth tokens or API keys to a project-scoped `.mcp.json`. Use Paperclip secrets (Configuration tab) for any static API key your MCP server needs, then reference it via env var in the MCP server's `env` block.

## See also

- Paperclip docs — [Add an MCP server to an agent](https://docs.paperclip.ing/#/how-to/add-mcp-server-to-agent/add-an-mcp-server-to-an-agents-toolkit) (canonical reference)
- [MCP server directory](https://github.com/modelcontextprotocol/servers) — official + community servers
- Each agent's `TOOLS.md` — for the operational usage of these MCPs once they're wired
