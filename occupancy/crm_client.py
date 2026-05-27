"""
TAP CRM client for occupancy data.

Fetches properties, units, tenants, and leases from the TAP CRM REST API.
Auth: x-api-key header (post-May-2026 standard).
Pagination: follows cursor/offset until all pages retrieved.

Before any live use, capture fixture files:
  curl -s -H "x-api-key: $CRM_STAFF_API_KEY" "$CRM_API_BASE/com/properties/?format=json" \
    | tee tests/fixtures/properties_YYYY-MM-DD.json | python3 -m json.tool | head -30

  curl -s -H "x-api-key: $CRM_STAFF_API_KEY" "$CRM_API_BASE/com/units/?format=json" \
    | tee tests/fixtures/units_YYYY-MM-DD.json | python3 -m json.tool | head -30

  curl -s -H "x-api-key: $CRM_STAFF_API_KEY" "$CRM_API_BASE/com/tenants/?format=json" \
    | tee tests/fixtures/tenants_YYYY-MM-DD.json | python3 -m json.tool | head -30

  curl -s -H "x-api-key: $CRM_STAFF_API_KEY" "$CRM_API_BASE/com/leases/?format=json" \
    | tee tests/fixtures/leases_YYYY-MM-DD.json | python3 -m json.tool | head -30
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
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


class CRMClient:
    def __init__(self, cfg: OccupancyConfig) -> None:
        if not cfg.crm_api_base:
            raise CRMConfigError("CRM_API_BASE must be set")
        if not cfg.crm_api_key:
            raise CRMConfigError("CRM_STAFF_API_KEY must be set")
        self._base = cfg.crm_api_base.rstrip("/")
        self._key = cfg.crm_api_key
        self._property_module = cfg.property_module
        self._unit_module = cfg.unit_module
        self._tenant_module = cfg.tenant_module
        self._lease_module = cfg.lease_module

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

            # DRF ListSerializer or paginated response
            if isinstance(data, dict):
                items = data.get("results") or data.get("data") or []
                results.extend(items)
                next_url = data.get("next")
                if not next_url:
                    break
                # Strip the base URL, keep only the path+query
                parsed = urllib.parse.urlparse(next_url)
                current_path = parsed.path.lstrip("/") + ("?" + parsed.query if parsed.query else "")
                params = {}  # params are embedded in next_url
            elif isinstance(data, list):
                results.extend(data)
                break
            else:
                _stderr(f"Unexpected CRM response shape from {path}")
                break

        _info(f"Fetched {len(results)} records from {path}")
        return results

    def fetch_all(self) -> OccupancyData:
        """Fetch all occupancy-relevant data from the CRM in one call."""
        raw_properties = self._paginate(self._property_module)
        raw_units = self._paginate(self._unit_module)
        raw_tenants = self._paginate(self._tenant_module)
        raw_leases = self._paginate(self._lease_module)

        return OccupancyData(
            properties=[Property.from_crm(r) for r in raw_properties],
            units=[Unit.from_crm(r) for r in raw_units],
            tenants=[Tenant.from_crm(r) for r in raw_tenants],
            leases=[Lease.from_crm(r) for r in raw_leases],
            fetched_at=datetime.now(tz=timezone.utc).isoformat(),
        )


def load_from_fixtures(fixtures_dir: str | Path) -> OccupancyData:
    """
    Load occupancy data from JSON fixture files.
    Used in tests and dry-run mode.

    Looks for the most recent files matching:
      properties_*.json, units_*.json, tenants_*.json, leases_*.json
    """
    base = Path(fixtures_dir)

    def _latest(pattern: str) -> list[dict]:
        files = sorted(base.glob(pattern))
        if not files:
            return []
        raw = json.loads(files[-1].read_text())
        if isinstance(raw, dict):
            return raw.get("results") or raw.get("data") or []
        return raw

    return OccupancyData(
        properties=[Property.from_crm(r) for r in _latest("properties_*.json")],
        units=[Unit.from_crm(r) for r in _latest("units_*.json")],
        tenants=[Tenant.from_crm(r) for r in _latest("tenants_*.json")],
        leases=[Lease.from_crm(r) for r in _latest("leases_*.json")],
        fetched_at="fixture",
    )
