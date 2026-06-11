"""Property name cache — fetches canonical names from CRM, cached daily.

Canonical names come from room_availability unit.prop.name (uppercased).
Falls back to a bundled snapshot when CRM is unreachable.

Env vars used:
  CRM_API_BASE      — CRM base URL (default https://crm-api.theassemblyplace.com)
  CRM_STAFF_API_KEY — API key for x-api-key header
  METER_STATE_DIR   — cache file location (default /data/meter-intake-state)
"""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# Known properties as of 2026-06 — used when CRM is unreachable
SNAPSHOT_PROPERTIES: list[str] = [
    "18 JALAN JINTAN",
    "18 PENHAS",
    "51 MIDDLE ROAD",
    "96 OWEN ROAD",
    "TLKR CAMPUS",
    "TLKR CAMPUS - BLOCK A",
    "TLKR CAMPUS - BLOCK B",
    "MILL@32",
]

_CACHE_TTL_HOURS = 24


def _cache_path() -> Path:
    d = Path(os.environ.get("METER_STATE_DIR", "/data/meter-intake-state"))
    d.mkdir(parents=True, exist_ok=True)
    return d / "property_cache.json"


def _fetch_from_crm() -> Optional[list[str]]:
    base = os.environ.get("CRM_API_BASE", "https://crm-api.theassemblyplace.com").rstrip("/")
    key = os.environ.get("CRM_STAFF_API_KEY") or os.environ.get("CRM_API_KEY", "")
    if not key:
        return None
    names: set[str] = set()
    url: Optional[str] = f"{base}/com/dashboard/room_availability/?format=json&page_size=200"
    while url:
        req = urllib.request.Request(url, headers={"x-api-key": key, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
        except Exception:
            return None
        rooms = (data.get("results") or []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        for room in rooms:
            unit = room.get("unit") or {}
            prop = unit.get("prop") or {}
            name = (prop.get("name") or "").strip().upper()
            if name:
                names.add(name)
        url = data.get("next") if isinstance(data, dict) else None
    return sorted(names) if names else None


_INMEM_CACHE: list[str] | None = None


def get_property_names() -> list[str]:
    """Return canonical property names; refreshes from CRM at most once per day.

    Result is cached in-process after first load to avoid repeated disk/network hits.
    Call invalidate_cache() to force a refresh.
    """
    global _INMEM_CACHE
    if _INMEM_CACHE is not None:
        return _INMEM_CACHE
    result = _get_property_names_uncached()
    _INMEM_CACHE = result
    return result


def invalidate_cache() -> None:
    """Force the next get_property_names() call to re-read from disk/CRM."""
    global _INMEM_CACHE
    _INMEM_CACHE = None


def _get_property_names_uncached() -> list[str]:
    cache_file = _cache_path()

    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text())
            updated_at = datetime.fromisoformat(cached.get("updated_at", ""))
            if (datetime.now(tz=timezone.utc) - updated_at) < timedelta(hours=_CACHE_TTL_HOURS):
                return cached.get("properties") or SNAPSHOT_PROPERTIES
        except Exception:
            pass

    names = _fetch_from_crm()
    if names:
        try:
            cache_file.write_text(json.dumps({
                "updated_at": datetime.now(tz=timezone.utc).isoformat(),
                "properties": names,
            }))
        except Exception:
            pass
        return names

    # Stale cache is better than nothing
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text()).get("properties") or SNAPSHOT_PROPERTIES
        except Exception:
            pass

    return SNAPSHOT_PROPERTIES
