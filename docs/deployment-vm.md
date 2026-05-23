# Deployment — Cloud VM (shared runtime for TAP)

End-to-end runbook for hosting the TAP Automation agents on a single cloud Linux VM. After this, Yee Chin, AR staff, and Faisal access the agents via Paperclip's web UI from their own laptops — no per-user Claude Code or Cowork install required.

## Why this architecture

| Today (Cowork on laptops) | After (shared VM) |
| --- | --- |
| Each user installs Cowork, wires Xero, Twilio, Notion themselves | One install, one wiring on the VM |
| Agent runs only when the user's laptop is on | Heartbeats fire 24/7 |
| State / memory siloed per laptop | One shared agent memory, one issue queue |
| If user leaves, their setup walks out the door | Survives staff turnover |
| Wiring drift across laptops over time | One config, one source of truth |

## 1. Provision the VM

**Recommended provider for TAP (Singapore):** any provider with a SG region for low CRM latency. Concrete options at similar price/spec:

| Provider | Region | Spec | Cost |
| --- | --- | --- | --- |
| **Vultr** | Singapore | 2 vCPU / 4 GB RAM / 80 GB SSD | ~$24/mo |
| **DigitalOcean** | SGP1 | 2 vCPU / 4 GB / 80 GB | ~$24/mo |
| **Linode (Akamai)** | Singapore | 2 vCPU / 4 GB / 80 GB | ~$24/mo |
| **AWS Lightsail** | ap-southeast-1 | 2 vCPU / 4 GB / 80 GB | ~$20/mo |
| **Hetzner** | EU (no SG) | 4 vCPU / 8 GB / 160 GB | ~€8/mo — cheapest but higher CRM latency |

**Spec rationale:** Claude Code is lightweight at rest; each heartbeat spawns a Claude CLI process (~500 MB transient) plus the MCP servers (~100–200 MB each). 4 GB RAM covers concurrent heartbeats from all three agents comfortably. SSD matters for the agent's working directory and any settlement xlsx files generated.

**OS:** Ubuntu 24.04 LTS. Standard, well-supported, Claude Code + Paperclip both run on it.

**Boot setup:**
- Create one OS user `paperclip` who owns everything: `sudo adduser --disabled-password --gecos "" paperclip`
- SSH key access only — no password login
- UFW firewall: allow 22 (SSH), 443 (HTTPS for Paperclip web UI), block everything else
- Set timezone: `sudo timedatectl set-timezone Asia/Singapore` (so cron-like schedules fire at SGT)

## 2. Install Node.js + Claude Code + Paperclip

All commands as the `paperclip` user (`sudo su - paperclip`).

```bash
# Node 22 (required by both pnpm and Claude Code)
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo bash -
sudo apt install -y nodejs build-essential python3 python3-pip jq unzip

# pnpm (Paperclip's preferred package manager per their docs)
sudo npm install -g pnpm

# Claude Code CLI (the runtime that claude_local adapter drives)
sudo npm install -g @anthropic-ai/claude-code
claude --version   # confirm install
claude login       # one-time Claude auth flow — opens a URL to paste into a browser

# Paperclip CLI + server
sudo pnpm add -g @paperclipai/paperclipai
paperclipai --version
```

If `paperclipai` isn't on npm yet at the name above, check the Paperclip Quickstart docs for the canonical install command — the pattern is the same, just the package name might differ.

## 3. Run Paperclip as a systemd service

So it auto-restarts on boot and on crashes.

`/etc/systemd/system/paperclip.service`:

```ini
[Unit]
Description=Paperclip control plane
After=network.target

[Service]
Type=simple
User=paperclip
Group=paperclip
WorkingDirectory=/home/paperclip
Environment="HOME=/home/paperclip"
Environment="NODE_ENV=production"
ExecStart=/usr/local/bin/paperclipai server --port 3000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now paperclip
sudo systemctl status paperclip
```

Confirm with `curl http://localhost:3000/health` (or equivalent — check Paperclip's docs).

## 4. Expose Paperclip's web UI over HTTPS

Two clean options:

**Option A — Caddy (simplest, auto Let's Encrypt):**

```bash
sudo apt install -y caddy
sudo tee /etc/caddy/Caddyfile <<'EOF'
paperclip.theassemblyplace.com {
  reverse_proxy localhost:3000
}
EOF
sudo systemctl reload caddy
```

You'll need an A record for `paperclip.theassemblyplace.com` pointing at the VM's IP. Caddy auto-provisions TLS within ~30 seconds.

**Option B — Tailscale (no public DNS, no certs):**

Install Tailscale on the VM and on each user's laptop. Yee Chin / AR / Faisal access `http://<vm-tailnet-name>:3000` from their machines. No public exposure. Best if you don't want to think about DNS or TLS.

## 5. Set up per-agent working directories

Each agent gets its own cwd so its `.mcp.json` and skill files stay isolated.

```bash
mkdir -p ~/paperclip-workspace/{ceo,finance-lead,ops-lead}
```

You'll set these paths on each agent's Configuration tab after import (`Working directory` field).

## 6. Wire the Xero MCP via Custom Connection

This is the part that's been tripping you up. The Custom Connection path avoids OAuth-at-runtime entirely — fix scopes once, agents use it forever.

### 6a. Create the Custom Connection in Xero (per entity)

In Xero Developer portal at `developer.xero.com/app/manage`:

1. **My Apps → New app**
2. Choose **Custom Connection** (NOT Standard / OAuth 2.0)
3. App name: e.g. `TAP Automation — Co-Livings`
4. Select the Xero org this connection is for (TAP Co-Livings Pte. Ltd., UEN 202300680H)
5. Set scopes — keep **read-only** for safety:
   - `accounting.reports.read` (for P&L)
   - `accounting.transactions.read` (for invoices, receivables, bank rec)
   - `accounting.contacts.read` (for contact / tenant lookups)
   - `accounting.settings.read` (for org metadata)
6. Create → copy the **Client ID** and **Client Secret** that Xero shows once
7. Repeat for TLKR Pte. Ltd. (UEN 201901964D) — a second Custom Connection with the same scopes

Cost: ~$10/month per Custom Connection (per Xero org), billed by Xero. So ~$20/month for the two TAP entities.

### 6b. Install the Xero MCP server on the VM

The official Xero MCP supports Custom Connection auth via env vars:

```bash
# As paperclip user
cd ~/paperclip-workspace/finance-lead

# Install via npx (Claude Code spawns this on demand)
# Test the binary works:
npx -y @xeroapi/xero-mcp-server --help
```

### 6c. Wire it as a project-scoped MCP for the Finance Lead agent

```bash
cd ~/paperclip-workspace/finance-lead

# TAP Co-Livings connection
claude mcp add --transport stdio --scope project xero-tap-colivings \
  -e XERO_CLIENT_ID="<tap-colivings-client-id>" \
  -e XERO_CLIENT_SECRET="<tap-colivings-client-secret>" \
  -- npx -y @xeroapi/xero-mcp-server

# TLKR connection
claude mcp add --transport stdio --scope project xero-tlkr \
  -e XERO_CLIENT_ID="<tlkr-client-id>" \
  -e XERO_CLIENT_SECRET="<tlkr-client-secret>" \
  -- npx -y @xeroapi/xero-mcp-server

# Verify
claude mcp list
# Expect: xero-tap-colivings ✓ Connected, xero-tlkr ✓ Connected
```

Custom Connection auth uses client_credentials grant (machine-to-machine) — no browser, no token rotation, no per-user OAuth. The MCP server exchanges client_id + client_secret for a fresh access token on each connection.

**Don't commit secrets to .mcp.json.** The `-e` flags above bake env vars into the project's `.mcp.json` which IS readable by anyone with shell access to the VM. Better pattern: leave the env vars in `.mcp.json` as placeholders (`${XERO_TAPCO_CLIENT_ID}`) and set the real values in the systemd service env or in `~/.bashrc` for the paperclip user. Most MCP clients resolve `${VAR}` interpolation in `.mcp.json`.

### 6d. Test from Claude Code directly

```bash
cd ~/paperclip-workspace/finance-lead
claude
> /mcp
# Pick xero-tap-colivings, check that tools list. Try: "List my Xero organisations."
# Should return: TAP Co-Livings Pte. Ltd.
```

If `claude mcp list` shows ✓ but the agent can't actually call tools, double-check the Custom Connection scopes — Xero will return 403 silently if the scope you're calling isn't granted.

## 7. Add Notion MCP (also Finance Lead and Ops Lead)

```bash
# Finance Lead
cd ~/paperclip-workspace/finance-lead
claude mcp add --transport http --scope user notion https://mcp.notion.com/sse
claude   # interactive once
> /mcp   # pick notion, complete OAuth in browser

# Ops Lead (same notion server, but project-scoped to ops-lead cwd is also fine)
cd ~/paperclip-workspace/ops-lead
claude mcp add --transport http --scope project notion https://mcp.notion.com/sse
# OAuth carries over if you authorised at user scope above
```

## 8. Import the tap-company package

Transfer the package to the VM:

```bash
# On your laptop
scp -r tap-company paperclip@<vm-ip>:~/

# On the VM (as paperclip)
paperclipai company import ~/tap-company --target new --new-company-name "TAP Automation" --dry-run
# Read the preview carefully.
paperclipai company import ~/tap-company --target new --new-company-name "TAP Automation"
```

After import, in the Paperclip web UI:
- Open each agent → Configuration → set cwd to `/home/paperclip/paperclip-workspace/<agent>`
- Set env vars per `.paperclip.yaml` (Xero is now via MCP, but CRM_STAFF_EMAIL/PASSWORD, TWILIO_*, etc. still need to be set)
- Set per-agent budgets

## 9. Add team members to Paperclip's board

In the Paperclip web UI:
- Settings → Members → Invite
- Add Yee Chin, AR staff, Faisal with the **board** role (so they can approve hires / budgets / risky actions but can't tamper with adapter wiring)
- They log in from their own laptops at `https://paperclip.theassemblyplace.com` (or the Tailscale URL)

## 10. Enable heartbeats one at a time

For each agent: Configuration → Heartbeat enabled → run a manual heartbeat → read the Runs tab transcript → confirm nothing's broken → leave enabled.

Start with **CEO** (smallest blast radius), then **Finance Lead**, then **Ops Lead**.

## Ongoing operations

| Task | Cadence | How |
| --- | --- | --- |
| Re-auth OAuth MCPs (Notion) | When 401s appear | `claude` interactively, run `/mcp`, re-authorise |
| OS updates | Monthly | `sudo apt update && sudo apt upgrade && sudo reboot` (schedule for weekend) |
| Paperclip updates | When you see Changelog notes | `sudo pnpm add -g @paperclipai/paperclipai@latest && sudo systemctl restart paperclip` |
| Claude Code updates | When `claude --version` lags behind | `sudo npm install -g @anthropic-ai/claude-code@latest` |
| Backups | Weekly | `paperclipai company export <id> --out /backups/$(date +%F)` + offsite copy |
| Disk space | Monthly | `du -sh ~/paperclip-workspace/*` — settlement xlsx files build up |

## Cost summary

| Item | Monthly |
| --- | --- |
| VM (4 GB SG) | ~$24 |
| Domain + DNS (optional, if using Caddy) | ~$1 |
| Xero Custom Connection × 2 entities | ~$20 |
| Anthropic API (claude-sonnet-4-6 for Finance Lead + CEO, haiku for Ops Lead — depends on volume) | $30–$100 typical |
| **Total** | **~$75–$145/month** |

Compared to Cowork-on-laptops: similar Anthropic spend but no laptop-Cowork-licence overhead, plus 24/7 uptime and no silo issues.

## What's NOT in this guide (yet)

- **High availability** — single VM is fine for TAP's scale. If you outgrow that, look at active/passive failover with a second VM in a different region.
- **Audit log export** — Paperclip records every heartbeat. For compliance, periodically export and archive.
- **CI/CD for skill updates** — currently you'd `scp` updated skill files. Once the agents are stable, consider a git-backed flow where pushing to a repo triggers Paperclip to re-import skills.

## Troubleshooting

| Symptom | First thing to check |
| --- | --- |
| Agent never wakes | `systemctl status paperclip` — service running? Look at the agent's heartbeat-enabled toggle in UI. |
| MCP tool missing | `claude mcp list` from the agent's cwd, as the paperclip user. Compare to what the heartbeat env has via the run's Invocation card. |
| Xero MCP returns 403 | Custom Connection scope missing or wrong entity. Re-check in Xero Developer portal. |
| Notion MCP returns 401 | OAuth expired. Run `claude` interactively, `/mcp`, re-authorise. |
| Heartbeat times out | Agent's `timeout` in Configuration too low for the task. Bump to 600 sec, or split the work into smaller subtasks. |

## See also

- `./mcp-setup.md` — MCP-specific patterns (already in this package)
- Paperclip docs — [Deploy to a VPS or Fly.io](https://docs.paperclip.ing/#/how-to/deploy-to-vps-or-fly) — canonical reference once their hash routing cooperates
- Paperclip docs — [Installation](https://docs.paperclip.ing/#/guides/getting-started/installation)
- Xero docs — [Custom Connections](https://developer.xero.com/documentation/guides/oauth2/custom-connections/)
