#!/usr/bin/env python3
"""
Gmail search for Finance-emailed actuals (cleaning + servicing).

LLM-inference approach (Sebastien design amendment, THE-17480):
  - Pull a broad candidate set: emails received within
    [settlement month start - 7 days, settlement month end + 14 days].
  - For each candidate, use Claude Haiku to infer:
      (a) Is this a settlement-relevant email?
      (b) Which property does it refer to?
      (c) What's the cleaning $?
      (d) What servicing items + $?
  - Aggregate across multiple emails per property/month.
  - If no relevant lines found -> $0 (NOT yellow).

Robust to: arbitrary subjects, multiple senders, multiple emails per property,
PDF/xlsx attachments, forwarded threads, and varied phrasing.

Required env vars (for jarvis.ai@theassemblyplace.com):
  JARVIS_GOOGLE_CLIENT_ID
  JARVIS_GOOGLE_CLIENT_SECRET
  JARVIS_GOOGLE_REFRESH_TOKEN
  ANTHROPIC_API_KEY

  Falls back to GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN
  if the JARVIS_* vars are not set.

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
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
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

    emails_searched: int = 0             # raw candidate emails pulled
    emails_matched: int = 0              # emails matched to target property
    email_subjects: list[str] = field(default_factory=list)

    source_note: str = ""

    @property
    def servicing_total(self) -> float:
        return sum(s.amount for s in self.servicing_items)


# ---------------------------------------------------------------------------
# OAuth2 token refresh
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
# Gmail API thin wrapper
# ---------------------------------------------------------------------------

def _gmail_get(path: str, access_token: str, params: dict | None = None) -> dict:
    url = f"https://gmail.googleapis.com/gmail/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def _gmail_list_messages(
    query: str,
    access_token: str,
    user_id: str = "me",
    max_results: int = 50,
) -> list[dict]:
    """Returns list of message stubs: [{id, threadId}]."""
    result = _gmail_get(
        f"users/{user_id}/messages",
        access_token,
        {"q": query, "maxResults": max_results},
    )
    return result.get("messages", [])


def _gmail_get_message(msg_id: str, access_token: str, user_id: str = "me") -> dict:
    return _gmail_get(
        f"users/{user_id}/messages/{msg_id}",
        access_token,
        {"format": "full"},
    )


def _gmail_get_attachment(
    msg_id: str,
    attachment_id: str,
    access_token: str,
    user_id: str = "me",
) -> bytes:
    result = _gmail_get(
        f"users/{user_id}/messages/{msg_id}/attachments/{attachment_id}",
        access_token,
    )
    data = result.get("data", "")
    return base64.urlsafe_b64decode(data + "==")


def _get_header(msg: dict, name: str) -> str:
    for h in (msg.get("payload") or {}).get("headers", []):
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


# ---------------------------------------------------------------------------
# Email body + attachment extraction
# ---------------------------------------------------------------------------

def _extract_body_text(payload: dict) -> str:
    """Return all text/plain and text/html parts concatenated."""
    parts: list[str] = []

    def walk(node: dict) -> None:
        mime = node.get("mimeType", "")
        if mime in ("text/plain", "text/html"):
            data = (node.get("body") or {}).get("data", "")
            if data:
                parts.append(
                    base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
                )
        for child in node.get("parts", []):
            walk(child)

    walk(payload)
    return "\n".join(parts)


def _extract_xlsx_text(raw_bytes: bytes) -> str:
    """Extract cell values from an xlsx file using only stdlib (zipfile + xml)."""
    try:
        with zipfile.ZipFile(BytesIO(raw_bytes)) as zf:
            # Load shared strings
            shared_strings: list[str] = []
            if "xl/sharedStrings.xml" in zf.namelist():
                root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
                ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                for si in root.findall(".//x:si", ns):
                    t = "".join(e.text or "" for e in si.findall(".//x:t", ns))
                    shared_strings.append(t)

            # Extract all sheets
            rows: list[str] = []
            for name in zf.namelist():
                if re.match(r"xl/worksheets/sheet\d+\.xml", name):
                    root = ET.fromstring(zf.read(name))
                    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                    for row in root.findall(".//x:row", ns):
                        cells: list[str] = []
                        for c in row.findall("x:c", ns):
                            t_attr = c.get("t", "")
                            v_el = c.find("x:v", ns)
                            if v_el is None or v_el.text is None:
                                continue
                            if t_attr == "s":
                                idx = int(v_el.text)
                                cells.append(shared_strings[idx] if idx < len(shared_strings) else "")
                            else:
                                cells.append(v_el.text)
                        if cells:
                            rows.append("\t".join(cells))
            return "\n".join(rows)
    except Exception:
        return ""


def _collect_email_content(
    msg: dict,
    access_token: str,
    user_id: str,
    verbose: bool = False,
) -> tuple[str, list[bytes]]:
    """Return (text_content, pdf_bytes_list) from an email and its attachments."""
    text_parts: list[str] = []
    pdf_attachments: list[bytes] = []

    body_text = _extract_body_text(msg.get("payload", {}))
    if body_text:
        text_parts.append(body_text)

    def walk_parts(node: dict) -> None:
        mime = node.get("mimeType", "")
        filename = node.get("filename", "") or ""
        body = node.get("body", {}) or {}
        att_id = body.get("attachmentId")

        if att_id:
            try:
                raw = _gmail_get_attachment(msg["id"], att_id, access_token, user_id)
                if mime == "application/pdf" or filename.lower().endswith(".pdf"):
                    pdf_attachments.append(raw)
                elif (
                    "spreadsheet" in mime
                    or filename.lower().endswith(".xlsx")
                    or filename.lower().endswith(".xls")
                ):
                    xlsx_text = _extract_xlsx_text(raw)
                    if xlsx_text:
                        text_parts.append(f"[Spreadsheet: {filename}]\n{xlsx_text}")
                elif mime.startswith("text/"):
                    text_parts.append(raw.decode("utf-8", errors="replace"))
                elif verbose:
                    print(f"    [gmail_search] skipping attachment {filename!r} ({mime})")
            except Exception as exc:
                if verbose:
                    print(f"    [gmail_search] attachment fetch failed: {exc}")

        for child in node.get("parts", []):
            walk_parts(child)

    walk_parts(msg.get("payload", {}))
    return "\n\n".join(text_parts), pdf_attachments


# ---------------------------------------------------------------------------
# Claude Haiku inference
# ---------------------------------------------------------------------------

_INFERENCE_PROMPT_TEMPLATE = """\
You are a property management settlement analyzer for The Assembly Place (Singapore co-living operator).

Settlement period: {period}

An email has been sent to jarvis.ai@theassemblyplace.com. Read the content below and determine:
1. Is this email settlement-relevant? (i.e. does it contain financial charges for a specific property — cleaning, servicing, maintenance, repairs, aircon, pest control, etc.)
2. Which property does it refer to? (Extract the full address as written in the email.)
3. What is the total cleaning charge (SGD)?
4. What are the individual servicing / maintenance items (description + amount each)?

Email subject: {subject}
Email content:
{content}

Return ONLY a JSON object with EXACTLY this structure (no extra text):
{{
  "is_relevant": true or false,
  "property_name": "full address as written in email, or null",
  "cleaning": 123.00 or null,
  "servicing_items": [
    {{"description": "Aircon servicing", "amount": 180.00}}
  ]
}}

Rules:
- "cleaning" covers: cleaning charge, cleaner fee, house cleaning, housekeeping, spring cleaning.
- "servicing_items" covers: aircon service, pest control, plumbing, electrical, repairs, handyman, maintenance.
- All amounts are in SGD. If unlabelled, assume SGD.
- If the email is a general enquiry, marketing, reservation, or unrelated finance matter, set is_relevant to false.
- If cleaning is not mentioned, set cleaning to null (not 0).
- If no servicing items, set servicing_items to [].
"""


def _run_haiku_inference(
    subject: str,
    text_content: str,
    pdf_attachments: list[bytes],
    period: str,
) -> dict:
    """Call Claude Haiku to extract settlement actuals from email content.

    Returns:
    {
        "is_relevant": bool,
        "property_name": str | None,
        "cleaning": float | None,
        "servicing_items": [{"description": str, "amount": float}]
    }
    """
    from anthropic import Anthropic

    client = Anthropic()

    # Truncate text content to keep tokens manageable
    truncated = text_content[:6000]

    prompt = _INFERENCE_PROMPT_TEMPLATE.format(
        period=period,
        subject=subject,
        content=truncated,
    )

    # Build message content blocks: text prompt + optional PDF documents
    content_blocks: list[dict] = []
    for pdf_bytes in pdf_attachments[:3]:  # max 3 PDFs per email
        try:
            content_blocks.append({
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": base64.standard_b64encode(pdf_bytes).decode("ascii"),
                },
            })
        except Exception:
            pass

    content_blocks.append({"type": "text", "text": prompt})

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": content_blocks}],
        )
        raw = response.content[0].text.strip()
        # Pull out the JSON object (robust to minor preamble)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception:
        pass

    return {"is_relevant": False, "property_name": None, "cleaning": None, "servicing_items": []}


# ---------------------------------------------------------------------------
# Property name matching
# ---------------------------------------------------------------------------

_STOP_WORDS = re.compile(r"\b(road|rd|jalan|jln|street|st|avenue|ave|drive|dr|the|at|of|and)\b", re.I)


def _normalize_property(name: str) -> str:
    """Normalize a property name for fuzzy matching."""
    s = name.upper()
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = _STOP_WORDS.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def _property_matches(inferred: str | None, target: str) -> bool:
    """Return True if the LLM-inferred property name plausibly refers to the target."""
    if not inferred:
        return False
    n_inf = _normalize_property(inferred)
    n_tgt = _normalize_property(target)
    if not n_inf or not n_tgt:
        return False
    # Check for significant word overlap
    words_inf = set(n_inf.split())
    words_tgt = set(n_tgt.split())
    # Remove short/numeric tokens that add noise
    sig_inf = {w for w in words_inf if len(w) >= 3}
    sig_tgt = {w for w in words_tgt if len(w) >= 3}
    if not sig_tgt:
        return False
    overlap = sig_inf & sig_tgt
    return len(overlap) / len(sig_tgt) >= 0.5


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

    Uses LLM inference (Claude Haiku) to identify relevant emails and extract amounts.
    No hardcoded subject/sender patterns — robust to arbitrary Finance email formats.

    Args:
        property_name: e.g. "18 JALAN JINTAN"
        period: "YYYY-MM"
        credentials: dict with keys client_id, client_secret, refresh_token.
                     If None, reads from env vars (JARVIS_* or GOOGLE_*).
        user_id: Gmail userId to search.
        verbose: print debug info.

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

    # Broad date-range query: no property/keyword filtering.
    # Window: [month start - 7 days, month end + 14 days]
    import datetime
    y, m = map(int, period.split("-"))
    month_start = datetime.date(y, m, 1)
    # Last day of the month
    if m == 12:
        month_end = datetime.date(y + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        month_end = datetime.date(y, m + 1, 1) - datetime.timedelta(days=1)

    after_dt = month_start - datetime.timedelta(days=7)
    before_dt = month_end + datetime.timedelta(days=14)
    query = f"after:{after_dt.strftime('%Y/%m/%d')} before:{before_dt.strftime('%Y/%m/%d')}"

    if verbose:
        print(f"  [gmail_search] broad query: {query!r}")

    try:
        stubs = _gmail_list_messages(query, access_token, user_id=user_id, max_results=50)
    except Exception as exc:
        result.source_note = f"Gmail search failed ({exc}). Defaulting to $0."
        return result

    result.emails_searched = len(stubs)
    if verbose:
        print(f"  [gmail_search] {len(stubs)} candidate email(s) in window")

    cleaning_total = 0.0
    cleaning_found = False
    servicing_all: list[ServicingItem] = []
    matched_subjects: list[str] = []

    for stub in stubs:
        msg_id = stub["id"]
        try:
            msg = _gmail_get_message(msg_id, access_token, user_id=user_id)
        except Exception as exc:
            if verbose:
                print(f"    [gmail_search] fetch failed for {msg_id}: {exc}")
            continue

        subject = _get_header(msg, "subject")
        if verbose:
            print(f"  [gmail_search] inferring: {subject!r}")

        text_content, pdf_attachments = _collect_email_content(
            msg, access_token, user_id, verbose=verbose
        )

        inferred = _run_haiku_inference(subject, text_content, pdf_attachments, period)

        if verbose:
            print(f"    -> is_relevant={inferred.get('is_relevant')}, "
                  f"property={inferred.get('property_name')!r}, "
                  f"cleaning={inferred.get('cleaning')}, "
                  f"servicing={inferred.get('servicing_items')}")

        if not inferred.get("is_relevant"):
            continue

        if not _property_matches(inferred.get("property_name"), property_name):
            if verbose:
                print(f"    -> property mismatch, skipping")
            continue

        result.emails_matched += 1
        matched_subjects.append(subject)

        if inferred.get("cleaning") is not None:
            cleaning_total += float(inferred["cleaning"])
            cleaning_found = True

        for item in inferred.get("servicing_items") or []:
            try:
                servicing_all.append(ServicingItem(
                    description=str(item["description"])[:120],
                    amount=float(item["amount"]),
                ))
            except (KeyError, ValueError, TypeError):
                pass

    result.email_subjects = matched_subjects
    result.cleaning_total = cleaning_total if cleaning_found else 0.0
    result.servicing_items = servicing_all

    notes = [
        f"Gmail LLM search: {result.emails_searched} email(s) scanned, "
        f"{result.emails_matched} matched {property_name} {period}."
    ]
    if cleaning_found:
        notes.append(f"Cleaning: ${cleaning_total:,.2f} from email(s).")
    else:
        notes.append("Cleaning: not found in inbox → $0.00.")
    if servicing_all:
        notes.append(
            f"Servicing: {len(servicing_all)} item(s) totalling "
            f"${sum(s.amount for s in servicing_all):,.2f}."
        )
    else:
        notes.append("Servicing: not found in inbox → $0.00.")

    result.source_note = " ".join(notes)
    return result


# ---------------------------------------------------------------------------
# CLI (standalone test)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    property_name = sys.argv[1] if len(sys.argv) > 1 else "18 JALAN JINTAN"
    period = sys.argv[2] if len(sys.argv) > 2 else "2026-05"

    print(f"Searching Gmail (LLM inference) for {property_name!r} period {period!r}...")
    actuals = search_finance_actuals(property_name, period, verbose=True)
    print()
    print(f"Emails scanned:   {actuals.emails_searched}")
    print(f"Emails matched:   {actuals.emails_matched}")
    print(f"Cleaning total:   ${actuals.cleaning_total:,.2f}")
    print(f"Servicing items:  {len(actuals.servicing_items)}")
    for s in actuals.servicing_items:
        print(f"  - {s.description}: ${s.amount:,.2f}")
    print(f"Servicing total:  ${actuals.servicing_total:,.2f}")
    print(f"Source note: {actuals.source_note}")
