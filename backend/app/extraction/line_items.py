"""Line items from tender tables (schedule of requirements / bill of quantities).

A table qualifies when one of its first three rows is a header with a description-like column and a
quantity-like column. Tables on following pages with the same column count and no header are treated
as continuations. Quantities that are not plain numbers are kept as text and flagged for review.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from decimal import Decimal

from ..models import ExtractedLineItem, FieldStatus, SourceRef
from ..parsing.types import ParsedDocument, ParsedTable
from ..storage import new_id
from .normalize import parse_quantity

HEADER_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "item_no",
        re.compile(
            r"^(s\.?\s*no\.?|sr\.?\s*(no\.?)?|sl\.?\s*no\.?|item\s*(no\.?|#)|no\.?|#|serial(\s*no\.?)?|lot\s*no\.?)$",
            re.I,
        ),
    ),
    (
        "quantity",
        re.compile(
            r"^(req(uired|\.)?\s*)?(qty\.?|quantity|quantities|no\.?\s*of\s*(units|items|nos))(\s*\(.*\))?$", re.I
        ),
    ),
    ("unit", re.compile(r"^(unit|units|uom|u\.?o\.?m\.?|unit\s*of\s*(measure|measurement))$", re.I)),
    ("unit_price", re.compile(r"^(unit\s*(price|rate|cost)|rate|price)(\s*\(.*\))?$", re.I)),
    ("amount", re.compile(r"^(amount|total(\s*(price|amount|cost))?|line\s*total)(\s*\(.*\))?$", re.I)),
    ("specification", re.compile(r"(spec(ification)?s?|technical\s*(details|requirements?)|features|details)", re.I)),
    (
        "description",
        re.compile(
            r"(description|particulars|name\s*of\s*(item|goods|equipment)|^items?$|goods|equipment|product|services?)",
            re.I,
        ),
    ),
]

_TOTAL_ROW = re.compile(r"^(sub\s*-?\s*total|grand\s*total|total)\b", re.I)


def classify_header(cells: list[str]) -> dict[int, str]:
    mapping: dict[int, str] = {}
    used: set[str] = set()
    for idx, cell in enumerate(cells):
        text = cell.strip()
        if not text:
            continue
        for attr, rx in HEADER_PATTERNS:
            if attr in used:
                continue
            if rx.search(text):
                mapping[idx] = attr
                used.add(attr)
                break
    return mapping


def _header_index(table: ParsedTable) -> tuple[int, dict[int, str]] | None:
    for i, row in enumerate(table.rows[:3]):
        mapping = classify_header(row)
        attrs = set(mapping.values())
        if "description" in attrs and "quantity" in attrs:
            return i, mapping
    return None


def extract_line_items(
    parsed: ParsedDocument, make_ref: Callable[[str, int | None], SourceRef | None]
) -> tuple[list[ExtractedLineItem], list[str]]:
    items: list[ExtractedLineItem] = []
    warnings: list[str] = []
    active: dict[int, str] | None = None
    active_cols = 0
    last_page: int | None = None
    header_cells: list[str] = []

    for table in parsed.tables:
        found = _header_index(table)
        start = 0
        if found is not None:
            header_i, active = found
            active_cols = len(table.rows[header_i])
            header_cells = table.rows[header_i]
            start = header_i + 1
        elif (
            active is not None
            and table.rows
            and len(table.rows[0]) == active_cols
            and table.page is not None
            and last_page is not None
            and table.page == last_page + 1
        ):
            start = 0  # continuation of the previous items table on the next page
        else:
            active = None
            continue
        last_page = table.page
        for r in range(start, len(table.rows)):
            row = table.rows[r]
            if row == header_cells:
                continue  # repeated header on a new page
            cells = {attr: (row[i] if i < len(row) else "") for i, attr in active.items()}
            description = cells.get("description", "").strip()
            first = next((c for c in row if c.strip()), "")
            if _TOTAL_ROW.match(first) and not cells.get("quantity"):
                continue
            if not any(v.strip() for v in cells.values()):
                continue
            qty_text = cells.get("quantity", "").strip()
            qty, qty_unit = parse_quantity(qty_text)
            unit = cells.get("unit", "").strip() or qty_unit
            status = FieldStatus.extracted
            notes: list[str] = []
            if not description:
                status = FieldStatus.needs_review
                notes.append("No description in this row.")
            if qty is None:
                status = FieldStatus.needs_review
                notes.append(
                    f"Quantity “{qty_text}” is not a plain number." if qty_text else "No quantity in this row."
                )
            elif qty <= 0:
                status = FieldStatus.needs_review
                notes.append("Quantity is zero or negative.")
            items.append(
                ExtractedLineItem(
                    id=new_id("itm"),
                    item_no=cells.get("item_no") or None,
                    description=description or None,
                    quantity=qty,
                    quantity_text=qty_text or None,
                    unit=unit or None,
                    specification=cells.get("specification") or None,
                    status=status,
                    source=make_ref(table.block_ids[r], None),
                    notes=notes,
                )
            )

    _flag_duplicates(items)
    if not items:
        warnings.append(
            "No line-item table was recognised (a table with description and quantity columns). "
            "Add line items manually in the review step."
        )
    return items, warnings


def _norm_desc(text: str | None) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", (text or "").lower()).split())


def _flag_duplicates(items: list[ExtractedLineItem]) -> None:
    by_desc: dict[str, list[ExtractedLineItem]] = {}
    for it in items:
        key = _norm_desc(it.description)
        if key:
            by_desc.setdefault(key, []).append(it)
    for group in by_desc.values():
        if len(group) < 2:
            continue
        quantities = {it.quantity for it in group}
        if len(quantities) > 1:
            listing = ", ".join(str(q) if isinstance(q, Decimal) else "?" for q in quantities)
            for it in group:
                it.status = FieldStatus.conflict
                it.notes.append(f"This item appears {len(group)} times with different quantities ({listing}).")
