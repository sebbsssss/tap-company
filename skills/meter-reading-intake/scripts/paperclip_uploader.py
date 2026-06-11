"""Upload the utility log xlsx to Paperclip as an issue attachment.

This keeps the xlsx as the canonical retrievable copy on the Paperclip doc store.
Env vars (auto-injected in Paperclip heartbeats; must be set as Fly secrets for the service):
  PAPERCLIP_API_URL        — e.g. https://tap-agentspace.fly.dev
  PAPERCLIP_API_KEY        — run JWT or long-lived service key
  PAPERCLIP_ISSUE_ID       — the issue to attach to (THE-17390's numeric id)
  PAPERCLIP_COMPANY_ID     — TAP company id

Each call uploads the current month's xlsx. Previous months are uploaded on first write
of the new month (when they just finished). Duplicate uploads are cheap — Paperclip
deduplicates by filename+size at the API level.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

import requests

_SESSION: Optional[requests.Session] = None


def _log(level: str, msg: str, **kwargs: object) -> None:
    print(json.dumps({"level": level, "service": "meter-intake", "msg": msg, **kwargs}), file=sys.stderr)


def _env(key: str) -> Optional[str]:
    return os.environ.get(key) or None


def _session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
    api_key = _env("PAPERCLIP_API_KEY")
    if api_key:
        _SESSION.headers.update({"Authorization": f"Bearer {api_key}"})
    return _SESSION


def upload_xlsx(xlsx_path: Path) -> Optional[dict]:
    """Upload xlsx_path as an attachment to the configured Paperclip issue.

    Returns the attachment response dict, or None if env vars are not set
    (allows the service to run without Paperclip credentials in dev/test).
    """
    api_url = _env("PAPERCLIP_API_URL")
    issue_id = _env("PAPERCLIP_ISSUE_ID")
    company_id = _env("PAPERCLIP_COMPANY_ID")

    if not all([api_url, issue_id, company_id]):
        _log("warn", "paperclip_upload_skipped", reason="PAPERCLIP_API_URL/ISSUE_ID/COMPANY_ID not set")
        return None

    if not xlsx_path.exists():
        _log("warn", "paperclip_upload_skipped", reason="file not found", path=str(xlsx_path))
        return None

    url = f"{api_url}/api/companies/{company_id}/issues/{issue_id}/attachments"
    with xlsx_path.open("rb") as fh:
        try:
            resp = _session().post(url, files={"file": (xlsx_path.name, fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}, timeout=30)
            resp.raise_for_status()
            result = resp.json()
            _log("info", "paperclip_upload_ok", filename=xlsx_path.name, attachment_id=result.get("id"))
            return result
        except requests.HTTPError as exc:
            _log("error", "paperclip_upload_failed", status=exc.response.status_code, detail=exc.response.text[:200])
            return None
        except Exception as exc:
            _log("error", "paperclip_upload_failed", error=str(exc))
            return None


def list_attachments() -> list[dict]:
    """Return all xlsx attachments on the configured issue."""
    api_url = _env("PAPERCLIP_API_URL")
    issue_id = _env("PAPERCLIP_ISSUE_ID")

    if not all([api_url, issue_id]):
        return []

    url = f"{api_url}/api/issues/{issue_id}/attachments"
    try:
        resp = _session().get(url, timeout=15)
        resp.raise_for_status()
        attachments = resp.json()
        return [a for a in (attachments if isinstance(attachments, list) else attachments.get("data", []))
                if str(a.get("filename", "")).endswith(".xlsx")]
    except Exception as exc:
        _log("warn", "paperclip_list_attachments_failed", error=str(exc))
        return []
