"""
Occupancy domain models.

All date fields use date objects (not datetime) since occupancy is a day-level concept.
All optional fields that come from CRM can be None — the data quality checker flags those.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Property:
    id: str
    name: str
    property_type: str          # e.g. "co-living", "serviced-apartment"
    region: Optional[str]
    total_units: int            # total leasable units (denominator for occupancy)
    crm_link: Optional[str]

    @classmethod
    def from_crm(cls, raw: dict) -> "Property":
        return cls(
            id=str(raw["id"]),
            name=raw.get("name") or raw.get("property_name", ""),
            property_type=raw.get("property_type", "co-living"),
            region=raw.get("region"),
            total_units=int(raw.get("total_units", 0)),
            crm_link=raw.get("crm_link") or raw.get("url"),
        )


@dataclass
class Unit:
    id: str
    property_id: str
    unit_name: str
    unit_type: str              # "room", "bed", "studio", etc.
    status: str                 # "occupied", "vacant", "reserved", "maintenance"
    tenant_id: Optional[str]
    crm_link: Optional[str]

    @classmethod
    def from_crm(cls, raw: dict) -> "Unit":
        return cls(
            id=str(raw["id"]),
            property_id=str(raw.get("property_id", "")),
            unit_name=raw.get("unit_name") or raw.get("name", ""),
            unit_type=raw.get("unit_type", "unit"),
            status=(raw.get("status") or "vacant").lower(),
            tenant_id=str(raw["tenant_id"]) if raw.get("tenant_id") else None,
            crm_link=raw.get("crm_link") or raw.get("url"),
        )


@dataclass
class Tenant:
    id: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    crm_link: Optional[str]

    @classmethod
    def from_crm(cls, raw: dict) -> "Tenant":
        return cls(
            id=str(raw["id"]),
            name=raw.get("name") or raw.get("full_name", ""),
            email=raw.get("email"),
            phone=raw.get("phone") or raw.get("mobile"),
            crm_link=raw.get("crm_link") or raw.get("url"),
        )


@dataclass
class Lease:
    id: str
    unit_id: str
    tenant_id: str
    contract_start: Optional[date]
    contract_end: Optional[date]
    move_in_date: Optional[date]
    move_out_date: Optional[date]
    status: str                 # "active", "expired", "upcoming"
    crm_link: Optional[str]

    @classmethod
    def from_crm(cls, raw: dict) -> "Lease":
        def _parse(val: object) -> Optional[date]:
            if not val:
                return None
            if isinstance(val, date):
                return val
            try:
                return date.fromisoformat(str(val))
            except (ValueError, TypeError):
                return None

        return cls(
            id=str(raw["id"]),
            unit_id=str(raw.get("unit_id", "")),
            tenant_id=str(raw.get("tenant_id", "")),
            contract_start=_parse(raw.get("contract_start")),
            contract_end=_parse(raw.get("contract_end")),
            move_in_date=_parse(raw.get("move_in_date")),
            move_out_date=_parse(raw.get("move_out_date")),
            status=(raw.get("status") or "active").lower(),
            crm_link=raw.get("crm_link") or raw.get("url"),
        )


@dataclass
class OccupancyData:
    """All CRM data for a given query, loaded once per request."""
    properties: list[Property] = field(default_factory=list)
    units: list[Unit] = field(default_factory=list)
    tenants: list[Tenant] = field(default_factory=list)
    leases: list[Lease] = field(default_factory=list)
    fetched_at: Optional[str] = None

    def units_for_property(self, property_id: str) -> list[Unit]:
        return [u for u in self.units if u.property_id == property_id]

    def active_leases_for_unit(self, unit_id: str) -> list[Lease]:
        return [l for l in self.leases if l.unit_id == unit_id and l.status == "active"]

    def property_by_id(self, property_id: str) -> Optional[Property]:
        return next((p for p in self.properties if p.id == property_id), None)

    def tenant_by_id(self, tenant_id: str) -> Optional[Tenant]:
        return next((t for t in self.tenants if t.id == tenant_id), None)
