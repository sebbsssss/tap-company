"""Tests for daily_digest — no network calls, no API keys needed."""

from datetime import date

import pytest

import utility_log as ulog
from daily_digest import CAMPUS_PROPERTIES, EXPECTED_ROUTE, build_digest


@pytest.fixture(autouse=True)
def redirect_log_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("UTILITY_LOG_DIR", str(tmp_path))


def test_build_digest_no_readings():
    # 2026-06-11 is a Thursday (off-campus day) with no readings
    text = build_digest(date(2026, 6, 11))
    assert "No readings logged today" in text
    assert "MISS" in text or "off-campus" in text.lower()


def test_build_digest_campus_day_covered(tmp_path):
    # 2026-06-10 is a Wednesday (campus day)
    ulog.append_reading(
        reading_date=date(2026, 6, 10),
        property_name="TLKR CAMPUS",
        meter_id=None,
        utility_type="electricity",
        current_reading=5000.0,
    )
    text = build_digest(date(2026, 6, 10))
    assert "TLKR CAMPUS" in text
    assert "MISS" not in text


def test_build_digest_campus_day_missed(tmp_path):
    # Wednesday with only off-campus reading — should flag a miss
    ulog.append_reading(
        reading_date=date(2026, 6, 10),
        property_name="18 JALAN JINTAN",
        meter_id=None,
        utility_type="water",
        current_reading=100.0,
    )
    text = build_digest(date(2026, 6, 10))
    assert "MISS" in text


def test_build_digest_saturday_no_route():
    # 2026-06-13 is a Saturday — no route
    text = build_digest(date(2026, 6, 13))
    assert "No scheduled route" in text


def test_expected_route_values():
    # Verify the route schedule is defined correctly
    assert EXPECTED_ROUTE[0] == "campus"   # Monday
    assert EXPECTED_ROUTE[2] == "campus"   # Wednesday
    assert EXPECTED_ROUTE[1] == "off-campus"
    assert EXPECTED_ROUTE[3] == "off-campus"
    assert EXPECTED_ROUTE[4] is None
