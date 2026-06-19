"""
Email classifier and extractor for jarvis.ai@theassemblyplace.com inbox.

Per Sebastien architecture (THE-17480):
  - Every email is classified as finance / operations / neither.
  - Finance emails are further parsed for property, month, and line items.
  - No subject/sender patterns — pure LLM inference.
  - Handles PDF (Anthropic document API) and xlsx (zipfile+xml) attachments.

Line item types:
  cleaning        — cleaning charges, cleaner fees, housekeeping
  servicing       — aircon servicing, pest control, repairs, maintenance
  stock           — stock vouchers, supplies (maps to 'Stock taken' in settlement)
  deposits        — security deposit top-ups or refunds
  excess_utility  — excess utility charges billed to tenants
  pob             — payment on behalf (Whiz, subscriptions, etc.)
  other           — Finance-relevant but doesn't fit above categories

Usage:
  from email_classifier import classify_email, ClassifiedEmail
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class LineItem:
    type: str        # cleaning / servicing / stock / deposits / excess_utility / pob / other
    amount: float
    description: str


@dataclass
class ClassifiedEmail:
    category: str              # "finance" | "operations" | "neither"
    confidence: float          # 0.0 - 1.0
    property_name: str | None  # for finance emails, full address as written
    month: str | None          # "2026-06" format
    line_items: list[LineItem]
    raw_response: str          # full LLM response for audit


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_CLASSIFY_PROMPT = """\
You are a property management finance classifier for The Assembly Place (Singapore co-living operator).

Today's date: {today_date}
Current month: {today_month}

An email has been received at jarvis.ai@theassemblyplace.com. Classify it and extract structured data.

CATEGORIES:
- "finance": Settlement-relevant charges for a specific property. Includes cleaning fees, \
aircon servicing, pest control, repairs/maintenance, stock vouchers/supplies, \
security deposit top-ups or refunds, excess utility charges billed to tenants, \
payments on behalf (Whiz, subscriptions, etc.), or any invoice/charge tied to a unit/property.
- "operations": Maintenance requests, tenant complaints, booking/reservation inquiries, \
operational tasks, staff communications. NOT finance charges.
- "neither": General enquiries, marketing, newsletters, unrelated correspondence.

LINE ITEM TYPES (for finance emails only):
- "cleaning"        — cleaning charge, cleaner fee, housekeeping, spring cleaning
- "servicing"       — aircon servicing, pest control, plumbing, electrical, repairs, handyman, maintenance
- "stock"           — stock vouchers, supplies, consumables (maps to 'Stock taken' in settlement)
- "deposits"        — security deposit top-up or refund
- "excess_utility"  — excess utility charges billed to tenants
- "pob"             — payment on behalf (Whiz, subscriptions, platform fees, etc.)
- "other"           — finance-relevant but doesn't fit above categories

Email subject: {subject}

Email body:
{body_text}

{attachments_section}

INSTRUCTIONS:
1. Classify the email as "finance", "operations", or "neither".
2. If "finance": extract the property address (as written), the settlement month (YYYY-MM format), \
and all individual line items with type, amount (SGD), and description.
3. For the month: use the month explicitly stated in the email or attachment; if ambiguous or not \
stated, use the current month ({today_month}).
4. All amounts are SGD. If currency is unlabelled, assume SGD.
5. Return ONLY a JSON object — no preamble, no explanation, no markdown fences.

Return EXACTLY this JSON structure:
{{
  "category": "finance" | "operations" | "neither",
  "confidence": 0.0-1.0,
  "property_name": "full address as written, or null",
  "month": "YYYY-MM or null",
  "line_items": [
    {{"type": "cleaning", "amount": 120.00, "description": "Monthly cleaning fee"}}
  ]
}}
"""

# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

def classify_email(
    subject: str,
    body_text: str,                  # pre-extracted text from email body
    pdf_attachments: list[bytes],    # raw PDF bytes (up to 3)
    xlsx_texts: list[str],           # pre-extracted xlsx cell text
    today_date: str,                 # "2026-06-19" — helps with "this month" inference
) -> ClassifiedEmail:
    """Classify and extract structured data from an email using Claude Haiku.

    Args:
        subject:          Email subject line.
        body_text:        Pre-extracted plaintext of the email body (HTML stripped).
        pdf_attachments:  List of raw PDF bytes (max 3 will be sent to the LLM).
        xlsx_texts:       Pre-extracted cell text from any xlsx attachments.
        today_date:       ISO date string "YYYY-MM-DD" used for month inference.

    Returns:
        ClassifiedEmail with category, confidence, property_name, month, and line_items.
        On any error (missing SDK, API failure, JSON parse error), returns a safe
        "neither" result with confidence 0.0.
    """
    # Derive current month from today_date
    today_month = today_date[:7] if today_date else ""

    _empty = ClassifiedEmail(
        category="neither",
        confidence=0.0,
        property_name=None,
        month=None,
        line_items=[],
        raw_response="",
    )

    try:
        from anthropic import Anthropic
    except ImportError:
        _empty.raw_response = "anthropic SDK not available"
        return _empty

    client = Anthropic()

    # Build the attachments section of the prompt
    attachments_section_parts: list[str] = []
    if xlsx_texts:
        for i, text in enumerate(xlsx_texts, 1):
            truncated = text[:3000]
            attachments_section_parts.append(
                f"[Spreadsheet attachment {i}]:\n{truncated}"
            )
    attachments_section = "\n\n".join(attachments_section_parts) if attachments_section_parts else ""

    prompt_text = _CLASSIFY_PROMPT.format(
        today_date=today_date,
        today_month=today_month,
        subject=subject,
        body_text=body_text[:5000],
        attachments_section=attachments_section,
    )

    # Build content blocks: PDF documents first, then the text prompt
    content_blocks: list[dict] = []
    for pdf_bytes in pdf_attachments[:3]:
        try:
            content_blocks.append({
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": base64.standard_b64encode(pdf_bytes).decode("ascii"),
                },
            })
        except Exception:
            pass

    content_blocks.append({"type": "text", "text": prompt_text})

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": content_blocks}],
        )
        raw = response.content[0].text.strip()
    except Exception as exc:
        _empty.raw_response = f"LLM call failed: {exc}"
        return _empty

    # Parse JSON — robust to minor preamble/postamble
    parsed: dict = {}
    try:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            parsed = json.loads(m.group())
    except (json.JSONDecodeError, ValueError):
        _empty.raw_response = raw
        return _empty

    # Extract and validate fields
    category = str(parsed.get("category", "neither"))
    if category not in ("finance", "operations", "neither"):
        category = "neither"

    try:
        confidence = float(parsed.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.0

    property_name_raw = parsed.get("property_name")
    property_name = str(property_name_raw) if property_name_raw else None

    month_raw = parsed.get("month")
    month: str | None = None
    if month_raw:
        # Validate "YYYY-MM" format
        if re.match(r"^\d{4}-\d{2}$", str(month_raw)):
            month = str(month_raw)
        else:
            # Try to salvage a partial date like "2026-6" -> "2026-06"
            mo = re.search(r"(\d{4})-(\d{1,2})", str(month_raw))
            if mo:
                month = f"{mo.group(1)}-{int(mo.group(2)):02d}"

    line_items: list[LineItem] = []
    valid_types = {"cleaning", "servicing", "stock", "deposits", "excess_utility", "pob", "other"}
    for item in parsed.get("line_items") or []:
        try:
            item_type = str(item.get("type", "other"))
            if item_type not in valid_types:
                item_type = "other"
            amount = float(item.get("amount", 0.0))
            description = str(item.get("description", ""))[:200]
            line_items.append(LineItem(type=item_type, amount=amount, description=description))
        except (TypeError, ValueError, AttributeError):
            continue

    return ClassifiedEmail(
        category=category,
        confidence=confidence,
        property_name=property_name,
        month=month,
        line_items=line_items,
        raw_response=raw,
    )
