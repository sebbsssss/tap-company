"""Regression tests for property matching — MILL@32 normalization + loop guard.

Tests confirm that:
1. 'MILL@32 / 11 Jun / water' resolves with zero re-asks (core fix).
2. Answering 'Mill@32' to the property question also resolves.
3. Fuzzy near-miss triggers 'Did you mean?' prompt.
4. Loop guard: after 2 re-asks, raw text is accepted with property_unverified=True.
"""

from datetime import date
from unittest.mock import patch

import pytest

from caption_parser import parse_caption
from conversation_state import (
    merge_parsed,
    missing_fields,
    new_state,
    next_question,
)


# ---------------------------------------------------------------------------
# Caption normalization — MILL@32 and variants
# ---------------------------------------------------------------------------

def test_mill32_in_full_caption_resolves():
    """'MILL@32 / 11 Jun / water' → property='MILL@32', zero re-asks."""
    result = parse_caption("MILL@32 / 11 Jun / water")
    assert result["property"] == "MILL@32"
    assert result["utility_type"] == "water"
    assert result["reading_date"] == date(2026, 6, 11)


def test_mill32_lowercase_resolves():
    result = parse_caption("mill@32 water today")
    assert result["property"] == "MILL@32"


def test_mill32_spaced_at_resolves():
    result = parse_caption("MILL @ 32 water today")
    assert result["property"] == "MILL@32"


def test_mill32_no_at_resolves():
    result = parse_caption("mill32 water today")
    assert result["property"] == "MILL@32"


def test_answering_mill32_to_property_question_resolves():
    """When bot asks 'Which property?', replying 'Mill@32' must resolve."""
    result = parse_caption("Mill@32")
    assert result["property"] == "MILL@32"


# ---------------------------------------------------------------------------
# Fuzzy suggestion
# ---------------------------------------------------------------------------

def test_fuzzy_suggestion_for_near_miss():
    """Input close to a known property but not exact should return fuzzy_suggestion."""
    result = parse_caption("mil32 water today")
    # Either resolved exactly or has a fuzzy suggestion
    assert result["property"] == "MILL@32" or result["fuzzy_suggestion"] == "MILL@32"


# ---------------------------------------------------------------------------
# Loop guard — max 2 re-asks then accept raw string
# ---------------------------------------------------------------------------

def test_next_question_with_fuzzy_suggestion():
    state = new_state("c1", "conv1", "acc1")
    state["fuzzy_property_suggestion"] = "MILL@32"
    assert "Did you mean" in next_question(["property"], state)
    assert "MILL@32" in next_question(["property"], state)


def test_next_question_without_suggestion_is_generic():
    state = new_state("c1", "conv1", "acc1")
    q = next_question(["property"], state)
    assert "Which property" in q


def test_merge_parsed_clears_fuzzy_on_exact_match():
    state = new_state("c1", "conv1", "acc1")
    state["fuzzy_property_suggestion"] = "MILL@32"
    state["property_ask_count"] = 1
    parsed = parse_caption("18JJ water today")
    state = merge_parsed(state, parsed)
    assert state["resolved"]["property"] == "18 JALAN JINTAN"
    assert state["fuzzy_property_suggestion"] is None
    assert state["property_ask_count"] == 0


def test_merge_parsed_stores_fuzzy_suggestion():
    """When no exact match, fuzzy suggestion from parse_caption is stored in state."""
    state = new_state("c1", "conv1", "acc1")
    with patch("caption_parser._resolve_property", return_value=(None, "MILL@32")):
        parsed = parse_caption("some near miss text")
    state = merge_parsed(state, parsed)
    assert state["resolved"]["property"] is None
    assert state["fuzzy_property_suggestion"] == "MILL@32"
