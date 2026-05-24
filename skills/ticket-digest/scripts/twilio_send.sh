#!/usr/bin/env bash
# TAP Lease Renewal — Twilio WhatsApp Sandbox sender
#
# Usage:
#   ./twilio_send.sh "whatsapp:+6591234567" "Hi Jane, your lease at..."
#
# Reads credentials from .twilio_env in the same directory.
# .twilio_env should contain:
#   TWILIO_ACCOUNT_SID=AC...
#   TWILIO_AUTH_TOKEN=...
#   TWILIO_SANDBOX_FROM=whatsapp:+14155238886
#   TWILIO_TEST_TO=whatsapp:+65...
#
# Safety: this script does ONE send per invocation. Never bulk-loop without
# explicit per-message human approval upstream.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.twilio_env"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: $ENV_FILE not found. Save your Twilio credentials there first." >&2
    exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

if [[ -z "${TWILIO_ACCOUNT_SID:-}" || -z "${TWILIO_AUTH_TOKEN:-}" || -z "${TWILIO_SANDBOX_FROM:-}" ]]; then
    echo "ERROR: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, or TWILIO_SANDBOX_FROM not set in $ENV_FILE" >&2
    exit 1
fi

TO="${1:-}"
BODY="${2:-}"

if [[ -z "$TO" || -z "$BODY" ]]; then
    cat <<USAGE >&2
Usage: $0 "<to>" "<message>"
  <to>      Recipient in Twilio WhatsApp format, e.g. whatsapp:+6591234567
  <message> Message body (quote it)

Example:
  $0 "$TWILIO_TEST_TO" "Hello from TAP sandbox test"
USAGE
    exit 1
fi

# Sanity check the To format
if [[ ! "$TO" =~ ^whatsapp:\+[0-9]+$ ]]; then
    echo "ERROR: Recipient must be in format 'whatsapp:+<countrycode><number>' (e.g. whatsapp:+6591234567). Got: $TO" >&2
    exit 1
fi

echo "→ Sending via Twilio Sandbox"
echo "  From:  $TWILIO_SANDBOX_FROM"
echo "  To:    $TO"
echo "  Body:  $BODY"
echo

RESPONSE=$(curl -sS -X POST \
    "https://api.twilio.com/2010-04-01/Accounts/${TWILIO_ACCOUNT_SID}/Messages.json" \
    --data-urlencode "From=${TWILIO_SANDBOX_FROM}" \
    --data-urlencode "To=${TO}" \
    --data-urlencode "Body=${BODY}" \
    -u "${TWILIO_ACCOUNT_SID}:${TWILIO_AUTH_TOKEN}")

# Pretty-print just the useful fields
SID=$(echo "$RESPONSE" | python3 -c "import sys, json; d = json.load(sys.stdin); print(d.get('sid', ''))" 2>/dev/null || echo "")
STATUS=$(echo "$RESPONSE" | python3 -c "import sys, json; d = json.load(sys.stdin); print(d.get('status', ''))" 2>/dev/null || echo "")
ERROR_CODE=$(echo "$RESPONSE" | python3 -c "import sys, json; d = json.load(sys.stdin); print(d.get('code', ''))" 2>/dev/null || echo "")
ERROR_MSG=$(echo "$RESPONSE" | python3 -c "import sys, json; d = json.load(sys.stdin); print(d.get('message', ''))" 2>/dev/null || echo "")

if [[ -n "$SID" ]]; then
    echo "✓ Sent. SID: $SID  Status: $STATUS"
else
    echo "✗ Send failed."
    [[ -n "$ERROR_CODE" ]] && echo "  Code:    $ERROR_CODE"
    [[ -n "$ERROR_MSG" ]] && echo "  Message: $ERROR_MSG"
    echo "  Full response:"
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
    exit 2
fi
