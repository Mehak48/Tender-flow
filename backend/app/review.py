"""Extraction review (pipeline stage 4): the user confirms, edits or chooses extracted values.

Confirmed and unconfirmed values stay distinct (status), and every change is the user's explicit action.
"""

from __future__ import annotations

from typing import Literal

from .errors import AppError
from .extraction.normalize import parse_quantity
from .extraction.rules import SPEC_BY_KEY
from .models import ExtractedLineItem, Extraction, FieldStatus, Model, utcnow
from .storage import new_id

MAX_VALUE = 1000


class FieldUpdate(Model):
    key: str
    action: Literal["confirm", "edit", "choose", "unconfirm", "clear"]
    value: str | None = None
    candidate_index: int | None = None


class LineItemUpdate(Model):
    id: str | None = None
    action: Literal["confirm", "edit", "delete", "add", "unconfirm"]
    item_no: str | None = None
    description: str | None = None
    specification: str | None = None
    quantity: str | None = None
    unit: str | None = None


class RequirementUpdate(Model):
    id: str
    acknowledged: bool


class ExtractionUpdate(Model):
    fields: list[FieldUpdate] = []
    line_items: list[LineItemUpdate] = []
    requirements: list[RequirementUpdate] = []
    mark_reviewed: bool | None = None


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    v = " ".join(str(value).split())
    if len(v) > MAX_VALUE:
        raise AppError("value_too_long", f"Values are limited to {MAX_VALUE} characters.")
    return v or None


def _normalize(key: str, value: str | None) -> str | None:
    spec = SPEC_BY_KEY.get(key)
    if spec is None or spec.normalizer is None or not value:
        return None
    return spec.normalizer(value)


def apply_review(ext: Extraction, update: ExtractionUpdate) -> None:
    by_key = {f.key: f for f in ext.fields}
    for fu in update.fields:
        f = by_key.get(fu.key)
        if f is None:
            raise AppError("not_found", f"Unknown extracted field “{fu.key}”.", 404)
        if fu.action == "confirm":
            if f.status == FieldStatus.conflict:
                raise AppError("conflict_unresolved", f"Choose one of the values for “{f.label}” first.")
            if not f.value:
                raise AppError("nothing_to_confirm", f"“{f.label}” has no value to confirm. Enter one instead.")
            f.status = FieldStatus.confirmed
        elif fu.action == "edit":
            value = _clean(fu.value)
            f.value = value
            f.normalized = _normalize(f.key, value)
            f.status = FieldStatus.edited if value else FieldStatus.missing
            f.note = "Entered by you." if value else None
            if value:
                f.candidates = []
        elif fu.action == "choose":
            if fu.candidate_index is None or not (0 <= fu.candidate_index < len(f.candidates)):
                raise AppError("invalid_candidate", "Choose one of the listed values.")
            cand = f.candidates[fu.candidate_index]
            f.value = cand.value
            f.normalized = _normalize(f.key, cand.value)
            f.sources = [cand.source]
            f.status = FieldStatus.confirmed
            f.note = f"Chosen by you from {len(f.candidates)} conflicting values ({cand.source.label()})."
        elif fu.action == "unconfirm":
            if f.status in (FieldStatus.confirmed, FieldStatus.edited):
                f.status = FieldStatus.extracted if f.value else FieldStatus.missing
        elif fu.action == "clear":
            f.value = None
            f.normalized = None
            f.status = FieldStatus.missing

    items = {it.id: it for it in ext.line_items}
    for lu in update.line_items:
        if lu.action == "add":
            qty, qty_unit = parse_quantity(lu.quantity or "")
            ext.line_items.append(
                ExtractedLineItem(
                    id=new_id("itm"),
                    item_no=_clean(lu.item_no),
                    description=_clean(lu.description),
                    specification=_clean(lu.specification),
                    quantity=qty,
                    quantity_text=_clean(lu.quantity),
                    unit=_clean(lu.unit) or qty_unit,
                    status=FieldStatus.edited,
                    notes=["Added by you."],
                )
            )
            continue
        if lu.id is None or lu.id not in items:
            raise AppError("not_found", "That line item no longer exists.", 404)
        it = items[lu.id]
        if lu.action == "delete":
            ext.line_items = [x for x in ext.line_items if x.id != lu.id]
        elif lu.action == "confirm":
            it.status = FieldStatus.confirmed
        elif lu.action == "unconfirm":
            it.status = FieldStatus.extracted
        elif lu.action == "edit":
            if lu.description is not None:
                it.description = _clean(lu.description)
            if lu.specification is not None:
                it.specification = _clean(lu.specification)
            if lu.unit is not None:
                it.unit = _clean(lu.unit)
            if lu.item_no is not None:
                it.item_no = _clean(lu.item_no)
            if lu.quantity is not None:
                qty, qty_unit = parse_quantity(lu.quantity)
                if lu.quantity.strip() and qty is None:
                    raise AppError("invalid_number", "Quantity must be a number, optionally followed by a unit.")
                it.quantity = qty
                it.quantity_text = _clean(lu.quantity)
                if qty_unit and not it.unit:
                    it.unit = qty_unit
            it.status = FieldStatus.edited
            it.notes = [n for n in it.notes if "not a plain number" not in n and "No quantity" not in n]

    reqs = {r.id: r for r in ext.requirements}
    for ru in update.requirements:
        if ru.id in reqs:
            reqs[ru.id].acknowledged = ru.acknowledged

    if update.mark_reviewed is not None:
        ext.reviewed = update.mark_reviewed
        ext.reviewed_at = utcnow() if update.mark_reviewed else None
    ext.updated_at = utcnow()
