"""
Occupancy API handler functions.

Each handle_* function:
  - receives a query-param dict and a DataBundle
  - returns (status_code: int, headers: dict, body: bytes)

The stdlib HTTP server in server.py calls these based on path routing.
No framework dependency — pure stdlib + the approved deps (requests for CRM).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Optional

from occupancy.calculator import (
    compute_daily_series,
    compute_property_occupancy,
    compute_summary,
)
from occupancy.data_quality import run_checks
from occupancy.exporters import (
    export_finance_csv,
    export_ops_csv,
    export_pdf_data,
    export_property_csv,
)
from occupancy.models import OccupancyData
from occupancy.target_store import TargetStore


_JSON = "application/json"
_CSV  = "text/csv; charset=utf-8"

Response = tuple[int, dict, bytes]


def _json(data: Any, status: int = 200) -> Response:
    body = json.dumps(data, default=str).encode()
    return status, {"Content-Type": _JSON}, body


def _error(message: str, status: int = 400) -> Response:
    return _json({"error": message}, status)


def _current_month() -> str:
    return date.today().strftime("%Y-%m")


def _require_month(params: dict) -> tuple[Optional[str], Optional[Response]]:
    month = params.get("month", _current_month())
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        return None, _error("month must be YYYY-MM")
    return month, None


def _unit_drill_down(data: OccupancyData, property_id: str) -> list[dict]:
    """Build unit drill-down rows for /api/occupancy/units/:propertyId."""
    today = date.today()
    tenant_map = {t.id: t for t in data.tenants}
    units = data.units_for_property(property_id)
    result = []

    for u in units:
        leases = [l for l in data.leases if l.unit_id == u.id]
        active = next((l for l in leases if l.status == "active"), None)
        tenant = tenant_map.get(active.tenant_id if active else (u.tenant_id or ""))

        # Days vacant: if move_out recorded and unit is vacant
        days_vacant: Optional[int] = None
        if u.status == "vacant":
            latest_out = max(
                (l.move_out_date for l in leases if l.move_out_date),
                default=None,
            )
            if latest_out:
                days_vacant = (today - latest_out).days

        # Next available: if reserved, use contract_start of upcoming lease
        next_available: Optional[str] = None
        upcoming = next(
            (l for l in leases
             if l.status in ("upcoming", "active")
             and l.contract_start and l.contract_start > today),
            None,
        )
        if upcoming and upcoming.contract_start:
            next_available = upcoming.contract_start.isoformat()

        result.append({
            "unit_id": u.id,
            "unit_name": u.unit_name,
            "unit_type": u.unit_type,
            "status": u.status,
            "tenant_name": tenant.name if tenant else None,
            "tenant_id": tenant.id if tenant else None,
            "contract_start": active.contract_start.isoformat() if (active and active.contract_start) else None,
            "contract_end": active.contract_end.isoformat() if (active and active.contract_end) else None,
            "move_in_date": active.move_in_date.isoformat() if (active and active.move_in_date) else None,
            "move_out_date": active.move_out_date.isoformat() if (active and active.move_out_date) else None,
            "days_vacant": days_vacant,
            "next_available": next_available,
            "crm_link": u.crm_link,
        })
    return result


def _actionable_flags(
    data: OccupancyData,
    property_occupancies: list,
    targets: dict[str, float],
    month: str,
) -> list[dict]:
    """Generate actionable flags for the frontend."""
    today = date.today()
    thirty_days = today + timedelta(days=30)
    flags = []

    # Properties below target
    for po in property_occupancies:
        target = targets.get(po.property_id, 0.85)
        if po.finance_rate < target:
            flags.append({
                "type": "below_target",
                "property_id": po.property_id,
                "property_name": po.property_name,
                "rate": round(po.finance_rate * 100, 1),
                "target": round(target * 100, 1),
            })

    # Units vacant > 14 days or > 30 days
    for u in data.units:
        if u.status != "vacant":
            continue
        leases = [l for l in data.leases if l.unit_id == u.id]
        latest_out = max((l.move_out_date for l in leases if l.move_out_date), default=None)
        if not latest_out:
            continue
        days = (today - latest_out).days
        if days > 30:
            flags.append({"type": "vacant_30d", "unit_id": u.id, "unit_name": u.unit_name,
                           "property_id": u.property_id, "days_vacant": days})
        elif days > 14:
            flags.append({"type": "vacant_14d", "unit_id": u.id, "unit_name": u.unit_name,
                           "property_id": u.property_id, "days_vacant": days})

    # Upcoming move-outs in next 30 days
    for l in data.leases:
        if l.status != "active" or not l.move_out_date:
            continue
        if today <= l.move_out_date <= thirty_days:
            unit = next((u for u in data.units if u.id == l.unit_id), None)
            flags.append({
                "type": "upcoming_moveout",
                "unit_id": l.unit_id,
                "unit_name": unit.unit_name if unit else l.unit_id,
                "property_id": unit.property_id if unit else None,
                "move_out_date": l.move_out_date.isoformat(),
                "days_until": (l.move_out_date - today).days,
            })

    return flags


# ---------------------------------------------------------------------------
# Endpoint handlers
# ---------------------------------------------------------------------------

def handle_summary(params: dict, data: OccupancyData, store: TargetStore) -> Response:
    """GET /api/occupancy/summary"""
    month, err = _require_month(params)
    if err:
        return err

    view_type = params.get("viewType", "finance")
    if view_type not in ("finance", "ops"):
        return _error("viewType must be 'finance' or 'ops'")

    targets = store.get_all()
    summary = compute_summary(
        data, month,
        view_type=view_type,
        property_id=params.get("property"),
        property_type=params.get("propertyType"),
        unit_type=params.get("unitType"),
        targets=targets,
    )
    flags = _actionable_flags(data, summary.properties, targets, month)

    return _json({
        "month": month,
        "viewType": view_type,
        "overallRate": round(summary.overall_rate * 100, 1),
        "totalAvailable": summary.total_available,
        "totalOccupied": summary.total_occupied,
        "totalVacant": summary.total_vacant,
        "momChange": round(summary.mom_change * 100, 1) if summary.mom_change is not None else None,
        "moveIns": summary.move_ins_this_month,
        "moveOuts": summary.move_outs_this_month,
        "belowTargetCount": summary.below_target_count,
        "actionableFlags": flags,
        "dataLastUpdated": data.fetched_at,
    })


def handle_daily(params: dict, data: OccupancyData, store: TargetStore) -> Response:
    """GET /api/occupancy/daily"""
    month, err = _require_month(params)
    if err:
        return err

    daily = compute_daily_series(data, month, property_id=params.get("property"))
    return _json({
        "month": month,
        "property": params.get("property"),
        "series": [
            {"date": dr.day.isoformat(), "occupied": dr.occupied,
             "available": dr.available, "rate": round(dr.rate * 100, 1)}
            for dr in daily
        ],
    })


def handle_properties(params: dict, data: OccupancyData, store: TargetStore) -> Response:
    """GET /api/occupancy/properties"""
    month, err = _require_month(params)
    if err:
        return err

    view_type = params.get("viewType", "finance")
    status_filter = params.get("status")
    targets = store.get_all()

    props = data.properties
    if params.get("property"):
        props = [p for p in props if p.id == params["property"]]

    rows = []
    for prop in props:
        po = compute_property_occupancy(prop, data, month)
        rate = po.ops_rate if view_type == "ops" else po.finance_rate
        target = targets.get(prop.id, 0.85)

        row = {
            "propertyId": prop.id,
            "propertyName": prop.name,
            "propertyType": prop.property_type,
            "region": prop.region,
            "available": po.total_available,
            "financeRate": round(po.finance_rate * 100, 1),
            "opsRate": round(po.ops_rate * 100, 1),
            "moveIns": po.move_ins,
            "moveOuts": po.move_outs,
            "targetRate": round(target * 100, 1),
            "belowTarget": rate < target,
            "lastUpdated": data.fetched_at,
        }
        if status_filter:
            if status_filter == "below_target" and rate >= target:
                continue
            elif status_filter == "on_track" and rate < target:
                continue
        rows.append(row)

    return _json({"month": month, "viewType": view_type, "properties": rows})


def handle_units(property_id: str, params: dict, data: OccupancyData, store: TargetStore) -> Response:
    """GET /api/occupancy/units/:propertyId"""
    prop = data.property_by_id(property_id)
    if not prop:
        return _error(f"Property '{property_id}' not found", 404)

    rows = _unit_drill_down(data, property_id)
    return _json({"propertyId": property_id, "propertyName": prop.name, "units": rows})


def handle_data_quality(params: dict, data: OccupancyData, store: TargetStore) -> Response:
    """GET /api/occupancy/data-quality"""
    issues = run_checks(data)
    property_filter = params.get("property")
    if property_filter:
        issues = [i for i in issues if i.property_id == property_filter]

    return _json({
        "total": len(issues),
        "issues": [
            {
                "type": i.issue_type,
                "entityType": i.entity_type,
                "entityId": i.entity_id,
                "entityName": i.entity_name,
                "propertyId": i.property_id,
                "propertyName": i.property_name,
                "detail": i.detail,
                "crmLink": i.crm_link,
            }
            for i in issues
        ],
        "summary": {
            t: sum(1 for i in issues if i.issue_type == t)
            for t in {i.issue_type for i in issues}
        },
    })


def handle_export_csv(params: dict, data: OccupancyData, store: TargetStore) -> Response:
    """GET /api/occupancy/export/csv"""
    month, err = _require_month(params)
    if err:
        return err

    export_type = params.get("type", "property")
    targets = store.get_all()

    if export_type == "property":
        summary = compute_summary(data, month, targets=targets)
        csv_content = export_property_csv(summary)
        fname = f"occupancy_property_{month}.csv"
    elif export_type == "finance":
        csv_content = export_finance_csv(data, month)
        fname = f"occupancy_finance_{month}.csv"
    elif export_type == "ops":
        csv_content = export_ops_csv(data, month, property_id=params.get("property"))
        fname = f"occupancy_ops_{month}.csv"
    else:
        return _error("type must be 'property', 'finance', or 'ops'")

    headers = {
        "Content-Type": _CSV,
        "Content-Disposition": f'attachment; filename="{fname}"',
    }
    return 200, headers, csv_content.encode()


def handle_export_pdf_data(params: dict, data: OccupancyData, store: TargetStore) -> Response:
    """GET /api/occupancy/export/pdf-data"""
    month, err = _require_month(params)
    if err:
        return err

    targets = store.get_all()
    view_type = params.get("viewType", "finance")
    summary = compute_summary(data, month, view_type=view_type, targets=targets)
    pdf_data = export_pdf_data(summary, data, month)
    return _json(pdf_data)


def handle_get_targets(params: dict, data: OccupancyData, store: TargetStore) -> Response:
    """GET /api/occupancy/settings/target"""
    all_targets = store.get_all()
    property_id = params.get("property")
    if property_id:
        rate = store.get(property_id)
        return _json({
            "propertyId": property_id,
            "targetRate": round(rate * 100, 1) if rate is not None else None,
        })
    return _json({
        "targets": [
            {"propertyId": pid, "targetRate": round(rate * 100, 1)}
            for pid, rate in all_targets.items()
        ]
    })


def handle_put_targets(body: dict, data: OccupancyData, store: TargetStore) -> Response:
    """PUT /api/occupancy/settings/target"""
    targets = body.get("targets")
    if not targets:
        # Single property mode: {"propertyId": "...", "targetRate": 85.0}
        pid = body.get("propertyId")
        rate_pct = body.get("targetRate")
        if not pid or rate_pct is None:
            return _error("Provide either 'targets' array or 'propertyId' + 'targetRate'")
        try:
            store.set(pid, float(rate_pct) / 100)
        except ValueError as e:
            return _error(str(e))
        return _json({"updated": [pid]})

    # Bulk mode
    if not isinstance(targets, list):
        return _error("'targets' must be an array of {propertyId, targetRate}")
    try:
        store.set_bulk({
            t["propertyId"]: float(t["targetRate"]) / 100
            for t in targets
        })
    except (KeyError, TypeError, ValueError) as e:
        return _error(str(e))
    return _json({"updated": [t["propertyId"] for t in targets]})
