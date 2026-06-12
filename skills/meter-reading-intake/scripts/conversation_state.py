"""Per-contact conversation state for multi-turn meter-reading intake.

State is persisted as JSON in STATE_DIR (default /data/meter-intake-state/).
Each file is keyed by contact_id and TTL-pruned after 24 h of inactivity.

State schema:
  {
    "contact_id": str,              -- Zernio conversation.contactId (state key)
    "conversation_id": str,         -- Zernio conversation.id (needed for replies)
    "account_id": str,              -- Zernio account.id (needed for replies)
    "resolved": {
      "property": str|null,
      "utility_type": str|null,
      "reading_date": str|null      -- ISO date string
    },
    "property_unverified": bool,    -- True when property accepted after loop guard
    "property_ask_count": int,      -- how many times we have asked 'Which property?'
    "fuzzy_property_suggestion": str|null,  -- near-miss candidate pending YES confirm
    "pending_image_url": str|null,
    "pending_mime": str|null,
    "awaiting_retake": bool,        -- True when we asked for a clearer photo
    "turn_history": list[dict],     -- [{role: "user"|"assistant", content: str}, ...]
    "last_question": str|null,      -- last question we sent (context for LLM brain)
    "last_activity": str            -- ISO datetime (UTC)
  }
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Optional


STATE_TTL_HOURS = 24


def _state_dir() -> Path:
    d = Path(os.environ.get("METER_STATE_DIR", "/data/meter-intake-state"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_path(contact_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", contact_id)
    return _state_dir() / f"{safe}.json"


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _expired(state: dict) -> bool:
    try:
        last = datetime.fromisoformat(state.get("last_activity", ""))
        return (datetime.now(tz=timezone.utc) - last) > timedelta(hours=STATE_TTL_HOURS)
    except (ValueError, TypeError):
        return True


def load(contact_id: str) -> Optional[dict]:
    """Return existing live state or None if absent / expired."""
    path = _state_path(contact_id)
    if not path.exists():
        return None
    try:
        state = json.loads(path.read_text())
        if _expired(state):
            path.unlink(missing_ok=True)
            return None
        return state
    except (json.JSONDecodeError, OSError):
        return None


def save(state: dict) -> None:
    state["last_activity"] = _now_iso()
    _state_path(state["contact_id"]).write_text(json.dumps(state, indent=2))


def clear(contact_id: str) -> None:
    _state_path(contact_id).unlink(missing_ok=True)


def new_state(contact_id: str, conversation_id: str, account_id: str) -> dict:
    return {
        "contact_id": contact_id,
        "conversation_id": conversation_id,
        "account_id": account_id,
        "resolved": {
            "property": None,
            "utility_type": None,
            "reading_date": None,
        },
        "property_unverified": False,
        "property_ask_count": 0,
        "fuzzy_property_suggestion": None,
        "pending_image_url": None,
        "pending_mime": "image/jpeg",
        "awaiting_retake": False,
        "turn_history": [],
        "last_question": None,
        "last_activity": _now_iso(),
    }


def merge_parsed(state: dict, parsed: dict) -> dict:
    """Merge freshly-parsed caption fields into state (don't overwrite already-resolved).

    Also propagates fuzzy_suggestion from parsed into state when no exact property found.
    """
    for field in ("property", "utility_type"):
        if state["resolved"][field] is None and parsed.get(field) is not None:
            state["resolved"][field] = parsed[field]
            if field == "property":
                # Exact match found — clear any pending fuzzy state
                state["fuzzy_property_suggestion"] = None
                state["property_ask_count"] = 0
    if state["resolved"]["reading_date"] is None and parsed.get("reading_date") is not None:
        rd = parsed["reading_date"]
        state["resolved"]["reading_date"] = rd.isoformat() if isinstance(rd, date) else rd
    # Store fuzzy suggestion when property still unresolved
    if state["resolved"]["property"] is None and parsed.get("fuzzy_suggestion"):
        state["fuzzy_property_suggestion"] = parsed["fuzzy_suggestion"]
    return state


def get_resolved_date(state: dict) -> Optional[date]:
    raw = state["resolved"].get("reading_date")
    if not raw:
        return None
    try:
        return date.fromisoformat(raw) if isinstance(raw, str) else raw
    except ValueError:
        return None


def missing_fields(state: dict) -> list[str]:
    return [k for k, v in state["resolved"].items() if v is None]


def is_complete(state: dict) -> bool:
    return not missing_fields(state) and not state.get("awaiting_retake", False)


def append_turn(state: dict, role: str, content: str, max_pairs: int = 6) -> None:
    """Append a turn to history, keeping the last max_pairs user+assistant pairs."""
    history = state.setdefault("turn_history", [])
    history.append({"role": role, "content": content})
    if len(history) > max_pairs * 2:
        state["turn_history"] = history[-(max_pairs * 2):]


def merge_brain(state: dict, brain: dict) -> dict:
    """Merge LLM brain extraction results into state.

    Brain values always win over regex pre-fill — the brain has more context.
    Only updates a field if brain returned a non-null value.
    """
    from zoneinfo import ZoneInfo
    from datetime import datetime as _dt
    SGT = ZoneInfo("Asia/Singapore")

    if brain.get("property"):
        state["resolved"]["property"] = brain["property"]
        state["fuzzy_property_suggestion"] = None
        state["property_ask_count"] = 0
    if brain.get("utility"):
        state["resolved"]["utility_type"] = brain["utility"]
    if brain.get("date"):
        d = brain["date"]
        if d == "today":
            d = _dt.now(tz=SGT).date().isoformat()
        state["resolved"]["reading_date"] = d
    return state


# ---------------------------------------------------------------------------
# Conversational prompts
# ---------------------------------------------------------------------------

FIELD_PROMPTS: dict[str, str] = {
    "property": "Which property is this for? (e.g. 18JJ, 18Penhas, 51MR, MILL@32, TLKR)",
    "utility_type": "Is this electricity, water, or gas?",
    "reading_date": "What date is this reading for? (e.g. today, 11/6, or 2026-06-11)",
}


def next_question(missing: list[str], state: Optional[dict] = None) -> str:
    """Return the most important single question to ask next."""
    for field in ("property", "utility_type", "reading_date"):
        if field in missing:
            if field == "property" and state is not None:
                suggestion = state.get("fuzzy_property_suggestion")
                if suggestion:
                    return f"Did you mean *{suggestion}*? Reply YES to confirm, or send the correct property name."
            return FIELD_PROMPTS[field]
    return FIELD_PROMPTS[missing[0]]
