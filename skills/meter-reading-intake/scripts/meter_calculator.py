"""MeterReadingCalculator — extract numeric reading from a meter photo via Claude vision.

Uses claude-sonnet-4-6 with base64-encoded image. Requires ANTHROPIC_API_KEY.
Returns a structured dict; caller decides whether to abort if reading is None.
"""

from __future__ import annotations

import base64
import json
import sys
from typing import Optional

import anthropic

_CLIENT: Optional[anthropic.Anthropic] = None
MODEL = "claude-sonnet-4-6"


def _log(level: str, msg: str, **kwargs: object) -> None:
    payload = {"level": level, "service": "meter-intake", "msg": msg, **kwargs}
    print(json.dumps(payload), file=sys.stderr)


def _client() -> anthropic.Anthropic:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    return _CLIENT


def extract_reading(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    context: Optional[dict] = None,
) -> dict:
    """Return {'reading': float|None, 'meter_id': str|None, 'confidence': str, 'notes': str}.

    confidence is 'high' | 'medium' | 'low'.
    reading is None when the display is unreadable.
    """
    b64 = base64.standard_b64encode(image_bytes).decode()
    ctx_note = ""
    if context:
        parts = []
        if context.get("property"):
            parts.append(f"property: {context['property']}")
        if context.get("utility_type"):
            parts.append(f"utility: {context['utility_type']}")
        if parts:
            ctx_note = f" ({', '.join(parts)})"

    prompt = (
        f"You are reading a utility meter photo{ctx_note}. "
        "Extract the numeric meter reading shown on the display or dial. "
        "Reply with a JSON object and nothing else — no markdown fences:\n"
        '{"reading": <number or null>, "meter_id": "<id visible on meter label or null>", '
        '"confidence": "high|medium|low", "notes": "<optional explanation>"}'
    )

    _log("info", "extract_reading_start", mime_type=mime_type, bytes=len(image_bytes))
    msg = _client().messages.create(
        model=MODEL,
        max_tokens=256,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )

    raw = msg.content[0].text.strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        _log("warn", "extract_reading_parse_error", raw=raw[:300])
        result = {
            "reading": None,
            "meter_id": None,
            "confidence": "low",
            "notes": f"parse error: {raw[:200]}",
        }

    # Coerce reading to float if present
    if result.get("reading") is not None:
        try:
            result["reading"] = float(result["reading"])
        except (TypeError, ValueError):
            _log("warn", "extract_reading_coerce_error", raw_reading=result.get("reading"))
            result["reading"] = None
            result["confidence"] = "low"

    _log("info", "extract_reading_done", reading=result.get("reading"), confidence=result.get("confidence"))
    return result
