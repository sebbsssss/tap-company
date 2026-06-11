"""Regression tests for _parse_event phone fallback chain.

Real Zernio payloads do not include message.senderPhoneNumber — the phone number
lives in message.senderId, conversation.participantUsername, or conversation.participantId.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from meter_intake import _parse_event


def _make_event(
    sender_phone=None,
    sender_id=None,
    participant_username=None,
    participant_id=None,
    contact_id=None,
    conv_id="conv-1",
    account_id="acc-1",
    text="",
    attachments=None,
):
    return {
        "message": {
            **({"senderPhoneNumber": sender_phone} if sender_phone else {}),
            **({"senderId": sender_id} if sender_id else {}),
            "text": text,
            "attachments": attachments or [],
        },
        "conversation": {
            "id": conv_id,
            **({"contactId": contact_id} if contact_id else {}),
            **({"participantUsername": participant_username} if participant_username else {}),
            **({"participantId": participant_id} if participant_id else {}),
        },
        "account": {"id": account_id},
    }


def test_phone_from_sender_phone_number():
    ev = _make_event(sender_phone="+6596370022")
    assert _parse_event(ev)["phone"] == "+6596370022"


def test_phone_falls_back_to_sender_id():
    """Real Zernio payloads: senderPhoneNumber absent, senderId has the number."""
    ev = _make_event(sender_id="+6596370022")
    parsed = _parse_event(ev)
    assert parsed["phone"] == "+6596370022"


def test_phone_falls_back_to_participant_username():
    ev = _make_event(participant_username="+6596370022")
    assert _parse_event(ev)["phone"] == "+6596370022"


def test_phone_falls_back_to_participant_id():
    ev = _make_event(participant_id="+6596370022")
    assert _parse_event(ev)["phone"] == "+6596370022"


def test_phone_none_when_all_absent():
    ev = _make_event()
    assert _parse_event(ev)["phone"] is None


def test_sender_id_falls_back_to_participant_id():
    ev = _make_event(participant_id="uid-999")
    parsed = _parse_event(ev)
    assert parsed["sender_id"] == "uid-999"


def test_contact_id_uses_conv_contact_id():
    ev = _make_event(sender_id="uid-1", contact_id="cid-42")
    assert _parse_event(ev)["contact_id"] == "cid-42"


def test_contact_id_falls_back_to_sender_id():
    ev = _make_event(sender_id="uid-1")
    assert _parse_event(ev)["contact_id"] == "uid-1"
