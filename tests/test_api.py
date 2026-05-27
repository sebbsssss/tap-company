"""
Tests for the API handler functions (no HTTP server required).

Exercises the handle_* functions directly with fixture data.
"""

import json
import tempfile
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from occupancy.api import (
    handle_data_quality,
    handle_daily,
    handle_export_csv,
    handle_get_targets,
    handle_properties,
    handle_put_targets,
    handle_summary,
    handle_units,
)
from occupancy.target_store import TargetStore


@pytest.fixture
def store(tmp_path):
    return TargetStore(str(tmp_path / "targets.db"))


def _body(response):
    status, headers, body = response
    return json.loads(body)


def test_summary_returns_200(data, store):
    status, _, _ = handle_summary({"month": "2026-05"}, data, store)
    assert status == 200


def test_summary_bad_month(data, store):
    status, _, body = handle_summary({"month": "bad"}, data, store)
    assert status == 400
    assert "error" in json.loads(body)


def test_summary_fields(data, store):
    result = _body(handle_summary({"month": "2026-05"}, data, store))
    assert "overallRate" in result
    assert "totalAvailable" in result
    assert "totalOccupied" in result
    assert "totalVacant" in result
    assert "moveIns" in result
    assert "moveOuts" in result
    assert "belowTargetCount" in result


def test_summary_view_type_ops(data, store):
    result = _body(handle_summary({"month": "2026-05", "viewType": "ops"}, data, store))
    assert result["viewType"] == "ops"


def test_summary_invalid_view_type(data, store):
    status, _, _ = handle_summary({"month": "2026-05", "viewType": "invalid"}, data, store)
    assert status == 400


def test_daily_series_length(data, store):
    result = _body(handle_daily({"month": "2026-05"}, data, store))
    assert len(result["series"]) == 31


def test_daily_series_fields(data, store):
    result = _body(handle_daily({"month": "2026-05"}, data, store))
    row = result["series"][0]
    assert "date" in row
    assert "rate" in row
    assert "occupied" in row
    assert "available" in row


def test_properties_list(data, store):
    result = _body(handle_properties({"month": "2026-05"}, data, store))
    assert len(result["properties"]) == 3
    for row in result["properties"]:
        assert "financeRate" in row
        assert "opsRate" in row


def test_properties_filter(data, store):
    result = _body(handle_properties({"month": "2026-05", "property": "prop-001"}, data, store))
    assert len(result["properties"]) == 1
    assert result["properties"][0]["propertyId"] == "prop-001"


def test_units_drill_down(data, store):
    status, _, body = handle_units("prop-001", {}, data, store)
    assert status == 200
    result = json.loads(body)
    assert result["propertyId"] == "prop-001"
    assert len(result["units"]) == 6  # units 001,002,003,004,005,013
    for u in result["units"]:
        assert "unit_id" in u
        assert "status" in u


def test_units_not_found(data, store):
    status, _, _ = handle_units("prop-999", {}, data, store)
    assert status == 404


def test_data_quality_returns_issues(data, store):
    result = _body(handle_data_quality({}, data, store))
    assert result["total"] >= 2  # missing_move_in + unit_no_tenant at minimum
    assert isinstance(result["issues"], list)
    assert isinstance(result["summary"], dict)


def test_export_csv_property(data, store):
    status, headers, body = handle_export_csv({"month": "2026-05", "type": "property"}, data, store)
    assert status == 200
    assert "text/csv" in headers["Content-Type"]
    csv_text = body.decode()
    assert "Property" in csv_text
    assert "Finance %" in csv_text


def test_export_csv_finance(data, store):
    status, headers, body = handle_export_csv({"month": "2026-05", "type": "finance"}, data, store)
    assert status == 200
    assert "Unit ID" in body.decode()


def test_export_csv_ops(data, store):
    status, headers, body = handle_export_csv({"month": "2026-05", "type": "ops"}, data, store)
    assert status == 200
    assert "Daily Rate" in body.decode()


def test_export_csv_bad_type(data, store):
    status, _, _ = handle_export_csv({"month": "2026-05", "type": "garbage"}, data, store)
    assert status == 400


def test_targets_get_set(data, store):
    store.set("prop-001", 0.90)
    result = _body(handle_get_targets({"property": "prop-001"}, data, store))
    assert result["targetRate"] == pytest.approx(90.0)


def test_targets_put_single(data, store):
    status, _, body = handle_put_targets(
        {"propertyId": "prop-002", "targetRate": 80.0}, data, store
    )
    assert status == 200
    assert store.get("prop-002") == pytest.approx(0.80)


def test_targets_put_bulk(data, store):
    status, _, _ = handle_put_targets(
        {"targets": [
            {"propertyId": "prop-001", "targetRate": 85.0},
            {"propertyId": "prop-003", "targetRate": 75.0},
        ]},
        data, store
    )
    assert status == 200
    assert store.get("prop-001") == pytest.approx(0.85)
    assert store.get("prop-003") == pytest.approx(0.75)


def test_targets_put_invalid(data, store):
    status, _, _ = handle_put_targets({}, data, store)
    assert status == 400
