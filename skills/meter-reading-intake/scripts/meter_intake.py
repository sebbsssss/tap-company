"""tap-meter-intake — Zernio webhook receiver for meter readings.

Routes:
  POST /webhook/zernio       — Zernio message.received event
  GET  /healthz              — health check
  POST /admin/register-webhook — (re)register Zernio webhook (idempotent)

Env vars:
  ZERNIO_API_KEY             — required; never logged
  ANTHROPIC_API_KEY          — required for meter reading extraction + query parsing
  METER_INTAKE_DRY_RUN       — 'true' (default) or 'false'; guards all outbound sends
  UTILITY_LOG_DIR            — override xlsx storage path (default /data/utility-logs)
  METER_STATE_DIR            — conversation state dir (default /data/meter-intake-state)
  WEBHOOK_CALLBACK_URL       — used by /admin/register-webhook if not passed in body
  ERWAN_CONTACT_ID           — Zernio contact for daily digest sends
  ERWAN_INBOX_ID             — Zernio inbox for daily digest sends
  PAPERCLIP_API_URL          — for xlsx attachment upload
  PAPERCLIP_API_KEY          — for xlsx attachment upload
  PAPERCLIP_ISSUE_ID         — issue to attach xlsx to (set to THE-17390's id)
  PAPERCLIP_COMPANY_ID       — TAP company id
  ALLOWLISTED_NUMBERS        — comma-separated E.164 numbers allowed to use the service

Operator approval gate: all send_reply calls default dry_run=True.
Set METER_INTAKE_DRY_RUN=false in Fly Secrets to enable live sends.

Low-confidence re-prompt: if meter_calculator returns confidence='low', we ask for a
retake rather than aborting. Conversation state is persisted per contact_id so that
multi-turn exchanges (missing fields + retakes) work across separate webhook events.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

import conversation_state as cs
from caption_parser import parse_caption
from meter_calculator import extract_reading
from query_handler import decline_message, handle_query, is_allowlisted, looks_like_query
from utility_log import append_reading
from zernio_client import _log, download_image, ensure_webhook, send_reply

app = FastAPI(title="tap-meter-intake", version="0.2.0")

LOW_CONFIDENCE_REPLY = (
    "The reading is not clear — please resend a front-facing photo with good lighting."
)


def _dry_run() -> bool:
    return os.environ.get("METER_INTAKE_DRY_RUN", "true").lower() != "false"


def _sender_phone(event: dict) -> str | None:
    """Extract the sender's E.164 phone number from a Zernio event."""
    sender = event.get("sender") or {}
    return sender.get("phone") or event.get("sender_phone") or None


def _contact_id(event: dict) -> str:
    return (
        event.get("contact_id")
        or (event.get("sender") or {}).get("id")
        or ""
    )


def _inbox_id(event: dict) -> str:
    return event.get("inbox_id") or ""


def _attachments(event: dict) -> list[dict]:
    return event.get("attachments") or []


def _first_image(attachments: list[dict]) -> tuple[str | None, str]:
    """Return (url, mime_type) of first image attachment, or (None, 'image/jpeg')."""
    for att in attachments:
        att_type = (att.get("content_type") or att.get("type") or "").lower()
        if "image" in att_type:
            url = att.get("data_url") or att.get("url") or ""
            mime = "image/png" if "png" in att_type else "image/jpeg"
            return url, mime
    return None, "image/jpeg"


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True, "dry_run": _dry_run()}


# ---------------------------------------------------------------------------
# Admin: register Zernio webhook
# ---------------------------------------------------------------------------


@app.post("/admin/register-webhook")
async def admin_register_webhook(request: Request) -> JSONResponse:
    body = await request.json()
    callback_url = body.get("callback_url") or os.environ.get("WEBHOOK_CALLBACK_URL", "")
    if not callback_url:
        raise HTTPException(400, "callback_url required (body or WEBHOOK_CALLBACK_URL env)")
    result = ensure_webhook(callback_url)
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Core message processing
# ---------------------------------------------------------------------------


async def _process_message(event: dict, dry_run: bool) -> None:  # noqa: C901
    """Background task — process one message.received event with conversation state."""
    phone = _sender_phone(event)
    contact_id = _contact_id(event)
    inbox_id = _inbox_id(event)
    text = (event.get("caption") or event.get("content") or "").strip()
    attachments = _attachments(event)
    image_url, mime_type = _first_image(attachments)
    has_image = bool(image_url)

    _log("info", "message_received", contact_id=contact_id, has_image=has_image, text=text[:80])

    # --- access control ---
    if not is_allowlisted(phone):
        send_reply(inbox_id, contact_id, decline_message(), dry_run=dry_run)
        return

    # --- query path ---
    if looks_like_query(text, has_image):
        _log("info", "query_path", contact_id=contact_id)
        reply = handle_query(text)
        send_reply(inbox_id, contact_id, reply, dry_run=dry_run)
        return

    # --- meter reading path: load or create conversation state ---
    state = cs.load(contact_id) or cs.new_state(contact_id, inbox_id)

    # If sender just replied to a retake request and provides a new image
    if state.get("awaiting_retake") and has_image:
        state["pending_image_url"] = image_url
        state["pending_mime"] = mime_type
        state["awaiting_retake"] = False

    # Merge any new caption fields
    if text:
        parsed = parse_caption(text)
        state = cs.merge_parsed(state, parsed)

    # Store image if provided and none cached yet
    if has_image and not state.get("pending_image_url"):
        state["pending_image_url"] = image_url
        state["pending_mime"] = mime_type

    # --- ask for missing fields one at a time ---
    missing = cs.missing_fields(state)
    if missing:
        question = cs.next_question(missing)
        cs.save(state)
        send_reply(inbox_id, contact_id, question, dry_run=dry_run)
        return

    # --- we have all fields; need an image ---
    if not state.get("pending_image_url"):
        cs.save(state)
        send_reply(inbox_id, contact_id, "Please send the meter photo.", dry_run=dry_run)
        return

    # --- download image ---
    try:
        image_bytes = download_image(state["pending_image_url"])
    except Exception as exc:
        _log("error", "image_download_failed", error=str(exc))
        cs.save(state)
        send_reply(inbox_id, contact_id, "Could not download the photo — please resend.", dry_run=dry_run)
        return

    # --- extract reading ---
    calc = extract_reading(
        image_bytes,
        mime_type=state.get("pending_mime", "image/jpeg"),
        context={
            "property": state["resolved"]["property"],
            "utility_type": state["resolved"]["utility_type"],
        },
    )

    current_reading = calc.get("reading")
    confidence = calc.get("confidence", "low")

    # Low-confidence or unreadable → ask for retake
    if current_reading is None or confidence == "low":
        _log("warn", "low_confidence_retake", confidence=confidence, contact_id=contact_id)
        state["awaiting_retake"] = True
        state["pending_image_url"] = None  # clear stale image
        cs.save(state)
        send_reply(inbox_id, contact_id, LOW_CONFIDENCE_REPLY, dry_run=dry_run)
        return

    # --- all good: append to utility log ---
    reading_date = cs.get_resolved_date(state)
    if reading_date is None:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        reading_date = datetime.now(tz=ZoneInfo("Asia/Singapore")).date()

    row = append_reading(
        reading_date=reading_date,
        property_name=state["resolved"]["property"],  # type: ignore[arg-type]
        meter_id=calc.get("meter_id"),
        utility_type=state["resolved"]["utility_type"],  # type: ignore[arg-type]
        current_reading=float(current_reading),
    )

    # Clear conversation state — this exchange is complete
    cs.clear(contact_id)

    # --- reply confirmation ---
    delta = row.get("delta")
    if delta is not None:
        delta_str = f"+{delta:.1f}" if float(delta) >= 0 else f"{delta:.1f}"
    else:
        delta_str = "? (first reading for this meter)"

    confirmation = f"Logged: {row['property']} {row['utility_type']} {delta_str} (reading: {current_reading})"
    send_reply(inbox_id, contact_id, confirmation, dry_run=dry_run)
    _log("info", "reading_logged", property=row["property"], utility_type=row["utility_type"], delta=delta)


@app.post("/webhook/zernio")
async def zernio_webhook(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    body = await request.json()
    event_type = (
        body.get("event")
        or body.get("type")
        or body.get("event_type")
        or ""
    )
    _log("info", "webhook_received", event_type=event_type)

    if event_type != "message.received":
        return JSONResponse({"ignored": True, "event_type": event_type})

    # Accept immediately; process in background (Zernio expects fast 200)
    background_tasks.add_task(_process_message, body, _dry_run())
    return JSONResponse({"status": "accepted"}, status_code=200)
