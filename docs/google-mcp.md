# Google Workspace MCP — Agent wiring

This doc covers which Paperclip agents are connected to the Google Workspace MCP server, what scopes each agent needs, and the one-time setup Sebastien must complete.

## MCP server

Registered in `opencode.json` at repo root:

```json
{
  "mcp": {
    "google": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@presto-ai/google-workspace-mcp@1.0.12"],
      "env": {
        "GOOGLE_CLIENT_ID": "${GOOGLE_CLIENT_ID}",
        "GOOGLE_CLIENT_SECRET": "${GOOGLE_CLIENT_SECRET}",
        "GOOGLE_REFRESH_TOKEN": "${GOOGLE_REFRESH_TOKEN}"
      }
    }
  }
}
```

The three env vars come from the one-time OAuth consent flow described below. Each agent that needs Google access must have all three set in Paperclip > Configuration > Environment variables.

## Agent → scope table

| Agent | Scopes needed | Why |
|-------|---------------|-----|
| Finance Lead | Gmail (send, draft, read), Drive (read) | Send settlement emails to Yee Chin; read Xero exports landlords email in |
| Ops Lead | Gmail (send), Calendar (read/write) | Send digests; schedule technician routes |
| CEO | Gmail (read, send), Calendar (read) | Oversight, leadership comms |
| TenancyReviewAgent | Drive (read) | Read landlord TAs uploaded to `tenancy@assemblyplace.com` Drive folder |

**Not wired to Google (intentional — less scope = less risk):**
BackendDev, FrontendDev, MaintenanceDispatcher, ProjectClaimsTracker, Hermes (WhatsApp-only per 11 May team decision), MeterReadingCalculator, UtilityExplainer, Supplier Invoice Intake.

## Full scope list minted by the refresh token

The `scripts/mint-google-refresh-token.js` script requests all scopes in one consent grant. Individual agents are constrained by their Paperclip instructions to only use the tools relevant to their role — they do not call scopes they are not supposed to use. The single refresh token covers all four agents.

| Scope | Used by |
|-------|---------|
| `gmail.send` | Finance Lead, Ops Lead, CEO |
| `gmail.readonly` | Finance Lead, CEO |
| `gmail.compose` | Finance Lead, CEO |
| `drive.readonly` | Finance Lead, TenancyReviewAgent |
| `calendar` | Ops Lead, CEO |

## One-time setup — for Sebastien

### Prerequisites

1. Google Cloud Console: create an OAuth 2.0 **Desktop app** client (or Web application — either works). Download the `client_secret_*.json`.
2. In the client's **Authorised redirect URIs**, add `http://127.0.0.1:8080/callback` before running the mint script.

### Mint the refresh token

```bash
node scripts/mint-google-refresh-token.js ~/Downloads/client_secret_*.json
```

The script:
1. Starts a local callback server on port 8080.
2. Prints a consent URL — open it and sign in as the **TAP service Google account**.
3. Catches the redirect, exchanges the code for tokens.
4. Prints `GOOGLE_REFRESH_TOKEN` (and reminds you of `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`).

No npm install needed — the script uses only Node.js built-ins.

### Paste env vars into Paperclip

For each agent listed in the table above, go to:

**Paperclip → Agent → Configuration tab → Environment variables** and add (all sealed):

| Variable | Value |
|----------|-------|
| `GOOGLE_CLIENT_ID` | `client_id` field from the client_secret JSON |
| `GOOGLE_CLIENT_SECRET` | `client_secret` field from the client_secret JSON |
| `GOOGLE_REFRESH_TOKEN` | Printed by `mint-google-refresh-token.js` |

### Verify the connection

Ask Finance Lead:

> Draft a Gmail to `sebastien@theassemblyplace.com` with subject "MCP test" and body "Google MCP is live." Do not send — just create the draft.

If the draft appears in your Gmail Drafts folder, the connection works. Delete the draft after verifying.

## Token rotation

The refresh token does not expire unless:
- You explicitly revoke access at https://myaccount.google.com/permissions
- The Google Cloud project's OAuth consent screen is put back to "Testing" mode and the token lapses
- Google detects suspicious activity and revokes it

If agents start failing with `invalid_grant`, re-run the mint script and paste the new `GOOGLE_REFRESH_TOKEN` into each agent.

## See also

- `scripts/mint-google-refresh-token.js` — source of the consent flow script
- `opencode.json` — MCP server registration
- `docs/mcp-setup.md` — full MCP setup guide (Xero, Notion, etc.)
