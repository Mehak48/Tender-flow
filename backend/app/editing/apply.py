"""Apply structured edit operations to a quotation and describe the resulting changes.

Manual edits from the editor and natural-language proposals use the same operations, so there is one
validated code path for every change. Totals are always recalculated by ``quotation.recalculate``.
"""

from __future__ import annotations

import re
from decimal import Decimal

from ..errors import AppError
from ..extraction.normalize import SUPPORTED_CURRENCIES, detect_currency, parse_decimal
from ..fields import COMMITMENT_FIELDS, QUOTATION_FIELDS
from ..models import (
    AddItemOp,
    ConfirmFieldsOp,
    ConfirmPricesOp,
    EditOperation,
    FieldChange,
    HighlightMissingOp,
    Origin,
    Project,
    QField,
    Quotation,
    QuotationLineItem,
    RemoveItemOp,
    SetCurrencyOp,
    SetFieldOp,
    SetItemOp,
    SetTaxOp,
)
from ..quotation import format_money, format_quantity, recalculate, update_validity_date
from ..storage import new_id

DERIVED_FIELDS = {"subtotal", "tax_label", "tax_rate", "tax_amount", "total", "currency"}
MAX_TEXT = 2000
MATERIAL_ATTRS = {"quantity", "unit_price", "amount_override"}


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    v = re.sub(r"[ \t]+", " ", str(value)).strip()
    if len(v) > MAX_TEXT:
        raise AppError("value_too_long", f"Values are limited to {MAX_TEXT} characters.")
    return v or None


def _decimal(value: str | None, what: str, *, allow_negative: bool = False) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    d = parse_decimal(value)
    if d is None:
        raise AppError("invalid_number", f"{what} must be a number.")
    if d.is_nan() or d.is_infinite() or abs(d) > Decimal("1e15"):
        raise AppError("invalid_number", f"{what} is out of range.")
    if d < 0 and not allow_negative:
        # Negative values are kept so validation can flag them; they are never silently changed.
        return d
    return d


def find_item(q: Quotation, item_id: str) -> QuotationLineItem:
    for it in q.line_items:
        if it.id == item_id:
            return it
    raise AppError("not_found", "That line item no longer exists.", 404)


def apply_operations(project: Project, q: Quotation, ops: list[EditOperation], origin: Origin) -> None:
    for op in ops:
        if isinstance(op, SetFieldOp):
            key = op.field_key
            if key not in QUOTATION_FIELDS:
                raise AppError("invalid_edit", f"Unknown field “{key}”.")
            if QUOTATION_FIELDS[key].never_fill:
                raise AppError("invalid_edit", "Signatures are never filled by TenderFlow.")
            if key in DERIVED_FIELDS:
                raise AppError("invalid_edit", f"{QUOTATION_FIELDS[key].label} is calculated automatically.")
            value = _clean(op.value)
            q.fields[key] = QField(
                key=key,
                label=QUOTATION_FIELDS[key].label,
                value=value,
                origin=origin if value else "missing",
                confirmed=bool(value),
                note="Suggested by the external AI provider and applied by you."
                if origin == "ai_suggestion" and value
                else None,
            )
            if key == "validity_terms":
                update_validity_date(q, project)
        elif isinstance(op, SetItemOp):
            item = find_item(q, op.line_item_id)
            attr = op.attribute
            if attr in ("quantity", "unit_price", "amount_override"):
                setattr(item, attr, _decimal(op.value, attr.replace("_", " ").capitalize()))
                if attr == "unit_price":
                    item.price_confirmed = True
                    item.price_note = "Entered by you." if origin == "user" else "Set by an instruction you applied."
                    item.origins["unit_price"] = origin if item.unit_price is not None else "missing"
                elif attr == "quantity":
                    item.origins["quantity"] = origin if item.quantity is not None else "missing"
            else:
                value = _clean(op.value)
                setattr(item, attr, value)
                item.origins[attr] = origin if value else "missing"
        elif isinstance(op, AddItemOp):
            description = _clean(op.description)
            if not description:
                raise AppError("invalid_edit", "A new line item needs a description.")
            item = QuotationLineItem(
                id=new_id("itm"),
                item_no="",
                description=description,
                specification=_clean(op.specification),
                quantity=_decimal(op.quantity, "Quantity"),
                unit=_clean(op.unit),
                unit_price=_decimal(op.unit_price, "Unit price"),
                reviewed=True,
            )
            for attr in ("description", "specification", "quantity", "unit", "unit_price"):
                item.origins[attr] = origin if getattr(item, attr) is not None else "missing"
            if item.unit_price is not None:
                item.price_note = "Entered by you." if origin == "user" else "From your instruction."
            q.line_items.append(item)
        elif isinstance(op, RemoveItemOp):
            item = find_item(q, op.line_item_id)
            q.line_items.remove(item)
        elif isinstance(op, SetCurrencyOp):
            code = (op.currency or "").strip().upper()
            if code not in SUPPORTED_CURRENCIES:
                detected = detect_currency(op.currency or "")
                if detected is None:
                    raise AppError("invalid_currency", "Unknown currency. Use a code such as PKR, USD or EUR.")
                code = detected
            q.currency = code
            q.currency_origin = origin
        elif isinstance(op, SetTaxOp):
            if op.enabled:
                rate = _decimal(op.rate, "Tax rate") if op.rate is not None else None
                if rate is not None and not (Decimal("0") <= rate <= Decimal("100")):
                    raise AppError("invalid_number", "Tax rate must be between 0 and 100 percent.")
                q.tax.enabled = True
                q.tax.rate = rate
                q.tax.label = _clean(op.label) or q.tax.label or "Tax"
            else:
                q.tax.enabled = False
                q.tax.rate = None
            q.tax_origin = origin
        elif isinstance(op, ConfirmFieldsOp):
            for key in op.field_keys:
                qf = q.fields.get(key)
                if qf is not None and qf.value:
                    qf.confirmed = True
                    if qf.note and "Confirm" in qf.note:
                        qf.note = "Confirmed by you."
        elif isinstance(op, ConfirmPricesOp):
            for item_id in op.line_item_ids:
                it = find_item(q, item_id)
                it.price_confirmed = True
        elif isinstance(op, HighlightMissingOp):
            pass  # presentation only
        else:  # pragma: no cover - the discriminated union makes this unreachable
            raise AppError("invalid_edit", "Unsupported edit operation.")
    recalculate(q)


# --- describing changes -------------------------------------------------------


def _item_attrs(it: QuotationLineItem) -> dict[str, str | None]:
    return {
        "Description": it.description,
        "Specification": it.specification,
        "Quantity": format_quantity(it.quantity),
        "Unit": it.unit,
        "Unit price": format_money(it.unit_price),
        "Amount": format_money(it.amount),
    }


def diff_quotations(before: Quotation, after: Quotation) -> list[FieldChange]:
    changes: list[FieldChange] = []
    skip = {"subtotal", "tax_amount", "total", "tax_label", "tax_rate", "currency"}
    for key, fdef in QUOTATION_FIELDS.items():
        if key in skip:
            continue
        a = before.fields.get(key)
        b = after.fields.get(key)
        av, bv = (a.value if a else None), (b.value if b else None)
        if av != bv:
            changes.append(FieldChange(target=fdef.label, before=av, after=bv))
    before_items = {it.id: it for it in before.line_items}
    after_items = {it.id: it for it in after.line_items}
    for it in after.line_items:
        old = before_items.get(it.id)
        if old is None:
            changes.append(
                FieldChange(
                    target=f"Item {it.item_no} (new)",
                    before=None,
                    after=" · ".join(
                        v
                        for v in (it.description, format_quantity(it.quantity), it.unit, format_money(it.unit_price))
                        if v
                    ),
                )
            )
            continue
        old_attrs, new_attrs = _item_attrs(old), _item_attrs(it)
        for label, new_value in new_attrs.items():
            if old_attrs[label] != new_value:
                changes.append(
                    FieldChange(target=f"Item {it.item_no} · {label}", before=old_attrs[label], after=new_value)
                )
    for it in before.line_items:
        if it.id not in after_items:
            changes.append(FieldChange(target=f"Item {it.item_no} (removed)", before=it.description, after=None))
    if before.currency != after.currency:
        changes.append(FieldChange(target="Currency", before=before.currency, after=after.currency))
    tb = f"{before.tax.label or 'Tax'} {format_quantity(before.tax.rate)}%" if before.tax.enabled else "Not applied"
    ta = f"{after.tax.label or 'Tax'} {format_quantity(after.tax.rate)}%" if after.tax.enabled else "Not applied"
    if tb != ta:
        changes.append(FieldChange(target="Tax", before=tb, after=ta))
    for label, attr in (("Subtotal", "subtotal"), ("Tax amount", "tax_amount"), ("Total", "total")):
        bv_m, av_m = format_money(getattr(before, attr)), format_money(getattr(after, attr))
        if bv_m != av_m:
            changes.append(FieldChange(target=label, before=bv_m or "Pending", after=av_m or "Pending"))
    return changes


def material_reasons(ops: list[EditOperation], changes: list[FieldChange]) -> list[str]:
    reasons: list[str] = []
    for op in ops:
        if isinstance(op, SetItemOp) and op.attribute in MATERIAL_ATTRS:
            reasons.append("changes a price, quantity or amount")
        elif isinstance(op, AddItemOp | RemoveItemOp):
            reasons.append("adds or removes a line item")
        elif isinstance(op, SetCurrencyOp):
            reasons.append("changes the currency")
        elif isinstance(op, SetTaxOp):
            reasons.append("changes tax")
        elif isinstance(op, SetFieldOp) and op.field_key in COMMITMENT_FIELDS:
            reasons.append("changes a commercial commitment")
    if any(c.target == "Total" for c in changes):
        reasons.append("changes the quotation total")
    seen: list[str] = []
    for r in reasons:
        if r not in seen:
            seen.append(r)
    return seen
