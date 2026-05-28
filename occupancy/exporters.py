"""
Export functions for occupancy data.

CSV export (3 types):
  property  — one row per property: name, finance%, ops%, move-ins, move-outs
  finance   — one row per unit: unit, property, finance-occupied (bool), contract dates
  ops       — one row per (unit, day): daily occupied flag

PDF-data export:
  Returns a structured JSON dict suitable for PDF snapshot rendering by the frontend.
"""

from __future__ import annotations

import csv
import io
from dataclasses import asdict
from datetime import date
from typing import Optional

from occupancy.calculator import OccupancySummary, PropertyOccupancy, compute_daily_series
from occupancy.models import OccupancyData


def _pct(rate: float) -> str:
    return f"{rate * 100:.1f}%"


def export_property_csv(summary: OccupancySummary) -> str:
    """One row per property with Finance% and Ops%."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Property", "Available Units", "Finance Occupied", "Finance %", "Ops %", "Move-ins", "Move-outs"])
    for po in summary.properties:
        w.writerow([
            po.property_name,
            po.total_available,
            po.finance_occupied,
            _pct(po.finance_rate),
            _pct(po.ops_rate),
            po.move_ins,
            po.move_outs,
        ])
    # Totals row
    total_avail = sum(po.total_available for po in summary.properties)
    total_occ = sum(po.finance_occupied for po in summary.properties)
    total_mi = sum(po.move_ins for po in summary.properties)
    total_mo = sum(po.move_outs for po in summary.properties)
    w.writerow([
        "TOTAL",
        total_avail,
        total_occ,
        _pct(total_occ / total_avail) if total_avail else "0.0%",
        _pct(summary.overall_rate) if summary.view_type == "ops" else "",
        total_mi,
        total_mo,
    ])
    return buf.getvalue()


def export_finance_csv(data: OccupancyData, month: str) -> str:
    """One row per unit with Finance occupancy status."""
    from occupancy.calculator import _month_bounds, _finance_occupied

    month_start, month_end = _month_bounds(month)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "Unit ID", "Unit Name", "Unit Type", "Property", "Status",
        "Occupied (Finance)", "Contract Start", "Contract End",
        "Tenant", "CRM Link",
    ])

    property_map = {p.id: p for p in data.properties}
    tenant_map = {t.id: t for t in data.tenants}

    for unit in data.units:
        leases = [l for l in data.leases if l.unit_id == unit.id]
        occupied = _finance_occupied(leases, month_start, month_end)
        prop = property_map.get(unit.property_id)
        active = next((l for l in leases if l.status == "active"), None)
        tenant = tenant_map.get(unit.tenant_id or "") if unit.tenant_id else None
        w.writerow([
            unit.id,
            unit.unit_name,
            unit.unit_type,
            prop.name if prop else "",
            unit.status,
            "Yes" if occupied else "No",
            active.contract_start.isoformat() if (active and active.contract_start) else "",
            active.contract_end.isoformat() if (active and active.contract_end) else "",
            tenant.name if tenant else "",
            unit.crm_link or "",
        ])
    return buf.getvalue()


def export_ops_csv(data: OccupancyData, month: str, property_id: Optional[str] = None) -> str:
    """Daily occupancy rate time series for the month."""
    daily = compute_daily_series(data, month, property_id=property_id)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Date", "Occupied", "Available", "Daily Rate %"])
    for dr in daily:
        w.writerow([dr.day.isoformat(), dr.occupied, dr.available, _pct(dr.rate)])
    return buf.getvalue()


def export_pdf_data(summary: OccupancySummary, data: OccupancyData, month: str) -> dict:
    """Structured JSON for PDF snapshot rendering."""
    return {
        "snapshot_month": month,
        "generated_at": data.fetched_at,
        "view_type": summary.view_type,
        "kpi": {
            "overall_rate_pct": round(summary.overall_rate * 100, 1),
            "total_available": summary.total_available,
            "total_occupied": summary.total_occupied,
            "total_vacant": summary.total_vacant,
            "mom_change_pct": round(summary.mom_change * 100, 1) if summary.mom_change is not None else None,
            "move_ins": summary.move_ins_this_month,
            "move_outs": summary.move_outs_this_month,
            "below_target_count": summary.below_target_count,
        },
        "properties": [
            {
                "id": po.property_id,
                "name": po.property_name,
                "available": po.total_available,
                "finance_rate_pct": round(po.finance_rate * 100, 1),
                "ops_rate_pct": round(po.ops_rate * 100, 1),
                "move_ins": po.move_ins,
                "move_outs": po.move_outs,
            }
            for po in summary.properties
        ],
        "daily_series": [
            {"date": dr.day.isoformat(), "rate_pct": round(dr.rate * 100, 1)}
            for po in summary.properties
            for dr in po.daily_rates
        ],
    }
