"""Tests for conversation_state — no network calls."""

from datetime import date

import pytest

import conversation_state as cs


@pytest.fixture(autouse=True)
def redirect_state_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("METER_STATE_DIR", str(tmp_path))


def test_new_state_has_all_none():
    state = cs.new_state("contact_001", "conv_001", "acc_001")
    assert state["resolved"]["property"] is None
    assert state["resolved"]["utility_type"] is None
    assert state["resolved"]["reading_date"] is None
    assert state["awaiting_retake"] is False


def test_save_and_load_roundtrip(tmp_path):
    state = cs.new_state("contact_001", "conv_001", "acc_001")
    state["resolved"]["property"] = "18 JALAN JINTAN"
    cs.save(state)
    loaded = cs.load("contact_001")
    assert loaded is not None
    assert loaded["resolved"]["property"] == "18 JALAN JINTAN"


def test_clear_removes_state(tmp_path):
    state = cs.new_state("contact_002", "conv_001", "acc_001")
    cs.save(state)
    cs.clear("contact_002")
    assert cs.load("contact_002") is None


def test_load_returns_none_for_unknown():
    assert cs.load("nonexistent_contact_xyz") is None


def test_merge_parsed_fills_missing():
    state = cs.new_state("c", "conv_1", "acc_1")
    parsed = {"property": "18 JALAN JINTAN", "utility_type": "electricity", "reading_date": date(2026, 6, 11)}
    state = cs.merge_parsed(state, parsed)
    assert state["resolved"]["property"] == "18 JALAN JINTAN"
    assert state["resolved"]["utility_type"] == "electricity"
    assert state["resolved"]["reading_date"] == "2026-06-11"


def test_merge_parsed_does_not_overwrite():
    state = cs.new_state("c", "conv_1", "acc_1")
    state["resolved"]["property"] = "TLKR CAMPUS"
    parsed = {"property": "18 PENHAS", "utility_type": None, "reading_date": None}
    state = cs.merge_parsed(state, parsed)
    # Already-resolved field must not be overwritten
    assert state["resolved"]["property"] == "TLKR CAMPUS"


def test_missing_fields_partial():
    state = cs.new_state("c", "conv_1", "acc_1")
    state["resolved"]["property"] = "18 JALAN JINTAN"
    missing = cs.missing_fields(state)
    assert "property" not in missing
    assert "utility_type" in missing
    assert "reading_date" in missing


def test_missing_fields_empty_when_complete():
    state = cs.new_state("c", "conv_1", "acc_1")
    state["resolved"]["property"] = "18 JALAN JINTAN"
    state["resolved"]["utility_type"] = "electricity"
    state["resolved"]["reading_date"] = "2026-06-11"
    assert cs.missing_fields(state) == []


def test_is_complete_false_when_awaiting_retake():
    state = cs.new_state("c", "conv_1", "acc_1")
    state["resolved"]["property"] = "18 JALAN JINTAN"
    state["resolved"]["utility_type"] = "water"
    state["resolved"]["reading_date"] = "2026-06-11"
    state["awaiting_retake"] = True
    assert not cs.is_complete(state)


def test_next_question_property_first():
    q = cs.next_question(["property", "utility_type"])
    assert "property" in q.lower()


def test_next_question_utility_when_property_resolved():
    q = cs.next_question(["utility_type", "reading_date"])
    assert "electric" in q.lower() or "water" in q.lower() or "gas" in q.lower()
