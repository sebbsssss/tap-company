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


# ---------------------------------------------------------------------------
# append_turn
# ---------------------------------------------------------------------------

def test_append_turn_adds_entries():
    state = cs.new_state("c", "conv_1", "acc_1")
    cs.append_turn(state, "user", "18JJ elec today")
    cs.append_turn(state, "assistant", "Got it!")
    assert len(state["turn_history"]) == 2
    assert state["turn_history"][0] == {"role": "user", "content": "18JJ elec today"}
    assert state["turn_history"][1] == {"role": "assistant", "content": "Got it!"}


def test_append_turn_trims_to_max_pairs():
    state = cs.new_state("c", "conv_1", "acc_1")
    for i in range(8):
        cs.append_turn(state, "user", f"msg {i}")
        cs.append_turn(state, "assistant", f"reply {i}")
    # max_pairs=6 → 12 entries max
    assert len(state["turn_history"]) == 12


def test_append_turn_new_state_starts_empty():
    state = cs.new_state("c", "conv_1", "acc_1")
    assert state["turn_history"] == []


# ---------------------------------------------------------------------------
# merge_brain
# ---------------------------------------------------------------------------

def test_merge_brain_fills_all_fields():
    state = cs.new_state("c", "conv_1", "acc_1")
    brain = {"property": "MILL@32", "utility": "electricity", "date": "2026-06-12", "missing_fields": []}
    cs.merge_brain(state, brain)
    assert state["resolved"]["property"] == "MILL@32"
    assert state["resolved"]["utility_type"] == "electricity"
    assert state["resolved"]["reading_date"] == "2026-06-12"


def test_merge_brain_skips_null_fields():
    state = cs.new_state("c", "conv_1", "acc_1")
    state["resolved"]["property"] = "TLKR CAMPUS"
    brain = {"property": None, "utility": "water", "date": None}
    cs.merge_brain(state, brain)
    # property and date unchanged
    assert state["resolved"]["property"] == "TLKR CAMPUS"
    assert state["resolved"]["reading_date"] is None
    assert state["resolved"]["utility_type"] == "water"


def test_merge_brain_overrides_regex_prefill():
    state = cs.new_state("c", "conv_1", "acc_1")
    state["resolved"]["utility_type"] = "water"  # wrong regex pre-fill
    brain = {"property": None, "utility": "electricity", "date": None}
    cs.merge_brain(state, brain)
    assert state["resolved"]["utility_type"] == "electricity"


def test_merge_brain_clears_fuzzy_on_property_set():
    state = cs.new_state("c", "conv_1", "acc_1")
    state["fuzzy_property_suggestion"] = "MILL@32"
    state["property_ask_count"] = 1
    brain = {"property": "MILL@32", "utility": None, "date": None}
    cs.merge_brain(state, brain)
    assert state["fuzzy_property_suggestion"] is None
    assert state["property_ask_count"] == 0


def test_merge_brain_today_resolves_to_iso_date():
    state = cs.new_state("c", "conv_1", "acc_1")
    brain = {"property": None, "utility": None, "date": "today"}
    cs.merge_brain(state, brain)
    # Should be an ISO date string, not the literal "today"
    assert state["resolved"]["reading_date"] != "today"
    assert len(state["resolved"]["reading_date"]) == 10  # YYYY-MM-DD
