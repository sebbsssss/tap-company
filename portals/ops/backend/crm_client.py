"""CRM API wrapper with 60-second in-memory cache.

Auth via x-api-key header. Base URL from CRM_API_BASE env var.
Uses only stdlib (urllib) + requests-style patterns from fetch_open.py.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Optional

CRM_BASE = os.environ.get("CRM_API_BASE", "https://crm-api.theassemblyplace.com")
CRM_KEY = os.environ.get("CRM_API_KEY") or os.environ.get("CRM_STAFF_API_KEY")
CACHE_TTL = 60  # seconds

_cache: dict[str, tuple[Any, float]] = {}
_cache_lock = threading.Lock()


def _headers() -> dict[str, str]:
    if not CRM_KEY:
        raise RuntimeError("CRM_API_KEY not set in environment")
    return {
        "x-api-key": CRM_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _crm_request(method: str, path: str, body: Optional[dict] = None) -> Any:
    url = f"{CRM_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        print(
            json.dumps({"level": "error", "event": "crm_http_error", "method": method,
                        "path": path, "status": e.code, "body": body_text[:500]}),
            file=sys.stderr,
        )
        raise


def crm_get(path: str, cached: bool = False) -> Any:
    if cached:
        return _crm_get_cached(path)
    return _crm_request("GET", path)


def _crm_get_cached(path: str) -> Any:
    now = time.monotonic()
    with _cache_lock:
        entry = _cache.get(path)
        if entry and (now - entry[1]) < CACHE_TTL:
            return entry[0]
    result = _crm_request("GET", path)
    with _cache_lock:
        _cache[path] = (result, time.monotonic())
    return result


def crm_post(path: str, body: dict) -> Any:
    return _crm_request("POST", path, body)


def crm_patch(path: str, body: dict) -> Any:
    return _crm_request("PATCH", path, body)


def invalidate_cache(*paths: str) -> None:
    with _cache_lock:
        for p in paths:
            _cache.pop(p, None)
        # Also clear any list cache that starts with the path prefix
        prefix = paths[0].split("?")[0] if paths else ""
        stale = [k for k in _cache if k.startswith(prefix)]
        for k in stale:
            _cache.pop(k, None)
