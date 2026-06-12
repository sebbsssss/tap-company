"""Tests for caption_parser — no network calls, no API keys needed."""

import json
from datetime import date
from pathlib import Path

import pytest

from caption_parser import ask_for_missing, missing_fields, parse_caption

FIXTURE_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Caption parsing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "caption, exp_property, exp_utility, exp_date",
    [
        # ISO date, property alias, utility keyword
        ("18JJ elec 2026-06-11", "18 JALAN JINTAN", "electricity", date(2026, 6, 11)),
        ("18jj electricity 2026-06-11", "18 JALAN JINTAN", "electricity", date(2026, 6, 11)),
        # DD/MM date, different property
        ("18Penhas water 11/6", "18 PENHAS", "water", date(2026, 6, 11)),
        # "today" keyword (cannot assert exact date, just that it's not None)
        ("TLKR gas today", "TLKR CAMPUS", "gas", None),
        # DD Mon pattern
        ("51MR elec 11 Jun", "51 MIDDLE ROAD", "electricity", date(2026, 6, 11)),
        # Block-level alias
        ("BlockA water 2026-06-11", "TLKR CAMPUS - BLOCK A", "water", date(2026, 6, 11)),
        # Uppercase mix
        ("18JLN ELEC 2026-06-11", "18 JALAN JINTAN", "electricity", date(2026, 6, 11)),
        # BUG 2 regressions: ordinal date + electric synonym (Sebastien repro 2026-06-12)
        ("MILL@32, 11th June, water", "MILL@32", "water", date(2026, 6, 11)),
        ("MILL@32, today, electric", "MILL@32", "electricity", None),
        ("18JJ electric 11th Jun", "18 JALAN JINTAN", "electricity", date(2026, 6, 11)),
        ("51MR elec 1st June", "51 MIDDLE ROAD", "electricity", date(2026, 6, 1)),
    ],
)
def test_parse_caption_happy(caption, exp_property, exp_utility, exp_date):
    result = parse_caption(caption)
    assert result["property"] == exp_property, f"caption={caption!r}"
    assert result["utility_type"] == exp_utility, f"caption={caption!r}"
    if exp_date is not None:
        assert result["reading_date"] == exp_date, f"caption={caption!r}"
    else:
        assert result["reading_date"] is not None, "today should resolve"


def test_parse_caption_missing_all():
    result = parse_caption("some random text that matches nothing")
    assert result["property"] is None
    assert result["utility_type"] is None
    # date may also be None — that's fine


def test_parse_caption_missing_property():
    result = parse_caption("elec 2026-06-11")
    assert result["property"] is None
    assert result["utility_type"] == "electricity"
    assert result["reading_date"] == date(2026, 6, 11)


def test_missing_fields_all_present():
    parsed = {
        "property": "18 JALAN JINTAN",
        "utility_type": "electricity",
        "reading_date": date(2026, 6, 11),
    }
    assert missing_fields(parsed) == []


def test_missing_fields_partial():
    parsed = {"property": None, "utility_type": "water", "reading_date": date(2026, 6, 11)}
    assert missing_fields(parsed) == ["property"]


def test_ask_for_missing_message():
    msg = ask_for_missing(["property", "utility_type"])
    assert "property" in msg.lower()
    assert "utility" in msg.lower()


# ---------------------------------------------------------------------------
# Fixture smoke
# ---------------------------------------------------------------------------

def test_full_fixture_parseable():
    data = json.loads((FIXTURE_DIR / "zernio_message_received_2026-06-11.json").read_text())
    assert data["event"] == "message.received"
    text = data["message"]["text"]
    parsed = parse_caption(text)
    assert parsed["property"] == "18 JALAN JINTAN"
    assert parsed["utility_type"] == "electricity"
    assert parsed["reading_date"] == date(2026, 6, 11)
    assert missing_fields(parsed) == []


def test_incomplete_fixture_has_missing():
    data = json.loads((FIXTURE_DIR / "zernio_message_incomplete_2026-06-11.json").read_text())
    text = data["message"]["text"]
    parsed = parse_caption(text)
    assert "property" in missing_fields(parsed)
