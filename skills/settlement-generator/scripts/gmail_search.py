#!/usr/bin/env python3
"""
Gmail search for Finance-emailed actuals (cleaning + servicing).

Finance team emails cleaning and servicing line items to
jarvis.ai@theassemblyplace.com. This module searches that inbox
and parses the dollar amounts for use in the settlement generator.

Convention (per Sebastien, THE-17480):
  - If an email is found → use the parsed amount(s).
  - If no email found → $0 (NOT yellow). Do not leave cells yellow
    when the inbox has been searched and returned nothing.

Required env vars (for jarvis.ai@theassemblyplace.com):
  JARVIS_GOOGLE_CLIENT_ID
  JARVIS_GOOGLE_CLIENT_SECRET
  JARVIS_GOOGLE_REFRESH_TOKEN

  Falls back to GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET /
  GOOGLE_REFRESH_TOKEN if the JARVIS_* vars are not set.

Usage (standalone test):
  python3 gmail_search.py "18 JALAN JINTAN" 2026-05
"""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ServicingItem:
    description: str
    amount: float


@dataclass
class FinanceActuals:
    """Parsed actuals from Finance emails for one property + period."""
    property_name: str
    period: str                          # "2026-05"

    cleaning_total: float = 0.0          # $0 if not found
    servicing_items: list[ServicingItem] = field(default_factory=list)

    emails_searched: int = 0             # how many raw emails we read
    email_subjects: list[str] = field(default_factory=list)

    source_note: str = ""

    @property
    def servicing_total(self) -> float:
        return sum(s.amount for s in self.servicing_items)

    @property
    def found_cleaning(self) -> bool:
        return any("cleaning" in e.lower() for e in self.email_subjects)

    @property
    def found_servicing(self) -> bool:
        return bool(self.servicing_items)


# ---------------------------------------------------------------------------
# OAuth2 token refresh (no third-party libs required)
# ---------------------------------------------------------------------------

def _get_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.load(resp)
    if "access_token" not in result:
        raise RuntimeError(f"Token refresh failed: {result}")
    return result["access_token"]


# ---------------------------------------------------------------------------
# Gmail API thin wrapper (no third-party libs required)
# ---------------------------------------------------------------------------

def _gmail_get(path: str, access_token: str, params: dict | None = None) -> dict:
    url = f"https://gmail.googleapis.com/gmail/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def _gmail_search(
    query: str,
    access_token: str,
    user_id: str = "me",
    max_results: int = 20,
) -> list[dict]:
    """Returns list of message stubs: [{id, threadId}]."""
    result = _gmail_get(
        f"users/{user_id}/messages",
        access_token,
        {"q": query, "maxResults": max_results},
    )
    return result.get("messages", [])


def _gmail_get_message(
    msg_id: str,
    access_token: str,
    user_id: str = "me",
) -> dict:
    return _gmail_get(
        f"users/{user_id}/messages/{msg_id}",
        access_token,
        {"format": "full"},
    )


def _extract_body_text(msg: dict) -> str:
    """Walk the MIME tree and return all text/plain + text/html parts concatenated."""
    parts_text: list[str] = []

    def walk(payload: dict):
        mime = payload.get("mimeType", "")
        if mime in ("text/plain", "text/html"):
            data = (payload.get("body") or {}).get("data", "")
            if data:
                parts_text.append(base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace"))
        for part in payload.get("parts", []):
            walk(part)

    walk(msg.get("payload", {}))
    return "\n".join(parts_text)


def _get_header(msg: dict, name: str) -> str:
    for h in (msg.get("payload") or {}).get("headers", []):
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


# ---------------------------------------------------------------------------
# Dollar-amount parser
# ---------------------------------------------------------------------------

# Matches patterns like "$720", "S$720", "$1,200.00", "SGD 720.00"
_MONEY_RE = re.compile(
    r"(?:S?\$|SGD\s*)(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)",
    re.IGNORECASE,
)

# Keywords that tag a line as a cleaning row
_CLEANING_KEYWORDS = re.compile(r"\bcleaning\b", re.IGNORECASE)

# Keywords that tag a line as a servicing / maintenance row
_SERVICING_KEYWORDS = re.compile(
    r"\b(servic|maintenance|repair|handyman|aircon|pest|plumb)\b",
    re.IGNORECASE,
)


def _parse_money(text: str) -> list[float]:
    return [float(m.replace(",", "")) for m in _MONEY_RE.findall(text)]


def _parse_email_body(body: str) -> dict:
    """Extract cleaning total and servicing items from an email body.

    Strategy:
      1. Split into lines; tag each line with its keywords.
      2. Sum cleaning amounts; collect servicing amounts with descriptions.
      3. If no tagged lines found but the email has a known header block,
         fall back to scanning all labelled rows.

    Returns:
      {
        "cleaning": float | None,      # None = keyword not found in this email
        "servicing": [{desc, amount}]  # empty list = not found
      }
    """
    cleaning_amounts: list[float] = []
    servicing_items: list[ServicingItem] = []

    for line in body.splitlines():
        line_stripped = line.strip()
        if not line_stripped:
            continue
        amounts = _parse_money(line_stripped)
        if not amounts:
            continue

        if _CLEANING_KEYWORDS.search(line_stripped):
            cleaning_amounts.extend(amounts)
        elif _SERVICING_KEYWORDS.search(line_stripped):
            # Use the line as the description (trimmed to 120 chars)
            desc = re.sub(r"\s+", " ", line_stripped)[:120]
            for amt in amounts:
                servicing_items.append(ServicingItem(description=desc, amount=amt))

    return {
        "cleaning": sum(cleaning_amounts) if cleaning_amounts else None,
        "servicing": servicing_items,
    }


# ---------------------------------------------------------------------------
# Property → search term mapping
# ---------------------------------------------------------------------------

_PROPERTY_SEARCH_TERMS: dict[str, list[str]] = {
    "18 JALAN JINTAN": ["jintan", "jln jintan", "jalan jintan"],
    "18 PENHAS": ["penhas"],
    "18 PENHAS ROAD": ["penhas"],
    "51 MIDDLE ROAD": ["middle road", "sophia"],
    "51 MIDDLE RD": ["middle road", "sophia"],
}


def _property_search_terms(property_name: str) -> list[str]:
    upper = property_name.upper()
    for key, terms in _PROPERTY_SEARCH_TERMS.items():
        if upper == key or upper.startswith(key[:6]):
            return terms
    # Generic fallback: use last word of property name
    words = property_name.split()
    return [words[-1].lower()] if words else [property_name.lower()]


def _month_label(period: str) -> str:
    """'2026-05' → 'May 2026'"""
    import datetime
    y, m = map(int, period.split("-"))
    return datetime.date(y, m, 1).strftime("%B %Y")


# ---------------------------------------------------------------------------
# Main search function
# ---------------------------------------------------------------------------

def search_finance_actuals(
    property_name: str,
    period: str,
    credentials: Optional[dict] = None,
    user_id: str = "jarvis.ai@theassemblyplace.com",
    verbose: bool = False,
) -> FinanceActuals:
    """Search jarvis.ai Gmail inbox for Finance emails with cleaning + servicing amounts.

    Args:
        property_name: e.g. "18 JALAN JINTAN"
        period: "YYYY-MM"
        credentials: dict with keys client_id, client_secret, refresh_token.
                     If None, reads from env vars (JARVIS_* or GOOGLE_*).
        user_id: Gmail userId to search. Defaults to jarvis.ai@theassemblyplace.com.
        verbose: print debug info

    Returns:
        FinanceActuals with cleaning_total + servicing_items populated.
        cleaning_total = 0.0 and servicing_items = [] if nothing found.
    """
    result = FinanceActuals(property_name=property_name, period=period)

    # Resolve credentials
    if credentials is None:
        credentials = {
            "client_id": (
                os.environ.get("JARVIS_GOOGLE_CLIENT_ID")
                or os.environ.get("GOOGLE_CLIENT_ID", "")
            ),
            "client_secret": (
                os.environ.get("JARVIS_GOOGLE_CLIENT_SECRET")
                or os.environ.get("GOOGLE_CLIENT_SECRET", "")
            ),
            "refresh_token": (
                os.environ.get("JARVIS_GOOGLE_REFRESH_TOKEN")
                or os.environ.get("GOOGLE_REFRESH_TOKEN", "")
            ),
        }

    if not all(credentials.get(k) for k in ("client_id", "client_secret", "refresh_token")):
        result.source_note = (
            "Gmail search skipped — JARVIS_GOOGLE_REFRESH_TOKEN not set. "
            "Cleaning and servicing default to $0."
        )
        return result

    try:
        access_token = _get_access_token(
            credentials["client_id"],
            credentials["client_secret"],
            credentials["refresh_token"],
        )
    except Exception as exc:
        result.source_note = f"Gmail token refresh failed ({exc}). Defaulting to $0."
        return result

    # Build search query:
    # Look in a ±1 month window around the settlement period for emails
    # mentioning the property and cleaning/servicing keywords.
    import datetime
    y, m = map(int, period.split("-"))
    # Window: 1 month before → 1 month after
    start_dt = datetime.date(y, m, 1) - datetime.timedelta(days=32)
    end_dt = (
        datetime.date(y, m + 1, 1) if m < 12 else datetime.date(y + 1, 1, 1)
    ) + datetime.timedelta(days=32)
    after_str = start_dt.strftime("%Y/%m/%d")
    before_str = end_dt.strftime("%Y/%m/%d")

    prop_terms = _property_search_terms(property_name)
    month_label = _month_label(period)  # e.g. "May 2026"

    queries = []
    for term in prop_terms:
        queries.append(
            f'({term} OR "{month_label}") (cleaning OR servicing OR maintenance) '
            f"after:{after_str} before:{before_str}"
        )

    all_msg_ids: set[str] = set()
    for q in queries:
        if verbose:
            print(f"  [gmail_search] query: {q!r}")
        try:
            msgs = _gmail_search(q, access_token, user_id=user_id)
            for msg in msgs:
                all_msg_ids.add(msg["id"])
        except Exception as exc:
            if verbose:
                print(f"  [gmail_search] search error: {exc}")

    result.emails_searched = len(all_msg_ids)
    if verbose:
        print(f"  [gmail_search] found {len(all_msg_ids)} candidate message(s)")

    cleaning_total = 0.0
    cleaning_found = False
    servicing_all: list[ServicingItem] = []

    for msg_id in all_msg_ids:
        try:
            msg = _gmail_get_message(msg_id, access_token, user_id=user_id)
        except Exception as exc:
            if verbose:
                print(f"  [gmail_search] failed to fetch message {msg_id}: {exc}")
            continue

        subject = _get_header(msg, "subject")
        result.email_subjects.append(subject)
        if verbose:
            print(f"  [gmail_search] reading: {subject!r}")

        body = _extract_body_text(msg)
        parsed = _parse_email_body(body)

        if parsed["cleaning"] is not None:
            cleaning_total += parsed["cleaning"]
            cleaning_found = True

        servicing_all.extend(parsed["servicing"])

    result.cleaning_total = cleaning_total if cleaning_found else 0.0
    result.servicing_items = servicing_all

    notes = []
    notes.append(
        f"Gmail search: {len(all_msg_ids)} email(s) read for {property_name} "
        f"{period} in jarvis.ai@theassemblyplace.com inbox."
    )
    if cleaning_found:
        notes.append(f"Cleaning: ${cleaning_total:,.2f} parsed from email(s).")
    else:
        notes.append("Cleaning: no email found → $0.00.")
    if servicing_all:
        notes.append(
            f"Servicing: {len(servicing_all)} item(s) totalling "
            f"${sum(s.amount for s in servicing_all):,.2f} parsed from email(s)."
        )
    else:
        notes.append("Servicing: no email found → $0.00.")

    result.source_note = " ".join(notes)
    return result


# ---------------------------------------------------------------------------
# CLI (standalone test)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    property_name = sys.argv[1] if len(sys.argv) > 1 else "18 JALAN JINTAN"
    period = sys.argv[2] if len(sys.argv) > 2 else "2026-05"

    print(f"Searching Gmail for {property_name!r} period {period!r}...")
    actuals = search_finance_actuals(property_name, period, verbose=True)
    print()
    print(f"Cleaning total:   ${actuals.cleaning_total:,.2f}")
    print(f"Servicing items:  {len(actuals.servicing_items)}")
    for s in actuals.servicing_items:
        print(f"  - {s.description}: ${s.amount:,.2f}")
    print(f"Servicing total:  ${actuals.servicing_total:,.2f}")
    print(f"Emails searched:  {actuals.emails_searched}")
    print(f"Source note: {actuals.source_note}")
