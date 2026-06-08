"""Magic-link auth + session management backed by SQLite.

Magic links: 15-min TTL, one-time use.
Sessions: 30-day, HttpOnly+Secure cookie named ops_session.
Allowed emails: OPS_PORTAL_ALLOWED_EMAILS comma-separated env var.
"""
from __future__ import annotations

import json
import os
import secrets
import smtplib
import sqlite3
import sys
import threading
import time
from email.mime.text import MIMEText
from typing import Optional

DB_PATH = os.environ.get("AUTH_DB_PATH", "/tmp/ops_portal_auth.db")
MAGIC_LINK_TTL = 15 * 60   # seconds
SESSION_TTL = 30 * 24 * 3600  # seconds

ALLOWED_EMAILS: frozenset[str] = frozenset(
    e.strip().lower()
    for e in os.environ.get("OPS_PORTAL_ALLOWED_EMAILS", "").split(",")
    if e.strip()
)

_db_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript("""
            CREATE TABLE IF NOT EXISTS magic_links (
                token TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                expires_at REAL NOT NULL,
                used INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                expires_at REAL NOT NULL
            );
        """)
        _conn.commit()
    return _conn


def is_allowed(email: str) -> bool:
    return email.strip().lower() in ALLOWED_EMAILS


def generate_magic_link(email: str) -> str:
    """Create a one-time token valid for 15 minutes. Returns the raw token."""
    token = secrets.token_urlsafe(32)
    with _db_lock:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO magic_links (token, email, expires_at) VALUES (?, ?, ?)",
            (token, email.lower(), time.time() + MAGIC_LINK_TTL),
        )
        conn.commit()
    return token


def _send_magic_link_email(to: str, link: str) -> None:
    """Best-effort SMTP send. Skipped when SMTP_HOST is not configured."""
    host = os.environ.get("SMTP_HOST")
    if not host:
        return
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASS", "")
    from_addr = os.environ.get("OPS_PORTAL_FROM_EMAIL", user)

    msg = MIMEText(
        f"Click the link below to sign in to the TAP Ops Portal (expires in 15 minutes):\n\n{link}\n",
        "plain",
    )
    msg["Subject"] = "TAP Ops Portal — Sign in link"
    msg["From"] = from_addr
    msg["To"] = to

    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.ehlo()
            if smtp.has_extn("STARTTLS"):
                smtp.starttls()
            if user and password:
                smtp.login(user, password)
            smtp.sendmail(from_addr, [to], msg.as_string())
    except Exception as exc:
        print(
            json.dumps({"level": "error", "event": "smtp_send_failed", "detail": str(exc)}),
            file=sys.stderr,
        )


def send_magic_link(email: str, link: str) -> None:
    """Send magic link by email (no-op if SMTP not configured; link is also logged)."""
    print(
        json.dumps({"level": "info", "event": "magic_link_generated",
                    "email": email, "link": link}),
        file=sys.stderr,
    )
    _send_magic_link_email(email, link)


def verify_magic_link(token: str) -> Optional[str]:
    """Verify token and mark used. Returns email on success, None otherwise."""
    now = time.time()
    with _db_lock:
        conn = _get_conn()
        row = conn.execute(
            "SELECT email, expires_at, used FROM magic_links WHERE token = ?", (token,)
        ).fetchone()
        if not row or row["used"] or row["expires_at"] < now:
            return None
        conn.execute("UPDATE magic_links SET used = 1 WHERE token = ?", (token,))
        conn.commit()
    return row["email"]


def create_session(email: str) -> str:
    """Create a 30-day session token."""
    token = secrets.token_urlsafe(48)
    with _db_lock:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO sessions (token, email, expires_at) VALUES (?, ?, ?)",
            (token, email.lower(), time.time() + SESSION_TTL),
        )
        conn.commit()
    return token


def validate_session(token: str) -> Optional[str]:
    """Return email for a valid session token, or None if invalid/expired."""
    if not token:
        return None
    with _db_lock:
        conn = _get_conn()
        row = conn.execute(
            "SELECT email, expires_at FROM sessions WHERE token = ?", (token,)
        ).fetchone()
    if not row or row["expires_at"] < time.time():
        return None
    return row["email"]
