"""Tests for the Tenant Concierge (THE-17982).

Tests are unit-level — all network / LLM calls are monkeypatched out.
Verifies: routing, FAQ answer / escalate, ticket gate, finance gate, dry-run guard.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import concierge
import concierge_tickets


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_event(text: str = "Hello", phone: str = "+6591234567") -> dict:
    return {
        "text": text,
        "phone": phone,
        "conversation_id": "conv-abc",
        "account_id": "6a3b387a9d9472faaecbc09a",
        "contact_id": "contact-xyz",
        "attachments": [],
    }


def _make_claude_response(text: str) -> MagicMock:
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------

class TestClassifyIntent:
    def test_empty_text_returns_escalate(self):
        assert concierge._classify_intent("") == "escalate"

    def test_returns_escalate_on_api_error(self, monkeypatch):
        monkeypatch.setattr(concierge, "_client", lambda: MagicMock(
            messages=MagicMock(create=MagicMock(side_effect=RuntimeError("API down")))
        ))
        assert concierge._classify_intent("anything") == "escalate"

    def test_valid_faq_intent(self, monkeypatch):
        monkeypatch.setattr(concierge, "_client", lambda: MagicMock(
            messages=MagicMock(create=MagicMock(
                return_value=_make_claude_response('{"intent": "faq", "reason": "house rule question"}')
            ))
        ))
        assert concierge._classify_intent("What are the quiet hours?") == "faq"

    def test_valid_ticket_intent(self, monkeypatch):
        monkeypatch.setattr(concierge, "_client", lambda: MagicMock(
            messages=MagicMock(create=MagicMock(
                return_value=_make_claude_response('{"intent": "ticket", "reason": "maintenance issue"}')
            ))
        ))
        assert concierge._classify_intent("My aircon is leaking") == "ticket"

    def test_unknown_intent_coerced_to_escalate(self, monkeypatch):
        monkeypatch.setattr(concierge, "_client", lambda: MagicMock(
            messages=MagicMock(create=MagicMock(
                return_value=_make_claude_response('{"intent": "bogus", "reason": "none"}')
            ))
        ))
        assert concierge._classify_intent("random message") == "escalate"

    def test_invalid_json_returns_escalate(self, monkeypatch):
        monkeypatch.setattr(concierge, "_client", lambda: MagicMock(
            messages=MagicMock(create=MagicMock(
                return_value=_make_claude_response("not json at all")
            ))
        ))
        assert concierge._classify_intent("anything") == "escalate"


# ---------------------------------------------------------------------------
# FAQ answering
# ---------------------------------------------------------------------------

class TestAnswerFaq:
    def test_returns_none_when_kb_empty(self):
        assert concierge._answer_faq("When is rent due?", "") is None

    def test_escalate_response_returns_none(self, monkeypatch):
        monkeypatch.setattr(concierge, "_client", lambda: MagicMock(
            messages=MagicMock(create=MagicMock(
                return_value=_make_claude_response("ESCALATE — not covered in KB")
            ))
        ))
        assert concierge._answer_faq("What is the WiFi password?", "some kb") is None

    def test_valid_answer_returned(self, monkeypatch):
        monkeypatch.setattr(concierge, "_client", lambda: MagicMock(
            messages=MagicMock(create=MagicMock(
                return_value=_make_claude_response("Rent is due on the 1st of each month.")
            ))
        ))
        result = concierge._answer_faq("When is rent due?", "some kb")
        assert result == "Rent is due on the 1st of each month."

    def test_api_error_returns_none(self, monkeypatch):
        monkeypatch.setattr(concierge, "_client", lambda: MagicMock(
            messages=MagicMock(create=MagicMock(side_effect=RuntimeError("error")))
        ))
        assert concierge._answer_faq("anything", "kb") is None


# ---------------------------------------------------------------------------
# handle_finance_message integration
# ---------------------------------------------------------------------------

class TestHandleFinanceMessage:
    def test_no_text_sends_welcome(self, monkeypatch):
        sent = []
        monkeypatch.setattr(concierge, "send_reply", lambda cid, aid, msg, dry_run=True: sent.append(msg))
        event = _fake_event(text="")
        concierge.handle_finance_message(event, "conv-1", "acc-1", dry_run=True)
        assert len(sent) == 1
        assert "text message" in sent[0].lower() or "assistant" in sent[0].lower()

    def test_faq_intent_answered_from_kb(self, monkeypatch):
        sent = []
        monkeypatch.setattr(concierge, "_classify_intent", lambda t: "faq")
        monkeypatch.setattr(concierge, "_load_kb", lambda: "fake kb content")
        monkeypatch.setattr(concierge, "_answer_faq", lambda t, kb: "Rent is due the 1st.")
        monkeypatch.setattr(concierge, "send_reply", lambda cid, aid, msg, dry_run=True: sent.append(msg))

        concierge.handle_finance_message(_fake_event("When is rent due?"), "c", "a", dry_run=True)
        assert sent == ["Rent is due the 1st."]

    def test_faq_no_kb_answer_escalates(self, monkeypatch):
        sent = []
        monkeypatch.setattr(concierge, "_classify_intent", lambda t: "faq")
        monkeypatch.setattr(concierge, "_load_kb", lambda: "fake kb content")
        monkeypatch.setattr(concierge, "_answer_faq", lambda t, kb: None)
        monkeypatch.setattr(concierge, "send_reply", lambda cid, aid, msg, dry_run=True: sent.append(msg))

        concierge.handle_finance_message(_fake_event("Random question"), "c", "a", dry_run=True)
        assert concierge._ESCALATE_REPLY in sent

    def test_escalate_intent_sends_escalate_reply(self, monkeypatch):
        sent = []
        monkeypatch.setattr(concierge, "_classify_intent", lambda t: "escalate")
        monkeypatch.setattr(concierge, "send_reply", lambda cid, aid, msg, dry_run=True: sent.append(msg))

        concierge.handle_finance_message(_fake_event("I want to sue you"), "c", "a", dry_run=True)
        assert concierge._ESCALATE_REPLY in sent

    def test_payment_gate_off_escalates(self, monkeypatch):
        sent = []
        monkeypatch.setattr(concierge, "_classify_intent", lambda t: "payment")
        monkeypatch.setattr(concierge, "_finance_enabled", lambda: False)
        monkeypatch.setattr(concierge, "send_reply", lambda cid, aid, msg, dry_run=True: sent.append(msg))

        concierge.handle_finance_message(_fake_event("What is my balance?"), "c", "a", dry_run=True)
        assert concierge._ESCALATE_REPLY in sent

    def test_ticket_gate_off_sends_gate_reply(self, monkeypatch):
        sent = []
        monkeypatch.setattr(concierge, "_classify_intent", lambda t: "ticket")
        monkeypatch.setattr(concierge, "_tickets_enabled", lambda: False)
        monkeypatch.setattr(concierge, "send_reply", lambda cid, aid, msg, dry_run=True: sent.append(msg))

        concierge.handle_finance_message(_fake_event("My aircon is broken"), "c", "a", dry_run=True)
        assert concierge._TICKET_GATE_REPLY in sent

    def test_send_reply_always_called_with_dry_run_true(self, monkeypatch):
        """Verify dry_run=True is propagated — never fires live Zernio call in test."""
        calls = []
        monkeypatch.setattr(concierge, "_classify_intent", lambda t: "escalate")
        monkeypatch.setattr(
            concierge, "send_reply",
            lambda cid, aid, msg, dry_run=True: calls.append({"dry_run": dry_run, "msg": msg})
        )
        concierge.handle_finance_message(_fake_event("test"), "c", "a", dry_run=True)
        assert all(c["dry_run"] is True for c in calls)


# ---------------------------------------------------------------------------
# concierge_tickets — classify_issue
# ---------------------------------------------------------------------------

SAMPLE_CATEGORIES = [
    {"id": 12, "name": "Power trip", "service": "Maintenance", "recommended_priority": 1},
    {"id": 21, "name": "WiFi Down", "service": "Maintenance", "recommended_priority": 2},
    {"id": 7, "name": "Cleaning", "service": "Housekeeping", "recommended_priority": 3},
    {"id": 6, "name": "General Repairs", "service": "Maintenance", "recommended_priority": 4},
]


class TestClassifyIssue:
    def test_empty_categories_returns_none(self):
        assert concierge_tickets.classify_issue("power went out", []) is None

    def test_api_error_returns_none(self, monkeypatch):
        monkeypatch.setattr(concierge_tickets, "_client", lambda: MagicMock(
            messages=MagicMock(create=MagicMock(side_effect=RuntimeError("API error")))
        ))
        assert concierge_tickets.classify_issue("power trip", SAMPLE_CATEGORIES) is None

    def test_null_id_returns_none(self, monkeypatch):
        monkeypatch.setattr(concierge_tickets, "_client", lambda: MagicMock(
            messages=MagicMock(create=MagicMock(
                return_value=_make_claude_response('{"id": null}')
            ))
        ))
        assert concierge_tickets.classify_issue("something weird", SAMPLE_CATEGORIES) is None

    def test_matched_category_returned(self, monkeypatch):
        monkeypatch.setattr(concierge_tickets, "_client", lambda: MagicMock(
            messages=MagicMock(create=MagicMock(
                return_value=_make_claude_response(
                    '{"id": 12, "name": "Power trip", "service": "Maintenance", "priority": 1}'
                )
            ))
        ))
        result = concierge_tickets.classify_issue("power trip in my room", SAMPLE_CATEGORIES)
        assert result is not None
        assert result["id"] == 12


class TestPostTicket:
    def test_dry_run_does_not_call_crm(self):
        result = concierge_tickets.post_ticket(
            room="18JJ / B-12",
            category_id=12,
            priority=1,
            remarks="Power trip",
            raised_by="+6591234567",
            dry_run=True,
        )
        assert result is not None
        assert result.get("dry_run") is True
        assert "would_post" in result

    def test_dry_run_payload_shape(self):
        result = concierge_tickets.post_ticket(
            room="51MR / 03-01",
            category_id=7,
            priority=3,
            remarks="Room needs cleaning",
            raised_by="+6591234999",
            dry_run=True,
        )
        payload = result["would_post"]
        assert payload["room"] == "51MR / 03-01"
        assert payload["category"] == 7
        assert payload["status"] == "Open"
        assert payload["source"] == "whatsapp-concierge"
