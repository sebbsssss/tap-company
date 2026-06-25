# Hotel Xero Custom Connection — Setup Guide

This guide sets up a read-only Xero Custom Connection for **TAP Hotels Pte Ltd**
so the IPT runner can pull its financial data.

> **Who must do this:** A Xero admin/owner on the TAP Hotels Pte Ltd organisation.
> If you're unsure who has admin access, check with William or Sebastien.

---

## Step 1 — Create the Custom Connection app

1. Go to [developer.xero.com](https://developer.xero.com) and sign in with the Xero account
   that has **admin access to TAP Hotels Pte Ltd** (not TAP Co-Livings).
2. Click **New App** (top right).
3. Fill in the form:
   - **App name:** `TAP Hotels IPT Runner` (or any descriptive name)
   - **Integration type:** Select **Custom connection**
   - **Company or application URL:** `https://theassemblyplace.com`
4. Click **Create App**.

## Step 2 — Set the scopes

Inside the new app's Settings:

1. Click **Configuration** → **Scopes**.
2. Enable exactly these three scopes:
   - `accounting.transactions.read`
   - `accounting.contacts.read`
   - `accounting.settings.read`
3. Click **Save**.

## Step 3 — Authorise against TAP Hotels Pte Ltd

1. In the app dashboard, click **Try in API Explorer** or **Authorise**.
2. You will be redirected to Xero's org picker.
3. **Select "TAP Hotels Pte Ltd"** — not TAP Co-Livings, not TLKR.
4. Approve the access.

> The connection is now bound to TAP Hotels. A Custom Connection does not expire
> like OAuth tokens — it stays valid until you revoke it.

## Step 4 — Copy the credentials

1. Back in the app dashboard, go to **Configuration**.
2. Note the **Client ID** and **Client Secret**.
   - The Client ID is visible directly.
   - The Client Secret may need to be regenerated if not yet shown — click **Generate Secret**.
3. Copy both values. **Do not paste them in plaintext anywhere** — use the secret-setting
   commands below.

## Step 5 — Set the secrets

### Option A: Fly.io secret (for the ipt-runner Fly app)

```bash
flyctl secrets set XERO_HOTEL_ID="<client_id>" XERO_HOTEL_SECRET="<client_secret>" \
  --app ipt-runner
```

### Option B: Agent environment variable (for Finance Lead agent in Paperclip)

Have the Paperclip admin add these to the Finance Lead agent's env config:
- `XERO_HOTEL_ID` = `<client_id>`
- `XERO_HOTEL_SECRET` = `<client_secret>`

Both can be set simultaneously if both paths are needed.

## Step 6 — Verify the connection

Run the connection test:

```bash
python3 ipt-runner/test_xero_connection.py "$XERO_HOTEL_ID" "$XERO_HOTEL_SECRET"
```

Expected output:
```
connected org: TAP Hotels Pte Ltd
```

If you see a different org name (e.g. "TAP Co-livings Pte. Ltd."), the app was
authorised against the wrong entity. Revoke the connection in developer.xero.com
and repeat from Step 3 with the correct org selected.

## Step 7 — Run the Hotel IPT

```bash
python3 ipt-runner/ipt_agent.py \
  --only-entity "TAP Hotels Pte Ltd" \
  --start 2026-01-01 \
  --end 2026-06-30
```

Output file: `ipt_tap_hotels_pte_ltd_2026-01-01_2026-06-30.xlsx`

---

## Same pattern for other entities

| Entity | Env var pair | Notes |
|--------|-------------|-------|
| TLKR Pte Ltd | `XERO_TLKR_ID` / `XERO_TLKR_SECRET` | Separate Xero org |
| TAP Service Apartments | `XERO_SAPT_ID` / `XERO_SAPT_SECRET` | Separate Xero org |
| TAP Holdings Pte Ltd | `XERO_HOLDINGS_ID` / `XERO_HOLDINGS_SECRET` | Separate Xero org |

Repeat Steps 1–6 for each, selecting the correct org at Step 3.
