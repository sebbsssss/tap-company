"""
Occupancy calculation engine.

Finance View:  was the unit occupied at any point in the selected month?
  occupied = contract_start <= month_end AND contract_end >= month_start
  rate = occupied_unit_count / available_unit_count

Operations View:  average daily occupancy across the month.
  For each day D:
    daily_rate[D] = count(units where move_in <= D <= move_out) / total_available
  monthly_ops_rate = mean(daily_rate[1..N])

All inputs are pre-filtered to the target property if property_id is given.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from occupancy.models import Lease, OccupancyData, Property, Unit


@dataclass
class DailyRate:
    day: date
    occupied: int
    available: int
    rate: float  # 0.0–1.0


@dataclass
class PropertyOccupancy:
    property_id: str
    property_name: str
    total_available: int
    finance_occupied: int
    finance_rate: float             # 0.0–1.0
    ops_rate: float                 # 0.0–1.0 (average daily)
    move_ins: int
    move_outs: int
    daily_rates: list[DailyRate] = field(default_factory=list)
    last_updated: Optional[str] = None


@dataclass
class OccupancySummary:
    month: str                      # "YYYY-MM"
    view_type: str                  # "finance" | "ops"
    total_available: int
    total_occupied: int             # finance-view occupied
    total_vacant: int
    overall_rate: float             # 0.0–1.0
    mom_change: Optional[float]     # month-over-month delta
    move_ins_this_month: int
    move_outs_this_month: int
    below_target_count: int
    properties: list[PropertyOccupancy] = field(default_factory=list)


def _month_bounds(month: str) -> tuple[date, date]:
    """Parse "YYYY-MM" and return (first_day, last_day)."""
    year, mon = int(month[:4]), int(month[5:7])
    first = date(year, mon, 1)
    last = date(year, mon, calendar.monthrange(year, mon)[1])
    return first, last


def _finance_occupied(leases: list[Lease], month_start: date, month_end: date) -> bool:
    """Return True if any active lease overlaps the month window."""
    for l in leases:
        cs = l.contract_start or l.move_in_date
        ce = l.contract_end or l.move_out_date
        if cs is None or ce is None:
            continue
        if cs <= month_end and ce >= month_start:
            return True
    return False


def _ops_occupied_on_day(leases: list[Lease], day: date) -> bool:
    """Return True if any lease covers this specific day (move-in basis)."""
    for l in leases:
        mi = l.move_in_date
        mo = l.move_out_date
        if mi is None:
            continue
        # If no move-out recorded, treat unit as still occupied
        if mo is None:
            if mi <= day:
                return True
        else:
            if mi <= day <= mo:
                return True
    return False


def _compute_daily_rates(
    units: list[Unit],
    leases_by_unit: dict[str, list[Lease]],
    month_start: date,
    month_end: date,
) -> list[DailyRate]:
    available = len(units)
    if available == 0:
        return []

    rates: list[DailyRate] = []
    day = month_start
    while day <= month_end:
        occ = sum(
            1 for u in units if _ops_occupied_on_day(leases_by_unit.get(u.id, []), day)
        )
        rates.append(DailyRate(
            day=day,
            occupied=occ,
            available=available,
            rate=occ / available,
        ))
        day += timedelta(days=1)
    return rates


def compute_property_occupancy(
    prop: Property,
    data: OccupancyData,
    month: str,
) -> PropertyOccupancy:
    month_start, month_end = _month_bounds(month)
    units = data.units_for_property(prop.id)
    available = len(units) or prop.total_units  # fallback to CRM total

    leases_by_unit: dict[str, list[Lease]] = {
        u.id: [l for l in data.leases if l.unit_id == u.id]
        for u in units
    }

    # Finance view
    finance_occupied = sum(
        1 for u in units if _finance_occupied(leases_by_unit.get(u.id, []), month_start, month_end)
    )
    finance_rate = finance_occupied / available if available else 0.0

    # Ops view
    daily_rates = _compute_daily_rates(units, leases_by_unit, month_start, month_end)
    ops_rate = (sum(dr.rate for dr in daily_rates) / len(daily_rates)) if daily_rates else 0.0

    # Move-ins / move-outs within the month
    move_ins = sum(
        1 for l in data.leases
        if l.unit_id in {u.id for u in units}
        and l.move_in_date is not None
        and month_start <= l.move_in_date <= month_end
    )
    move_outs = sum(
        1 for l in data.leases
        if l.unit_id in {u.id for u in units}
        and l.move_out_date is not None
        and month_start <= l.move_out_date <= month_end
    )

    return PropertyOccupancy(
        property_id=prop.id,
        property_name=prop.name,
        total_available=available,
        finance_occupied=finance_occupied,
        finance_rate=finance_rate,
        ops_rate=ops_rate,
        move_ins=move_ins,
        move_outs=move_outs,
        daily_rates=daily_rates,
        last_updated=data.fetched_at,
    )


def compute_summary(
    data: OccupancyData,
    month: str,
    view_type: str = "finance",
    property_id: Optional[str] = None,
    property_type: Optional[str] = None,
    unit_type: Optional[str] = None,
    targets: Optional[dict[str, float]] = None,
) -> OccupancySummary:
    """
    Compute the KPI summary card values.

    targets: dict of property_id -> target_rate (0.0–1.0).
             If None, default target is 0.85.
    """
    props = data.properties
    if property_id:
        props = [p for p in props if p.id == property_id]
    if property_type:
        props = [p for p in props if p.property_type.lower() == property_type.lower()]

    # If unit_type filter is present, temporarily restrict which units count
    if unit_type:
        original_units = data.units
        data.units = [u for u in data.units if u.unit_type.lower() == unit_type.lower()]

    prop_occupancies = [compute_property_occupancy(p, data, month) for p in props]

    if unit_type:
        data.units = original_units  # restore

    total_available = sum(po.total_available for po in prop_occupancies)
    total_finance_occupied = sum(po.finance_occupied for po in prop_occupancies)
    total_ops_rate = (
        sum(po.ops_rate * po.total_available for po in prop_occupancies) / total_available
        if total_available else 0.0
    )
    total_vacant = total_available - total_finance_occupied

    if view_type == "ops":
        overall_rate = total_ops_rate
    else:
        overall_rate = total_finance_occupied / total_available if total_available else 0.0

    move_ins = sum(po.move_ins for po in prop_occupancies)
    move_outs = sum(po.move_outs for po in prop_occupancies)

    _targets = targets or {}
    default_target = 0.85
    below_target = sum(
        1 for po in prop_occupancies
        if po.finance_rate < _targets.get(po.property_id, default_target)
    )

    return OccupancySummary(
        month=month,
        view_type=view_type,
        total_available=total_available,
        total_occupied=total_finance_occupied,
        total_vacant=total_vacant,
        overall_rate=overall_rate,
        mom_change=None,  # requires previous month data; computed at API layer if needed
        move_ins_this_month=move_ins,
        move_outs_this_month=move_outs,
        below_target_count=below_target,
        properties=prop_occupancies,
    )


def compute_daily_series(
    data: OccupancyData,
    month: str,
    property_id: Optional[str] = None,
) -> list[DailyRate]:
    """Return daily occupancy rate series for the given month / property."""
    month_start, month_end = _month_bounds(month)

    props = data.properties
    if property_id:
        props = [p for p in props if p.id == property_id]

    units: list[Unit] = []
    for p in props:
        units.extend(data.units_for_property(p.id))

    if not units:
        return []

    leases_by_unit: dict[str, list[Lease]] = {
        u.id: [l for l in data.leases if l.unit_id == u.id]
        for u in units
    }
    return _compute_daily_rates(units, leases_by_unit, month_start, month_end)
