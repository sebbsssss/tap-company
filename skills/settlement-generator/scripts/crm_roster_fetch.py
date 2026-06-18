#!/usr/bin/env python3
"""
crm_roster_fetch.py — CRM roster fetcher for settlement-generator

Workaround for /com/report/settlement/ returning HTTP 500.
Pulls from the working /com/dashboard/room_availability/ endpoint and
transforms it into the roster JSON shape that settlement.py --roster expects.

Issue: THE-17330 (CRM /com/report/settlement/ returns 500 on all requests)

Usage:
  python3 crm_roster_fetch.py --property "18 JALAN JINTAN" --period 2026-03
  python3 crm_roster_fetch.py --property "18 JALAN JINTAN" \\
      --start 2026-05-01 --end 2026-05-11
  python3 crm_roster_fetch.py --property "18 JALAN JINTAN" \\
      --period 2026-03 --output crm_roster_mar26.json

Output JSON shape (roster list, matches settlement.py --roster schema):
  [
    {
      "tenant": "Guan Mingjun",
      "room": "B01",
      "duration": "12 months",    // computed from booking dates; approximation
      "month_of": "1/12",         // computed; approximation
      "rental_rate": 2800.00,
      "rental_date": "1 Mar 26",  // formatted move_in_date
      "lease_end": "31 Mar 26"    // formatted actual_lease_end_date
    },
    ...
  ]

Limitations vs /com/report/settlement/ (when that endpoint works):
  - "duration" label may differ: "12 months" vs "Extend 12 months" (extension label
    requires lease history not available from room_availability).
  - "month_of" is computed from move_in → period start; may be off by 1 if the
    CRM settlement report uses a different reference date.
  - Only surfaces the primary booking tenant (first member). Multi-occupant
    bookings show the first member only, same as the settlement report.

Env vars required:
  CRM_API_BASE   — e.g. https://crm-api.theassemblyplace.com
  CRM_STAFF_API_KEY (or CRM_API_KEY) — x-api-key value
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

SGT = ZoneInfo("Asia/Singapore")
CRM_BASE = os.environ.get("CRM_API_BASE", "https://crm-api.theassemblyplace.com")
CRM_KEY = os.environ.get("CRM_STAFF_API_KEY") or os.environ.get("CRM_API_KEY")

MONTH_ABBR = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}


def _log(msg: str, **kw: object) -> None:
    print(json.dumps({"ts": dt.datetime.now(tz=SGT).isoformat(), "msg": msg, **kw}), file=sys.stderr)


def _headers() -> dict[str, str]:
    if not CRM_KEY:
        raise RuntimeError("CRM_STAFF_API_KEY (or CRM_API_KEY) not set in environment")
    return {"x-api-key": CRM_KEY, "Accept": "application/json"}


def _fetch_json(url: str) -> object:
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        _log("crm_http_error", status=e.code, url=url, body=body)
        raise


def fetch_rooms_for_property(property_search: str) -> list[dict]:
    """Fetch all room_availability records matching the property search term."""
    results: list[dict] = []
    page_size = 100
    params = urllib.parse.urlencode({
        "format": "json",
        "page_size": page_size,
        "search": property_search,
    })
    url: str | None = f"{CRM_BASE}/com/dashboard/room_availability/?{params}"

    while url:
        _log("fetching", url=url)
        data = _fetch_json(url)
        page = data.get("results", [])
        results.extend(page)
        url = data.get("next")  # None when last page

    _log("rooms_fetched", count=len(results), search=property_search)
    return results


def _parse_date(val: str | None) -> dt.date | None:
    if not val:
        return None
    try:
        return dt.date.fromisoformat(val)
    except (ValueError, TypeError):
        return None


def _fmt_date(d: dt.date | None) -> str:
    """Format date as "1 Mar 26"."""
    if d is None:
        return ""
    return f"{d.day} {MONTH_ABBR[d.month]} {str(d.year)[-2:]}"


def _compute_month_of(move_in: dt.date | None, period_start: dt.date, lease_end: dt.date | None) -> str:
    """
    Return "{month_index}/{total_months}" string.

    month_index: how many full months from move_in to period_start, + 1.
    total_months: from move_in to lease_end, rounded.
    """
    if not move_in or not lease_end:
        return ""
    # months from move_in to period_start (0 if same month)
    idx = (period_start.year - move_in.year) * 12 + (period_start.month - move_in.month) + 1
    idx = max(1, idx)
    # total lease months
    total = (lease_end.year - move_in.year) * 12 + (lease_end.month - move_in.month) + 1
    total = max(1, total)
    if idx > total:
        idx = total
    return f"{idx}/{total}"


def _compute_duration(total_months: int) -> str:
    """Return a display string like "12 months" or "1 month"."""
    if total_months == 1:
        return "1 month"
    return f"{total_months} months"


def _extract_booking_active_in_period(
    room: dict,
    period_start: dt.date,
    period_end: dt.date,
) -> dict | None:
    """
    Return the first occupancy_booking that overlaps with [period_start, period_end],
    or None if no active booking in that window.
    """
    for bk in room.get("occupancy_bookings", []) or []:
        move_in = _parse_date(bk.get("move_in_date"))
        lease_end = _parse_date(bk.get("actual_lease_end_date") or bk.get("lease_end_date"))
        if not move_in or not lease_end:
            continue
        # Active if booking overlaps period: started before period end AND ended after period start
        if move_in <= period_end and lease_end >= period_start:
            return bk
    return None


def build_roster(
    rooms: list[dict],
    period_start: dt.date,
    period_end: dt.date,
) -> list[dict]:
    """Transform room_availability records into settlement roster dicts."""
    roster: list[dict] = []

    for room in rooms:
        booking = _extract_booking_active_in_period(room, period_start, period_end)
        if not booking:
            continue

        members = booking.get("members") or []
        if not members:
            continue  # no named tenant

        tenant_name: str = members[0].get("name", "")
        room_number: str = room.get("number", "")
        rental_rate_raw = booking.get("rental_rate") or room.get("rental_price")
        try:
            rental_rate = float(rental_rate_raw)
        except (TypeError, ValueError):
            rental_rate = 0.0

        move_in = _parse_date(booking.get("move_in_date"))
        lease_end = _parse_date(booking.get("actual_lease_end_date") or booking.get("lease_end_date"))

        total_months = 1
        if move_in and lease_end:
            total_months = max(
                1,
                (lease_end.year - move_in.year) * 12 + (lease_end.month - move_in.month) + 1,
            )

        roster.append({
            "tenant": tenant_name,
            "room": room_number,
            "duration": _compute_duration(total_months),
            "month_of": _compute_month_of(move_in, period_start, lease_end),
            "rental_rate": rental_rate,
            "rental_date": _fmt_date(move_in),
            "lease_end": _fmt_date(lease_end),
            # metadata fields (not used by settlement.py, useful for audit)
            "_booking_id": booking.get("id"),
            "_move_in_iso": booking.get("move_in_date"),
            "_lease_end_iso": booking.get("actual_lease_end_date") or booking.get("lease_end_date"),
            "_source": "crm_roster_fetch/room_availability",
        })

    roster.sort(key=lambda r: r.get("room", ""))
    return roster


def parse_period(period: str) -> tuple[dt.date, dt.date]:
    """Parse YYYY-MM into (first_of_month, last_of_month)."""
    year, month = int(period[:4]), int(period[5:7])
    start = dt.date(year, month, 1)
    # last day of month
    if month == 12:
        end = dt.date(year + 1, 1, 1) - dt.timedelta(days=1)
    else:
        end = dt.date(year, month + 1, 1) - dt.timedelta(days=1)
    return start, end


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Fetch CRM settlement roster via room_availability (workaround for THE-17330)"
    )
    parser.add_argument("--property", required=True, help="Property name search string, e.g. '18 JALAN JINTAN'")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--period", help="YYYY-MM period (full month)")
    group.add_argument("--start", help="Period start date YYYY-MM-DD (use with --end)")
    parser.add_argument("--end", help="Period end date YYYY-MM-DD (use with --start)")
    parser.add_argument("--output", help="Output JSON file path (default: stdout)")
    parser.add_argument(
        "--fixture",
        help="Load rooms from a local JSON fixture instead of calling the API (for testing)",
    )
    args = parser.parse_args(argv)

    if args.period:
        period_start, period_end = parse_period(args.period)
    else:
        if not args.end:
            parser.error("--end is required when --start is given")
        period_start = dt.date.fromisoformat(args.start)
        period_end = dt.date.fromisoformat(args.end)

    _log(
        "fetching_roster",
        property=args.property,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
    )

    if args.fixture:
        with open(args.fixture) as f:
            raw = json.load(f)
        rooms = raw.get("results", raw) if isinstance(raw, dict) else raw
        _log("using_fixture", path=args.fixture, rooms=len(rooms))
    else:
        rooms = fetch_rooms_for_property(args.property)

    roster = build_roster(rooms, period_start, period_end)
    _log("roster_built", tenants=len(roster))

    out = json.dumps(roster, indent=2)
    if args.output:
        with open(args.output, "w") as f:
            f.write(out)
        _log("written", path=args.output)
    else:
        print(out)


if __name__ == "__main__":
    main()
