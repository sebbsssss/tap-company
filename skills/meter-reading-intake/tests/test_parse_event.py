"""Regression tests for _parse_event — Zernio webhook schema (authoritative).

Authoritative fields per Zernio OpenAPI spec:
  message.sender.id              — phone WITHOUT '+' (e.g. "6596370022")
  conversation.participantUsername — phone WITH '+'  (e.g. "+6596370022")
  conversation.id, conversation.contactId, account.id

NOT in webhook payloads: message.senderPhoneNumber, message.senderId
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from meter_intake import _parse_event


def _make_event(
    sender_id_no_plus=None,
    participant_username=None,
    contact_id=None,
    conv_id="conv-1",
    account_id="acc-1",
    text="",
    attachments=None,
):
    """Build a Zernio webhook event using the authoritative schema shape."""
    return {
        "message": {
            **({"sender": {"id": sender_id_no_plus}} if sender_id_no_plus else {}),
            "text": text,
            "attachments": attachments or [],
        },
        "conversation": {
            "id": conv_id,
            **({"contactId": contact_id} if contact_id else {}),
            **({"participantUsername": participant_username} if participant_username else {}),
        },
        "account": {"id": account_id},
    }


def test_phone_from_participant_username():
    """Primary source: conversation.participantUsername (with '+')."""
    ev = _make_event(participant_username="+6596370022")
    assert _parse_event(ev)["phone"] == "+6596370022"


def test_phone_falls_back_to_sender_id():
    """Fallback: message.sender.id (without '+') when participantUsername absent."""
    ev = _make_event(sender_id_no_plus="6596370022")
    assert _parse_event(ev)["phone"] == "6596370022"


def test_participant_username_preferred_over_sender_id():
    """conversation.participantUsername (with '+') takes precedence over message.sender.id."""
    ev = _make_event(sender_id_no_plus="6596370022", participant_username="+6596370022")
    assert _parse_event(ev)["phone"] == "+6596370022"


def test_phone_none_when_all_absent():
    ev = _make_event()
    assert _parse_event(ev)["phone"] is None


def test_sender_id_from_message_sender_id():
    """sender_id comes from message.sender.id (no '+')."""
    ev = _make_event(sender_id_no_plus="6596370022")
    assert _parse_event(ev)["sender_id"] == "6596370022"


def test_sender_id_none_when_sender_absent():
    """sender_id is None when message.sender object is absent."""
    ev = _make_event(participant_username="+6596370022")
    assert _parse_event(ev)["sender_id"] is None


def test_contact_id_uses_conv_contact_id():
    ev = _make_event(sender_id_no_plus="6596370022", contact_id="cid-42")
    assert _parse_event(ev)["contact_id"] == "cid-42"


def test_contact_id_falls_back_to_sender_id():
    ev = _make_event(sender_id_no_plus="6596370022")
    assert _parse_event(ev)["contact_id"] == "6596370022"


def test_contact_id_empty_when_nothing():
    ev = _make_event()
    assert _parse_event(ev)["contact_id"] == ""


def test_text_extracted():
    ev = _make_event(text="18JJ elec 2026-06-11")
    assert _parse_event(ev)["text"] == "18JJ elec 2026-06-11"


def test_conversation_id_extracted():
    ev = _make_event(conv_id="conv-abc")
    assert _parse_event(ev)["conversation_id"] == "conv-abc"


def test_account_id_extracted():
    ev = _make_event(account_id="acc-xyz")
    assert _parse_event(ev)["account_id"] == "acc-xyz"


def test_attachments_extracted():
    atts = [{"mimeType": "image/jpeg", "url": "https://cdn.zernio.com/img/x.jpg"}]
    ev = _make_event(attachments=atts)
    assert _parse_event(ev)["attachments"] == atts
