"""Tests for query_handler — no network calls (mocks Claude + utility_log)."""

from datetime import date
from unittest.mock import patch

import pytest

import query_handler as qh
import utility_log as ulog


@pytest.fixture(autouse=True)
def redirect_log_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("UTILITY_LOG_DIR", str(tmp_path))


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

def test_allowlist_open_when_not_set(monkeypatch):
    monkeypatch.delenv("ALLOWLISTED_NUMBERS", raising=False)
    assert qh.is_allowlisted("+6591234567") is True


def test_allowlist_allows_listed_number(monkeypatch):
    monkeypatch.setenv("ALLOWLISTED_NUMBERS", "+6591234567,+6598765432")
    assert qh.is_allowlisted("+6591234567") is True


def test_allowlist_blocks_unlisted_number(monkeypatch):
    monkeypatch.setenv("ALLOWLISTED_NUMBERS", "+6591234567,+6598765432")
    assert qh.is_allowlisted("+6500000000") is False


def test_allowlist_blocks_none(monkeypatch):
    monkeypatch.setenv("ALLOWLISTED_NUMBERS", "+6591234567")
    assert qh.is_allowlisted(None) is False


def test_decline_message_not_empty():
    msg = qh.decline_message()
    assert len(msg) > 10


# ---------------------------------------------------------------------------
# Query signal detection
# ---------------------------------------------------------------------------

def test_looks_like_query_with_question():
    assert qh.looks_like_query("what was the water reading last month?", has_attachment=False)


def test_looks_like_query_with_show():
    assert qh.looks_like_query("show me electricity readings for 18JJ", has_attachment=False)


def test_not_query_with_attachment():
    assert not qh.looks_like_query("18JJ water today", has_attachment=True)


def test_not_query_plain_caption():
    assert not qh.looks_like_query("18JJ elec 2026-06-11", has_attachment=False)


# ---------------------------------------------------------------------------
# Query result formatting (no Claude calls — mock intent parsing)
# ---------------------------------------------------------------------------

def test_handle_query_no_readings(monkeypatch):
    monkeypatch.setattr(qh, "_parse_query_intent", lambda _: {
        "property": "18 JALAN JINTAN",
        "utility_type": "electricity",
        "month": "2026-06",
        "query_type": "lookup",
    })
    result = qh.handle_query("what was the electricity reading for 18JJ?")
    assert "No readings found" in result


def test_handle_query_with_data(tmp_path, monkeypatch):
    monkeypatch.setenv("UTILITY_LOG_DIR", str(tmp_path))
    monkeypatch.setattr(qh, "_parse_query_intent", lambda _: {
        "property": "18 JALAN JINTAN",
        "utility_type": "electricity",
        "month": "2026-06",
        "query_type": "lookup",
    })
    ulog.append_reading(
        reading_date=date(2026, 6, 11),
        property_name="18 JALAN JINTAN",
        meter_id=None,
        utility_type="electricity",
        current_reading=12345.0,
    )
    result = qh.handle_query("what was the electricity reading for 18JJ this month?")
    assert "18 JALAN JINTAN" in result
    assert "12345" in result


def test_resolve_property_alias():
    assert qh._resolve_property("18JJ") == "18 JALAN JINTAN"
    assert qh._resolve_property("TLKR") == "TLKR CAMPUS"
    assert qh._resolve_property("96 Owen") == "96 OWEN ROAD"
