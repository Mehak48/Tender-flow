"""Optional user-supplied price list (XLSX/CSV) and deterministic matching to tender line items.

Matching uses token overlap between the tender item description and the price-list item name. A match
is only *proposed*: identical names are marked confirmed, anything fuzzier needs the user's confirmation.
Items without a match keep a missing price — TenderFlow never estimates prices.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from .extraction.normalize import detect_currency, parse_decimal
from .models import DocumentRecord, PriceList, PriceListRow
from .parsing.types import ParsedDocument

_NAME_HEADER = re.compile(
    r"^(item|items|item name|description|product|particulars|name|service|item description)$", re.I
)
_PRICE_HEADER = re.compile(r"(unit\s*price|price|rate|unit\s*rate|unit\s*cost|cost)", re.I)
_UNIT_HEADER = re.compile(r"^(unit|uom|units)$", re.I)
STOPWORDS = {
    "and",
    "the",
    "of",
    "for",
    "with",
    "a",
    "an",
    "to",
    "in",
    "on",
    "x",
    "nos",
    "no",
    "lot",
    "box",
    "boxes",
    "unit",
    "units",
}


def _header_key(text: str) -> str:
    return re.sub(r"\(.*?\)", "", text).strip()


def parse_price_list(parsed: ParsedDocument, record: DocumentRecord) -> PriceList:
    pl = PriceList(document_id=record.id, document_name=record.filename)
    for table in parsed.tables:
        header_at: int | None = None
        name_col = price_col = unit_col = None
        currency: str | None = None
        for i, row in enumerate(table.rows[:6]):
            n = next((j for j, c in enumerate(row) if _NAME_HEADER.match(_header_key(c))), None)
            p = next((j for j, c in enumerate(row) if j != n and _PRICE_HEADER.search(c)), None)
            if n is not None and p is not None:
                header_at, name_col, price_col = i, n, p
                unit_col = next((j for j, c in enumerate(row) if _UNIT_HEADER.match(_header_key(c))), None)
                currency = detect_currency(row[p])
                break
        if header_at is None or name_col is None or price_col is None:
            continue
        for r in range(header_at + 1, len(table.rows)):
            row = table.rows[r]
            name = row[name_col].strip() if name_col < len(row) else ""
            raw_price = row[price_col] if price_col < len(row) else ""
            price = parse_decimal(raw_price)
            if not name:
                continue
            block = parsed.block(table.block_ids[r])
            block_row = block.row if block is not None and block.row is not None else r + 1
            if price is None or price < 0:
                pl.warnings.append(f"Row {block_row}: “{name[:40]}” has no valid price and was skipped.")
                continue
            unit = row[unit_col].strip() if unit_col is not None and unit_col < len(row) else None
            pl.rows.append(
                PriceListRow(row=block_row, name=name, unit_price=price, unit=unit or None, currency=currency)
            )
        if pl.rows:
            break
    if not pl.rows:
        pl.warnings.append(
            "No price rows were found. The price list needs a header row with an item/description column and "
            "a price column (for example “Item” and “Unit Price”)."
        )
    return pl


def tokens(text: str | None) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if w not in STOPWORDS and (len(w) > 1 or w.isdigit())}


@dataclass
class PriceMatch:
    row: PriceListRow
    score: float
    exact: bool


def match_price(description: str | None, price_list: PriceList | None) -> PriceMatch | None:
    if not description or price_list is None or not price_list.rows:
        return None
    a = tokens(description)
    if not a:
        return None
    scored: list[PriceMatch] = []
    for row in price_list.rows:
        b = tokens(row.name)
        if not b:
            continue
        common = a & b
        overlap = len(common) / min(len(a), len(b))
        if len(common) < min(2, len(a), len(b)):
            continue
        if overlap >= 0.75:
            exact = a == b
            scored.append(PriceMatch(row=row, score=round(overlap, 2), exact=exact))
    if not scored:
        return None
    scored.sort(key=lambda m: (m.exact, m.score), reverse=True)
    if len(scored) > 1 and scored[0].score == scored[1].score and scored[0].exact == scored[1].exact:
        return None  # ambiguous: two equally good rows — leave the price for the user
    return scored[0]


def describe_match(m: PriceMatch) -> str:
    if m.exact:
        kind = "exact name match"
    elif m.score >= 1:
        kind = "all words of the shorter name match — please confirm"
    else:
        kind = f"{int(m.score * 100)}% word overlap — please confirm"
    return f"Price list row {m.row.row}: “{m.row.name}” ({kind})"


def price_currency(price_list: PriceList | None) -> str | None:
    if not price_list:
        return None
    codes = {r.currency for r in price_list.rows if r.currency}
    return codes.pop() if len(codes) == 1 else None


__all__ = ["Decimal", "PriceMatch", "describe_match", "match_price", "parse_price_list", "price_currency", "tokens"]
