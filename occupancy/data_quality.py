"""
Data quality checks for occupancy CRM data.

Surfaces 7 categories of data issues:
  1. missing_move_in         — active lease with no move_in_date
  2. missing_move_out        — lease that has ended but no move_out_date recorded
  3. inverted_dates          — contract_end earlier than contract_start
  4. occupied_no_lease       — unit.status==occupied but no active lease
  5. vacant_with_lease       — unit.status==vacant but has an active lease
  6. tenant_multi_unit       — same tenant has more than one active unit
  7. unit_no_tenant          — unit.status==occupied but unit.tenant_id is None
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from occupancy.models import Lease, OccupancyData, Unit


@dataclass
class DataQualityIssue:
    issue_type: str
    entity_type: str        # "unit" | "lease" | "tenant"
    entity_id: str
    entity_name: str
    property_id: Optional[str]
    property_name: Optional[str]
    detail: str
    crm_link: Optional[str]


def _active_leases(leases: list[Lease]) -> list[Lease]:
    return [l for l in leases if l.status == "active"]


def run_checks(data: OccupancyData, reference_date: Optional[date] = None) -> list[DataQualityIssue]:
    issues: list[DataQualityIssue] = []
    ref = reference_date or date.today()

    property_map = {p.id: p for p in data.properties}
    unit_map = {u.id: u for u in data.units}

    active_leases = _active_leases(data.leases)
    active_lease_by_unit: dict[str, list[Lease]] = {}
    for l in active_leases:
        active_lease_by_unit.setdefault(l.unit_id, []).append(l)

    active_units_by_tenant: dict[str, list[str]] = {}
    for l in active_leases:
        if l.tenant_id:
            active_units_by_tenant.setdefault(l.tenant_id, []).append(l.unit_id)

    def _prop_name(unit: Unit) -> Optional[str]:
        p = property_map.get(unit.property_id)
        return p.name if p else None

    # 1. Missing move-in date on active leases
    for l in active_leases:
        if l.move_in_date is None:
            unit = unit_map.get(l.unit_id)
            issues.append(DataQualityIssue(
                issue_type="missing_move_in",
                entity_type="lease",
                entity_id=l.id,
                entity_name=f"Lease {l.id}",
                property_id=unit.property_id if unit else None,
                property_name=_prop_name(unit) if unit else None,
                detail="Active lease has no move-in date.",
                crm_link=l.crm_link,
            ))

    # 2. Missing move-out date on leases that have ended (contract_end in the past)
    for l in data.leases:
        ce = l.contract_end
        if ce is not None and ce < ref and l.move_out_date is None:
            unit = unit_map.get(l.unit_id)
            issues.append(DataQualityIssue(
                issue_type="missing_move_out",
                entity_type="lease",
                entity_id=l.id,
                entity_name=f"Lease {l.id}",
                property_id=unit.property_id if unit else None,
                property_name=_prop_name(unit) if unit else None,
                detail=f"Lease ended {ce} but no move-out date recorded.",
                crm_link=l.crm_link,
            ))

    # 3. Inverted dates (contract_end < contract_start)
    for l in data.leases:
        cs = l.contract_start
        ce = l.contract_end
        if cs and ce and ce < cs:
            unit = unit_map.get(l.unit_id)
            issues.append(DataQualityIssue(
                issue_type="inverted_dates",
                entity_type="lease",
                entity_id=l.id,
                entity_name=f"Lease {l.id}",
                property_id=unit.property_id if unit else None,
                property_name=_prop_name(unit) if unit else None,
                detail=f"contract_end {ce} is before contract_start {cs}.",
                crm_link=l.crm_link,
            ))
        mi = l.move_in_date
        mo = l.move_out_date
        if mi and mo and mo < mi:
            unit = unit_map.get(l.unit_id)
            issues.append(DataQualityIssue(
                issue_type="inverted_dates",
                entity_type="lease",
                entity_id=l.id,
                entity_name=f"Lease {l.id}",
                property_id=unit.property_id if unit else None,
                property_name=_prop_name(unit) if unit else None,
                detail=f"move_out_date {mo} is before move_in_date {mi}.",
                crm_link=l.crm_link,
            ))

    # 4. Unit marked occupied but no active lease
    for u in data.units:
        if u.status == "occupied" and not active_lease_by_unit.get(u.id):
            issues.append(DataQualityIssue(
                issue_type="occupied_no_lease",
                entity_type="unit",
                entity_id=u.id,
                entity_name=u.unit_name,
                property_id=u.property_id,
                property_name=_prop_name(u),
                detail="Unit is marked occupied but has no active lease.",
                crm_link=u.crm_link,
            ))

    # 5. Unit marked vacant but has an active lease
    for u in data.units:
        if u.status == "vacant" and active_lease_by_unit.get(u.id):
            issues.append(DataQualityIssue(
                issue_type="vacant_with_lease",
                entity_type="unit",
                entity_id=u.id,
                entity_name=u.unit_name,
                property_id=u.property_id,
                property_name=_prop_name(u),
                detail="Unit is marked vacant but has an active lease.",
                crm_link=u.crm_link,
            ))

    # 6. Tenant assigned to more than one active unit
    for tenant_id, unit_ids in active_units_by_tenant.items():
        if len(unit_ids) > 1:
            tenant = next((t for t in data.tenants if t.id == tenant_id), None)
            issues.append(DataQualityIssue(
                issue_type="tenant_multi_unit",
                entity_type="tenant",
                entity_id=tenant_id,
                entity_name=tenant.name if tenant else tenant_id,
                property_id=None,
                property_name=None,
                detail=f"Tenant has active leases on {len(unit_ids)} units: {', '.join(unit_ids)}.",
                crm_link=tenant.crm_link if tenant else None,
            ))

    # 7. Occupied unit with no tenant attached
    for u in data.units:
        if u.status == "occupied" and not u.tenant_id:
            issues.append(DataQualityIssue(
                issue_type="unit_no_tenant",
                entity_type="unit",
                entity_id=u.id,
                entity_name=u.unit_name,
                property_id=u.property_id,
                property_name=_prop_name(u),
                detail="Unit is marked occupied but no tenant is attached in CRM.",
                crm_link=u.crm_link,
            ))

    return issues
