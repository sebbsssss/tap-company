#!/usr/bin/env python3
"""
TAP Finance Brief generator (CFO Brief v4 — TAP-wide)

Produces a Markdown brief covering all four TAP entities (TLKR, TAP Co-Livings,
Hotel, Service Apartment), structured for paste into a Google Doc and onward
share to leadership.

Data sources (per entity):
  - Xero P&L for the period (Trading Income + Cost of Sales + Operating Expenses)
  - CRM occupancy snapshot (room counts by status)
  - Xero Aged Receivables

Inputs:
  --month YYYY-MM             Period to brief (default: previous calendar month)
  --data-file <path>          Path to entity data JSON (see schema below). Defaults to bundled sample.
  --output <path>             Output Markdown file. Default: brief_<month>.md in cwd.
  --section <name>            Render only one entity section (tlkr | colivings | hotel | service_apt)

Entity data JSON schema (per entity):
  {
    "tlkr": {
      "name": "TLKR (Campus by The Assembly Place)",
      "uen": "201901964D",
      "status": "active",            # active | placeholder
      "rental_income": 1010314.00,
      "cost_of_sales": 69694.00,
      "operating_expenses": 0,
      "rooms_total": 80,
      "rooms_occupied": 76,
      "ar_total": 225171.07,
      "ar_buckets": {"current": 0, "<30d": 91385, "30-60d": 74804, "60-90d": 25974, ">90d": 33008},
      "notes": ["Block A margin 97.7%, Block B margin 91.1%", "Block B AR > Block A AR"]
    },
    "colivings": { ... },
    ...
  }

Run:
  python3 finance_brief.py --month 2026-05
  python3 finance_brief.py --month 2026-05 --section tlkr
  python3 finance_brief.py --month 2026-05 --data-file ./my-data.json --output ./brief_may.md
"""

from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUNDLED_SAMPLE = HERE / "sample_finance_entities.json"

ENTITY_ORDER = ["tlkr", "colivings", "hotel", "service_apt"]


# ---------------------------------------------------------------------------

def fmt_money(x) -> str:
    if x is None: return "—"
    try:
        if x < 0:
            return f"(S${abs(x):,.2f})"
        return f"S${x:,.2f}"
    except (TypeError, ValueError):
        return str(x)


def fmt_pct(num, denom) -> str:
    if not denom: return "—"
    try:
        return f"{(num/denom)*100:.1f}%"
    except (TypeError, ValueError, ZeroDivisionError):
        return "—"


def prev_month_iso(today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    first_of_this = today.replace(day=1)
    last_of_prev = first_of_this - dt.timedelta(days=1)
    return f"{last_of_prev.year}-{last_of_prev.month:02d}"


def period_label(month_iso: str) -> str:
    y, m = month_iso.split("-")
    return dt.date(int(y), int(m), 1).strftime("%B %Y")


# ---------------------------------------------------------------------------
# Section rendering
# ---------------------------------------------------------------------------

def render_tldr(entities: dict, period: str) -> str:
    actives = {k: v for k, v in entities.items() if v.get("status") == "active"}
    total_rev = sum(v.get("rental_income", 0) or 0 for v in actives.values())
    total_cos = sum(v.get("cost_of_sales", 0) or 0 for v in actives.values())
    total_opex = sum(v.get("operating_expenses", 0) or 0 for v in actives.values())
    total_net = total_rev - total_cos - total_opex
    rooms_tot = sum(v.get("rooms_total", 0) or 0 for v in actives.values())
    rooms_occ = sum(v.get("rooms_occupied", 0) or 0 for v in actives.values())
    ar_tot = sum(v.get("ar_total", 0) or 0 for v in actives.values())

    pending = [k for k, v in entities.items() if v.get("status") == "placeholder"]
    pending_label = ", ".join(entities[k]["name"] for k in pending) if pending else ""

    lines = []
    lines.append(f"# TAP — Finance Brief ({period})")
    lines.append("")
    lines.append("> **Status**: Draft for review by Sebastien + Yee Chin before share to leadership. Replaces CFO Brief v1–v3 (TLKR-only).")
    if pending_label:
        lines.append(f"> **Coverage**: {len(actives)} of {len(entities)} TAP entities ({pending_label} pending Xero access).")
    lines.append("")
    lines.append("## TL;DR")
    lines.append("")
    lines.append(f"- **Total rental income** across reported entities: **{fmt_money(total_rev)}**")
    lines.append(f"- **Total cost of sales**: {fmt_money(total_cos)} — margin **{fmt_pct(total_rev - total_cos, total_rev)}** before OpEx")
    lines.append(f"- **Operating expenses**: {fmt_money(total_opex)}")
    lines.append(f"- **Net before tax**: **{fmt_money(total_net)}**")
    lines.append(f"- **Occupancy**: {rooms_occ}/{rooms_tot} rooms ({fmt_pct(rooms_occ, rooms_tot)})")
    lines.append(f"- **Aged receivables (total)**: {fmt_money(ar_tot)} = **{fmt_pct(ar_tot, total_rev)}** of period rental")
    lines.append("")
    if pending:
        lines.append(f"_Entities pending: {pending_label}. Sections below show structure with placeholders until Xero access lands._")
        lines.append("")
    return "\n".join(lines)


def render_entity(key: str, e: dict) -> str:
    name = e.get("name") or key
    status = e.get("status", "unknown")
    lines = []
    lines.append(f"## {name}")
    if e.get("uen"):
        lines.append(f"*UEN: {e['uen']}*")
    lines.append("")

    if status == "placeholder":
        lines.append("**⏳ Awaiting data.** Xero org access for this entity has not yet been granted. Once it lands, this section will populate with the same template structure as the others.")
        lines.append("")
        return "\n".join(lines)

    rev = e.get("rental_income", 0) or 0
    cos = e.get("cost_of_sales", 0) or 0
    opex = e.get("operating_expenses", 0) or 0
    net = rev - cos - opex
    rooms_tot = e.get("rooms_total")
    rooms_occ = e.get("rooms_occupied")

    lines.append("### Headline P&L")
    lines.append("")
    lines.append("| Line | Amount |")
    lines.append("| --- | --- |")
    lines.append(f"| Rental income | {fmt_money(rev)} |")
    lines.append(f"| Cost of sales | {fmt_money(cos)} |")
    if opex:
        lines.append(f"| Operating expenses | {fmt_money(opex)} |")
    lines.append(f"| **Net** | **{fmt_money(net)}** |")
    lines.append(f"| Gross margin | {fmt_pct(rev - cos, rev)} |")
    if opex:
        lines.append(f"| Net margin | {fmt_pct(net, rev)} |")
    lines.append("")

    if rooms_tot:
        lines.append("### Occupancy")
        lines.append("")
        lines.append(f"- Rooms total: **{rooms_tot}**")
        lines.append(f"- Rooms occupied: **{rooms_occ}** ({fmt_pct(rooms_occ, rooms_tot)})")
        vacant = rooms_tot - (rooms_occ or 0)
        lines.append(f"- Rooms vacant: {vacant}")
        lines.append("")

    ar_tot = e.get("ar_total")
    ar_buckets = e.get("ar_buckets", {})
    if ar_tot is not None:
        lines.append("### Aged Receivables")
        lines.append("")
        lines.append(f"- **Total AR**: {fmt_money(ar_tot)} ({fmt_pct(ar_tot, rev)} of rental income)")
        if ar_buckets:
            lines.append("- Aging:")
            for bucket in ("current", "<30d", "30-60d", "60-90d", ">90d"):
                if bucket in ar_buckets:
                    lines.append(f"    - {bucket}: {fmt_money(ar_buckets[bucket])}")
        lines.append("")

    notes = e.get("notes") or []
    if notes:
        lines.append("### Observations")
        lines.append("")
        for n in notes:
            lines.append(f"- {n}")
        lines.append("")
    return "\n".join(lines)


def render_cross_entity_section(entities: dict) -> str:
    actives = {k: v for k, v in entities.items() if v.get("status") == "active"}
    if len(actives) < 2:
        return ""
    # Find which entity has the highest AR ratio
    ratios = [(k, (v.get("ar_total") or 0) / max(v.get("rental_income") or 1, 1)) for k, v in actives.items()]
    ratios.sort(key=lambda x: -x[1])
    lines = []
    lines.append("## Cross-entity observations")
    lines.append("")
    if ratios:
        worst = ratios[0]
        lines.append(f"- **Highest AR-to-rental ratio**: {entities[worst[0]]['name']} ({worst[1]*100:.1f}%). Worth a follow-up with Finance on dunning status.")
    margins = [(k, ((v.get("rental_income") or 0) - (v.get("cost_of_sales") or 0)) / max(v.get("rental_income") or 1, 1)) for k, v in actives.items()]
    margins.sort(key=lambda x: x[1])
    if margins:
        worst_m = margins[0]
        lines.append(f"- **Lowest gross margin**: {entities[worst_m[0]]['name']} ({worst_m[1]*100:.1f}%). Line-item review recommended.")
    lines.append("")
    return "\n".join(lines)


def render_methodology(period: str) -> str:
    lines = []
    lines.append("---")
    lines.append("")
    lines.append("## Methodology")
    lines.append("")
    lines.append(f"- Period: **{period}**")
    lines.append("- Rental income, cost of sales, OpEx: Xero P&L per entity (Tracking Category: Location for property-level filtering)")
    lines.append("- Occupancy: CRM (room status snapshot)")
    lines.append("- Aged receivables: Xero Aged Receivables report (by Location)")
    lines.append("- All amounts in SGD unless noted")
    lines.append("")
    lines.append("## Distribution")
    lines.append("")
    lines.append("- **Draft** — for Sebastien + Yee Chin to review")
    lines.append("- **Approved** — share with CFO + CEO")
    lines.append("- **Final** — file in Drive folder _CFO Briefs / [Period]_")
    lines.append("")
    lines.append(f"_Generated {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} by tap-automations / tap-finance-brief skill._")
    return "\n".join(lines)


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="TAP TAP-wide CFO Brief generator (v4)")
    ap.add_argument("--month", default=prev_month_iso(),
                    help="Period to brief, YYYY-MM. Default: previous calendar month.")
    ap.add_argument("--data-file", default=str(BUNDLED_SAMPLE),
                    help="Path to entity data JSON. Default: bundled sample.")
    ap.add_argument("--output", default=None,
                    help="Output Markdown file. Default: brief_<month>.md in cwd.")
    ap.add_argument("--section", default=None, choices=[None] + ENTITY_ORDER,
                    help="Render only one entity section instead of the full brief.")
    args = ap.parse_args()

    data_path = Path(args.data_file)
    if not data_path.exists():
        sys.exit(f"ERROR: data file not found: {data_path}")
    with data_path.open() as f:
        raw = json.load(f)
    # Filter out metadata keys (anything starting with underscore)
    entities = {k: v for k, v in raw.items() if not k.startswith("_") and isinstance(v, dict)}

    period = period_label(args.month)
    out_path = Path(args.output or f"brief_{args.month}.md")

    parts = []
    if args.section:
        parts.append(render_entity(args.section, entities[args.section]))
    else:
        parts.append(render_tldr(entities, period))
        for key in ENTITY_ORDER:
            if key in entities:
                parts.append(render_entity(key, entities[key]))
        parts.append(render_cross_entity_section(entities))
        parts.append(render_methodology(period))

    out_path.write_text("\n".join(parts))
    print(f"✓ Wrote {out_path}  ({out_path.stat().st_size:,} bytes)")
    if not args.section:
        print(f"  → Paste into a new Google Doc, share with: Sebastien, Yee Chin (review).")


if __name__ == "__main__":
    main()
