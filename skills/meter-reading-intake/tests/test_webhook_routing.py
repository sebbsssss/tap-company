"""Regression tests for Zernio webhook account-based routing.

THE-17980: both WhatsApp numbers share one Zernio webhook. The handler must
branch on account.id so the finance number never triggers the meter flow.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from meter_intake import (
    _FINANCE_ACCOUNT_ID,
    _METER_ACCOUNT_ID,
    _account_route,
)


def test_meter_account_routes_to_meter():
    assert _account_route(_METER_ACCOUNT_ID) == "meter"


def test_finance_account_routes_to_finance():
    assert _account_route(_FINANCE_ACCOUNT_ID) == "finance"


def test_unknown_account_routes_to_ignore():
    assert _account_route("deadbeefdeadbeefdeadbeef") == "ignore"


def test_empty_account_id_routes_to_ignore():
    assert _account_route("") == "ignore"
