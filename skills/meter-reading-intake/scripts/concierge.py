"""Tenant Concierge — LLM-first handler for the Finance WhatsApp number (+1 775-773-9261).

Routes each inbound tenant message to one of:
  faq      — answered strictly from knowledge_base/faq_kb.md
  ticket   — raise a maintenance ticket (GATE: CONCIERGE_TICKETS_ENABLED)
  payment  — payment / deposit / utility finance question (GATE: CONCIERGE_FINANCE_ENABLED)
  escalate — out-of-scope, low-confidence, or billing dispute

Entry point:
  handle_finance_message(event, conversation_id, account_id, dry_run) -> None

Env vars:
  ANTHROPIC_API_KEY          — required
  CONCIERGE_TICKETS_ENABLED  — 'true' / 'false' (default 'false')
  CONCIERGE_FINANCE_ENABLED  — 'true' / 'false' (default 'false')
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

import anthropic

from zernio_client import send_reply

MODEL = "claude-haiku-4-5-20251001"  # fast + cheap for FAQ routing
_CLIENT: Optional[anthropic.Anthropic] = None

_KB_PATH = Path(__file__).parent.parent / "knowledge_base" / "faq_kb.md"

# Escalation message template — never invent policy or numbers
_ESCALATE_REPLY = (
    "Thanks for reaching out! This is something our team will need to help you with directly. "
    "A team member will follow up with you shortly. 🙏"
)

# Ticket gate disabled message — collect details + escalate
_TICKET_GATE_REPLY = (
    "I've noted your maintenance request. Our team will follow up with you shortly to arrange assistance. "
    "If it's urgent, please also reach us via the ops channel."
)


def _log(level: str, msg: str, **kwargs: object) -> None:
    payload = {"level": level, "service": "tenant-concierge", "msg": msg, **kwargs}
    print(json.dumps(payload), file=sys.stderr)


def _client() -> anthropic.Anthropic:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = anthropic.Anthropic()
    return _CLIENT


def _tickets_enabled() -> bool:
    return os.environ.get("CONCIERGE_TICKETS_ENABLED", "false").lower() == "true"


def _finance_enabled() -> bool:
    return os.environ.get("CONCIERGE_FINANCE_ENABLED", "false").lower() == "true"


def _load_kb() -> str:
    """Load the FAQ knowledge base. Returns empty string if missing (safe fallback)."""
    if _KB_PATH.exists():
        return _KB_PATH.read_text(encoding="utf-8")
    _log("warn", "faq_kb_missing", path=str(_KB_PATH))
    return ""


# ---------------------------------------------------------------------------
# Step 1: Classify intent
# ---------------------------------------------------------------------------

_CLASSIFY_SYSTEM = """\
You are a message classifier for The Assembly Place (TAP), a Singapore coliving company.
A tenant has sent a WhatsApp message to TAP's Finance number.

Classify the message into EXACTLY ONE of:
  faq      — general question answerable from a knowledge base (house rules, lease, wifi, mail, etc.)
  ticket   — maintenance or housekeeping issue the tenant wants to report/fix
  payment  — question about rent payment status, deposit, or utility bill amount
  escalate — complaint, billing dispute, legal threat, very low confidence, or unclear

Respond with a single JSON object — no markdown, no prose:
{"intent": "faq" | "ticket" | "payment" | "escalate", "reason": "<10 words max>"}
"""


def _classify_intent(text: str) -> str:
    """Return 'faq', 'ticket', 'payment', or 'escalate'."""
    if not text.strip():
        return "escalate"
    try:
        msg = _client().messages.create(
            model=MODEL,
            max_tokens=64,
            system=_CLASSIFY_SYSTEM,
            messages=[{"role": "user", "content": text}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip().rstrip("```").strip()
        result = json.loads(raw)
        intent = result.get("intent", "escalate")
        if intent not in ("faq", "ticket", "payment", "escalate"):
            intent = "escalate"
        _log("info", "intent_classified", intent=intent, reason=result.get("reason", ""))
        return intent
    except Exception as exc:
        _log("error", "classify_failed", error=str(exc)[:200])
        return "escalate"


# ---------------------------------------------------------------------------
# Step 2: FAQ answering
# ---------------------------------------------------------------------------

_FAQ_SYSTEM = """\
You are the tenant support assistant for The Assembly Place (TAP), a Singapore coliving company.
Answer the tenant's question using ONLY the information in the knowledge base below.

Rules:
1. If the answer is clearly in the KB, answer concisely (2–4 sentences max). Be friendly and professional.
2. If the answer contains [GENERIC-confirm] or is not covered in the KB, respond with the literal word ESCALATE.
3. Never invent a policy, number, date, amount, or email address not in the KB.
4. Never combine entries to synthesise a new policy.
5. If the question is about raising a maintenance/housekeeping issue, respond with ESCALATE (handled separately).

KNOWLEDGE BASE:
{kb}
"""


def _answer_faq(text: str, kb: str) -> Optional[str]:
    """Return a KB-grounded answer, or None to signal escalate."""
    if not kb:
        return None
    try:
        system = _FAQ_SYSTEM.format(kb=kb)
        msg = _client().messages.create(
            model=MODEL,
            max_tokens=256,
            system=system,
            messages=[{"role": "user", "content": text}],
        )
        answer = msg.content[0].text.strip()
        if answer.upper().startswith("ESCALATE"):
            _log("info", "faq_escalated", reason="not_in_kb_or_generic_confirm")
            return None
        _log("info", "faq_answered", preview=answer[:80])
        return answer
    except Exception as exc:
        _log("error", "faq_answer_failed", error=str(exc)[:200])
        return None


# ---------------------------------------------------------------------------
# Step 3: Ticket collection (when CONCIERGE_TICKETS_ENABLED=true)
# ---------------------------------------------------------------------------

def _handle_ticket(
    text: str,
    event: dict,
    conversation_id: str,
    account_id: str,
    dry_run: bool,
) -> None:
    """Route to ticket creator or collect-and-escalate depending on the gate."""
    if _tickets_enabled():
        try:
            from concierge_tickets import handle_ticket_flow
            handle_ticket_flow(text, event, conversation_id, account_id, dry_run)
        except Exception as exc:
            _log("error", "ticket_flow_failed", error=str(exc)[:200])
            send_reply(conversation_id, account_id, _TICKET_GATE_REPLY, dry_run=dry_run)
    else:
        _log("info", "ticket_gate_off", detail="CONCIERGE_TICKETS_ENABLED not set; collecting + escalating")
        send_reply(conversation_id, account_id, _TICKET_GATE_REPLY, dry_run=dry_run)


# ---------------------------------------------------------------------------
# Step 4: Finance / payment answers (when CONCIERGE_FINANCE_ENABLED=true)
# ---------------------------------------------------------------------------

def _handle_payment(
    text: str,
    conversation_id: str,
    account_id: str,
    dry_run: bool,
) -> None:
    """Handle payment/deposit/utility questions — gated behind CONCIERGE_FINANCE_ENABLED."""
    if not _finance_enabled():
        _log("info", "finance_gate_off", detail="CONCIERGE_FINANCE_ENABLED not set; escalating")
        send_reply(conversation_id, account_id, _ESCALATE_REPLY, dry_run=dry_run)
        return

    # Finance answers require strict identity: phone must resolve to exactly one tenancy.
    # That wire-up (PHONE_SOURCE) is pending; escalate until available.
    _log("info", "finance_identity_not_wired", detail="escalating until PHONE_SOURCE wired")
    send_reply(
        conversation_id,
        account_id,
        "Our Finance team will be in touch to assist with your account query.",
        dry_run=dry_run,
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def handle_finance_message(
    event: dict,
    conversation_id: str,
    account_id: str,
    dry_run: bool,
) -> None:
    """Process one inbound message from a tenant on the Finance WhatsApp number.

    Called from meter_intake.py after HMAC verify + dedup. Runs in background thread.
    Never raises — all errors are logged and gracefully escalated.
    """
    text = (event.get("text") or "").strip()
    phone = event.get("phone") or "unknown"

    _log("info", "concierge_received", phone_prefix=phone[:6] if len(phone) >= 6 else phone,
         text_preview=text[:80])

    if not text:
        # No text (e.g. image or sticker) — escalate gracefully
        _log("info", "concierge_no_text", detail="non-text message escalated")
        send_reply(
            conversation_id,
            account_id,
            "Hi! I'm the TAP tenant support assistant. Please send a text message and I'll do my best to help.",
            dry_run=dry_run,
        )
        return

    intent = _classify_intent(text)

    if intent == "ticket":
        _handle_ticket(text, event, conversation_id, account_id, dry_run)
        return

    if intent == "payment":
        _handle_payment(text, conversation_id, account_id, dry_run)
        return

    if intent == "faq":
        kb = _load_kb()
        answer = _answer_faq(text, kb)
        if answer:
            send_reply(conversation_id, account_id, answer, dry_run=dry_run)
            return
        # No KB answer → fall through to escalate
        _log("info", "faq_no_answer_escalating")

    # escalate (intent='escalate' OR faq fell through)
    _log("info", "concierge_escalating", intent=intent, phone_prefix=phone[:6] if len(phone) >= 6 else phone)
    send_reply(conversation_id, account_id, _ESCALATE_REPLY, dry_run=dry_run)
