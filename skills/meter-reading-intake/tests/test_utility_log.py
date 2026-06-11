"""Tests for utility_log — no network calls, no API keys needed.

Uses tmp_path to redirect LOG_DIR so tests don't touch /data/.
"""

from datetime import date

import pytest

import utility_log as ulog


@pytest.fixture(autouse=True)
def redirect_log_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("UTILITY_LOG_DIR", str(tmp_path))
    # Force module to re-read env on next call
    yield


def test_append_first_reading_no_delta(tmp_path):
    row = ulog.append_reading(
        reading_date=date(2026, 6, 11),
        property_name="18 JALAN JINTAN",
        meter_id="M001",
        utility_type="electricity",
        current_reading=12345.0,
    )
    assert row["reading"] == 12345.0
    assert row["delta"] is None
    assert row["prev_reading"] is None
    assert row["days_elapsed"] is None


def test_append_second_reading_computes_delta(tmp_path):
    ulog.append_reading(
        reading_date=date(2026, 6, 11),
        property_name="18 JALAN JINTAN",
        meter_id="M001",
        utility_type="electricity",
        current_reading=12345.0,
    )
    row2 = ulog.append_reading(
        reading_date=date(2026, 6, 13),
        property_name="18 JALAN JINTAN",
        meter_id="M001",
        utility_type="electricity",
        current_reading=12389.0,
    )
    assert row2["delta"] == pytest.approx(44.0)
    assert row2["prev_reading"] == pytest.approx(12345.0)
    assert row2["days_elapsed"] == 2


def test_different_utility_types_tracked_separately(tmp_path):
    ulog.append_reading(
        reading_date=date(2026, 6, 11),
        property_name="18 JALAN JINTAN",
        meter_id=None,
        utility_type="electricity",
        current_reading=1000.0,
    )
    # Water reading should have no delta (different utility)
    row = ulog.append_reading(
        reading_date=date(2026, 6, 11),
        property_name="18 JALAN JINTAN",
        meter_id=None,
        utility_type="water",
        current_reading=500.0,
    )
    assert row["delta"] is None


def test_different_properties_tracked_separately(tmp_path):
    ulog.append_reading(
        reading_date=date(2026, 6, 11),
        property_name="18 JALAN JINTAN",
        meter_id=None,
        utility_type="electricity",
        current_reading=1000.0,
    )
    # Different property — no delta
    row = ulog.append_reading(
        reading_date=date(2026, 6, 11),
        property_name="TLKR CAMPUS",
        meter_id=None,
        utility_type="electricity",
        current_reading=800.0,
    )
    assert row["delta"] is None


def test_get_today_readings(tmp_path):
    ulog.append_reading(
        reading_date=date(2026, 6, 11),
        property_name="18 JALAN JINTAN",
        meter_id=None,
        utility_type="water",
        current_reading=100.0,
    )
    ulog.append_reading(
        reading_date=date(2026, 6, 11),
        property_name="18 PENHAS",
        meter_id=None,
        utility_type="electricity",
        current_reading=200.0,
    )
    ulog.append_reading(
        reading_date=date(2026, 6, 12),
        property_name="18 JALAN JINTAN",
        meter_id=None,
        utility_type="water",
        current_reading=110.0,
    )
    rows = ulog.get_today_readings(date(2026, 6, 11))
    assert len(rows) == 2
    props = {r["property"] for r in rows}
    assert "18 JALAN JINTAN" in props
    assert "18 PENHAS" in props

    rows_12 = ulog.get_today_readings(date(2026, 6, 12))
    assert len(rows_12) == 1


def test_get_today_readings_empty(tmp_path):
    rows = ulog.get_today_readings(date(2026, 6, 11))
    assert rows == []


def test_idempotent_xlsx_save(tmp_path):
    """Multiple appends should not corrupt the file."""
    for i in range(5):
        ulog.append_reading(
            reading_date=date(2026, 6, 11),
            property_name="18 JALAN JINTAN",
            meter_id=None,
            utility_type="gas",
            current_reading=float(100 + i),
        )
    rows = ulog.get_today_readings(date(2026, 6, 11))
    assert len(rows) == 5
