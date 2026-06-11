"""Zernio API client — WhatsApp message/inbox operations.

Auth: Authorization: Bearer $ZERNIO_API_KEY
Base: https://api.zernio.com/v1

Never log the API key; the _api_key() helper redacts it from all output.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Optional

import requests

ZERNIO_BASE = "https://api.zernio.com/v1"
_SESSION: Optional[requests.Session] = None


def _log(level: str, msg: str, **kwargs: object) -> None:
    payload = {"level": level, "service": "meter-intake", "msg": msg, **kwargs}
    print(json.dumps(payload), file=sys.stderr)


def _api_key() -> str:
    key = os.environ.get("ZERNIO_API_KEY", "")
    if not key:
        _log("error", "ZERNIO_API_KEY not set")
        raise RuntimeError("ZERNIO_API_KEY not set — set the env var before running")
    return key


def _session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
    _SESSION.headers.update({"Authorization": f"Bearer {_api_key()}"})
    return _SESSION


def _request(method: str, path: str, body: Optional[dict] = None, timeout: int = 15) -> dict:
    url = f"{ZERNIO_BASE}{path}"
    resp = _session().request(method, url, json=body, timeout=timeout)
    if not resp.ok:
        _log("error", "zernio_api_error", path=path, status=resp.status_code, detail=resp.text[:300])
        resp.raise_for_status()
    return resp.json()


def list_webhooks() -> list[dict]:
    """Return existing webhook registrations."""
    result = _request("GET", "/webhooks")
    return result if isinstance(result, list) else result.get("data", [])


def ensure_webhook(callback_url: str, events: Optional[list[str]] = None) -> dict:
    """Idempotent: register the webhook only if one for callback_url doesn't exist."""
    if events is None:
        events = ["message.received"]
    existing = list_webhooks()
    for w in existing:
        if w.get("url") == callback_url:
            _log("info", "webhook_already_registered", url=callback_url)
            return w
    result = _request("POST", "/webhooks", {"url": callback_url, "events": events})
    _log("info", "webhook_registered", url=callback_url, result=str(result)[:120])
    return result


def send_reply(inbox_id: str, contact_id: str, message: str, *, dry_run: bool = True) -> dict:
    """Send a free-form reply via the Zernio inbox API.

    dry_run=True (default): logs intent, never calls the API.
    Caller must explicitly pass dry_run=False to send.
    """
    payload = {"inbox_id": inbox_id, "contact_id": contact_id, "content": message}
    _log(
        "info" if dry_run else "warn",
        "send_reply",
        dry_run=dry_run,
        contact_id=contact_id,
        inbox_id=inbox_id,
        message_preview=message[:100],
    )
    if dry_run:
        return {"dry_run": True, "would_send": payload}
    result = _request("POST", "/inbox/messages", payload)
    _log("info", "reply_sent", contact_id=contact_id)
    return result


def download_image(url: str, *, max_bytes: int = 5 * 1024 * 1024) -> bytes:
    """Download an image attachment (authenticated). Raises ValueError if > max_bytes."""
    resp = _session().get(url, timeout=30, stream=True)
    resp.raise_for_status()
    data = b""
    for chunk in resp.iter_content(chunk_size=65536):
        data += chunk
        if len(data) > max_bytes:
            raise ValueError(f"Image exceeds {max_bytes // 1024 // 1024} MB limit")
    return data
