"""LLM-first conversation handler for meter reading intake.

Replaces the one-question-at-a-time state-machine drip with a single Claude call
that understands full context, extracts all fields at once, and composes one
natural reply.

One call per inbound message:
  process_turn(state, new_text, has_image) → {intent, property, utility, date,
                                               missing_fields, reply_text}
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import anthropic

MODEL = "claude-sonnet-4-6"
SGT = ZoneInfo("Asia/Singapore")
_CLIENT: Optional[anthropic.Anthropic] = None

_PROPERTIES = (
    "18 JALAN JINTAN (aliases: 18JJ, 18JLN, 18jalan, 18jintan), "
    "18 PENHAS (aliases: 18P, 18Penhas), "
    "51 MIDDLE ROAD (aliases: 51MR, 51middle), "
    "TLKR CAMPUS (aliases: TLKR, campus), "
    "TLKR CAMPUS - BLOCK A (alias: BlockA, blockA), "
    "TLKR CAMPUS - BLOCK B (alias: BlockB, blockB), "
    "MILL@32 (aliases: Mill@32, mill32, mill 32, MILL32, Mill 32), "
    "96 OWEN ROAD (aliases: 96Owen, 96 Owen, owen)"
)

_SYSTEM = """\
You are the meter-reading intake assistant for The Assembly Place (TAP), Singapore.
Helmy WhatsApps utility meter photos with captions so they can be logged.

PROPERTIES (canonical → aliases):
{properties}

UTILITY TYPES: electricity (elec / electric / electrical / power), water, gas

Your response MUST be a single JSON object — no markdown fences, no prose, nothing else:
{{
  "intent": "new_reading" | "field_answer" | "status_query" | "other",
  "property": "<canonical property name>" | null,
  "utility": "electricity" | "water" | "gas" | null,
  "date": "YYYY-MM-DD" | null,
  "missing_fields": ["property", "utility", "date"],
  "reply_text": "<one natural SMS-style reply to Helmy, or null>"
}}

EXTRACTION RULES (apply all):
1. Be maximally liberal extracting fields from the new message AND conversation history:
   - 'electric' / 'electrical' / 'power' → electricity
   - '11th June', '11 Jun', '11/6' → ISO date using today's year
   - 'today' → today's ISO date (provided below)
   - 'Mill@32' / 'mill 32' / 'mill32' → MILL@32
   - Quoted/forwarded replies: still parse embedded field values
2. missing_fields MUST only list fields that remain null AFTER merging your extracted
   values with already_resolved. Do NOT list a field that is already in already_resolved.
3. If missing_fields=[] AND image_stored_on_volume=true → set reply_text=null.
   Do NOT tell Helmy to wait — the system runs extraction automatically.
4. If missing_fields=[] AND image_stored_on_volume=false → reply_text="Please send the meter photo."
5. If missing_fields is non-empty → craft ONE natural question covering ALL missing fields
   together. Never ask for a photo if image_stored_on_volume=true.
   Example: "Got the photo! Just need: which property (18JJ? 51MR? MILL@32?), the utility type, and the date."
6. For status_query intent ('has it been logged?', 'did you get it?') → answer from context.
7. Loop guard: if property_ask_count >= 2 AND property is still null AND user sent text →
   set property = the user's text verbatim (best-effort; mark as unverified in your notes).
   Set missing_fields accordingly.
""".format(properties=_PROPERTIES)


def _log(level: str, msg: str, **kwargs: object) -> None:
    payload = {"level": level, "service": "meter-intake", "msg": msg, **kwargs}
    print(json.dumps(payload), file=sys.stderr)


def _client() -> anthropic.Anthropic:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = anthropic.Anthropic()
    return _CLIENT


def _format_history(turn_history: list[dict]) -> str:
    if not turn_history:
        return "(no prior turns)"
    lines = []
    for t in turn_history[-12:]:  # up to 6 pairs
        role = t.get("role", "user").upper()
        lines.append(f"{role}: {t.get('content', '')}")
    return "\n".join(lines)


def process_turn(state: dict, new_text: str, has_image: bool) -> dict:
    """Single Claude call: extract fields + decide the reply.

    Returns {intent, property, utility, date, missing_fields, reply_text}.
    Caller is responsible for merging into state and sending the reply.
    """
    today = datetime.now(tz=SGT).date().isoformat()
    resolved = state.get("resolved", {})
    image_stored = bool(state.get("pending_image_url"))
    turn_history = state.get("turn_history", [])
    property_ask_count = state.get("property_ask_count", 0)
    fuzzy = state.get("fuzzy_property_suggestion")

    state_context = {
        "already_resolved": {
            "property": resolved.get("property"),
            "utility": resolved.get("utility_type"),
            "date": resolved.get("reading_date"),
        },
        "image_stored_on_volume": image_stored,
        "photo_attached_in_this_message": has_image,
        "property_ask_count": property_ask_count,
        "fuzzy_property_suggestion": fuzzy,
        "today_sgt": today,
    }

    history_text = _format_history(turn_history)
    user_content = (
        f"TODAY (SGT): {today}\n\n"
        f"Conversation so far:\n{history_text}\n\n"
        f"Current state:\n{json.dumps(state_context, indent=2)}\n\n"
        f"New message from Helmy: {new_text or '(no text — photo only)'}\n"
        f"Photo just attached: {has_image}\n\n"
        "Extract all fields and reply."
    )

    _log("info", "brain_call_start", has_image=has_image, text_preview=(new_text or "")[:60])
    try:
        msg = _client().messages.create(
            model=MODEL,
            max_tokens=512,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_content}],
        )
        raw = msg.content[0].text.strip()
        # Strip accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
    except json.JSONDecodeError:
        _log("warn", "brain_parse_error", raw=(raw[:300] if "raw" in dir() else ""))
        # Graceful fallback: ask for everything still missing
        missing = [
            f for f in ("property", "utility", "date")
            if not resolved.get(f if f != "utility" else "utility_type")
        ]
        result = {
            "intent": "other",
            "property": None,
            "utility": None,
            "date": None,
            "missing_fields": missing,
            "reply_text": (
                "Sorry, I had trouble understanding that. "
                "Could you resend with property name, utility type, and date?"
            ) if missing else None,
        }
    except Exception as exc:
        _log("error", "brain_call_failed", error=str(exc)[:200])
        raise

    _log("info", "brain_call_done", intent=result.get("intent"),
         missing=result.get("missing_fields"), has_reply=bool(result.get("reply_text")))
    return result
