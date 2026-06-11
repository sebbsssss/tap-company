"""tap-meter-intake — Zernio webhook receiver for meter readings.

Routes:
  POST /webhook/zernio       — Zernio message.received event
  GET  /healthz              — health check
  POST /admin/register-webhook — (re)register Zernio webhook (idempotent)

Env vars:
  ZERNIO_API_KEY             — required; never logged
  ANTHROPIC_API_KEY          — required for meter reading extraction
  METER_INTAKE_DRY_RUN       — 'true' (default) or 'false'; guards all outbound sends
  UTILITY_LOG_DIR            — override xlsx storage path (default /data/utility-logs)
  WEBHOOK_CALLBACK_URL       — used by /admin/register-webhook if not passed in body
  ERWAN_CONTACT_ID           — Zernio contact for daily digest sends
  ERWAN_INBOX_ID             — Zernio inbox for daily digest sends

Operator approval gate: all send_reply calls default dry_run=True.
Set METER_INTAKE_DRY_RUN=false in Fly Secrets to enable live sends.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from caption_parser import ask_for_missing, missing_fields, parse_caption
from meter_calculator import extract_reading
from utility_log import append_reading
from zernio_client import _log, download_image, ensure_webhook, send_reply

app = FastAPI(title="tap-meter-intake", version="0.1.0")


def _dry_run() -> bool:
    return os.environ.get("METER_INTAKE_DRY_RUN", "true").lower() != "false"


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
# Zernio webhook receiver
# ---------------------------------------------------------------------------


async def _process_message(event: dict, dry_run: bool) -> None:
    """Background task — process one message.received event end-to-end."""
    msg_id = event.get("id", "unknown")
    # Contact/inbox IDs vary slightly across Zernio webhook versions
    contact_id = (
        event.get("contact_id")
        or (event.get("sender") or {}).get("id")
        or ""
    )
    inbox_id = event.get("inbox_id") or ""
    caption = (event.get("caption") or event.get("content") or "").strip()
    attachments: list[dict] = event.get("attachments") or []

    _log("info", "message_processing_start", msg_id=msg_id, caption=caption[:120])

    # --- parse caption ---
    parsed = parse_caption(caption)
    missing = missing_fields(parsed)
    if missing:
        reply = ask_for_missing(missing)
        _log("info", "caption_incomplete", missing=missing)
        send_reply(inbox_id, contact_id, reply, dry_run=dry_run)
        return

    # --- find image attachment ---
    image_url: str | None = None
    mime_type = "image/jpeg"
    for att in attachments:
        att_type = (att.get("content_type") or att.get("type") or "").lower()
        if "image" in att_type:
            image_url = att.get("data_url") or att.get("url") or ""
            if "png" in att_type:
                mime_type = "image/png"
            break

    if not image_url:
        _log("warn", "no_image_attachment", msg_id=msg_id)
        send_reply(
            inbox_id,
            contact_id,
            "No image found — please resend the meter photo.",
            dry_run=dry_run,
        )
        return

    # --- download image ---
    try:
        image_bytes = download_image(image_url)
    except Exception as exc:
        _log("error", "image_download_failed", error=str(exc))
        send_reply(
            inbox_id,
            contact_id,
            "Could not download the photo — please resend.",
            dry_run=dry_run,
        )
        return

    # --- extract reading ---
    calc = extract_reading(
        image_bytes,
        mime_type=mime_type,
        context={
            "property": parsed["property"],
            "utility_type": parsed["utility_type"],
        },
    )

    current_reading = calc.get("reading")
    if current_reading is None:
        _log("warn", "no_reading_extracted", confidence=calc.get("confidence"), notes=calc.get("notes"))
        send_reply(
            inbox_id,
            contact_id,
            "Could not read the meter value from the photo — please resend a clearer image.",
            dry_run=dry_run,
        )
        return

    # --- append to utility log ---
    row = append_reading(
        reading_date=parsed["reading_date"],  # type: ignore[arg-type]
        property_name=parsed["property"],  # type: ignore[arg-type]
        meter_id=calc.get("meter_id"),
        utility_type=parsed["utility_type"],  # type: ignore[arg-type]
        current_reading=float(current_reading),
    )

    # --- reply confirmation ---
    delta = row.get("delta")
    if delta is not None:
        delta_str = f"+{delta:.1f}" if float(delta) >= 0 else f"{delta:.1f}"
    else:
        delta_str = "? (first reading for this meter)"
    confirmation = (
        f"Logged: {row['property']} {row['utility_type']} {delta_str} "
        f"(reading: {current_reading})"
    )
    send_reply(inbox_id, contact_id, confirmation, dry_run=dry_run)
    _log(
        "info",
        "message_processing_done",
        property=row["property"],
        utility_type=row["utility_type"],
        delta=delta,
    )


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
