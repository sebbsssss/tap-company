#!/usr/bin/env python3
"""
TAP CRM — Ticket Digest v2 (Tier A: read + WhatsApp summary)

Pulls open tickets from the CRM (Operations → Ticketing), computes a digest,
and (optionally) sends it via Twilio WhatsApp to the configured recipient(s).

Phase 1 Tier A scope per the 12 May 2026 Ops meeting:
  - READ ONLY: no replies posted to tickets, no status changes
  - WhatsApp summary every 2 hrs to Sebastien (validation period)
  - Scope: ALL CRM tickets (Co-livings + Hotel + Service Apt).
    TLKR Campus is intentionally out — it does NOT use CRM ticketing
    (confirmed 12 May 2026: TELOK KURAU / TLKR searches return 0 records).

Field structure mirrors the live Operations > Ticketing UI as observed:
  service, category, area_type, ticket_priority (Low/Mid/High),
  ticket_id, area (region), property, unit, room, rate,
  created_at, preferred_visit_date, completed_on, ticket_status

Data source modes:
  --source sample   Read from sample_tickets.json (default; demo mode)
  --source api      Call /com/service/tickets/ on the staff API (requires CRM_STAFF_TOKEN env var)

Send modes:
  --send dry        Print digest to stdout only (default; for review)
  --send whatsapp   Use ../twilio_send.sh to fire the message to RECIPIENT_NUMBER

Run:
  python3 digest.py --source sample --send dry
  python3 digest.py --source sample --send whatsapp
  python3 digest.py --source api --send whatsapp     # once staff API token lands
"""

from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SAMPLE_PATH = HERE / "sample_tickets.json"
TWILIO_SCRIPT = HERE.parent / "twilio_send.sh"

# Statuses considered "open" (still need staff attention).
# Names confirmed from the live Ticket Status dropdown 14 May 2026.
OPEN_STATUSES = {"Open", "Acknowledged", "In Progress", "Scheduled"}

# Recipient for the validation period — Sebastien's WhatsApp.
DEFAULT_RECIPIENT = os.environ.get("TAP_DIGEST_TO", os.environ.get("TLKR_DIGEST_TO", ""))

NOW = dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))   # Singapore time


# ---------------------------------------------------------------------------
# Data fetch
# ---------------------------------------------------------------------------

def load_sample() -> list[dict]:
    with SAMPLE_PATH.open() as f:
        payload = json.load(f)
    return payload.get("results", [])


def _flatten_ticket(t: dict) -> dict:
    """Map the API's nested ticket shape to the flat shape build_digest expects.
    Works for both /com/service/tickets/ (staff) and /member/service/tickets/ (tenant).
    """
    room = t.get("room") or {}
    unit = (room.get("unit") or {}) if isinstance(room.get("unit"), dict) else {}
    prop = (unit.get("prop") or {}) if isinstance(unit.get("prop"), dict) else {}
    cat  = t.get("category") or {}
    pri  = t.get("priority") or {}
    statuses = t.get("statuses") or []
    # Current status = the most recent entry by `created`.
    current_status = ""
    if statuses:
        try:
            latest = max(statuses, key=lambda s: s.get("created", ""))
            current_status = (latest.get("status") or "").strip()
        except Exception:
            current_status = (statuses[-1].get("status") or "").strip()
    # Most recent staff/anyone modification across the status trail
    last_modified_at = None
    for s in statuses:
        c = s.get("created")
        if c and (last_modified_at is None or c > last_modified_at):
            last_modified_at = c
    return {
        "ticket_id":             t.get("id"),
        "service":               cat.get("service") or "",
        "category":              cat.get("name") or "",
        "area_type":             "",  # not exposed on member endpoint
        "ticket_priority":       (pri.get("name") if isinstance(pri, dict) else (pri or "")) or "",
        "area":                  prop.get("area") or "",
        "property":              prop.get("name") or "",
        "unit":                  unit.get("name") or "",
        "room":                  room.get("number") or "",
        "rate":                  None,
        "created_at":            t.get("created"),
        "preferred_visit_date":  t.get("preferred_date"),
        "completed_on":          t.get("completed_on"),
        "ticket_status":         current_status,
        "last_staff_reply_at":   last_modified_at,
        "comment_count":         len(statuses),
        "remarks":               t.get("remarks") or "",
        "raised_by":             (t.get("raised_by") or {}).get("name") if isinstance(t.get("raised_by"), dict) else "",
    }


def load_api() -> list[dict]:
    """Pull tickets from CRM API. Prefers staff /com/ if CRM_STAFF_TOKEN is set;
    otherwise falls back to /member/ with CRM_MEMBER_TOKEN."""
    staff_token  = os.environ.get("CRM_STAFF_TOKEN")
    member_token = os.environ.get("CRM_MEMBER_TOKEN")
    base = os.environ.get("CRM_API_BASE", "https://crm-api.theassemblyplace.com").rstrip("/")

    if staff_token:
        url = f"{base}/com/service/tickets/?limit=500&ordering=-id"
        token = staff_token
        scope = "staff (/com/)"
    elif member_token:
        url = f"{base}/member/service/tickets/?limit=500"
        token = member_token
        scope = "member (/member/)"
    else:
        sys.exit("ERROR: --source api requires CRM_STAFF_TOKEN or CRM_MEMBER_TOKEN env var.")

    print(f"[api] scope: {scope}", file=sys.stderr)
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Token {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as e:
        sys.exit(f"ERROR: API returned HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}")
    raw = payload.get("results", payload if isinstance(payload, list) else [])
    return [_flatten_ticket(t) for t in raw]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_dt(s: str | None) -> dt.datetime | None:
    if not s: return None
    s = s.replace("Z", "+00:00")
    try:
        return dt.datetime.fromisoformat(s)
    except ValueError:
        return None


def hours_since(when: dt.datetime | None) -> float:
    if when is None: return float("inf")
    return (NOW - when).total_seconds() / 3600.0


def fmt_age(hours: float) -> str:
    if hours == float("inf"): return "—"
    if hours < 48:   return f"{hours:.0f}h"
    if hours < 24*14: return f"{hours/24:.0f}d"
    return f"{hours/(24*7):.0f}w"


# Priority ordering for sorting (lower number = higher priority).
# Tickets with no priority go to the end.
PRI_RANK = {"High": 0, "Mid": 1, "Low": 2, "": 3, None: 3}


# ---------------------------------------------------------------------------
# Digest computation
# ---------------------------------------------------------------------------

def filter_open(tickets: list[dict]) -> list[dict]:
    return [t for t in tickets if t.get("ticket_status") in OPEN_STATUSES]


def build_digest(tickets: list[dict]) -> str:
    open_tickets = filter_open(tickets)
    total = len(open_tickets)
    # Recent activity context (used both as headline and as fallback when nothing is open)
    recent_30d = [t for t in tickets if hours_since(parse_dt(t.get("created_at"))) <= 24*30]
    recent_status_counts = Counter(t.get("ticket_status") or "(none)" for t in recent_30d)

    # Age buckets (based on created_at)
    aged = {"<24h": 0, "1-7d": 0, "1-4w": 0, ">1mo": 0}
    for t in open_tickets:
        h = hours_since(parse_dt(t.get("created_at")))
        if   h < 24:        aged["<24h"]  += 1
        elif h < 24*7:      aged["1-7d"]  += 1
        elif h < 24*30:     aged["1-4w"]  += 1
        else:               aged[">1mo"]  += 1

    by_service  = Counter(t.get("service")        for t in open_tickets)
    by_category = Counter(t.get("category")       for t in open_tickets)
    by_area     = Counter(t.get("area")           for t in open_tickets)
    by_status   = Counter(t.get("ticket_status")  for t in open_tickets)
    by_priority = Counter(t.get("ticket_priority") or "(unset)" for t in open_tickets)
    by_property = Counter(t.get("property")       for t in open_tickets)

    # Highest priority unresolved, oldest within priority first
    top_priority = sorted(
        open_tickets,
        key=lambda t: (PRI_RANK.get(t.get("ticket_priority"), 9),
                       -hours_since(parse_dt(t.get("created_at"))))
    )[:7]

    # New in the last 2 hours (matches our cadence)
    new_window = [
        t for t in open_tickets
        if hours_since(parse_dt(t.get("created_at"))) <= 2
    ]

    # Oldest unresolved (any priority) — top 5
    oldest = sorted(
        open_tickets,
        key=lambda t: -hours_since(parse_dt(t.get("created_at")))
    )[:5]

    # ---- Render ----
    lines = []
    lines.append(f"*TAP Tickets — {NOW:%a %d %b, %H:%M}*")
    lines.append("_Scope: all CRM ticketing (Co-livings + Hotel + Service Apt). TLKR Campus runs separately._")
    lines.append("")
    lines.append(f"Open: *{total}*    New (≤2h): *{len(new_window)}*    Activity (last 30d): *{len(recent_30d)}*")
    lines.append("")

    if total == 0:
        # Fallback content so the digest is informative when there are no open tickets.
        if recent_30d:
            lines.append("*No open tickets right now.*")
            lines.append("Recent activity (last 30d):")
            counts = recent_status_counts
        else:
            lines.append("*No open tickets, no activity in the last 30d.*")
            lines.append(f"All-time accessible tickets ({len(tickets)}):")
            counts = Counter(t.get("ticket_status") or "(none)" for t in tickets)
        for st, n in counts.most_common():
            lines.append(f"  {st}: {n}")
        # Show service & property breakdown to confirm the API is talking to us
        if tickets:
            lines.append("")
            lines.append("By service (all-time):")
            for svc, n in Counter(t.get("service") or "—" for t in tickets).most_common():
                lines.append(f"  {svc}: {n}")
            lines.append("")
            lines.append("By property (all-time, top 5):")
            for prop, n in Counter(t.get("property") or "—" for t in tickets).most_common(5):
                lines.append(f"  {prop}: {n}")
        lines.append("")
        lines.append(f"_Pipeline test — pulled live from CRM API ({os.environ.get('CRM_API_BASE','crm-api.theassemblyplace.com')})._")
        lines.append("_Reply STOP to pause this digest._")
        return "\n".join(lines)


    lines.append("*Age:*")
    lines.append(f"  <24h: {aged['<24h']}    1–7d: {aged['1-7d']}    1–4w: {aged['1-4w']}    >1mo: *{aged['>1mo']}*")
    lines.append("")

    lines.append("*By service:*")
    for svc, n in by_service.most_common():
        lines.append(f"  {svc}: {n}")
    lines.append("")

    lines.append("*By priority:*")
    for pri, n in sorted(by_priority.items(), key=lambda x: PRI_RANK.get(x[0], 9)):
        emphasis = "*" if pri == "High" else ""
        lines.append(f"  {emphasis}{pri}: {n}{emphasis}")
    lines.append("")

    lines.append("*By area:*")
    for area, n in by_area.most_common():
        lines.append(f"  {area or '(none)'}: {n}")
    lines.append("")

    lines.append("*By category (top 6):*")
    for cat, n in by_category.most_common(6):
        lines.append(f"  {cat}: {n}")
    lines.append("")

    lines.append("*Top properties (top 5):*")
    for prop, n in by_property.most_common(5):
        lines.append(f"  {prop}: {n}")
    lines.append("")

    lines.append("*Top priorities — oldest within highest priority first:*")
    for t in top_priority:
        age = fmt_age(hours_since(parse_dt(t.get("created_at"))))
        pri = (t.get("ticket_priority") or "—")
        prop = t.get("property", "")
        room = t.get("room", "")
        cat = t.get("category", "")
        svc = t.get("service", "")
        lines.append(f"  • #{t.get('ticket_id')} [{pri}] {svc}/{cat} — {prop} {room} ({age} old)")
    lines.append("")

    lines.append("*Oldest unresolved (any priority):*")
    for t in oldest:
        age = fmt_age(hours_since(parse_dt(t.get("created_at"))))
        lines.append(f"  • #{t.get('ticket_id')} {t.get('property','')} {t.get('room','')} — {t.get('category','')} ({age})")
    lines.append("")

    lines.append("_Reply STOP to pause this digest. Reply HOURLY/2H/3H to change cadence._")
    lines.append("_Tier A: read-only. AI does NOT reply to tenants in this mode._")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------

def send_via_twilio(body: str, to: str):
    if not to:
        sys.exit("ERROR: no recipient. Set TAP_DIGEST_TO env var (e.g. whatsapp:+65XXXXXXXX)")
    if not TWILIO_SCRIPT.exists():
        sys.exit(f"ERROR: Twilio sender not found at {TWILIO_SCRIPT}")
    res = subprocess.run([str(TWILIO_SCRIPT), to, body], capture_output=True, text=True)
    sys.stdout.write(res.stdout)
    if res.returncode != 0:
        sys.stderr.write(res.stderr)
        sys.exit(res.returncode)


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="TAP CRM ticket digest (Tier A — all CRM divisions)")
    ap.add_argument("--source", choices=["sample", "api"], default="sample")
    ap.add_argument("--send",   choices=["dry", "whatsapp"], default="dry")
    ap.add_argument("--to",     default=DEFAULT_RECIPIENT)
    args = ap.parse_args()

    tickets = load_sample() if args.source == "sample" else load_api()
    digest  = build_digest(tickets)

    print(digest)
    print()
    print(f"-- end of digest ({len(digest)} chars) --")

    if args.send == "whatsapp":
        send_via_twilio(digest, args.to)


if __name__ == "__main__":
    main()
