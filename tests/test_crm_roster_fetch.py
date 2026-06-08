"""
Tests for crm_roster_fetch.py (workaround for THE-17330: /com/report/settlement/ 500).

Uses the captured fixture: tests/fixtures/room_availability_18jntn_2026-06-08.json
The fixture is a live snapshot from 2026-06-08 of 18 JALAN JINTAN rooms.

Important limitation documented here: room_availability only returns CURRENT bookings,
so crm_roster_fetch is only accurate for the current settlement period.
For historical periods, the roster will be incomplete/incorrect.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pytest

# Add scripts dir to path so we can import the module under test
SCRIPTS_DIR = Path(__file__).parent.parent / "skills" / "settlement-generator" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from crm_roster_fetch import (  # noqa: E402
    _compute_month_of,
    _fmt_date,
    _extract_booking_active_in_period,
    build_roster,
    parse_period,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURE_18JNTN = FIXTURES_DIR / "room_availability_18jntn_2026-06-08.json"


@pytest.fixture()
def jintan_rooms() -> list[dict]:
    with FIXTURE_18JNTN.open() as f:
        data = json.load(f)
    return data["results"]


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestFormatDate:
    def test_basic(self) -> None:
        d = dt.date(2026, 3, 1)
        assert _fmt_date(d) == "1 Mar 26"

    def test_single_digit_day(self) -> None:
        d = dt.date(2026, 3, 5)
        assert _fmt_date(d) == "5 Mar 26"

    def test_december(self) -> None:
        d = dt.date(2025, 12, 31)
        assert _fmt_date(d) == "31 Dec 25"

    def test_none(self) -> None:
        assert _fmt_date(None) == ""


class TestParsePeriod:
    def test_march_2026(self) -> None:
        start, end = parse_period("2026-03")
        assert start == dt.date(2026, 3, 1)
        assert end == dt.date(2026, 3, 31)

    def test_december(self) -> None:
        start, end = parse_period("2025-12")
        assert start == dt.date(2025, 12, 1)
        assert end == dt.date(2025, 12, 31)

    def test_february_nonleap(self) -> None:
        start, end = parse_period("2025-02")
        assert end == dt.date(2025, 2, 28)

    def test_february_leap(self) -> None:
        start, end = parse_period("2024-02")
        assert end == dt.date(2024, 2, 29)


class TestComputeMonthOf:
    def test_first_month_of_twelve(self) -> None:
        move_in = dt.date(2026, 3, 1)
        period_start = dt.date(2026, 3, 1)
        lease_end = dt.date(2027, 2, 28)
        result = _compute_month_of(move_in, period_start, lease_end)
        assert result == "1/12"

    def test_third_month_of_twelve(self) -> None:
        move_in = dt.date(2026, 1, 1)
        period_start = dt.date(2026, 3, 1)
        lease_end = dt.date(2026, 12, 31)
        result = _compute_month_of(move_in, period_start, lease_end)
        assert result == "3/12"

    def test_none_move_in(self) -> None:
        assert _compute_month_of(None, dt.date(2026, 3, 1), dt.date(2027, 3, 1)) == ""

    def test_none_lease_end(self) -> None:
        assert _compute_month_of(dt.date(2026, 1, 1), dt.date(2026, 3, 1), None) == ""


class TestExtractBookingActiveinPeriod:
    def _make_room(self, move_in: str, lease_end: str) -> dict:
        return {
            "occupancy_bookings": [{
                "id": 999,
                "move_in_date": move_in,
                "lease_end_date": lease_end,
                "actual_lease_end_date": lease_end,
                "members": [{"id": 1, "name": "Test Tenant"}],
                "rental_rate": "1000.00",
            }]
        }

    def test_booking_active_in_period(self) -> None:
        room = self._make_room("2026-01-01", "2026-06-30")
        result = _extract_booking_active_in_period(
            room, dt.date(2026, 3, 1), dt.date(2026, 3, 31)
        )
        assert result is not None
        assert result["id"] == 999

    def test_booking_ended_before_period(self) -> None:
        room = self._make_room("2026-01-01", "2026-02-28")
        result = _extract_booking_active_in_period(
            room, dt.date(2026, 3, 1), dt.date(2026, 3, 31)
        )
        assert result is None

    def test_booking_starts_after_period(self) -> None:
        room = self._make_room("2026-04-01", "2026-09-30")
        result = _extract_booking_active_in_period(
            room, dt.date(2026, 3, 1), dt.date(2026, 3, 31)
        )
        assert result is None

    def test_booking_overlaps_period_start(self) -> None:
        room = self._make_room("2026-02-15", "2026-03-15")
        result = _extract_booking_active_in_period(
            room, dt.date(2026, 3, 1), dt.date(2026, 3, 31)
        )
        assert result is not None

    def test_booking_overlaps_period_end(self) -> None:
        room = self._make_room("2026-03-15", "2026-04-15")
        result = _extract_booking_active_in_period(
            room, dt.date(2026, 3, 1), dt.date(2026, 3, 31)
        )
        assert result is not None


# ---------------------------------------------------------------------------
# Integration tests against fixture
# ---------------------------------------------------------------------------


class TestBuildRoster:
    """Tests using the captured live fixture."""

    def test_june_2026_returns_tenants(self, jintan_rooms: list[dict]) -> None:
        period_start, period_end = parse_period("2026-06")
        roster = build_roster(jintan_rooms, period_start, period_end)
        assert len(roster) >= 6, f"Expected at least 6 active tenants, got {len(roster)}"

    def test_june_2026_known_continuous_tenants_present(
        self, jintan_rooms: list[dict]
    ) -> None:
        """Tenants with leases spanning June 2026 must appear in the roster."""
        period_start, period_end = parse_period("2026-06")
        roster = build_roster(jintan_rooms, period_start, period_end)
        names = {r["tenant"] for r in roster}
        # These tenants have leases spanning June 2026
        assert "Xu Jia" in names, "Xu Jia (B02, ends Mar 2027) must be present"
        assert "Drishti Sehgal" in names, "Drishti Sehgal (B06, ends Nov 2026) must be present"

    def test_june_2026_schema_complete(self, jintan_rooms: list[dict]) -> None:
        """Every roster entry must have required settlement.py fields."""
        period_start, period_end = parse_period("2026-06")
        roster = build_roster(jintan_rooms, period_start, period_end)
        required = {"tenant", "room", "duration", "month_of", "rental_rate", "rental_date", "lease_end"}
        for entry in roster:
            missing = required - set(entry.keys())
            assert not missing, f"{entry['tenant']} missing fields: {missing}"

    def test_roster_sorted_by_room(self, jintan_rooms: list[dict]) -> None:
        period_start, period_end = parse_period("2026-06")
        roster = build_roster(jintan_rooms, period_start, period_end)
        rooms = [r["room"] for r in roster]
        assert rooms == sorted(rooms)

    def test_rental_rates_are_float(self, jintan_rooms: list[dict]) -> None:
        period_start, period_end = parse_period("2026-06")
        roster = build_roster(jintan_rooms, period_start, period_end)
        for entry in roster:
            assert isinstance(entry["rental_rate"], float), (
                f"{entry['tenant']} rental_rate is {type(entry['rental_rate'])}, expected float"
            )
            assert entry["rental_rate"] > 0, f"{entry['tenant']} has zero/negative rental_rate"

    def test_no_tenants_for_far_past_period(self, jintan_rooms: list[dict]) -> None:
        """
        Known limitation: room_availability only has current bookings.
        A far-past period should return empty or very few results.
        This test documents the limitation rather than asserting it's a bug.
        """
        period_start, period_end = parse_period("2020-01")  # Before any booking in fixture
        roster = build_roster(jintan_rooms, period_start, period_end)
        # Expectation: 0 or very few — documents current-state-only limitation
        assert len(roster) == 0, (
            f"Expected 0 results for 2020-01 (far past), got {len(roster)}. "
            "If this fails, room_availability now supports historical data — remove this test."
        )

    def test_xu_jia_rental_rate(self, jintan_rooms: list[dict]) -> None:
        """Xu Jia B02 @ $3000/mo — cross-check against known sample_roster_18jntn_mar26.json."""
        period_start, period_end = parse_period("2026-06")
        roster = build_roster(jintan_rooms, period_start, period_end)
        xu_jia = next((r for r in roster if r["tenant"] == "Xu Jia"), None)
        assert xu_jia is not None, "Xu Jia must be in June 2026 roster"
        assert xu_jia["rental_rate"] == 3000.0
        assert xu_jia["room"] == "B02"
