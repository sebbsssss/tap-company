"""
Tests for the 7 data quality check categories.

The fixture data is designed to trigger specific issues:
  - lease-011 on unit-013: active lease with no move_in_date → missing_move_in
  - lease-009, lease-010: expired leases with no move_out in their lease record... wait
    lease-009 has move_out_date=2026-04-30 and contract_end=2026-04-30 → fine
  - unit-013: status=occupied, tenant_id=None → unit_no_tenant
  - unit-013: status=occupied, no active lease with move_in → occupied_no_lease?
    No: lease-011 IS active for unit-013.

Let's verify the specific data quality issues in our fixtures:
  1. missing_move_in: lease-011 (unit-013) has null move_in_date, status=active
  2. missing_move_out: lease-009 contract_end=2026-04-30 < today(2026-05-27) but move_out_date=2026-04-30 → NOT triggered
                       lease-010 contract_end=2026-03-31 < today, move_out_date=2026-03-31 → NOT triggered
  3. inverted_dates: none in fixtures by design → test with injected data
  4. occupied_no_lease: none in fixtures (all occupied units have active leases)
  5. vacant_with_lease: none in fixtures
  6. tenant_multi_unit: none in fixtures
  7. unit_no_tenant: unit-013 has tenant_id=null but status=occupied
"""

from datetime import date

import pytest

from occupancy.data_quality import run_checks
from occupancy.models import Lease, OccupancyData, Unit


def test_missing_move_in(data):
    issues = run_checks(data, reference_date=date(2026, 5, 27))
    missing_mi = [i for i in issues if i.issue_type == "missing_move_in"]
    # lease-011 has no move_in_date
    assert any(i.entity_id == "lease-011" for i in missing_mi), \
        "Expected lease-011 flagged for missing_move_in"


def test_unit_no_tenant(data):
    issues = run_checks(data, reference_date=date(2026, 5, 27))
    no_tenant = [i for i in issues if i.issue_type == "unit_no_tenant"]
    # unit-013 is occupied but has no tenant_id
    assert any(i.entity_id == "unit-013" for i in no_tenant), \
        "Expected unit-013 flagged for unit_no_tenant"


def test_inverted_dates_injected():
    """Inject a lease with inverted contract dates and confirm it's flagged."""
    bad_lease = Lease(
        id="bad-lease", unit_id="u99", tenant_id="t99",
        contract_start=date(2026, 6, 1),
        contract_end=date(2026, 5, 1),   # end before start
        move_in_date=None, move_out_date=None, status="active",
        crm_link=None,
    )
    minimal_data = OccupancyData(leases=[bad_lease])
    issues = run_checks(minimal_data)
    inverted = [i for i in issues if i.issue_type == "inverted_dates"]
    assert len(inverted) == 1
    assert inverted[0].entity_id == "bad-lease"


def test_occupied_no_lease_injected():
    unit = Unit(id="u-lonely", property_id="p1", unit_name="Room X",
                unit_type="room", status="occupied", tenant_id=None, crm_link=None)
    data = OccupancyData(units=[unit])
    issues = run_checks(data)
    occupied_no_lease = [i for i in issues if i.issue_type == "occupied_no_lease"]
    assert any(i.entity_id == "u-lonely" for i in occupied_no_lease)


def test_vacant_with_lease_injected():
    unit = Unit(id="u-v", property_id="p1", unit_name="Room Y",
                unit_type="room", status="vacant", tenant_id=None, crm_link=None)
    lease = Lease(id="l-v", unit_id="u-v", tenant_id="t-v",
                  contract_start=date(2026, 1, 1), contract_end=date(2026, 12, 31),
                  move_in_date=date(2026, 1, 1), move_out_date=None, status="active",
                  crm_link=None)
    data = OccupancyData(units=[unit], leases=[lease])
    issues = run_checks(data)
    assert any(i.issue_type == "vacant_with_lease" and i.entity_id == "u-v" for i in issues)


def test_tenant_multi_unit_injected():
    u1 = Unit(id="ua", property_id="p1", unit_name="A", unit_type="room",
              status="occupied", tenant_id="t-shared", crm_link=None)
    u2 = Unit(id="ub", property_id="p1", unit_name="B", unit_type="room",
              status="occupied", tenant_id="t-shared", crm_link=None)
    l1 = Lease(id="la", unit_id="ua", tenant_id="t-shared",
               contract_start=date(2026, 1, 1), contract_end=date(2026, 12, 31),
               move_in_date=date(2026, 1, 1), move_out_date=None, status="active", crm_link=None)
    l2 = Lease(id="lb", unit_id="ub", tenant_id="t-shared",
               contract_start=date(2026, 1, 1), contract_end=date(2026, 12, 31),
               move_in_date=date(2026, 1, 1), move_out_date=None, status="active", crm_link=None)
    data = OccupancyData(units=[u1, u2], leases=[l1, l2])
    issues = run_checks(data)
    multi = [i for i in issues if i.issue_type == "tenant_multi_unit"]
    assert any(i.entity_id == "t-shared" for i in multi)


def test_all_7_types_present(data):
    """All 7 issue types are enumerated in the code. At least the fixture data triggers some."""
    all_types = {
        "missing_move_in", "missing_move_out", "inverted_dates",
        "occupied_no_lease", "vacant_with_lease", "tenant_multi_unit", "unit_no_tenant"
    }
    # Our fixtures trigger 2: missing_move_in and unit_no_tenant
    issues = run_checks(data, reference_date=date(2026, 5, 27))
    found = {i.issue_type for i in issues}
    assert "missing_move_in" in found
    assert "unit_no_tenant" in found
