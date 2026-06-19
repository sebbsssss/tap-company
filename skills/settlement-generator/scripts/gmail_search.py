#!/usr/bin/env python3
"""
Gmail actuals reader for the settlement generator.

Architecture (Sebastien, THE-17480):
  The jarvis.ai inbox is watched continuously by inbox_watcher.py (runs every 15 min).
  The watcher classifies each incoming email and persists line items to the actuals store
  (Notion DB preferred, JSON file fallback).

  Settlement runs NO LONGER scan email at xlsx-build time.
  This module reads from the actuals store and returns the aggregated actuals for a
  given property + period. If the store has no entry → $0, not yellow.

  For store setup and env vars, see: skills/settlement-generator/scripts/actuals_store.py
  For watcher setup, see:           skills/settlement-generator/scripts/inbox_watcher.py

Required env vars (for actuals store access):
  NOTION_API_KEY          — Notion integration token
  NOTION_ACTUALS_DB_ID    — Notion DB created from the schema in actuals_store.py
  (Falls back to JSON file at ACTUALS_STORE_PATH if Notion vars are absent)

Usage (standalone test):
  python3 gmail_search.py "18 JALAN JINTAN" 2026-05
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Data types (public API — unchanged so settlement.py needs no edits)
# ---------------------------------------------------------------------------

@dataclass
class ServicingItem:
    description: str
    amount: float


@dataclass
class FinanceActuals:
    """Aggregated actuals from the structured store for one property + period."""
    property_name: str
    period: str                          # "2026-05"

    cleaning_total: float = 0.0          # $0 if no store entry found
    servicing_items: list[ServicingItem] = field(default_factory=list)

    emails_searched: int = 0             # not meaningful post-watcher; kept for compat
    emails_matched: int = 0
    email_subjects: list[str] = field(default_factory=list)

    source_note: str = ""

    @property
    def servicing_total(self) -> float:
        return sum(s.amount for s in self.servicing_items)


# ---------------------------------------------------------------------------
# Store-backed lookup
# ---------------------------------------------------------------------------

def search_finance_actuals(
    property_name: str,
    period: str,
    credentials: Optional[dict] = None,
    user_id: str = "jarvis.ai@theassemblyplace.com",
    verbose: bool = False,
) -> FinanceActuals:
    """Read cleaning + servicing actuals from the structured store.

    The store is populated by inbox_watcher.py running every 15 minutes.
    This function no longer scans Gmail at call time — it queries the store
    for pre-classified entries matching (property_name, period).

    Args:
        property_name: e.g. "18 JALAN JINTAN"
        period:        "YYYY-MM"
        credentials:   ignored (kept for API compatibility with old call sites)
        user_id:       ignored (kept for API compatibility)
        verbose:       print debug info

    Returns:
        FinanceActuals with cleaning_total + servicing_items populated.
        cleaning_total = 0.0 and servicing_items = [] if nothing in store.
    """
    result = FinanceActuals(property_name=property_name, period=period)

    # Import the store (same scripts directory)
    sys.path.insert(0, os.path.dirname(__file__))
    try:
        from actuals_store import ActualsStore
    except ImportError as exc:
        result.source_note = (
            f"actuals_store module not found ({exc}). "
            "Ensure inbox_watcher dependencies are installed. Defaulting to $0."
        )
        return result

    store = ActualsStore()

    try:
        entries = store.query(property_name=property_name, month=period)
    except Exception as exc:
        result.source_note = f"Store query failed ({exc}). Defaulting to $0."
        return result

    if verbose:
        print(f"  [gmail_search] store returned {len(entries)} entry(ies) for {property_name!r} {period}")

    # Line-item type mapping:
    #   cleaning        → cleaning_total
    #   servicing       → servicing_items
    #   stock           → servicing_items (maps to 'Stock taken' row in template)
    #   deposits        → skipped here (handled separately in settlement.py)
    #   excess_utility  → skipped here
    #   pob             → skipped here
    #   other           → servicing_items (Finance can label in description)

    cleaning_found = False
    servicing: list[ServicingItem] = []

    for entry in entries:
        if verbose:
            print(f"    [{entry.line_item_type}] {entry.description}: ${entry.amount:,.2f} "
                  f"(confidence={entry.confidence:.2f})")

        if entry.line_item_type == "cleaning":
            result.cleaning_total += entry.amount
            cleaning_found = True

        elif entry.line_item_type in ("servicing", "stock", "other"):
            servicing.append(ServicingItem(
                description=entry.description,
                amount=entry.amount,
            ))

        # deposits / excess_utility / pob are handled by other parts of settlement.py

    result.servicing_items = servicing
    result.emails_matched = len(set(e.source_email_id for e in entries if e.source_email_id))
    result.email_subjects = list({e.source_email_subject for e in entries if e.source_email_subject})

    notes = [f"Store query: {len(entries)} entry(ies) for {property_name} {period}."]
    if cleaning_found:
        notes.append(f"Cleaning: ${result.cleaning_total:,.2f}.")
    else:
        notes.append("Cleaning: no store entry → $0.00.")
    if servicing:
        notes.append(
            f"Servicing/stock: {len(servicing)} item(s) totalling "
            f"${sum(s.amount for s in servicing):,.2f}."
        )
    else:
        notes.append("Servicing: no store entry → $0.00.")

    result.source_note = " ".join(notes)
    return result


# ---------------------------------------------------------------------------
# CLI (standalone test)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    property_name = sys.argv[1] if len(sys.argv) > 1 else "18 JALAN JINTAN"
    period = sys.argv[2] if len(sys.argv) > 2 else "2026-05"

    print(f"Reading actuals store for {property_name!r} period {period!r}...")
    actuals = search_finance_actuals(property_name, period, verbose=True)
    print()
    print(f"Cleaning total:   ${actuals.cleaning_total:,.2f}")
    print(f"Servicing items:  {len(actuals.servicing_items)}")
    for s in actuals.servicing_items:
        print(f"  - {s.description}: ${s.amount:,.2f}")
    print(f"Servicing total:  ${actuals.servicing_total:,.2f}")
    print(f"Emails matched:   {actuals.emails_matched}")
    print(f"Source note: {actuals.source_note}")
