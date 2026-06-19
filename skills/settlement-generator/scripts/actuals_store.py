"""
Structured store for Finance email actuals extracted from jarvis.ai inbox.

Keyed by (property, month, line_item_type). Append-only.
Primary store: Notion DB (Finance can audit in Notion UI).
Fallback store: JSON file at ACTUALS_STORE_PATH (default: /data/actuals_store.json).

Required env vars (for Notion):
  NOTION_API_KEY        — Integration token
  NOTION_ACTUALS_DB_ID  — Database ID (create the DB manually first using schema below)

Notion DB schema:
  Name (title)              — auto: "PROPERTY MONTH TYPE"
  Property (rich_text)      — property address
  Month (rich_text)         — "2026-06"
  Line Item Type (select)   — cleaning/servicing/stock/deposits/excess_utility/pob/other
  Amount (number)           — SGD
  Description (rich_text)   — detail text
  Source Email ID (rich_text) — Gmail message ID for audit
  Source Email Subject (rich_text)
  Source Email Date (date)  — date email was received
  Confidence (number)       — classifier confidence 0.0-1.0
  Processed At (date)       — when the watcher processed this email

Usage:
  from actuals_store import ActualsStore, ActualEntry
  store = ActualsStore()
  store.append(entry)
  entries = store.query(property_name="18 Jalan Jintan", month="2026-05")
"""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ActualEntry:
    property_name: str
    month: str                   # "2026-06"
    line_item_type: str          # cleaning / servicing / stock / deposits / excess_utility / pob / other
    amount: float
    description: str
    source_email_id: str         # Gmail message ID
    source_email_subject: str
    source_email_date: str       # ISO date "2026-06-19"
    confidence: float
    processed_at: str            # ISO datetime "2026-06-19T14:30:00"


# ---------------------------------------------------------------------------
# Property name fuzzy-matching (mirrors gmail_search._property_matches)
# ---------------------------------------------------------------------------

_STOP_WORDS = re.compile(
    r"\b(road|rd|jalan|jln|street|st|avenue|ave|drive|dr|the|at|of|and)\b", re.I
)


def _normalize_property(name: str) -> str:
    s = name.upper()
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = _STOP_WORDS.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def _property_matches(stored: str, target: str) -> bool:
    """Return True if stored property name plausibly refers to target (≥50% word overlap)."""
    n_stored = _normalize_property(stored)
    n_target = _normalize_property(target)
    if not n_stored or not n_target:
        return False
    words_stored = set(n_stored.split())
    words_target = set(n_target.split())
    sig_stored = {w for w in words_stored if len(w) >= 3}
    sig_target = {w for w in words_target if len(w) >= 3}
    if not sig_target:
        return False
    overlap = sig_stored & sig_target
    return len(overlap) / len(sig_target) >= 0.5


# ---------------------------------------------------------------------------
# Notion REST helpers (stdlib urllib only)
# ---------------------------------------------------------------------------

_NOTION_API_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


def _notion_request(method: str, path: str, api_key: str, body: dict | None = None) -> dict:
    url = f"{_NOTION_API_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def _rich_text(value: str) -> list[dict]:
    return [{"type": "text", "text": {"content": value[:2000]}}]


def _notion_create_page(db_id: str, api_key: str, entry: ActualEntry) -> dict:
    name = f"{entry.property_name} {entry.month} {entry.line_item_type}".upper()
    properties: dict = {
        "Name": {"title": _rich_text(name)},
        "Property": {"rich_text": _rich_text(entry.property_name)},
        "Month": {"rich_text": _rich_text(entry.month)},
        "Line Item Type": {"select": {"name": entry.line_item_type}},
        "Amount": {"number": entry.amount},
        "Description": {"rich_text": _rich_text(entry.description)},
        "Source Email ID": {"rich_text": _rich_text(entry.source_email_id)},
        "Source Email Subject": {"rich_text": _rich_text(entry.source_email_subject)},
        "Source Email Date": {"date": {"start": entry.source_email_date}},
        "Confidence": {"number": entry.confidence},
        "Processed At": {"date": {"start": entry.processed_at}},
    }
    return _notion_request(
        "POST",
        "/pages",
        api_key,
        {"parent": {"database_id": db_id}, "properties": properties},
    )


def _notion_query(db_id: str, api_key: str, filter_body: dict) -> list[dict]:
    """Query a Notion DB with a single filter; returns all result pages."""
    results: list[dict] = []
    start_cursor: str | None = None
    while True:
        body: dict = {"filter": filter_body, "page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor
        resp = _notion_request("POST", f"/databases/{db_id}/query", api_key, body)
        results.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        start_cursor = resp.get("next_cursor")
    return results


def _notion_page_to_entry(page: dict) -> ActualEntry | None:
    """Convert a raw Notion page dict back to an ActualEntry. Returns None on error."""
    try:
        props = page["properties"]

        def rich(key: str) -> str:
            parts = props.get(key, {}).get("rich_text", [])
            return "".join(p.get("plain_text", "") for p in parts)

        def date_start(key: str) -> str:
            d = props.get(key, {}).get("date") or {}
            return d.get("start", "")

        return ActualEntry(
            property_name=rich("Property"),
            month=rich("Month"),
            line_item_type=(props.get("Line Item Type", {}).get("select") or {}).get("name", "other"),
            amount=props.get("Amount", {}).get("number") or 0.0,
            description=rich("Description"),
            source_email_id=rich("Source Email ID"),
            source_email_subject=rich("Source Email Subject"),
            source_email_date=date_start("Source Email Date"),
            confidence=props.get("Confidence", {}).get("number") or 0.0,
            processed_at=date_start("Processed At"),
        )
    except (KeyError, TypeError):
        return None


# ---------------------------------------------------------------------------
# JSON fallback helpers (append-only, fcntl-locked)
# ---------------------------------------------------------------------------

_DEFAULT_JSON_PATH = "/data/actuals_store.json"


def _json_path() -> str:
    return os.environ.get("ACTUALS_STORE_PATH", _DEFAULT_JSON_PATH)


def _json_load(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _json_append(path: str, entry: ActualEntry) -> None:
    """Append entry to the JSON file with fcntl locking."""
    import fcntl

    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "a+", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            fh.seek(0)
            content = fh.read().strip()
            records: list[dict] = json.loads(content) if content else []
            records.append(asdict(entry))
            fh.seek(0)
            fh.truncate()
            json.dump(records, fh, indent=2, ensure_ascii=False)
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _json_read_all(path: str) -> list[dict]:
    """Read all records with shared lock."""
    if not os.path.exists(path):
        return []
    import fcntl

    with open(path, "r", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_SH)
        try:
            content = fh.read().strip()
            return json.loads(content) if content else []
        except (json.JSONDecodeError, OSError):
            return []
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


# ---------------------------------------------------------------------------
# ActualsStore
# ---------------------------------------------------------------------------

class ActualsStore:
    """Append-only store for Finance email actuals.

    Tries Notion first; falls back to a local JSON file if Notion env vars
    are not set or if a Notion call fails.
    """

    def __init__(self) -> None:
        self._notion_key: str = os.environ.get("NOTION_API_KEY", "")
        self._notion_db_id: str = os.environ.get("NOTION_ACTUALS_DB_ID", "")
        self._use_notion: bool = bool(self._notion_key and self._notion_db_id)
        self._json_path: str = _json_path()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append(self, entry: ActualEntry) -> None:
        """Store a new ActualEntry. Idempotency is NOT enforced here — callers
        should call is_email_processed() before appending to avoid duplicates."""
        if self._use_notion:
            try:
                _notion_create_page(self._notion_db_id, self._notion_key, entry)
                return
            except Exception:
                pass  # fall through to JSON fallback
        _json_append(self._json_path, entry)

    def query(self, property_name: str, month: str) -> list[ActualEntry]:
        """Return all ActualEntry records for the given property + month.

        Property matching is fuzzy (≥50% significant word overlap).
        """
        if self._use_notion:
            try:
                return self._notion_query_by_month(property_name, month)
            except Exception:
                pass  # fall through to JSON fallback
        return self._json_query(property_name, month)

    def is_email_processed(self, email_id: str) -> bool:
        """Return True if an entry with this Gmail message ID already exists (idempotency)."""
        if self._use_notion:
            try:
                return self._notion_email_processed(email_id)
            except Exception:
                pass  # fall through to JSON fallback
        return self._json_email_processed(email_id)

    # ------------------------------------------------------------------
    # Notion internals
    # ------------------------------------------------------------------

    def _notion_query_by_month(self, property_name: str, month: str) -> list[ActualEntry]:
        pages = _notion_query(
            self._notion_db_id,
            self._notion_key,
            {"property": "Month", "rich_text": {"equals": month}},
        )
        entries: list[ActualEntry] = []
        for page in pages:
            entry = _notion_page_to_entry(page)
            if entry and _property_matches(entry.property_name, property_name):
                entries.append(entry)
        return entries

    def _notion_email_processed(self, email_id: str) -> bool:
        pages = _notion_query(
            self._notion_db_id,
            self._notion_key,
            {"property": "Source Email ID", "rich_text": {"equals": email_id}},
        )
        return len(pages) > 0

    # ------------------------------------------------------------------
    # JSON fallback internals
    # ------------------------------------------------------------------

    def _json_query(self, property_name: str, month: str) -> list[ActualEntry]:
        records = _json_read_all(self._json_path)
        entries: list[ActualEntry] = []
        for rec in records:
            if rec.get("month") != month:
                continue
            if not _property_matches(rec.get("property_name", ""), property_name):
                continue
            try:
                entries.append(ActualEntry(**rec))
            except TypeError:
                continue
        return entries

    def _json_email_processed(self, email_id: str) -> bool:
        records = _json_read_all(self._json_path)
        return any(r.get("source_email_id") == email_id for r in records)
