"""Rule-based natural-language instruction parser (no AI required).

Turns a short instruction into structured edit operations. It understands a fixed set of phrasings
(listed in SUPPORTED_EXAMPLES). Anything else is reported as "not understood" — the parser never guesses.
Values come only from the instruction itself, the current quotation, the tender extraction or the
user's settings; nothing is invented.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..extraction.normalize import _DURATION_RE, detect_currency, parse_decimal
from ..fields import QUOTATION_FIELDS, match_field_label
from ..models import (
    AddItemOp,
    CompanyProfile,
    EditOperation,
    HighlightMissingOp,
    Project,
    Quotation,
    RemoveItemOp,
    SetCurrencyOp,
    SetFieldOp,
    SetItemOp,
    SetTaxOp,
)
from ..pricing import tokens
from .apply import DERIVED_FIELDS

SUPPORTED_EXAMPLES = [
    "Change the delivery period to 30 days.",
    "Add a line item for the installation service.",
    "Rewrite the payment terms using the information I supplied.",
    "Highlight missing information.",
    "Change the quotation title to match the tender reference.",
    "Set the unit price of item 4 to 95000.",
    "Change the quantity of item 2 to 10.",
    "Remove item 5.",
    "Set the warranty to 2 years.",
    "Set the quotation validity to 120 days.",
    "Set currency to PKR.",
    "Set sales tax to 18%.",
    "Add a note: Prices include delivery to site.",
]


@dataclass
class ParseResult:
    understood: bool
    ops: list[EditOperation] = field(default_factory=list)
    interpreted_as: str = ""
    message: str | None = None  # shown when the instruction cannot be carried out
    warnings: list[str] = field(default_factory=list)


def _strip(text: str) -> str:
    t = text.strip().strip("\"'“”‘’").strip()
    return re.sub(r"[.!]+$", "", t).strip()


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _unquote(text: str) -> str:
    return text.strip().strip("\"'“”‘’").strip()


PERIOD_FIELDS = [
    (re.compile(r"^delivery(\s+(period|time|terms?|schedule|date))?$", re.I), "delivery_terms"),
    (re.compile(r"^((quotation|quote|offer|bid)\s+)?validity(\s+period)?$", re.I), "validity_terms"),
    (re.compile(r"^warranty(\s+(period|terms?))?$", re.I), "warranty_terms"),
    (re.compile(r"^payment(\s+(terms?|conditions))?$", re.I), "payment_terms"),
]

SET_RE = re.compile(
    r"^(?:please\s+)?(?:change|set|update|make|modify|replace)\s+(?:the\s+)?(?P<target>[a-z][a-z .'/-]*?)\s+(?:to|as|with|=|:)\s+(?P<value>.+)$",
    re.I,
)
TITLE_MATCH_REF_RE = re.compile(
    r"^(?:please\s+)?(?:change|set|update|rename|make)\s+(?:the\s+)?(?:quotation\s+|document\s+|quote\s+)?title\s+"
    r"(?:to\s+)?(?:match|use|be|reflect|include)\s+(?:the\s+)?tender(?:'s)?\s+(?:reference|ref(?:erence)?|number|no)",
    re.I,
)
PAYMENT_REWRITE_RE = re.compile(
    r"^(?:please\s+)?(?:re-?write|rephrase|redo|draft|fill(?:\s+in)?|update|complete)\s+(?:the\s+)?payment\s+terms?"
    r"(?:\s+(?:using|from|with|based\s+on)\b.*)?$",
    re.I,
)
ADD_ITEM_RE = re.compile(
    r"^(?:please\s+)?add\s+(?:a\s+|an\s+|one\s+)?(?:new\s+)?(?:line\s+item|line|item|row)\s*(?:for|called|named|:|-)?\s*(?P<rest>.+)$",
    re.I,
)
ADD_NOTE_RE = re.compile(r"^(?:please\s+)?add\s+(?:a\s+)?note\s*[:\-]?\s*(?P<value>.+)$", re.I)
PRICE_RE = re.compile(
    r"^(?:please\s+)?(?:set|change|update|make|put|enter)\s+(?:the\s+)?(?:unit\s+)?(?:price|rate|cost)\s+(?:of|for)\s+"
    r"(?P<ref>.+?)\s+(?:to|as|at|=)\s+(?:rs\.?\s*|pkr\s*|usd\s*|\$\s*)?(?P<value>-?\d[\d,]*(?:\.\d+)?)\s*(?:each|per\s+\w+)?$",
    re.I,
)
QTY_RE = re.compile(
    r"^(?:please\s+)?(?:set|change|update|make)\s+(?:the\s+)?(?:quantity|qty)\s+(?:of|for)\s+(?P<ref>.+?)\s+(?:to|as|=)\s+"
    r"(?P<value>-?\d[\d,]*(?:\.\d+)?)(?:\s+\w+)?$",
    re.I,
)
REMOVE_RE = re.compile(
    r"^(?:please\s+)?(?:remove|delete|drop)\s+(?:the\s+)?(?:line\s+)?(?:item\s+)?(?P<ref>.+?)(?:\s+(?:line\s+)?item)?$",
    re.I,
)
CURRENCY_RE = re.compile(
    r"^(?:please\s+)?(?:set|change|use|switch)\s+(?:the\s+)?currency\s+(?:to\s+)?(?P<cur>.+)$", re.I
)
QUOTE_IN_RE = re.compile(r"^(?:please\s+)?(?:quote|price)\s+(?:everything\s+)?in\s+(?P<cur>.+)$", re.I)
TAX_SET_RE = re.compile(
    r"^(?:please\s+)?(?:set|apply|add|change|use)\s+(?:the\s+)?(?:a\s+)?(?P<label>(?:general\s+)?sales\s+tax|gst|vat|tax)(?:\s+rate)?\s*(?:to|of|at|=|as)?\s+(?P<rate>\d+(?:\.\d+)?)\s*(?:%|percent)",
    re.I,
)
TAX_REMOVE_RE = re.compile(
    r"^(?:please\s+)?(?:remove|disable|clear|turn\s+off)\s+(?:the\s+)?(?:sales\s+)?(?:tax|gst|vat)$", re.I
)
HIGHLIGHT_RE = re.compile(
    r"^(?:please\s+)?(?:highlight|show|mark|list|find)\s+(?:all\s+|me\s+)?(?:the\s+)?(?:missing|required|incomplete|empty|unfilled)"
    r"(?:\s+(?:information|info|fields?|values?|data|items?|details))?$",
    re.I,
)
ITEM_NUM_RE = re.compile(r"^(?:item|line|row|no\.?|number|#)?\s*#?\s*(?P<n>\d{1,3})$", re.I)


def resolve_item(q: Quotation, ref: str) -> tuple[str | None, str | None]:
    """Return (item_id, error message)."""
    ref_clean = _strip(ref)
    ref_clean = re.sub(r"^(the|a|an)\s+", "", ref_clean, flags=re.I)
    m = ITEM_NUM_RE.match(ref_clean)
    if m:
        n = int(m.group("n"))
        if 1 <= n <= len(q.line_items):
            return q.line_items[n - 1].id, None
        return None, f"There is no item {n}. The quotation has {len(q.line_items)} item(s)."
    wanted = tokens(ref_clean)
    if not wanted:
        return None, "Say which item you mean, for example “item 2” or its description."
    scored = []
    for it in q.line_items:
        have = tokens(it.description)
        common = wanted & have
        if common:
            scored.append((len(common) / len(wanted), len(common), it))
    if not scored:
        return None, f"No line item matches “{ref_clean}”."
    scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
    if len(scored) > 1 and scored[0][:2] == scored[1][:2]:
        names = ", ".join(f"item {s[2].item_no}" for s in scored[:3])
        return None, f"“{ref_clean}” matches more than one item ({names}). Use the item number."
    if scored[0][0] < 0.5:
        return None, f"No line item clearly matches “{ref_clean}”. Use the item number."
    return scored[0][2].id, None


def _period_value(current: str | None, new_value: str) -> str:
    """Replace only the duration inside the current text when possible: keeps the rest of the wording."""
    new_clean = _unquote(new_value)
    if current and _DURATION_RE.fullmatch(new_clean.strip()) and _DURATION_RE.search(current):
        m = _DURATION_RE.search(current)
        assert m is not None
        return current[: m.start()] + new_clean + current[m.end() :]
    return _cap(new_clean)


def _item_label(q: Quotation, item_id: str) -> str:
    for it in q.line_items:
        if it.id == item_id:
            return f"item {it.item_no} ({it.description or 'untitled'})"
    return "the item"


def parse_instruction(text: str, project: Project, q: Quotation, company: CompanyProfile) -> ParseResult:
    raw = (text or "").strip()
    if not raw:
        return ParseResult(False, message="Type an instruction first.")
    instr = _strip(raw)

    if HIGHLIGHT_RE.match(instr):
        return ParseResult(
            True, [HighlightMissingOp()], "Highlight every field that still needs a value (no data changes)."
        )

    if TITLE_MATCH_REF_RE.match(instr):
        ref = q.fields.get("tender_reference")
        if not ref or not ref.value:
            return ParseResult(True, message="The tender reference is missing, so the title cannot match it yet.")
        new_title = f"Quotation for Tender {ref.value}"
        return ParseResult(
            True,
            [SetFieldOp(field_key="quotation_title", value=new_title)],
            f"Set the quotation title to “{new_title}”.",
        )

    if PAYMENT_REWRITE_RE.match(instr) and not SET_RE.match(instr):
        if company.default_payment_terms:
            return ParseResult(
                True,
                [SetFieldOp(field_key="payment_terms", value=company.default_payment_terms)],
                "Replace the payment terms with your default payment terms from Settings → Company profile.",
            )
        tender = next(
            (f for f in (project.extraction.fields if project.extraction else []) if f.key == "payment_terms"), None
        )
        current = q.fields.get("payment_terms")
        if tender and tender.value and (not current or current.value != tender.value):
            where = tender.sources[0].label() if tender.sources else "the tender"
            return ParseResult(
                True,
                [SetFieldOp(field_key="payment_terms", value=tender.value)],
                f"Use the payment terms stated in the tender ({where}).",
            )
        return ParseResult(
            True,
            message=(
                "There is no supplied payment information to rewrite from. Add default payment terms in "
                "Settings → Company profile, or type the terms, e.g. “Set payment terms to 50% advance, 50% on delivery”. "
                "Free-text rewriting needs an AI provider (see Settings → AI processing)."
            ),
        )

    m = ADD_NOTE_RE.match(instr)
    if m:
        note = _cap(_unquote(m.group("value")))
        existing = q.fields.get("notes")
        value = f"{existing.value} {note}".strip() if existing and existing.value else note
        return ParseResult(True, [SetFieldOp(field_key="notes", value=value)], f"Add the note “{note}”.")

    m = ADD_ITEM_RE.match(instr)
    if m:
        return _parse_add_item(m.group("rest"))

    m = PRICE_RE.match(instr)
    if m:
        item_id, err = resolve_item(q, m.group("ref"))
        if err or item_id is None:
            return ParseResult(True, message=err)
        value = m.group("value").replace(",", "")
        return ParseResult(
            True,
            [SetItemOp(line_item_id=item_id, attribute="unit_price", value=value)],
            f"Set the unit price of {_item_label(q, item_id)} to {value}.",
        )

    m = QTY_RE.match(instr)
    if m:
        item_id, err = resolve_item(q, m.group("ref"))
        if err or item_id is None:
            return ParseResult(True, message=err)
        value = m.group("value").replace(",", "")
        return ParseResult(
            True,
            [SetItemOp(line_item_id=item_id, attribute="quantity", value=value)],
            f"Set the quantity of {_item_label(q, item_id)} to {value}.",
        )

    m = TAX_SET_RE.match(instr)
    if m:
        label = m.group("label").strip()
        label = label.upper() if label.lower() in ("gst", "vat") else _cap(label.lower())
        rate = m.group("rate")
        return ParseResult(True, [SetTaxOp(enabled=True, rate=rate, label=label)], f"Apply {label} at {rate}%.")
    if TAX_REMOVE_RE.match(instr):
        return ParseResult(True, [SetTaxOp(enabled=False)], "Remove tax from the quotation.")

    m = CURRENCY_RE.match(instr) or QUOTE_IN_RE.match(instr)
    if m:
        code = detect_currency(m.group("cur"))
        if code is None:
            return ParseResult(True, message="Unknown currency. Use a code such as PKR, USD or EUR.")
        return ParseResult(True, [SetCurrencyOp(currency=code)], f"Set the currency to {code}.")

    m = REMOVE_RE.match(instr)
    if m and not re.search(r"\b(tax|gst|vat)\b", m.group("ref"), re.I):
        item_id, err = resolve_item(q, m.group("ref"))
        if err or item_id is None:
            return ParseResult(True, message=err)
        return ParseResult(True, [RemoveItemOp(line_item_id=item_id)], f"Remove {_item_label(q, item_id)}.")

    m = SET_RE.match(instr)
    if m:
        target = m.group("target").strip()
        value = m.group("value")
        for rx, key in PERIOD_FIELDS:
            if rx.match(target):
                current = q.fields.get(key)
                new_value = _period_value(current.value if current else None, value)
                return ParseResult(
                    True,
                    [SetFieldOp(field_key=key, value=new_value)],
                    f"Set the {QUOTATION_FIELDS[key].label.lower()} to “{new_value}”.",
                )
        if re.match(r"^(quotation\s+|document\s+)?title$", target, re.I):
            new_title = _cap(_unquote(value))
            return ParseResult(
                True,
                [SetFieldOp(field_key="quotation_title", value=new_title)],
                f"Set the quotation title to “{new_title}”.",
            )
        if re.match(r"^(buyer|customer|client)(\s+name)?$", target, re.I):
            v = _unquote(value)
            return ParseResult(True, [SetFieldOp(field_key="buyer_name", value=v)], f"Set the buyer to “{v}”.")
        if re.match(r"^notes?$", target, re.I):
            v = _cap(_unquote(value))
            return ParseResult(True, [SetFieldOp(field_key="notes", value=v)], f"Set the notes to “{v}”.")
        field_key = match_field_label(target)
        if field_key and field_key not in DERIVED_FIELDS and not QUOTATION_FIELDS[field_key].never_fill:
            v = _unquote(value)
            return ParseResult(
                True,
                [SetFieldOp(field_key=field_key, value=v)],
                f"Set {QUOTATION_FIELDS[field_key].label.lower()} to “{v}”.",
            )
        if field_key in DERIVED_FIELDS:
            return ParseResult(
                True,
                message=f"{QUOTATION_FIELDS[field_key].label} is calculated automatically and cannot be set directly.",
            )

    return ParseResult(False, message="That instruction is not one TenderFlow understands in local mode.")


_PRICE_TAIL = re.compile(
    r"\s*,?\s+(?:at|@|for|priced\s+at|costing)\s+(?:rs\.?\s*|pkr\s*|usd\s*|\$\s*)?(?P<price>\d[\d,]*(?:\.\d+)?)\s*(?:each|per\s+\w+|/\s*\w+)?\s*$",
    re.I,
)
_QTY_TAIL = re.compile(
    r"\s*(?:,|\bwith\b|\bx\b|\bqty\b|\bquantity\b)\s*(?:qty|quantity)?\s*(?P<qty>\d+(?:\.\d+)?)\s*(?P<unit>[a-z]{1,12})?\s*$",
    re.I,
)


def _parse_add_item(rest: str) -> ParseResult:
    text = _strip(rest)
    price = qty = unit = None
    pm = _PRICE_TAIL.search(text)
    if pm:
        price = pm.group("price").replace(",", "")
        text = text[: pm.start()].strip()
    qm = _QTY_TAIL.search(text)
    if qm:
        qty = qm.group("qty")
        unit = qm.group("unit")
        text = text[: qm.start()].strip()
    text = re.sub(r"^(the|a|an)\s+", "", text, flags=re.I).strip(" ,;:-")
    if not text:
        return ParseResult(
            True, message="Say what the new line item is, e.g. “Add a line item for installation service”."
        )
    description = _cap(text)
    parts = [f"Add a line item “{description}”"]
    if qty:
        parts.append(f"quantity {qty}{' ' + unit if unit else ''}")
    if price:
        parts.append(f"unit price {price}")
    warnings = []
    if not qty or not price:
        missing = [w for w, v in (("quantity", qty), ("unit price", price)) if not v]
        warnings.append(
            f"The {' and '.join(missing)} {'is' if len(missing) == 1 else 'are'} not given and will stay missing until you enter {'it' if len(missing) == 1 else 'them'}."
        )
    return ParseResult(
        True,
        [AddItemOp(description=description, quantity=qty, unit=unit, unit_price=price)],
        ", ".join(parts) + ".",
        warnings=warnings,
    )


__all__ = ["SUPPORTED_EXAMPLES", "ParseResult", "parse_decimal", "parse_instruction", "resolve_item"]
