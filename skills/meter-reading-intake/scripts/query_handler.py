"""WhatsApp query handler — answer free-text meter reading questions.

Supports questions like:
  "what was the water reading for 18JJ last month?"
  "show me electricity readings for TLKR"
  "96 Owen water this month"

Uses Claude to parse query intent, then looks up utility_log.py data.

Access control is enforced by meter_intake.py before this module is called.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import anthropic

from caption_parser import PROPERTY_ALIASES, UTILITY_KEYWORDS
from utility_log import get_today_readings, _workbook_path, _month_key, HEADERS

import openpyxl

SGT = ZoneInfo("Asia/Singapore")
_CLIENT: Optional[anthropic.Anthropic] = None
MODEL = "claude-sonnet-4-6"

# Extend property lookup with street address variants
EXTENDED_PROPERTY_ALIASES = {
    **PROPERTY_ALIASES,
    "96owen": "96 OWEN ROAD",
    "96 owen": "96 OWEN ROAD",
    "owendroad": "96 OWEN ROAD",
    "owen": "96 OWEN ROAD",
}


def _log(level: str, msg: str, **kwargs: object) -> None:
    print(json.dumps({"level": level, "service": "meter-intake", "msg": msg, **kwargs}), file=sys.stderr)


def _client() -> anthropic.Anthropic:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = anthropic.Anthropic()
    return _CLIENT


def _parse_query_intent(text: str) -> dict:
    """Use Claude to extract {property, utility_type, month} from a free-text query."""
    today = datetime.now(tz=SGT)
    prompt = (
        f"Today is {today.strftime('%Y-%m-%d')} (SGT). "
        "A TAP operations staff member sent this WhatsApp message asking about utility meter readings. "
        "Extract the intent as JSON with no markdown fences:\n"
        '{"property": "<property name or null>", "utility_type": "<electricity|water|gas|null>", '
        '"month": "<YYYY-MM or null>", "query_type": "lookup|summary"}\n'
        "Use null for fields not mentioned. month should be the specific month they asked about; "
        "if they said 'last month' compute it relative to today.\n\n"
        f"Message: {text}"
    )
    msg = _client().messages.create(
        model=MODEL,
        max_tokens=128,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"property": None, "utility_type": None, "month": None, "query_type": "lookup"}


def _resolve_property(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    normalized = name.lower().replace(" ", "").replace("-", "")
    for alias, canonical in EXTENDED_PROPERTY_ALIASES.items():
        if alias.replace(" ", "") in normalized or normalized in alias.replace(" ", ""):
            return canonical
    return name.upper()


def _get_readings_for_month(month: str, property_name: Optional[str] = None, utility_type: Optional[str] = None) -> list[dict]:
    """Return all rows from a month's xlsx, optionally filtered."""
    path = _workbook_path(month)
    if not path.exists():
        return []
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(min_row=2, values_only=True):
            if len(row) < len(HEADERS):
                continue
            row_dict = dict(zip(HEADERS, row))
            if property_name and str(row_dict.get("property", "")).lower() != property_name.lower():
                continue
            if utility_type and str(row_dict.get("utility_type", "")).lower() != utility_type.lower():
                continue
            rows.append(row_dict)
    wb.close()
    return rows


def _format_readings_reply(rows: list[dict], property_name: Optional[str], utility_type: Optional[str], month: str) -> str:
    if not rows:
        parts = []
        if property_name:
            parts.append(property_name)
        if utility_type:
            parts.append(utility_type)
        parts.append(month)
        return f"No readings found for {' / '.join(parts)}."

    lines = []
    for r in rows:
        delta = r.get("delta")
        delta_str = f" (+{delta:.1f})" if delta is not None and float(delta) >= 0 else (f" ({delta:.1f})" if delta is not None else "")
        lines.append(
            f"• {r.get('date')} — {r.get('property')} {r.get('utility_type')} "
            f"{r.get('reading')}{delta_str} [by {r.get('reader', '?')}]"
        )
    header = f"Readings"
    if property_name:
        header += f" for {property_name}"
    if utility_type:
        header += f" ({utility_type})"
    header += f" — {month}:"
    return header + "\n" + "\n".join(lines)


def handle_query(text: str) -> str:
    """Parse a free-text query and return a formatted reply string."""
    intent = _parse_query_intent(text)
    _log("info", "query_intent", intent=intent)

    property_name = _resolve_property(intent.get("property"))
    utility_type = intent.get("utility_type")
    month = intent.get("month")

    if not month:
        # Default: last full month
        today = datetime.now(tz=SGT).date()
        first_of_this_month = today.replace(day=1)
        last_month = (first_of_this_month - timedelta(days=1))
        month = _month_key(last_month)

    rows = _get_readings_for_month(month, property_name=property_name, utility_type=utility_type)
    return _format_readings_reply(rows, property_name, utility_type, month)


# ---------------------------------------------------------------------------
# Intent classification: is this a query or a new meter reading?
# ---------------------------------------------------------------------------

QUERY_SIGNALS = [
    "what", "show", "tell me", "how much", "last month", "this month",
    "reading for", "readings for", "meter for", "history", "?",
]


def looks_like_query(text: str, has_attachment: bool) -> bool:
    """Heuristic: text-only messages with question words → likely a query."""
    if has_attachment:
        return False
    text_lower = text.lower()
    return any(sig in text_lower for sig in QUERY_SIGNALS)


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

def _normalize_phone(raw: str) -> str:
    """Digits-only: strip whitespace, drop leading +, remove separators."""
    return raw.strip().lstrip("+").replace(" ", "").replace("-", "")


def is_allowlisted(phone: Optional[str], sender_id: Optional[str] = None) -> bool:
    """Return True if phone or sender_id matches ALLOWLISTED_NUMBERS.

    Normalizes both sides (digits-only) so +65XXXXX, 65XXXXX, and spaced
    variants all compare equal. Checks both senderPhoneNumber (with +) and
    senderId (without +) from the Zernio payload.
    """
    import os
    allowlist_raw = os.environ.get("ALLOWLISTED_NUMBERS", "").strip()
    if not allowlist_raw:
        _log("warn", "access_control_open", reason="ALLOWLISTED_NUMBERS not set")
        return True
    allowlist = {_normalize_phone(n) for n in allowlist_raw.split(",") if n.strip()}
    candidates = [_normalize_phone(v) for v in (phone, sender_id) if v]
    allowed = bool(candidates and any(c in allowlist for c in candidates))
    if not allowed:
        _log("warn", "access_denied", phone_preview=(phone or sender_id or "")[:6] + "***")
    return allowed


def decline_message() -> str:
    return "Sorry, this number is not authorised to use the TAP meter reading service."
