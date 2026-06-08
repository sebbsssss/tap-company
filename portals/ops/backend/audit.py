"""Audit log: append-only structured log for all write actions.

Log file: /paperclip/.audit/ticket-auto-reply.log (override via AUDIT_LOG_PATH).
Each line: 2026-06-07T14:00:00Z actor=ops@theassemblyplace.com action=comment ticket=12345 status=200
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Union

AUDIT_LOG = os.environ.get("AUDIT_LOG_PATH", "/paperclip/.audit/ticket-auto-reply.log")


def write_audit(
    actor: str,
    action: str,
    ticket_id: Union[int, str],
    http_status: int,
) -> None:
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{ts} actor={actor} action={action} ticket={ticket_id} status={http_status}\n"
    try:
        os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
        with open(AUDIT_LOG, "a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception as exc:
        print(
            json.dumps({"level": "error", "event": "audit_write_failed", "detail": str(exc)}),
            file=sys.stderr,
        )


def read_audit(limit: int = 50) -> list[dict]:
    """Read the last `limit` audit entries in reverse-chronological order."""
    try:
        with open(AUDIT_LOG, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except FileNotFoundError:
        return []

    entries: list[dict] = []
    for raw in reversed(lines):
        raw = raw.strip()
        if not raw:
            continue
        tokens = raw.split()
        entry: dict = {}
        if tokens:
            entry["timestamp"] = tokens[0]
        for tok in tokens[1:]:
            if "=" in tok:
                k, v = tok.split("=", 1)
                entry[k] = v
        entries.append(entry)
        if len(entries) >= limit:
            break
    return entries
