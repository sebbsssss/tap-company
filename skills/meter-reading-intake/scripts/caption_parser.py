"""Parse WhatsApp captions sent by Helmy for meter reading intake.

Expected caption patterns (case-insensitive, flexible):
  "18JJ elec 2026-06-11"
  "18Penhas water 11/6"
  "TLKR campus gas 11 Jun"
  "51MR electricity today"

Returns a dict with keys: property, utility_type, reading_date.
Missing fields are None — caller should ask for them.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

SGT = ZoneInfo("Asia/Singapore")

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


def parse_caption(caption: str) -> dict[str, object]:
    """Return {property: str|None, utility_type: str|None, reading_date: date|None}."""
    text = caption.lower().strip()
    normalized = re.sub(r"[\s\-_/]", "", text)
    today = datetime.now(tz=SGT).date()

    # --- property ---
    property_name: Optional[str] = None
    for alias, canonical in PROPERTY_ALIASES.items():
        if alias in normalized:
            property_name = canonical
            break

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
    }


def missing_fields(parsed: dict[str, object]) -> list[str]:
    """Return list of field names that are None."""
    return [k for k, v in parsed.items() if v is None]


def ask_for_missing(missing: list[str]) -> str:
    """Compose a polite reply asking for missing caption fields."""
    labels = {
        "property": "property name (e.g. 18JJ, 18Penhas, 51MR, TLKR)",
        "utility_type": "utility type (electricity / water / gas)",
        "reading_date": "date of reading (e.g. 11/6 or 2026-06-11)",
    }
    needed = ", ".join(labels.get(f, f) for f in missing)
    return (
        f"Hi! To log this meter reading I still need: {needed}. "
        "Please reply with the missing info and resend the photo."
    )
