"""Sweeper — poll active Zernio conversations to catch missed webhook deliveries.

Zernio webhooks occasionally miss delivery (confirmed dispatch gaps). The sweeper
runs every SWEEP_INTERVAL seconds, scans state files for active conversations, and
re-processes any inbound messages that were never delivered as webhook events.

Deduplication is handled by the same _ack_event / _SEEN_EVENTS mechanism used for
live webhooks — the sweeper calls seen_fn(f"sweep:{msg_id}") so a message that DID
arrive via webhook is not processed a second time by the sweeper.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Callable

from zernio_client import _log, list_conversation_messages

SWEEP_INTERVAL = 300  # 5 minutes


def _build_synthetic_event(msg: dict, conv_id: str, contact_id: str, account_id: str) -> dict:
    """Map a Zernio REST message object to the webhook event shape expected by _parse_event.

    REST messages carry senderId (no '+') and optionally senderPhoneNumber (with '+').
    Webhook events carry message.sender.id (no '+') and conversation.participantUsername (with '+').
    """
    sender_id = msg.get("senderId") or ""
    sender_phone = msg.get("senderPhoneNumber") or ""
    participant_username = sender_phone or (f"+{sender_id}" if sender_id else "")
    return {
        "event": "message.received",
        "message": {
            "id": msg.get("id") or "",
            "text": msg.get("text") or "",
            "attachments": msg.get("attachments") or [],
            "sender": {"id": sender_id},
        },
        "conversation": {
            "id": conv_id,
            "contactId": contact_id,
            "participantUsername": participant_username,
        },
        "account": {"id": account_id},
    }


def sweep_once(
    seen_fn: Callable[[str], bool],
    process_fn: Callable[[dict, bool], None],
    dry_run: bool,
) -> int:
    """Poll active conversations for unprocessed inbound messages.

    seen_fn(event_id) — same contract as _ack_event: returns True if already
    processed (and marks it seen on first call so it won't be reprocessed).
    process_fn(event, dry_run) — called for each new inbound message.
    Returns count of messages submitted for processing.
    """
    state_dir = Path(os.environ.get("METER_STATE_DIR", "/data/meter-intake-state"))
    if not state_dir.exists():
        return 0

    submitted = 0
    for state_file in state_dir.glob("*.json"):
        try:
            state = json.loads(state_file.read_text())
        except Exception:
            continue

        conv_id = state.get("conversation_id", "")
        contact_id = state.get("contact_id", "")
        account_id = state.get("account_id", "")
        if not conv_id:
            continue

        try:
            messages = list_conversation_messages(conv_id, limit=20)
        except Exception as exc:
            _log("warn", "sweeper_fetch_failed", conv_id=conv_id[:24], error=str(exc)[:120])
            continue

        for msg in messages:
            msg_id = msg.get("id") or ""
            if not msg_id:
                continue

            # Skip outbound messages (our own replies)
            direction = (msg.get("direction") or msg.get("type") or "").lower()
            if direction and "inbound" not in direction and "incoming" not in direction:
                continue

            sweep_event_id = f"sweep:{msg_id}"
            if seen_fn(sweep_event_id):
                continue

            event = _build_synthetic_event(msg, conv_id, contact_id, account_id)
            _log("info", "sweeper_reprocessing_missed_message", msg_id=msg_id[:24], conv_id=conv_id[:24])
            process_fn(event, dry_run)
            submitted += 1

    return submitted


def start_sweeper(
    seen_fn: Callable[[str], bool],
    process_fn: Callable[[dict, bool], None],
    dry_run_fn: Callable[[], bool],
) -> threading.Thread:
    """Start a daemon sweeper thread. Returns the thread (already started)."""

    def _loop() -> None:
        _log("info", "sweeper_started", interval_seconds=SWEEP_INTERVAL)
        while True:
            time.sleep(SWEEP_INTERVAL)
            try:
                count = sweep_once(seen_fn, process_fn, dry_run_fn())
                if count:
                    _log("info", "sweeper_cycle_done", submitted=count)
            except Exception as exc:
                _log("error", "sweeper_cycle_error", error=str(exc)[:200])

    t = threading.Thread(target=_loop, name="meter-sweeper", daemon=True)
    t.start()
    return t
