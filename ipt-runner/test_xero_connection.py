#!/usr/bin/env python3
"""
Verify a Xero Custom Connection credential pair.

Usage:
    python3 test_xero_connection.py <XERO_CLIENT_ID> <XERO_CLIENT_SECRET>

Expected output on success:
    connected org: TAP Hotels Pte Ltd

Exit code 0 = connected to the expected org.
Exit code 1 = auth failed or wrong org (see error message).
"""

import sys
import requests

XERO_TOKEN_URL = "https://identity.xero.com/connect/token"
XERO_CONNECTIONS_URL = "https://api.xero.com/connections"
XERO_ORG_URL = "https://api.xero.com/api.xro/2.0/Organisation"


def get_token(client_id: str, client_secret: str) -> str:
    resp = requests.post(
        XERO_TOKEN_URL,
        data={"grant_type": "client_credentials", "scope": "accounting.settings.read"},
        auth=(client_id, client_secret),
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"ERROR: token request failed {resp.status_code}: {resp.text[:300]}", file=sys.stderr)
        sys.exit(1)
    return resp.json()["access_token"]


def get_org_name(token: str) -> str:
    resp = requests.get(
        XERO_ORG_URL,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"ERROR: org request failed {resp.status_code}: {resp.text[:300]}", file=sys.stderr)
        sys.exit(1)
    orgs = resp.json().get("Organisations", [])
    if not orgs:
        print("ERROR: no organisations returned", file=sys.stderr)
        sys.exit(1)
    return orgs[0].get("Name", "")


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <XERO_CLIENT_ID> <XERO_CLIENT_SECRET>", file=sys.stderr)
        sys.exit(1)

    client_id, client_secret = sys.argv[1], sys.argv[2]
    token = get_token(client_id, client_secret)
    org_name = get_org_name(token)
    print(f"connected org: {org_name}")

    expected = "TAP Hotels Pte Ltd"
    if org_name != expected:
        print(
            f"ERROR: expected '{expected}' but got '{org_name}'. "
            "The Custom Connection was authorised against the wrong Xero org — redo the setup.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
