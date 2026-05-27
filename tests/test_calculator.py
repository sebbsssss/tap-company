"""
Tests for the occupancy calculation engine.

Uses fixture data from tests/fixtures/*.json.
"""

from datetime import date

import pytest

from occupancy.calculator import (
    _finance_occupied,
    _month_bounds,
    compute_daily_series,
    compute_property_occupancy,
    compute_summary,
)
from occupancy.models import Lease, OccupancyData, Property


def test_month_bounds():
    start, end = _month_bounds("2026-05")
    assert start == date(2026, 5, 1)
    assert end == date(2026, 5, 31)


def test_month_bounds_feb_leap():
    start, end = _month_bounds("2024-02")
    assert end == date(2024, 2, 29)


def test_finance_occupied_overlapping_lease():
    lease = Lease(
        id="l1", unit_id="u1", tenant_id="t1",
        contract_start=date(2026, 4, 15), contract_end=date(2026, 7, 31),
        move_in_date=date(2026, 4, 15), move_out_date=None, status="active",
        crm_link=None,
    )
    # May: lease covers the whole month
    assert _finance_occupied([lease], date(2026, 5, 1), date(2026, 5, 31)) is True
    # April: lease starts mid-month but still overlaps
    assert _finance_occupied([lease], date(2026, 4, 1), date(2026, 4, 30)) is True
    # August: lease ended in July
    assert _finance_occupied([lease], date(2026, 8, 1), date(2026, 8, 31)) is False


def test_finance_occupied_no_dates():
    lease = Lease(
        id="l2", unit_id="u1", tenant_id="t1",
        contract_start=None, contract_end=None,
        move_in_date=None, move_out_date=None, status="active",
        crm_link=None,
    )
    # Missing dates → not counted (fail safe)
    assert _finance_occupied([lease], date(2026, 5, 1), date(2026, 5, 31)) is False


def test_compute_property_occupancy_finance_rate(data):
    """prop-001 has 6 units (001,002,003,004,005,013); leases for 1,2,4,13 overlap May."""
    prop = next(p for p in data.properties if p.id == "prop-001")
    po = compute_property_occupancy(prop, data, "2026-05")
    assert po.total_available == 6
    # Units 1,2,4 have active leases overlapping May.
    # unit-013: lease-011 uses contract_start_date=2026-04-01 (move_in_date=null → DQ issue),
    #   contract_end=2026-09-30 → overlaps May.
    # Units 3 and 5 have no active lease overlapping May.
    assert po.finance_occupied == 4
    assert po.finance_rate == pytest.approx(4 / 6)


def test_compute_property_occupancy_ops_rate(data):
    """Ops rate should be a non-zero average across 31 days in May."""
    prop = next(p for p in data.properties if p.id == "prop-001")
    po = compute_property_occupancy(prop, data, "2026-05")
    assert 0.0 < po.ops_rate <= 1.0
    assert len(po.daily_rates) == 31


def test_compute_daily_series_count(data):
    series = compute_daily_series(data, "2026-05")
    assert len(series) == 31
    for dr in series:
        assert 0 <= dr.occupied <= dr.available
        assert 0.0 <= dr.rate <= 1.0


def test_compute_summary_totals(data):
    summary = compute_summary(data, "2026-05", view_type="finance")
    total_units = sum(len(data.units_for_property(p.id)) for p in data.properties)
    assert summary.total_available == total_units
    assert summary.total_occupied + summary.total_vacant == summary.total_available


def test_compute_summary_property_filter(data):
    summary = compute_summary(data, "2026-05", view_type="finance", property_id="prop-002")
    assert len(summary.properties) == 1
    assert summary.properties[0].property_id == "prop-002"


def test_compute_summary_move_ins(data):
    """lease-007 (unit-011) and lease-008 (unit-014) moved in during May 2026."""
    summary = compute_summary(data, "2026-05")
    assert summary.move_ins_this_month == 2
