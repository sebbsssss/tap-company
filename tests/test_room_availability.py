"""
Integration-style smoke tests using the live room_availability_2026-05-27.json fixture.

These tests verify that _map_rooms_to_occupancy correctly parses the real CRM response shape
and produces plausible OccupancyData. They do not assert specific values — production data
changes; they assert structural correctness and numerical sanity.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from occupancy.calculator import compute_summary
from occupancy.crm_client import _load_room_availability_file, _map_rooms_to_occupancy

FIXTURES_DIR = Path(__file__).parent / "fixtures"
LIVE_FIXTURE = FIXTURES_DIR / "room_availability_2026-05-27.json"


@pytest.fixture(scope="module")
def live_data():
    raw = json.loads(LIVE_FIXTURE.read_text())
    rooms = raw["results"]
    return _map_rooms_to_occupancy(rooms)


@pytest.fixture(scope="module")
def live_data_10():
    """Slice of the first 10 rooms for fast sanity checks."""
    raw = json.loads(LIVE_FIXTURE.read_text())
    return _map_rooms_to_occupancy(raw["results"][:10])


def test_live_fixture_room_count(live_data):
    """Fixture has 100 rooms (first page of 1831)."""
    assert len(live_data.units) == 100


def test_live_fixture_properties_non_empty(live_data):
    assert len(live_data.properties) > 0


def test_live_fixture_tenants_non_empty(live_data):
    assert len(live_data.tenants) > 0


def test_live_fixture_all_units_have_valid_status(live_data):
    valid = {"occupied", "vacant", "reserved"}
    for unit in live_data.units:
        assert unit.status in valid, f"unit {unit.id} has unexpected status {unit.status!r}"


def test_live_fixture_leases_have_unit_ids(live_data):
    unit_ids = {u.id for u in live_data.units}
    for lease in live_data.leases:
        assert lease.unit_id in unit_ids, f"lease {lease.id} references unknown unit {lease.unit_id!r}"


def test_live_fixture_occupancy_rates_plausible_10_rooms(live_data_10):
    """Smoke: compute finance+ops rates on 10 rooms, rates must be in [0, 1]."""
    assert len(live_data_10.properties) > 0
    summary = compute_summary(live_data_10, "2026-05", view_type="finance")
    assert 0.0 <= summary.overall_rate <= 1.0
    assert summary.total_available == 10
    assert summary.total_occupied + summary.total_vacant == summary.total_available

    ops_summary = compute_summary(live_data_10, "2026-05", view_type="ops")
    assert 0.0 <= ops_summary.overall_rate <= 1.0


def test_live_fixture_load_via_helper():
    """load_from_fixtures falls back to the live fixture when room_availability_test.json absent."""
    data = _load_room_availability_file(LIVE_FIXTURE)
    assert len(data.units) == 100
    assert data.fetched_at == "fixture"
