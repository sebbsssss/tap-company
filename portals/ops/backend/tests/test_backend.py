"""Smoke tests for the Ops Portal backend.

Run: python3 -m pytest tests/ -v (from the backend/ directory)
"""
import sys
import os
import time

# Add parent to path so modules are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import audit
import auth


# ── audit module ─────────────────────────────────────────────────────────────


def test_audit_write_and_read(tmp_path):
    log = str(tmp_path / "test.log")
    os.environ["AUDIT_LOG_PATH"] = log
    # Patch the module-level constant
    import importlib
    importlib.reload(audit)

    audit.write_audit("alice@example.com", "comment", 12345, 200)
    audit.write_audit("bob@example.com", "approve_draft", 12345, 200)

    entries = audit.read_audit(10)
    assert len(entries) == 2
    # read_audit returns newest-first
    assert entries[0]["action"] == "approve_draft"
    assert entries[0]["ticket"] == "12345"
    assert entries[0]["status"] == "200"
    assert entries[1]["actor"] == "alice@example.com"


def test_audit_read_missing_file(tmp_path):
    os.environ["AUDIT_LOG_PATH"] = str(tmp_path / "nonexistent.log")
    import importlib
    importlib.reload(audit)
    assert audit.read_audit(50) == []


# ── auth module ──────────────────────────────────────────────────────────────


def test_is_allowed():
    os.environ["OPS_PORTAL_ALLOWED_EMAILS"] = "alice@example.com, bob@example.com"
    import importlib
    importlib.reload(auth)
    assert auth.is_allowed("alice@example.com")
    assert auth.is_allowed("BOB@EXAMPLE.COM")  # case-insensitive
    assert not auth.is_allowed("eve@example.com")


def test_magic_link_one_time_use(tmp_path):
    os.environ["AUTH_DB_PATH"] = str(tmp_path / "auth.db")
    os.environ["OPS_PORTAL_ALLOWED_EMAILS"] = "test@example.com"
    import importlib
    importlib.reload(auth)

    token = auth.generate_magic_link("test@example.com")
    # First use: valid
    email = auth.verify_magic_link(token)
    assert email == "test@example.com"
    # Second use: rejected
    email2 = auth.verify_magic_link(token)
    assert email2 is None


def test_magic_link_wrong_token(tmp_path):
    os.environ["AUTH_DB_PATH"] = str(tmp_path / "auth2.db")
    import importlib
    importlib.reload(auth)
    assert auth.verify_magic_link("notarealtoken") is None


def test_session_lifecycle(tmp_path):
    os.environ["AUTH_DB_PATH"] = str(tmp_path / "auth3.db")
    import importlib
    importlib.reload(auth)

    token = auth.create_session("ops@example.com")
    assert auth.validate_session(token) == "ops@example.com"
    assert auth.validate_session("bad-token") is None
    assert auth.validate_session("") is None
