"""TAP Ops Portal — FastAPI backend.

CRM proxy + magic-link auth + audit log.
All routes except /health and /auth/* require a valid ops_session cookie.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
from datetime import datetime, timezone
from typing import Optional

from fastapi import Cookie, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import audit as audit_mod
import auth
import crm_client
from models import CommentRequest, StatusChangeRequest

# ── Kill switch: read env per-request so toggling via Fly env update takes effect
# without a code redeploy. (Fly secrets update + `fly deploy` required either way,
# but the logic branch is the env var — not a compiled constant.)

def _bot_enabled() -> bool:
    return os.environ.get("OPS_PORTAL_BOT_ENABLED", "true").lower() not in ("false", "0", "off")


FRONTEND_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

app = FastAPI(title="TAP Ops Portal", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _require_session(ops_session: Optional[str]) -> str:
    """Validate session cookie, return actor email, raise 401 if invalid."""
    if not ops_session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    email = auth.validate_session(ops_session)
    if not email:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return email


def _crm_error(exc: Exception) -> HTTPException:
    if isinstance(exc, urllib.error.HTTPError):
        return HTTPException(status_code=exc.code, detail=f"CRM upstream error {exc.code}: {exc.reason}")
    return HTTPException(status_code=502, detail=f"CRM unreachable: {exc}")


def _age_hours(created: Optional[str]) -> Optional[int]:
    if not created:
        return None
    try:
        ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
        return int((datetime.now(tz=timezone.utc) - ts).total_seconds() / 3600)
    except (ValueError, TypeError):
        return None


def _enrich_ticket(ticket: dict, comments: Optional[list] = None) -> dict:
    """Add computed fields: age_hours, last_action_by, bot_pending."""
    comments = comments or []
    auto_stamps = [
        c.get("created") for c in comments
        if "[AUTO-REPLY" in (c.get("comment") or "") and c.get("created")
    ]
    member_stamps = [
        c.get("created") for c in comments
        if not c.get("is_reply") and c.get("created")
    ]

    last_action_by: Optional[str] = None
    if comments:
        latest = max(comments, key=lambda c: c.get("created") or "")
        last_action_by = "staff" if latest.get("is_reply") else "member"

    bot_pending = bool(auto_stamps) and (
        not member_stamps or max(auto_stamps) > max(member_stamps)
    )

    return {
        **ticket,
        "age_hours": _age_hours(ticket.get("created")),
        "last_action_by": last_action_by,
        "bot_pending": bot_pending,
    }


# ── Health ──────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["ops"])
def health() -> dict:
    return {"status": "ok", "bot_enabled": _bot_enabled()}


# ── Auth ────────────────────────────────────────────────────────────────────────

@app.get("/auth/magic-link", tags=["auth"])
def magic_link_request(email: str = Query(...)) -> dict:
    email = email.strip().lower()
    if not auth.is_allowed(email):
        raise HTTPException(status_code=403, detail="Email not in allowlist")
    token = auth.generate_magic_link(email)
    base_url = os.environ.get("OPS_PORTAL_BASE_URL", "http://localhost:8000")
    link = f"{base_url}/auth/verify?token={token}"
    auth.send_magic_link(email, link)
    resp: dict = {"message": "Magic link sent"}
    # Only expose the link in non-production environments (e.g. staging without SMTP)
    if not os.environ.get("SMTP_HOST"):
        resp["link"] = link
    return resp


@app.get("/auth/verify", tags=["auth"])
def magic_link_verify(
    token: str = Query(...),
    response: Response = None,  # type: ignore[assignment]
) -> dict:
    email = auth.verify_magic_link(token)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired magic link")
    session_token = auth.create_session(email)
    response.set_cookie(
        key="ops_session",
        value=session_token,
        max_age=30 * 24 * 3600,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return {"message": "Authenticated", "email": email}


# ── Tickets — list ──────────────────────────────────────────────────────────────

@app.get("/api/tickets/", tags=["tickets"])
def list_tickets(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    property: Optional[str] = None,
    assignee: Optional[str] = None,
    ops_session: Optional[str] = Cookie(default=None),
) -> dict:
    _require_session(ops_session)

    qs_parts: list[str] = ["limit=100", "ordering=-id"]
    if status:
        import urllib.parse
        qs_parts.append(f"status__in={urllib.parse.quote(status)}")

    path = f"/com/service/tickets/?{'&'.join(qs_parts)}"
    try:
        data = crm_client.crm_get(path, cached=True)
    except Exception as exc:
        raise _crm_error(exc)

    tickets: list[dict] = data.get("results", [])

    # Post-filter (CRM doesn't support all filters natively)
    if property:
        tickets = [
            t for t in tickets
            if _prop_name(t) == property
        ]
    if assignee:
        tickets = [
            t for t in tickets
            if (t.get("assigned_to") or {}).get("name") == assignee
        ]
    if priority:
        tickets = [
            t for t in tickets
            if (t.get("priority") or {}).get("name", "").lower() == priority.lower()
        ]

    return {"count": len(tickets), "results": [_enrich_ticket(t) for t in tickets]}


def _prop_name(ticket: dict) -> Optional[str]:
    return (
        ((ticket.get("room") or {}).get("unit") or {}).get("prop") or {}
    ).get("name")


# ── Tickets — detail ────────────────────────────────────────────────────────────

@app.get("/api/tickets/{ticket_id}", tags=["tickets"])
def get_ticket(
    ticket_id: int,
    ops_session: Optional[str] = Cookie(default=None),
) -> dict:
    _require_session(ops_session)
    try:
        ticket = crm_client.crm_get(f"/com/service/tickets/{ticket_id}/")
        comment_data = crm_client.crm_get(
            f"/com/service/ticket_comment/?ticket={ticket_id}&limit=200"
        )
        comments: list[dict] = comment_data.get("results", [])
    except Exception as exc:
        raise _crm_error(exc)

    ticket_audit = [
        e for e in audit_mod.read_audit(200)
        if str(e.get("ticket")) == str(ticket_id)
    ]

    return {
        **_enrich_ticket(ticket, comments),
        "comments": comments,
        "audit_entries": ticket_audit,
    }


# ── Tickets — write actions ─────────────────────────────────────────────────────

def _post_crm_comment(ticket_id: int, comment: str, is_internal: bool = False) -> dict:
    payload: dict = {"ticket": ticket_id, "comment": comment, "is_reply": True}
    if is_internal:
        payload["is_internal"] = True
    return crm_client.crm_post("/com/service/ticket_comment/", payload)


@app.post("/api/tickets/{ticket_id}/comment", tags=["tickets"])
def post_comment(
    ticket_id: int,
    body: CommentRequest,
    ops_session: Optional[str] = Cookie(default=None),
) -> dict:
    actor = _require_session(ops_session)
    try:
        result = _post_crm_comment(ticket_id, body.comment)
    except Exception as exc:
        audit_mod.write_audit(actor, "comment", ticket_id, _exc_status(exc))
        raise _crm_error(exc)
    audit_mod.write_audit(actor, "comment", ticket_id, 200)
    crm_client.invalidate_cache(f"/com/service/tickets/{ticket_id}/")
    return result


@app.post("/api/tickets/{ticket_id}/comment_internal", tags=["tickets"])
def post_internal_comment(
    ticket_id: int,
    body: CommentRequest,
    ops_session: Optional[str] = Cookie(default=None),
) -> dict:
    actor = _require_session(ops_session)
    try:
        result = _post_crm_comment(ticket_id, body.comment, is_internal=True)
    except Exception as exc:
        audit_mod.write_audit(actor, "comment_internal", ticket_id, _exc_status(exc))
        raise _crm_error(exc)
    audit_mod.write_audit(actor, "comment_internal", ticket_id, 200)
    crm_client.invalidate_cache(f"/com/service/tickets/{ticket_id}/")
    return result


@app.post("/api/tickets/{ticket_id}/status", tags=["tickets"])
def change_status(
    ticket_id: int,
    body: StatusChangeRequest,
    ops_session: Optional[str] = Cookie(default=None),
) -> dict:
    actor = _require_session(ops_session)
    try:
        result = crm_client.crm_patch(
            f"/com/service/tickets/{ticket_id}/", {"status": body.status}
        )
    except Exception as exc:
        audit_mod.write_audit(actor, f"status:{body.status}", ticket_id, _exc_status(exc))
        raise _crm_error(exc)
    audit_mod.write_audit(actor, f"status:{body.status}", ticket_id, 200)
    crm_client.invalidate_cache(f"/com/service/tickets/{ticket_id}/")
    return result


@app.post("/api/tickets/{ticket_id}/approve_draft", tags=["tickets"])
def approve_draft(
    ticket_id: int,
    body: CommentRequest,
    ops_session: Optional[str] = Cookie(default=None),
) -> dict:
    if not _bot_enabled():
        raise HTTPException(status_code=503, detail="Bot actions disabled")
    actor = _require_session(ops_session)
    try:
        result = _post_crm_comment(ticket_id, body.comment)
    except Exception as exc:
        audit_mod.write_audit(actor, "approve_draft", ticket_id, _exc_status(exc))
        raise _crm_error(exc)
    audit_mod.write_audit(actor, "approve_draft", ticket_id, 200)
    crm_client.invalidate_cache(f"/com/service/tickets/{ticket_id}/")
    return result


@app.post("/api/tickets/{ticket_id}/edit_and_send", tags=["tickets"])
def edit_and_send(
    ticket_id: int,
    body: CommentRequest,
    ops_session: Optional[str] = Cookie(default=None),
) -> dict:
    if not _bot_enabled():
        raise HTTPException(status_code=503, detail="Bot actions disabled")
    actor = _require_session(ops_session)
    try:
        result = _post_crm_comment(ticket_id, body.comment)
    except Exception as exc:
        audit_mod.write_audit(actor, "edit_and_send", ticket_id, _exc_status(exc))
        raise _crm_error(exc)
    audit_mod.write_audit(actor, "edit_and_send", ticket_id, 200)
    crm_client.invalidate_cache(f"/com/service/tickets/{ticket_id}/")
    return result


# ── Audit log ────────────────────────────────────────────────────────────────────

@app.get("/api/audit/recent", tags=["audit"])
def recent_audit(
    limit: int = Query(50, ge=1, le=500),
    ops_session: Optional[str] = Cookie(default=None),
) -> dict:
    _require_session(ops_session)
    return {"entries": audit_mod.read_audit(limit)}


# ── Frontend static files ─────────────────────────────────────────────────────

if os.path.isdir(FRONTEND_PATH):
    app.mount("/", StaticFiles(directory=FRONTEND_PATH, html=True), name="frontend")


def _exc_status(exc: Exception) -> int:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code
    return 502


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
