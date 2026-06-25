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
  IRWAN_CONTACT_ID           — Zernio contact for daily digest sends
  IRWAN_INBOX_ID             — Zernio inbox for daily digest sends
  PAPERCLIP_API_URL          — for xlsx attachment upload
  PAPERCLIP_API_KEY          — for xlsx attachment upload
  PAPERCLIP_ISSUE_ID         — issue to attach xlsx to (set to THE-17390's id)
  PAPERCLIP_COMPANY_ID       — TAP company id
  ALLOWLISTED_NUMBERS        — comma-separated E.164 numbers allowed to use the service
  WEBHOOK_SECRET             — HMAC-SHA256 secret for X-Zernio-Signature verification;
                               if unset, incoming webhooks are accepted unsigned (warns in log)

Operator approval gate: all send_reply calls default dry_run=True.
Set METER_INTAKE_DRY_RUN=false in Fly Secrets to enable live sends.

Low-confidence re-prompt: if meter_calculator returns confidence='low', we ask for a
retake rather than aborting. Conversation state is persisted per contact_id so that
multi-turn exchanges (missing fields + retakes) work across separate webhook events.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import traceback as _traceback

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

import conversation_brain as cb
import conversation_state as cs
from caption_parser import parse_caption
from meter_calculator import extract_reading
from query_handler import decline_message, handle_query, is_allowlisted, looks_like_query
from utility_log import append_reading
from daily_digest import start_digest_scheduler
from sweeper import start_sweeper
from zernio_client import _log, download_image, ensure_webhook, send_reply
from concierge import handle_finance_message

_GIT_SHA = "pending"  # updated per deploy
app = FastAPI(title="tap-meter-intake", version="0.5.0")

# ---------------------------------------------------------------------------
# Event deduplication — prevents double-processing on Zernio retries
# ---------------------------------------------------------------------------
_SEEN_EVENTS: dict[str, float] = {}
_DEDUP_TTL = 300.0  # seconds — covers all Zernio retry windows

# Zernio account IDs for number routing.
# This webhook fires for ALL accounts in the workspace; only METER should run the meter flow.
_METER_ACCOUNT_ID = "6a2a31ab5f7d1751ab79f346"   # +1 856-447-1082
_FINANCE_ACCOUNT_ID = "6a3b387a9d9472faaecbc09a"  # +1 775-773-9261


def _account_route(account_id: str) -> str:
    """Return 'meter', 'finance', or 'ignore' based on Zernio destination account."""
    if account_id == _METER_ACCOUNT_ID:
        return "meter"
    if account_id == _FINANCE_ACCOUNT_ID:
        return "finance"
    return "ignore"


def _ack_event(event_id: str) -> bool:
    """Register event_id. Returns True if already seen (duplicate)."""
    now = time.monotonic()
    stale = [k for k, v in _SEEN_EVENTS.items() if now - v > _DEDUP_TTL]
    for k in stale:
        del _SEEN_EVENTS[k]
    if event_id in _SEEN_EVENTS:
        return True
    _SEEN_EVENTS[event_id] = now
    return False

LOW_CONFIDENCE_REPLY = (
    "The reading is not clear — please resend a front-facing photo with good lighting."
)


def _dry_run() -> bool:
    return os.environ.get("METER_INTAKE_DRY_RUN", "true").lower() != "false"


def _verify_hmac(raw_body: bytes, secret: str, sig_header: str) -> bool:
    """Verify X-Zernio-Signature (bare lowercase HMAC-SHA256 hex of raw body)."""
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig_header.lower())


def _parse_event(event: dict) -> dict:
    """Extract normalized fields from a Zernio message.received event.

    Authoritative webhook payload shape (per Zernio OpenAPI spec):
      message.sender.id              — phone WITHOUT '+'  (e.g. "6596370022")
      conversation.participantUsername — phone WITH '+'   (e.g. "+6596370022")
      conversation.id, conversation.contactId
      account.id

    Note: message.senderPhoneNumber and message.senderId are REST GET /messages fields
    only — they are NOT present in webhook payloads.
    """
    msg_raw = event.get("message")
    msg = msg_raw if isinstance(msg_raw, dict) else {}
    conv_raw = event.get("conversation")
    conv = conv_raw if isinstance(conv_raw, dict) else {}
    acc_raw = event.get("account")
    acc = acc_raw if isinstance(acc_raw, dict) else {}
    sender = msg.get("sender") or {}
    phone = conv.get("participantUsername") or sender.get("id") or None
    sender_id = sender.get("id") or None
    return {
        "phone": phone,
        "sender_id": sender_id,
        "contact_id": conv.get("contactId") or sender_id or "",
        "conversation_id": conv.get("id") or "",
        "account_id": acc.get("id") or "",
        "text": (msg.get("text") or "").strip(),
        "attachments": msg.get("attachments") or [],
    }


def _first_image(attachments: list[dict]) -> tuple[str | None, str]:
    """Return (url, mime_type) of first image attachment, or (None, 'image/jpeg')."""
    for att in attachments:
        att_type = (
            att.get("mimeType") or att.get("type") or att.get("content_type") or ""
        ).lower()
        url = att.get("url") or att.get("data_url") or ""
        if "image" in att_type:
            mime = "image/png" if "png" in att_type else "image/jpeg"
            return url, mime
        # fallback: infer from extension when type is missing
        if url.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
            mime = "image/png" if url.lower().endswith(".png") else "image/jpeg"
            return url, mime
    return None, "image/jpeg"


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    tb = _traceback.format_exc()
    _log("error", "unhandled_500", path=str(request.url.path),
         exc_type=type(exc).__name__, error=str(exc)[:300], traceback=tb[:800])
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


@app.on_event("startup")
async def startup_log() -> None:
    allowlist_raw = os.environ.get("ALLOWLISTED_NUMBERS", "")
    count = len([n for n in allowlist_raw.split(",") if n.strip()]) if allowlist_raw else 0
    _log("info", "app_startup", version="0.5.0", dry_run=_dry_run(), allowlist_count=count,
         webhook_secret_set=bool(os.environ.get("WEBHOOK_SECRET")))
    try:
        start_sweeper(_ack_event, _process_message, _dry_run)
    except Exception as exc:
        _log("error", "sweeper_start_failed", error=str(exc))
    try:
        start_digest_scheduler(_dry_run)
    except Exception as exc:
        _log("error", "digest_scheduler_start_failed", error=str(exc))


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True, "dry_run": _dry_run(), "version": app.version}


# ---------------------------------------------------------------------------
# Admin: register Zernio webhook
# ---------------------------------------------------------------------------


@app.post("/admin/register-webhook")
async def admin_register_webhook(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")
    callback_url = body.get("callback_url") or os.environ.get("WEBHOOK_CALLBACK_URL", "")
    if not callback_url:
        raise HTTPException(400, "callback_url required (body or WEBHOOK_CALLBACK_URL env)")
    secret = os.environ.get("WEBHOOK_SECRET") or None
    try:
        result = ensure_webhook(callback_url, secret=secret)
    except Exception as exc:
        _log("error", "register_webhook_failed", error=str(exc))
        raise HTTPException(502, f"Zernio API error: {exc}")
    return JSONResponse(result)


@app.delete("/admin/state/{contact_id}")
async def admin_delete_state(contact_id: str) -> JSONResponse:
    """Delete a conversation state file by contact_id (purge ghost/test states)."""
    cs.clear(contact_id)
    _log("info", "admin_state_deleted", contact_id=contact_id)
    return JSONResponse({"ok": True, "contact_id": contact_id})


# ---------------------------------------------------------------------------
# Core message processing
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Image persistence — download on first receipt, cache to volume
# ---------------------------------------------------------------------------


def _image_cache_path(contact_id: str, mime_type: str) -> Path:
    ext = ".png" if "png" in mime_type else ".jpg"
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", contact_id)
    d = Path(os.environ.get("METER_STATE_DIR", "/data/meter-intake-state"))
    d.mkdir(parents=True, exist_ok=True)
    return d / f"img_{safe}{ext}"


def _prefetch_image(contact_id: str, image_url: str, mime_type: str) -> str:
    """Download image immediately and save to volume. Returns local absolute path.

    Falls back to returning the original URL if download fails, so the caller
    always gets something to store in state.
    """
    try:
        img_bytes = download_image(image_url)
        path = _image_cache_path(contact_id, mime_type)
        path.write_bytes(img_bytes)
        _log("info", "image_cached_locally", path=str(path), bytes=len(img_bytes))
        return str(path)
    except Exception as exc:
        _log("warn", "image_prefetch_failed", error=str(exc), fallback="url")
        return image_url


def _load_image_bytes(image_src: str) -> bytes:
    """Read image from local path or remote URL."""
    if os.path.isabs(image_src):
        return Path(image_src).read_bytes()
    return download_image(image_src)


def _clear_pending_image(state: dict) -> None:
    """Remove cached image file and clear state."""
    src = state.get("pending_image_url") or ""
    if os.path.isabs(src):
        try:
            Path(src).unlink(missing_ok=True)
        except Exception:
            pass
    state["pending_image_url"] = None


def _process_message(event: dict, dry_run: bool) -> None:  # noqa: C901
    """Background task (sync → Starlette runs in thread pool, never blocks the event loop)."""
    try:
        _process_message_inner(event, dry_run)
    except Exception as exc:
        _log("error", "unhandled_error_in_message_processing", error=str(exc), exc_type=type(exc).__name__)


def _process_message_inner(event: dict, dry_run: bool) -> None:  # noqa: C901
    parsed_event = _parse_event(event)
    phone = parsed_event["phone"]
    sender_id = parsed_event["sender_id"]
    contact_id = parsed_event["contact_id"]
    conversation_id = parsed_event["conversation_id"]
    account_id = parsed_event["account_id"]
    text = parsed_event["text"]
    attachments = parsed_event["attachments"]
    image_url, mime_type = _first_image(attachments)
    has_image = bool(image_url)

    _log("info", "message_received", contact_id=contact_id, has_image=has_image, text=text[:80], phone=phone)

    # --- access control ---
    if not is_allowlisted(phone, sender_id):
        send_reply(conversation_id, account_id, decline_message(), dry_run=dry_run)
        return

    # --- query path (text-only messages with question keywords) ---
    if looks_like_query(text, has_image):
        _log("info", "query_path", contact_id=contact_id)
        reply = handle_query(text)
        send_reply(conversation_id, account_id, reply, dry_run=dry_run)
        return

    # --- meter reading path ---
    state = cs.load(contact_id) or cs.new_state(contact_id, conversation_id, account_id)
    state["conversation_id"] = conversation_id
    state["account_id"] = account_id

    # Persist image immediately — Zernio media URLs expire
    if has_image:
        if state.get("awaiting_retake"):
            _clear_pending_image(state)
            state["awaiting_retake"] = False
        if not state.get("pending_image_url"):
            state["pending_image_url"] = _prefetch_image(contact_id, image_url, mime_type)
            state["pending_mime"] = mime_type

    # Fast-path regex pre-fill (best-effort; brain fills what regex misses)
    if text:
        parsed = parse_caption(text)
        state = cs.merge_parsed(state, parsed)

    # Record user turn before brain call so brain sees it in history context
    cs.append_turn(state, "user", text or "(photo)")

    # --- LLM brain: single call extracts remaining fields + decides reply ---
    brain = cb.process_turn(state, text, has_image)
    cs.merge_brain(state, brain)

    # Loop guard: if brain still couldn't resolve property after 2 asks, accept raw text
    if (
        state["resolved"]["property"] is None
        and state.get("property_ask_count", 0) >= 2
        and text.strip()
    ):
        state["resolved"]["property"] = text.strip().upper()
        state["property_unverified"] = True
        state["fuzzy_property_suggestion"] = None
        state["property_ask_count"] = 0

    # Determine whether we can proceed to extraction
    missing = cs.missing_fields(state)
    image_stored = bool(state.get("pending_image_url"))

    if missing or not image_stored:
        # Brain composes the reply; fall back to a generic combined question if null
        reply_text = brain.get("reply_text")
        if not reply_text:
            if missing:
                from caption_parser import ask_for_missing
                reply_text = ask_for_missing(missing)
            else:
                reply_text = "Please send the meter photo."

        if "property" in missing:
            state["property_ask_count"] = state.get("property_ask_count", 0) + 1

        state["last_question"] = reply_text
        cs.append_turn(state, "assistant", reply_text)
        cs.save(state)
        send_reply(conversation_id, account_id, reply_text, dry_run=dry_run)
        return

    # --- all fields resolved AND image stored: load image ---
    try:
        image_bytes = _load_image_bytes(state["pending_image_url"])
    except Exception as exc:
        _log("error", "image_load_failed", src=state["pending_image_url"][:80], error=str(exc))
        _clear_pending_image(state)
        cs.save(state)
        send_reply(conversation_id, account_id, "Could not load the photo — please resend.", dry_run=dry_run)
        return

    # --- extract reading via Claude vision ---
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

    if current_reading is None or confidence == "low":
        _log("warn", "low_confidence_retake", confidence=confidence, contact_id=contact_id)
        state["awaiting_retake"] = True
        _clear_pending_image(state)
        cs.save(state)
        send_reply(conversation_id, account_id, LOW_CONFIDENCE_REPLY, dry_run=dry_run)
        return

    # --- append to utility log ---
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

    _clear_pending_image(state)
    cs.clear(contact_id)

    delta = row.get("delta")
    delta_str = (f"+{delta:.1f}" if float(delta) >= 0 else f"{delta:.1f}") if delta is not None else "? (first reading)"
    unverified_note = " *(property unverified — please confirm)*" if state.get("property_unverified") else ""
    confirmation = f"Logged: {row['property']} {row['utility_type']} {delta_str} (reading: {current_reading}){unverified_note}"
    send_reply(conversation_id, account_id, confirmation, dry_run=dry_run)
    _log("info", "reading_logged", property=row["property"], utility_type=row["utility_type"],
         delta=delta, property_unverified=state.get("property_unverified", False))


def _run_concierge(parsed_event: dict, conversation_id: str, account_id: str, dry_run: bool) -> None:
    """Background task wrapper for handle_finance_message — catches all errors."""
    try:
        handle_finance_message(parsed_event, conversation_id, account_id, dry_run)
    except Exception as exc:
        _log("error", "concierge_unhandled", error=str(exc)[:300])
        _traceback.print_exc(file=sys.stderr)


@app.post("/webhook/zernio")
async def zernio_webhook(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    raw_body = await request.body()

    secret = os.environ.get("WEBHOOK_SECRET", "")
    if secret:
        sig = request.headers.get("X-Zernio-Signature", "")
        if not _verify_hmac(raw_body, secret, sig):
            _log("warn", "webhook_hmac_invalid", sig_preview=sig[:16])
            raise HTTPException(403, "Invalid webhook signature")
    else:
        _log("warn", "webhook_secret_not_configured", detail="accepting unsigned request — set WEBHOOK_SECRET")

    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON")

    event_type = (
        body.get("event")
        or body.get("type")
        or body.get("event_type")
        or ""
    )
    _bm = body.get("message")
    msg_keys = list(_bm.keys()) if isinstance(_bm, dict) else []
    _bc = body.get("conversation")
    conv_keys = list(_bc.keys()) if isinstance(_bc, dict) else []
    _log("info", "webhook_received", event_type=event_type,
         msg_keys=msg_keys, conv_keys=conv_keys)

    if event_type != "message.received":
        return JSONResponse({"ignored": True, "event_type": event_type})

    # Deduplicate Zernio retries — Zernio resends if no 2xx within 5s
    event_id = (
        body.get("id")
        or request.headers.get("X-Zernio-Event-Id", "")
        or request.headers.get("X-Zernio-Delivery-Id", "")
    )
    if event_id and _ack_event(event_id):
        _log("info", "webhook_deduped", event_id=event_id[:16])
        return JSONResponse({"status": "already_accepted"}, status_code=200)

    # Route by destination account — this webhook fires for ALL numbers on the workspace.
    inbound_account_id = (body.get("account") or {}).get("id") or ""
    route = _account_route(inbound_account_id)
    if route == "finance":
        # Tenant Concierge — FAQ + ticket + escalate (see concierge.py)
        parsed = _parse_event(body)
        background_tasks.add_task(
            _run_concierge,
            parsed,
            parsed["conversation_id"],
            inbound_account_id,
            _dry_run(),
        )
        return JSONResponse({"status": "accepted", "route": "finance"}, status_code=200)
    if route == "ignore":
        _log("warn", "webhook_unknown_account_ignored", account_id=inbound_account_id)
        return JSONResponse({"status": "ignored", "account_id": inbound_account_id}, status_code=200)

    # Accept immediately; process in thread pool (Zernio expects fast 200)
    background_tasks.add_task(_process_message, body, _dry_run())
    return JSONResponse({"status": "accepted"}, status_code=200)
