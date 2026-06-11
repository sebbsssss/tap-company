"""Daily meter-reading digest — 18:00 SGT.

Summarises readings logged today vs expected route:
  Mon/Wed → campus properties (TLKR)
  Tue/Thu → off-campus properties (co-livings)

Sends via Zernio to Erwan. Use --send live to actually fire; default is dry-run.

Env vars:
  ERWAN_CONTACT_ID   — Zernio contact ID for Erwan (required for live sends)
  ERWAN_INBOX_ID     — Zernio inbox ID (required for live sends)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from utility_log import get_today_readings
from zernio_client import send_reply

SGT = ZoneInfo("Asia/Singapore")

CAMPUS_PROPERTIES = frozenset(
    {
        "TLKR CAMPUS",
        "TLKR CAMPUS - BLOCK A",
        "TLKR CAMPUS - BLOCK B",
    }
)

# 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
EXPECTED_ROUTE: dict[int, Optional[str]] = {
    0: "campus",
    1: "off-campus",
    2: "campus",
    3: "off-campus",
    4: None,
    5: None,
    6: None,
}


def _log(level: str, msg: str, **kwargs: object) -> None:
    payload = {"level": level, "service": "meter-intake", "msg": msg, **kwargs}
    print(json.dumps(payload), file=sys.stderr)


def build_digest(day: Optional[date] = None) -> str:
    """Compose the daily digest message string."""
    if day is None:
        day = datetime.now(tz=SGT).date()

    readings = get_today_readings(day)
    weekday = day.weekday()
    expected = EXPECTED_ROUTE.get(weekday)

    lines = [f"*Meter Reading Digest — {day.strftime('%a %d %b %Y')}*\n"]

    if not readings:
        lines.append("No readings logged today.")
    else:
        by_prop: dict[str, list[dict]] = {}
        for r in readings:
            prop = str(r.get("property", "unknown"))
            by_prop.setdefault(prop, []).append(r)
        for prop in sorted(by_prop):
            for r in by_prop[prop]:
                delta = r.get("delta")
                if delta is not None:
                    delta_str = f"+{delta:.1f}" if float(delta) >= 0 else f"{delta:.1f}"
                else:
                    delta_str = "?"
                lines.append(
                    f"• {prop} — {r.get('utility_type', '?')} "
                    f"reading {r.get('reading', '?')} ({delta_str}) "
                    f"by {r.get('reader', '?')}"
                )

    lines.append("")

    # Expectation check
    if expected == "campus":
        logged_campus = {r.get("property") for r in readings if r.get("property") in CAMPUS_PROPERTIES}
        if not logged_campus:
            lines.append("⚠️ MISS: campus readings expected today — none logged.")
        else:
            lines.append(f"✓ Campus route covered: {', '.join(sorted(logged_campus))}")
    elif expected == "off-campus":
        logged_offcampus = {r.get("property") for r in readings if r.get("property") not in CAMPUS_PROPERTIES}
        if not logged_offcampus:
            lines.append("⚠️ MISS: off-campus readings expected today — none logged.")
        else:
            lines.append(f"✓ Off-campus route covered: {', '.join(sorted(logged_offcampus))}")
    else:
        lines.append("(No scheduled route today.)")

    return "\n".join(lines)


def send_digest(dry_run: bool = True, day: Optional[date] = None) -> None:
    contact_id = os.environ.get("ERWAN_CONTACT_ID", "")
    inbox_id = os.environ.get("ERWAN_INBOX_ID", "")

    if not dry_run and (not contact_id or not inbox_id):
        _log("error", "ERWAN_CONTACT_ID and ERWAN_INBOX_ID must be set for live sends")
        raise RuntimeError("ERWAN_CONTACT_ID / ERWAN_INBOX_ID not set")

    text = build_digest(day)
    _log("info", "daily_digest_ready", dry_run=dry_run, length=len(text))
    send_reply(inbox_id or "ops", contact_id or "erwan", text, dry_run=dry_run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send daily meter-reading digest to Erwan")
    parser.add_argument("--send", choices=["dry", "live"], default="dry")
    parser.add_argument("--date", help="Override date (YYYY-MM-DD)", default=None)
    args = parser.parse_args()

    override_day: Optional[date] = None
    if args.date:
        override_day = date.fromisoformat(args.date)

    send_digest(dry_run=(args.send != "live"), day=override_day)
