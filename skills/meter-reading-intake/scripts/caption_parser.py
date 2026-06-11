"""Parse WhatsApp captions sent by Helmy for meter reading intake.

Expected caption patterns (case-insensitive, flexible):
  "18JJ elec 2026-06-11"
  "18Penhas water 11/6"
  "TLKR campus gas 11 Jun"
  "51MR electricity today"
  "MILL@32 / 11 Jun / water"

Returns a dict with keys: property, utility_type, reading_date, fuzzy_suggestion.
Missing fields are None — caller should ask for them.
fuzzy_suggestion is non-None when a close-but-not-exact property match was found.
"""

from __future__ import annotations

import difflib
import re
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

SGT = ZoneInfo("Asia/Singapore")

# Alias table — normalized alias key → canonical name
# Keys use _norm() encoding: lowercase alphanumeric only.
PROPERTY_ALIASES: dict[str, str] = {
    "18jj": "18 JALAN JINTAN",
    "18jln": "18 JALAN JINTAN",
    "18jintan": "18 JALAN JINTAN",
    "18jalanjintan": "18 JALAN JINTAN",
    "18p": "18 PENHAS",
    "18penhas": "18 PENHAS",
    "51mr": "51 MIDDLE ROAD",
    "51middle": "51 MIDDLE ROAD",
    "51middleroad": "51 MIDDLE ROAD",
    "tlkr": "TLKR CAMPUS",
    "campus": "TLKR CAMPUS",
    "blocka": "TLKR CAMPUS - BLOCK A",
    "blockb": "TLKR CAMPUS - BLOCK B",
    "mill32": "MILL@32",
    "96owen": "96 OWEN ROAD",
    "96owenroad": "96 OWEN ROAD",
}

UTILITY_KEYWORDS: dict[str, str] = {
    "electricity": "electricity",
    "electrical": "electricity",
    "elec": "electricity",
    "power": "electricity",
    "water": "water",
    "gas": "gas",
}

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _norm(s: str) -> str:
    """Normalize to lowercase alphanumeric only — strips spaces, @, /, -, etc."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _build_property_lookup() -> dict[str, str]:
    """Build normalized → canonical lookup from CRM names + aliases."""
    from property_cache import get_property_names
    lookup: dict[str, str] = {}
    for name in get_property_names():
        lookup[_norm(name)] = name
    for alias, canonical in PROPERTY_ALIASES.items():
        lookup[_norm(alias)] = canonical
    return lookup


def _resolve_property(text: str) -> tuple[Optional[str], Optional[str]]:
    """Try to resolve property name from text.

    Returns (canonical, fuzzy_suggestion):
      - (canonical, None)  — exact match found
      - (None, suggestion) — fuzzy near-miss; suggestion is the closest candidate
      - (None, None)       — no match at all
    """
    lookup = _build_property_lookup()
    normalized_text = _norm(text)
    keys = [k for k in lookup if k]

    # 1. Exact match: full normalized text matches a key
    if normalized_text in lookup:
        return lookup[normalized_text], None

    # 2. Substring match on full text
    for key, canonical in lookup.items():
        if key and (key in normalized_text or normalized_text in key):
            return canonical, None

    # 3. Token-by-token exact + substring match (handles "MILL@32 / water / 11 Jun")
    for raw_token in re.split(r"[^a-z0-9]+", text.lower()):
        tok = _norm(raw_token)
        if not tok:
            continue
        if tok in lookup:
            return lookup[tok], None
        for key, canonical in lookup.items():
            if key and len(key) >= 3 and (key in tok or tok in key):
                return canonical, None

    # 4. Fuzzy match via difflib — try full text then each token
    candidates: list[str] = []
    close = difflib.get_close_matches(normalized_text, keys, n=1, cutoff=0.7)
    if close:
        candidates.append(close[0])
    for raw_token in re.split(r"[^a-z0-9]+", text.lower()):
        tok = _norm(raw_token)
        if len(tok) < 3:
            continue
        close = difflib.get_close_matches(tok, keys, n=1, cutoff=0.7)
        if close:
            candidates.append(close[0])
    if candidates:
        return None, lookup[candidates[0]]

    return None, None


def parse_caption(caption: str) -> dict[str, object]:
    """Return {property, utility_type, reading_date, fuzzy_suggestion}.

    All values may be None. fuzzy_suggestion is set when a near-miss property
    was found but not confirmed — caller should ask 'Did you mean X?'.
    """
    text = caption.lower().strip()
    today = datetime.now(tz=SGT).date()

    # --- property ---
    property_name: Optional[str] = None
    fuzzy_suggestion: Optional[str] = None

    # Try to resolve from the full caption first, then token by token
    canonical, fuzzy = _resolve_property(caption.strip())
    if canonical:
        property_name = canonical
    else:
        fuzzy_suggestion = fuzzy

    # --- utility type ---
    utility_type: Optional[str] = None
    tokens = re.sub(r"[^\w]", " ", text).split()
    for token in tokens:
        if token in UTILITY_KEYWORDS:
            utility_type = UTILITY_KEYWORDS[token]
            break

    # --- date ---
    reading_date: Optional[date] = None

    # ISO: 2026-06-11
    iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", caption)
    if iso_match:
        try:
            reading_date = date.fromisoformat(iso_match.group(1))
        except ValueError:
            pass

    # DD/MM or DD-MM
    if not reading_date:
        dmy = re.search(r"\b(\d{1,2})[/\-](\d{1,2})\b", text)
        if dmy:
            try:
                d, m = int(dmy.group(1)), int(dmy.group(2))
                reading_date = date(today.year, m, d)
            except ValueError:
                pass

    # DD Mon (e.g. "11 Jun")
    if not reading_date:
        mon = re.search(r"\b(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b", text)
        if mon:
            try:
                reading_date = date(today.year, MONTH_MAP[mon.group(2)], int(mon.group(1)))
            except ValueError:
                pass

    # "today"
    if not reading_date and "today" in tokens:
        reading_date = today

    return {
        "property": property_name,
        "utility_type": utility_type,
        "reading_date": reading_date,
        "fuzzy_suggestion": fuzzy_suggestion,
    }


def missing_fields(parsed: dict[str, object]) -> list[str]:
    """Return list of field names that are None."""
    return [k for k, v in parsed.items() if v is None and k != "fuzzy_suggestion"]


def ask_for_missing(missing: list[str]) -> str:
    """Compose a polite reply asking for missing caption fields."""
    labels = {
        "property": "property name (e.g. 18JJ, 18Penhas, 51MR, MILL@32, TLKR)",
        "utility_type": "utility type (electricity / water / gas)",
        "reading_date": "date of reading (e.g. 11/6 or 2026-06-11)",
    }
    needed = ", ".join(labels.get(f, f) for f in missing)
    return (
        f"Hi! To log this meter reading I still need: {needed}. "
        "Please reply with the missing info and resend the photo."
    )
