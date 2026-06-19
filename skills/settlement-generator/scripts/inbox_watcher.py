#!/usr/bin/env python3
"""
Always-on inbox watcher / router for jarvis.ai@theassemblyplace.com.
Run by a Paperclip routine every 15 minutes.

Architecture (per Sebastien, THE-17480):
  1. Load last_processed_timestamp from state file.
  2. Fetch all emails newer than that timestamp from jarvis.ai Gmail inbox.
  3. For each email (oldest-first for correct ordering):
     a. Check idempotency: skip if email_id already in store.
     b. Extract body text + attachments.
     c. Call email_classifier.classify_email() -> ClassifiedEmail.
     d. Route:
        - Finance: persist all line_items to actuals_store.
        - Operations: call ops_routing_stub() (logs, does not raise).
        - Neither: skip, log.
  4. Update last_processed_timestamp to now.
  5. Print a summary of what was processed.

Required env vars:
  JARVIS_GOOGLE_CLIENT_ID
  JARVIS_GOOGLE_CLIENT_SECRET
  JARVIS_GOOGLE_REFRESH_TOKEN
  ANTHROPIC_API_KEY
  NOTION_API_KEY          (for Notion store)
  NOTION_ACTUALS_DB_ID    (for Notion store)
  WATCHER_STATE_PATH      (default: /data/watcher_state.json)

Usage:
  python3 inbox_watcher.py [--dry-run] [--since 2026-06-01T00:00:00Z] [--verbose]
"""

from __future__ import annotations

import argparse
import base64
import datetime
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO

sys.path.insert(0, os.path.dirname(__file__))
from email_classifier import classify_email
from actuals_store import ActualsStore, ActualEntry


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_STATE_PATH = "/data/watcher_state.json"
_GMAIL_USER_ID = "jarvis.ai@theassemblyplace.com"


# ---------------------------------------------------------------------------
# State file (last_processed_timestamp)
# ---------------------------------------------------------------------------

def _state_path() -> str:
    return os.environ.get("WATCHER_STATE_PATH", _DEFAULT_STATE_PATH)


def _load_last_timestamp() -> datetime.datetime:
    """Return last_processed_timestamp from state file, or 24 hours ago on first run."""
    path = _state_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            ts_str = data.get("last_processed_timestamp", "")
            if ts_str:
                # Parse ISO 8601 with optional Z suffix
                ts_str_clean = ts_str.rstrip("Z")
                return datetime.datetime.fromisoformat(ts_str_clean).replace(
                    tzinfo=datetime.timezone.utc
                )
        except (json.JSONDecodeError, ValueError, OSError):
            pass
    # Default: 24 hours ago
    return datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)


def _save_last_timestamp(ts: datetime.datetime) -> None:
    """Persist last_processed_timestamp to state file."""
    path = _state_path()
    dir_part = os.path.dirname(path)
    if dir_part:
        os.makedirs(dir_part, exist_ok=True)
    ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"last_processed_timestamp": ts_str}, fh, indent=2)


# ---------------------------------------------------------------------------
# OAuth2 token refresh (mirrors gmail_search.py)
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
# Gmail API thin wrapper (mirrors gmail_search.py)
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
    max_results: int = 100,
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
# Email body + attachment extraction (self-contained copy from gmail_search.py)
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
            shared_strings: list[str] = []
            if "xl/sharedStrings.xml" in zf.namelist():
                root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
                ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                for si in root.findall(".//x:si", ns):
                    t = "".join(e.text or "" for e in si.findall(".//x:t", ns))
                    shared_strings.append(t)

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
) -> tuple[str, list[bytes], list[str]]:
    """Return (body_text, pdf_bytes_list, xlsx_texts_list) from an email and its attachments."""
    text_parts: list[str] = []
    pdf_attachments: list[bytes] = []
    xlsx_texts: list[str] = []

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
                    if len(pdf_attachments) < 3:
                        pdf_attachments.append(raw)
                elif (
                    "spreadsheet" in mime
                    or filename.lower().endswith(".xlsx")
                    or filename.lower().endswith(".xls")
                ):
                    xlsx_text = _extract_xlsx_text(raw)
                    if xlsx_text:
                        xlsx_texts.append(xlsx_text)
                        text_parts.append(f"[Spreadsheet: {filename}]\n{xlsx_text}")
                elif mime.startswith("text/"):
                    text_parts.append(raw.decode("utf-8", errors="replace"))
                elif verbose:
                    print(f"    [inbox_watcher] skipping attachment {filename!r} ({mime})")
            except Exception as exc:
                if verbose:
                    print(f"    [inbox_watcher] attachment fetch failed: {exc}")

        for child in node.get("parts", []):
            walk_parts(child)

    walk_parts(msg.get("payload", {}))
    return "\n\n".join(text_parts), pdf_attachments, xlsx_texts


# ---------------------------------------------------------------------------
# Ops routing stub (v1 — will be replaced)
# ---------------------------------------------------------------------------

def ops_routing_stub(subject: str) -> None:
    """Log that ops routing is not yet wired for this email. Does not raise."""
    print(f"  [ops-routing] not yet wired for email {subject!r}")


# ---------------------------------------------------------------------------
# Gmail credential resolution
# ---------------------------------------------------------------------------

def _resolve_credentials() -> dict:
    return {
        "client_id": os.environ.get("JARVIS_GOOGLE_CLIENT_ID", ""),
        "client_secret": os.environ.get("JARVIS_GOOGLE_CLIENT_SECRET", ""),
        "refresh_token": os.environ.get("JARVIS_GOOGLE_REFRESH_TOKEN", ""),
    }


# ---------------------------------------------------------------------------
# Main watcher logic
# ---------------------------------------------------------------------------

def run_watcher(
    dry_run: bool = False,
    since: datetime.datetime | None = None,
    verbose: bool = False,
) -> None:
    run_start = datetime.datetime.now(datetime.timezone.utc)
    run_start_str = run_start.strftime("%Y-%m-%dT%H:%M:%SZ")
    today_date = run_start.strftime("%Y-%m-%d")

    # 1. Determine the "since" timestamp
    if since is not None:
        last_ts = since
    else:
        last_ts = _load_last_timestamp()

    last_ts_str = last_ts.strftime("%Y-%m-%dT%H:%M:%SZ")

    if verbose:
        print(f"[inbox_watcher] run start: {run_start_str}")
        print(f"[inbox_watcher] fetching emails since: {last_ts_str}")

    # 2. Resolve Gmail credentials
    creds = _resolve_credentials()
    if not all(creds.get(k) for k in ("client_id", "client_secret", "refresh_token")):
        print(
            "[inbox_watcher] ERROR: Missing JARVIS_GOOGLE_CLIENT_ID / "
            "JARVIS_GOOGLE_CLIENT_SECRET / JARVIS_GOOGLE_REFRESH_TOKEN"
        )
        sys.exit(1)

    try:
        access_token = _get_access_token(
            creds["client_id"], creds["client_secret"], creds["refresh_token"]
        )
    except Exception as exc:
        print(f"[inbox_watcher] ERROR: Gmail token refresh failed: {exc}")
        sys.exit(1)

    # Gmail `after:` accepts Unix epoch seconds
    epoch_seconds = int(last_ts.timestamp())
    query = f"after:{epoch_seconds}"

    if verbose:
        print(f"[inbox_watcher] Gmail query: {query!r}")

    try:
        stubs = _gmail_list_messages(query, access_token, user_id=_GMAIL_USER_ID)
    except Exception as exc:
        print(f"[inbox_watcher] ERROR: Gmail list failed: {exc}")
        sys.exit(1)

    # 3. Process each email oldest-first (Gmail returns newest-first by default)
    stubs_oldest_first = list(reversed(stubs))

    store = ActualsStore()

    count_total = len(stubs_oldest_first)
    count_finance = 0
    count_ops = 0
    count_neither = 0
    count_already_processed = 0

    for stub in stubs_oldest_first:
        msg_id = stub["id"]

        # 3a. Idempotency check
        if store.is_email_processed(msg_id):
            count_already_processed += 1
            if verbose:
                print(f"  [inbox_watcher] skip (already processed): {msg_id}")
            continue

        # Fetch full message
        try:
            msg = _gmail_get_message(msg_id, access_token, user_id=_GMAIL_USER_ID)
        except Exception as exc:
            if verbose:
                print(f"  [inbox_watcher] fetch failed for {msg_id}: {exc}")
            count_neither += 1
            continue

        subject = _get_header(msg, "subject")

        # Parse source_email_date from internalDate (milliseconds epoch)
        internal_date_ms = int(msg.get("internalDate", "0") or "0")
        email_dt = datetime.datetime.fromtimestamp(
            internal_date_ms / 1000.0, tz=datetime.timezone.utc
        )
        source_email_date = email_dt.strftime("%Y-%m-%d")

        if verbose:
            print(f"  [inbox_watcher] processing: {subject!r} (id={msg_id}, date={source_email_date})")

        # 3b. Extract body text + attachments
        try:
            body_text, pdf_attachments, xlsx_texts = _collect_email_content(
                msg, access_token, _GMAIL_USER_ID, verbose=verbose
            )
        except Exception as exc:
            if verbose:
                print(f"    [inbox_watcher] content extraction failed: {exc}")
            body_text, pdf_attachments, xlsx_texts = "", [], []

        # 3c. Classify
        try:
            classified = classify_email(
                subject=subject,
                body_text=body_text,
                pdf_attachments=pdf_attachments,
                xlsx_texts=xlsx_texts,
                today_date=today_date,
            )
        except Exception as exc:
            if verbose:
                print(f"    [inbox_watcher] classify_email raised: {exc}")
            count_neither += 1
            continue

        if verbose:
            print(
                f"    -> category={classified.category!r}, "
                f"confidence={classified.confidence:.2f}, "
                f"property={classified.property_name!r}, "
                f"month={classified.month!r}, "
                f"line_items={len(classified.line_items)}"
            )

        # 3d. Route
        if classified.category == "finance":
            count_finance += 1
            if not dry_run:
                processed_at = run_start.strftime("%Y-%m-%dT%H:%M:%SZ")
                property_name = classified.property_name or "UNKNOWN"
                month = classified.month or run_start.strftime("%Y-%m")

                for item in classified.line_items:
                    entry = ActualEntry(
                        property_name=property_name,
                        month=month,
                        line_item_type=item.type,
                        amount=item.amount,
                        description=item.description,
                        source_email_id=msg_id,
                        source_email_subject=subject,
                        source_email_date=source_email_date,
                        confidence=classified.confidence,
                        processed_at=processed_at,
                    )
                    try:
                        store.append(entry)
                        if verbose:
                            print(
                                f"      [store] persisted: {item.type} "
                                f"${item.amount:.2f} — {item.description[:60]}"
                            )
                    except Exception as exc:
                        if verbose:
                            print(f"      [store] append failed: {exc}")
            else:
                if verbose:
                    print(f"    [dry-run] would persist {len(classified.line_items)} line item(s)")

        elif classified.category == "operations":
            count_ops += 1
            ops_routing_stub(subject)

        else:
            count_neither += 1
            if verbose:
                print(f"    -> neither / skipped")

    # 4. Update state (unless --since was an explicit override for testing)
    if not dry_run:
        _save_last_timestamp(run_start)

    # 5. Print summary
    print(f"Watcher run: {run_start_str}")
    print(f"Emails checked: {count_total} new since {last_ts_str}")
    print(f"  Finance (persisted): {count_finance}")
    print(f"  Operations (stubbed): {count_ops}")
    print(f"  Neither / skipped: {count_neither}")
    print(f"  Already processed: {count_already_processed}")
    if dry_run:
        print("  [dry-run mode: no writes to store or state file]")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_iso_datetime(s: str) -> datetime.datetime:
    """Parse an ISO 8601 datetime string (with optional trailing Z) to UTC datetime."""
    cleaned = s.rstrip("Z")
    dt = datetime.datetime.fromisoformat(cleaned)
    return dt.replace(tzinfo=datetime.timezone.utc)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inbox watcher / router for jarvis.ai@theassemblyplace.com"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Classify and log but do not write to store or update state file",
    )
    parser.add_argument(
        "--since",
        metavar="TIMESTAMP",
        default=None,
        help="Override last_processed_timestamp (ISO 8601, e.g. 2026-06-01T00:00:00Z)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-email details",
    )
    args = parser.parse_args()

    since_dt: datetime.datetime | None = None
    if args.since:
        try:
            since_dt = _parse_iso_datetime(args.since)
        except ValueError as exc:
            print(f"[inbox_watcher] ERROR: invalid --since value {args.since!r}: {exc}")
            sys.exit(1)

    run_watcher(
        dry_run=args.dry_run,
        since=since_dt,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
