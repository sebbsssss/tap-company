"""
TAP CRM client for occupancy data.

Fetches room availability data from the TAP CRM dashboard API.
Auth: x-api-key header (post-May-2026 standard).
Pagination: follows DRF cursor/offset until all pages retrieved.

Live-probe command:
  curl -s -H "x-api-key: $CRM_STAFF_API_KEY" \
    "$CRM_API_BASE/com/dashboard/room_availability/?format=json&page_size=100" \
    | tee tests/fixtures/room_availability_YYYY-MM-DD.json | python3 -m json.tool | head -30
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from occupancy.config import OccupancyConfig
from occupancy.models import Lease, OccupancyData, Property, Tenant, Unit


class CRMConfigError(Exception):
    pass


class CRMAPIError(Exception):
    pass


_MAX_RETRIES = 3
_RETRY_BACKOFF = 1.5  # seconds, multiplied per retry


def _stderr(msg: str) -> None:
    print(json.dumps({"level": "error", "msg": msg, "ts": datetime.now(tz=timezone.utc).isoformat()}), file=sys.stderr)


def _info(msg: str, **kwargs: Any) -> None:
    print(json.dumps({"level": "info", "msg": msg, **kwargs, "ts": datetime.now(tz=timezone.utc).isoformat()}), file=sys.stderr)


def _parse_date(val: object) -> Optional[date]:
    if not val:
        return None
    if isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val))
    except (ValueError, TypeError):
        return None


def _prop_type(prop_data: dict) -> str:
    """Normalise CRM property_type/property_kind to a domain type string."""
    pt = (prop_data.get("property_type") or "").lower().replace(" ", "-")
    known = {"straight-lease", "co-living", "serviced-apartment", "mgmt-contract"}
    if pt in known:
        return pt
    pk_name = ((prop_data.get("property_kind") or {}).get("name") or "").lower()
    if "co living" in pk_name or "co-living" in pk_name:
        return "co-living"
    if "mgmt" in pk_name or "management" in pk_name:
        return "mgmt-contract"
    return pt or "co-living"


def _unit_status(occ_status: str, book_status: str) -> str:
    """Map CRM occupancy_status + booking_status to domain Unit.status."""
    if occ_status.lower() == "occupied":
        return "occupied"
    if book_status.lower() in ("reserved", "booked"):
        return "reserved"
    return "vacant"


def _map_rooms_to_occupancy(rooms: list[dict], fetched_at: str = "") -> OccupancyData:
    """
    Map a list of room_availability records to the OccupancyData domain model.

    Each room becomes a Unit. Properties are deduped from room.unit.prop.
    Tenants are deduped from occupancy_bookings members.
    Leases come from occupancy_bookings entries.

    Booking fields used:
      move_in_date         — physical move-in (may be null → missing_move_in DQ issue)
      contract_start_date  — explicit contract start (optional; falls back to move_in_date)
      lease_end_date       — contracted end date
      actual_lease_end_date — effective end (may extend lease_end_date)
      members              — list of {id, name, gender, ...}
    """
    today = date.today()
    props_meta: dict[str, dict] = {}
    props_count: dict[str, int] = {}
    units: list[Unit] = []
    tenants_seen: dict[str, Tenant] = {}
    leases: list[Lease] = []

    for room in rooms:
        unit_data = room.get("unit") or {}
        prop_data = unit_data.get("prop") or {}

        prop_id = str(prop_data.get("id", ""))
        if prop_id and prop_id not in props_meta:
            props_meta[prop_id] = prop_data
            props_count[prop_id] = 0
        if prop_id:
            props_count[prop_id] += 1

        room_id = str(room["id"])
        occ_status = room.get("occupancy_status") or "Vacant"
        book_status = room.get("booking_status") or "Available"

        # Primary tenant from first occupancy_booking's first member
        primary_tenant_id: Optional[str] = None
        for booking in room.get("occupancy_bookings") or []:
            members = booking.get("members") or []
            if members:
                primary_tenant_id = str(members[0]["id"])
                break

        units.append(Unit(
            id=room_id,
            property_id=prop_id,
            unit_name=room.get("number") or room.get("room_label") or room_id,
            unit_type=(room.get("room_type") or "room").lower(),
            status=_unit_status(occ_status, book_status),
            tenant_id=primary_tenant_id,
            crm_link=None,
        ))

        # Tenants from all occupancy_booking members
        for booking in room.get("occupancy_bookings") or []:
            for member in booking.get("members") or []:
                m_id = str(member["id"])
                if m_id not in tenants_seen:
                    tenants_seen[m_id] = Tenant(
                        id=m_id,
                        name=member.get("name", ""),
                        email=None,
                        phone=None,
                        crm_link=None,
                    )

        # Leases from occupancy_bookings
        for booking in room.get("occupancy_bookings") or []:
            members = booking.get("members") or []
            tenant_id = str(members[0]["id"]) if members else ""

            move_in_date = _parse_date(booking.get("move_in_date"))
            # contract_start_date is an optional override for cases where the lease
            # started (contract signed) before the physical move-in date was recorded.
            contract_start = _parse_date(
                booking.get("contract_start_date") or booking.get("move_in_date")
            )
            lease_end = _parse_date(booking.get("lease_end_date"))
            actual_end = _parse_date(booking.get("actual_lease_end_date"))
            effective_end = actual_end or lease_end

            if move_in_date and move_in_date > today:
                lease_status = "upcoming"
            elif effective_end and effective_end < today:
                lease_status = "expired"
            else:
                lease_status = "active"

            leases.append(Lease(
                id=str(booking["id"]),
                unit_id=room_id,
                tenant_id=tenant_id,
                contract_start=contract_start,
                contract_end=lease_end,
                move_in_date=move_in_date,
                move_out_date=actual_end if effective_end and effective_end < today else None,
                status=lease_status,
                crm_link=None,
            ))

    properties = [
        Property(
            id=pid,
            name=props_meta[pid].get("name", ""),
            property_type=_prop_type(props_meta[pid]),
            region=props_meta[pid].get("area"),
            total_units=props_count[pid],
            crm_link=None,
        )
        for pid in props_meta
    ]

    return OccupancyData(
        properties=properties,
        units=units,
        tenants=list(tenants_seen.values()),
        leases=leases,
        fetched_at=fetched_at or datetime.now(tz=timezone.utc).isoformat(),
    )


class CRMClient:
    def __init__(self, cfg: OccupancyConfig) -> None:
        if not cfg.crm_api_base:
            raise CRMConfigError("CRM_API_BASE must be set")
        if not cfg.crm_api_key:
            raise CRMConfigError("CRM_STAFF_API_KEY must be set")
        self._base = cfg.crm_api_base.rstrip("/")
        self._key = cfg.crm_api_key
        self._room_availability_module = cfg.room_availability_module

    def _request(self, path: str, params: Optional[dict] = None) -> Any:
        """GET a CRM endpoint, retrying on transient errors. Returns parsed JSON."""
        url = f"{self._base}/{path.lstrip('/')}"
        if params:
            url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})

        headers = {
            "x-api-key": self._key,
            "Accept": "application/json",
        }
        req = urllib.request.Request(url, headers=headers)

        for attempt in range(_MAX_RETRIES):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read())
                return data
            except urllib.error.HTTPError as e:
                body = e.read().decode(errors="replace")
                if e.code in (500, 502, 503, 504) and attempt < _MAX_RETRIES - 1:
                    wait = _RETRY_BACKOFF ** attempt
                    _info(f"CRM {path} HTTP {e.code}, retry {attempt+1} in {wait:.1f}s")
                    time.sleep(wait)
                    continue
                _stderr(f"CRM {path} HTTP {e.code}: {body[:200]}")
                raise CRMAPIError(f"CRM HTTP {e.code} on {path}: {body[:200]}") from e
            except urllib.error.URLError as e:
                if attempt < _MAX_RETRIES - 1:
                    wait = _RETRY_BACKOFF ** attempt
                    _info(f"CRM {path} URLError {e.reason}, retry {attempt+1}")
                    time.sleep(wait)
                    continue
                _stderr(f"CRM {path} URLError: {e.reason}")
                raise CRMAPIError(f"CRM URLError on {path}: {e.reason}") from e
        raise CRMAPIError(f"CRM {path}: exhausted retries")

    def _paginate(self, path: str, extra_params: Optional[dict] = None) -> list[dict]:
        """
        Fetch all pages from a paginated CRM list endpoint.
        Supports DRF-style 'next' cursor pagination and offset/limit pagination.
        """
        results: list[dict] = []
        params = dict(extra_params or {})
        params.setdefault("page_size", 100)
        current_path = path

        while True:
            data = self._request(current_path, params if current_path == path else None)

            if isinstance(data, dict):
                items = data.get("results") or data.get("data") or []
                results.extend(items)
                next_url = data.get("next")
                if not next_url:
                    break
                parsed = urllib.parse.urlparse(next_url)
                current_path = parsed.path.lstrip("/") + ("?" + parsed.query if parsed.query else "")
                params = {}
            elif isinstance(data, list):
                results.extend(data)
                break
            else:
                _stderr(f"Unexpected CRM response shape from {path}")
                break

        _info(f"Fetched {len(results)} records from {path}")
        return results

    def fetch_all(self) -> OccupancyData:
        """Fetch all occupancy-relevant data from the CRM room_availability endpoint."""
        rooms = self._paginate(self._room_availability_module)
        _info(f"Mapping {len(rooms)} room_availability records to OccupancyData")
        return _map_rooms_to_occupancy(rooms)


def load_from_fixtures(fixtures_dir: str | Path) -> OccupancyData:
    """
    Load occupancy data from JSON fixture files in room_availability format.
    Used in tests and dry-run mode.

    Resolution order:
      1. room_availability_test.json  — explicit synthetic test file
      2. room_availability_*.json     — latest date-stamped live fixture
         (summary files excluded)
    """
    base = Path(fixtures_dir)

    # 1. Explicit test fixture (preferred for unit tests)
    test_file = base / "room_availability_test.json"
    if test_file.exists():
        return _load_room_availability_file(test_file)

    # 2. Latest date-stamped room_availability file
    ra_files = sorted(
        f for f in base.glob("room_availability_*.json")
        if "summary" not in f.stem
    )
    if ra_files:
        return _load_room_availability_file(ra_files[-1])

    raise FileNotFoundError(
        f"No room_availability fixture found in {base}. "
        "Expected room_availability_test.json or room_availability_YYYY-MM-DD.json"
    )


def _load_room_availability_file(path: Path) -> OccupancyData:
    raw = json.loads(path.read_text())
    rooms: list[dict]
    if isinstance(raw, dict) and "results" in raw:
        rooms = raw["results"]
    elif isinstance(raw, list):
        rooms = raw
    else:
        rooms = []
    return _map_rooms_to_occupancy(rooms, fetched_at="fixture")
