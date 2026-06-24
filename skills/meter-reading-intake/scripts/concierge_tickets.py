"""Ticket creation handler for the Tenant Concierge.

Only imported when CONCIERGE_TICKETS_ENABLED=true. Presents a multi-turn flow:
  1. Collect property + room
  2. Classify issue category via CRM GET /com/service/categories/
  3. Echo back details for tenant confirmation
  4. POST /com/service/tickets/ (or dry-run log)

Dry-run guard: if dry_run=True, logs intent but never POSTs to CRM.

Env vars:
  CRM_API_BASE      — CRM base URL (default https://crm-api.theassemblyplace.com)
  CRM_STAFF_API_KEY — x-api-key header value
  ANTHROPIC_API_KEY — required for classify_issue
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import anthropic
import requests

from zernio_client import send_reply

MODEL = "claude-haiku-4-5-20251001"
SGT = ZoneInfo("Asia/Singapore")
_CLIENT: Optional[anthropic.Anthropic] = None


def _log(level: str, msg: str, **kwargs: object) -> None:
    payload = {"level": level, "service": "concierge-tickets", "msg": msg, **kwargs}
    print(json.dumps(payload), file=sys.stderr)


def _client() -> anthropic.Anthropic:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = anthropic.Anthropic()
    return _CLIENT


def _crm_base() -> str:
    return os.environ.get("CRM_API_BASE", "https://crm-api.theassemblyplace.com").rstrip("/")


def _crm_headers() -> dict:
    key = os.environ.get("CRM_STAFF_API_KEY") or os.environ.get("CRM_API_KEY", "")
    return {"x-api-key": key, "Accept": "application/json", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Fetch categories (cached in-process)
# ---------------------------------------------------------------------------

_CATEGORIES_CACHE: Optional[list[dict]] = None


def fetch_categories() -> list[dict]:
    """Return CRM service categories, cached for the process lifetime."""
    global _CATEGORIES_CACHE
    if _CATEGORIES_CACHE is not None:
        return _CATEGORIES_CACHE
    try:
        resp = requests.get(
            f"{_crm_base()}/com/service/categories/",
            headers=_crm_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        cats = data.get("results") if isinstance(data, dict) else data
        _CATEGORIES_CACHE = cats if isinstance(cats, list) else []
        _log("info", "categories_fetched", count=len(_CATEGORIES_CACHE))
    except Exception as exc:
        _log("error", "categories_fetch_failed", error=str(exc)[:200])
        _CATEGORIES_CACHE = []
    return _CATEGORIES_CACHE


# ---------------------------------------------------------------------------
# Classify the issue against available categories
# ---------------------------------------------------------------------------

def classify_issue(description: str, categories: list[dict]) -> Optional[dict]:
    """Use Claude to pick the best matching category for the description.

    Returns a category dict {id, name, service, recommended_priority} or None.
    """
    if not categories:
        return None

    cats_summary = "\n".join(
        f"  id={c['id']} | service={c['service']} | name={c['name']} | priority={c['recommended_priority']}"
        for c in categories
    )

    system = f"""\
You are a maintenance ticket classifier for a Singapore coliving company.
Given a tenant's issue description, pick the BEST matching category from the list.

Categories:
{cats_summary}

Respond with a single JSON object — no markdown:
{{"id": <integer id>, "name": "<name>", "service": "<service>", "priority": <1-4>}}

If nothing matches, respond: {{"id": null}}
"""
    try:
        msg = _client().messages.create(
            model=MODEL,
            max_tokens=128,
            system=system,
            messages=[{"role": "user", "content": description}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip().rstrip("```").strip()
        result = json.loads(raw)
        if result.get("id") is None:
            _log("info", "classify_no_match", description_preview=description[:60])
            return None
        _log("info", "classify_matched", cat_id=result["id"], name=result.get("name"))
        return result
    except Exception as exc:
        _log("error", "classify_failed", error=str(exc)[:200])
        return None


# ---------------------------------------------------------------------------
# CRM ticket POST
# ---------------------------------------------------------------------------

def post_ticket(
    *,
    room: str,
    category_id: int,
    priority: int,
    remarks: str,
    raised_by: str,
    dry_run: bool,
) -> Optional[dict]:
    """POST a ticket to CRM. Returns response dict or a dry-run sentinel."""
    payload = {
        "room": room,
        "category": category_id,
        "priority": priority,
        "remarks": remarks,
        "raised_by": raised_by,
        "status": "Open",
        "source": "whatsapp-concierge",
        "raised_at": datetime.now(tz=SGT).isoformat(),
    }
    _log(
        "info" if dry_run else "warn",
        "post_ticket",
        dry_run=dry_run,
        room=room,
        category_id=category_id,
        priority=priority,
        remarks_preview=remarks[:60],
    )
    if dry_run:
        return {"dry_run": True, "would_post": payload}
    try:
        resp = requests.post(
            f"{_crm_base()}/com/service/tickets/",
            headers=_crm_headers(),
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        ticket = resp.json()
        _log("info", "ticket_created", ticket_id=ticket.get("id"), room=room)
        return ticket
    except Exception as exc:
        _log("error", "ticket_post_failed", error=str(exc)[:200])
        raise


# ---------------------------------------------------------------------------
# Collect property / room from the tenant message using Claude
# ---------------------------------------------------------------------------

_KNOWN_PROPERTIES = (
    "18 JALAN JINTAN (18JJ), 18 PENHAS (18P), 51 MIDDLE ROAD (51MR), "
    "TLKR CAMPUS / BLOCK A / BLOCK B, MILL@32, 96 OWEN ROAD"
)

_COLLECT_SYSTEM = f"""\
You are a ticket intake assistant for The Assembly Place (TAP), Singapore.
A tenant is raising a maintenance request via WhatsApp.

TAP properties: {_KNOWN_PROPERTIES}

Extract from their message:
  - property: canonical property name (or null if not mentioned)
  - room: room or unit identifier e.g. "B-12", "Room 3", "#02-01" (or null)
  - issue_description: a concise description of the problem (or the full text if unclear)

Respond with ONLY a JSON object — no markdown:
{{"property": ..., "room": ..., "issue_description": ...}}
"""


def _extract_ticket_details(text: str) -> dict:
    try:
        msg = _client().messages.create(
            model=MODEL,
            max_tokens=200,
            system=_COLLECT_SYSTEM,
            messages=[{"role": "user", "content": text}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip().rstrip("```").strip()
        return json.loads(raw)
    except Exception as exc:
        _log("error", "extract_ticket_details_failed", error=str(exc)[:200])
        return {"property": None, "room": None, "issue_description": text}


# ---------------------------------------------------------------------------
# Multi-turn ticket flow
# ---------------------------------------------------------------------------

def handle_ticket_flow(
    text: str,
    event: dict,
    conversation_id: str,
    account_id: str,
    dry_run: bool,
) -> None:
    """Full ticket flow: extract details → classify → echo-confirm → post.

    Single-turn: extract everything possible from the first message, ask only for
    what's missing, then confirm before posting. In the current single-turn design
    we extract and classify in one pass; confirmation echo is sent before posting.
    """
    details = _extract_ticket_details(text)
    property_name = details.get("property")
    room = details.get("room")
    issue = details.get("issue_description") or text

    # If property or room missing, ask and escalate to human to complete
    if not property_name or not room:
        missing = []
        if not property_name:
            missing.append("your property name (e.g. 18JJ, 51MR, MILL@32)")
        if not room:
            missing.append("your room number")
        ask = "To log your request, could you also share " + " and ".join(missing) + "?"
        send_reply(conversation_id, account_id, ask, dry_run=dry_run)
        _log("info", "ticket_missing_fields", missing=missing)
        return

    # Classify against CRM categories
    categories = fetch_categories()
    matched = classify_issue(issue, categories)

    if matched:
        category_id = matched["id"]
        category_name = matched["name"]
        service = matched["service"]
        priority = matched.get("priority") or matched.get("recommended_priority") or 3
    else:
        # Fallback: General Repairs (id=6, P4) from the captured fixture
        category_id = 6
        category_name = "General Repairs"
        service = "Maintenance"
        priority = 4

    priority_label = {1: "Emergency", 2: "High", 3: "Normal", 4: "Low"}.get(int(priority), "Normal")

    # Echo confirmation message to tenant
    confirm_msg = (
        f"I'll log the following ticket:\n\n"
        f"📍 {property_name} — {room}\n"
        f"🔧 {service}: {category_name}\n"
        f"⚡ Priority: {priority_label}\n"
        f"📝 {issue}\n\n"
        f"Our team will follow up with you shortly."
    )
    send_reply(conversation_id, account_id, confirm_msg, dry_run=dry_run)

    # Post ticket
    try:
        phone = event.get("phone") or "whatsapp-concierge"
        post_ticket(
            room=f"{property_name} / {room}",
            category_id=category_id,
            priority=priority,
            remarks=issue,
            raised_by=phone,
            dry_run=dry_run,
        )
    except Exception as exc:
        _log("error", "ticket_post_error_after_confirm", error=str(exc)[:200])
        send_reply(
            conversation_id,
            account_id,
            "Your request has been noted. Our team will follow up — there was a brief issue logging it in our system.",
            dry_run=dry_run,
        )
