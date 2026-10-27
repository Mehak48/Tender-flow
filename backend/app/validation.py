"""Deterministic validation rules (pipeline stage 8).

Each rule is plain code. A rule "passes" when it produces no error or warning (informational notes do
not fail a rule). Acknowledging a warning records the user's decision but the warning stays listed —
TenderFlow never pretends the underlying issue disappeared. ``ready`` requires zero errors and every
warning acknowledged.

These are basic checks. They do not verify legal, procurement or eligibility compliance.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal

from .extraction.normalize import detect_currency, duration_days
from .fields import COMMITMENT_FIELDS, QUOTATION_FIELDS
from .models import (
    FieldStatus,
    Project,
    Quotation,
    QuotationSection,
    Severity,
    ValidationIssue,
    ValidationReport,
    utcnow,
)
from .quotation import format_money, format_quantity, money

GROUP_TO_SECTION: dict[str, QuotationSection] = {
    "company": "company",
    "details": "details",
    "buyer": "buyer",
    "terms": "terms",
    "totals": "totals",
    "authorization": "authorization",
}

COVERED_BY_OTHER_RULES = {"currency", "subtotal", "tax_label", "tax_rate", "tax_amount", "total"}

CLAIM_RE = re.compile(
    r"\b(iso\s*\d{3,5}|certified|certification|guaranteed?|authori[sz]ed\s+(dealer|distributor|partner|reseller)|"
    r"genuine|brand[- ]new|original\s+equipment|oem|registered\s+with|compliant\s+with|approved\s+by)\b",
    re.I,
)


def section_for_field(key: str) -> QuotationSection:
    fdef = QUOTATION_FIELDS.get(key)
    return GROUP_TO_SECTION.get(fdef.group, "details") if fdef else "details"


class _Ctx:
    def __init__(self, project: Project, q: Quotation) -> None:
        self.project = project
        self.q = q
        self.issues: list[ValidationIssue] = []
        self.ext = {f.key: f for f in (project.extraction.fields if project.extraction else [])}

    def add(
        self,
        rule: str,
        target: str,
        severity: Severity,
        title: str,
        message: str,
        section: QuotationSection,
        *,
        field_key: str | None = None,
        line_item_id: str | None = None,
        suggestion: str | None = None,
        fix: str | None = None,
    ) -> None:
        issue_id = f"{rule}:{target}"
        acknowledgeable = severity == "warning"
        self.issues.append(
            ValidationIssue(
                id=issue_id,
                rule=rule,
                severity=severity,
                title=title,
                message=message,
                section=section,
                field_key=field_key,
                line_item_id=line_item_id,
                suggestion=suggestion,
                acknowledgeable=acknowledgeable,
                acknowledged=acknowledgeable and issue_id in self.q.acknowledged_issue_ids,
                fix=fix,
            )
        )


def _item_label(q: Quotation, item_id: str) -> str:
    for it in q.line_items:
        if it.id == item_id:
            desc = (it.description or "Untitled item")[:48]
            return f"Item {it.item_no} ({desc})"
    return "Item"


# --- rules -------------------------------------------------------------------


def rule_mapping_confirmed(c: _Ctx) -> None:
    m = c.project.mapping
    if c.project.template is None or m is None:
        c.add(
            "mapping_confirmed",
            "template",
            "error",
            "No quotation template",
            "Upload a quotation template so the quotation can be written into your format.",
            "mapping",
            suggestion="Go back to step 1 and upload a .docx or .xlsx template.",
        )
        return
    if not m.confirmed:
        c.add(
            "mapping_confirmed",
            "mapping",
            "error",
            "Field mapping not confirmed",
            "Review how quotation data is placed into your template and confirm the mapping.",
            "mapping",
            suggestion="Open the mapping step and confirm.",
            fix="confirm_mapping",
        )


def rule_required_template_fields(c: _Ctx) -> None:
    t, m = c.project.template, c.project.mapping
    if t is None or m is None:
        return
    tf_by_id = {tf.id: tf for tf in t.fields}
    for row in m.fields:
        tf = tf_by_id.get(row.target_field_id)
        if tf is None or not tf.required:
            continue
        if row.source_key is None:
            c.add(
                "required_template_fields",
                tf.id,
                "error",
                f"“{tf.label}” has nothing mapped to it",
                f"Your template expects “{tf.label}” ({', '.join(tf.locations[:2])}), but no data is mapped to it.",
                "mapping",
                suggestion="Choose a source in the mapping step, or make the placeholder optional with {{name?}}.",
            )
            continue
        if row.source_key in COVERED_BY_OTHER_RULES:
            continue  # currency and totals have their own, more specific checks
        qf = c.q.fields.get(row.source_key)
        if qf is None or not qf.value:
            c.add(
                "required_template_fields",
                tf.id,
                "error",
                f"{QUOTATION_FIELDS[row.source_key].label} is empty",
                f"The template needs “{tf.label}”, but there is no value for it. TenderFlow does not invent values.",
                section_for_field(row.source_key),
                field_key=row.source_key,
                suggestion="Enter the value in the editor or in Settings → Company profile.",
            )
    if t.items_table is not None and not any(col.attribute == "description" for col in m.columns):
        c.add(
            "required_template_fields",
            "items-description",
            "warning",
            "No column receives item descriptions",
            "None of the template's item columns is mapped to the item description.",
            "mapping",
            suggestion="Map a column to “Description” in the mapping step.",
        )


def rule_extraction_reviewed(c: _Ctx) -> None:
    ext = c.project.extraction
    if ext is None:
        c.add(
            "extraction_reviewed",
            "missing",
            "error",
            "No tender extraction",
            "Upload a tender document first.",
            "extraction",
        )
        return
    used_keys = {"issuer_name", "issuer_address", "tender_reference", "tender_title", "submission_deadline"}
    pending = [
        f.label
        for f in ext.fields
        if f.key in used_keys and f.value and f.status in (FieldStatus.extracted, FieldStatus.needs_review)
    ]
    pending_items = [it for it in ext.line_items if it.status in (FieldStatus.extracted, FieldStatus.needs_review)]
    if pending or pending_items:
        parts = []
        if pending:
            parts.append(", ".join(pending))
        if pending_items:
            parts.append(f"{len(pending_items)} line item(s)")
        c.add(
            "extraction_reviewed",
            "unconfirmed",
            "warning",
            "Some extracted values are not confirmed",
            f"These values come from the tender but were not confirmed in the review step: {'; '.join(parts)}.",
            "extraction",
            suggestion="Confirm them in the extraction review, or acknowledge this warning.",
        )


def rule_extraction_conflicts(c: _Ctx) -> None:
    ext = c.project.extraction
    if ext is None:
        return
    for f in ext.fields:
        if f.status == FieldStatus.conflict:
            values = " / ".join(f"“{cand.value}” ({cand.source.label()})" for cand in f.candidates[:3])
            c.add(
                "extraction_conflicts",
                f.key,
                "error" if f.required else "warning",
                f"Conflicting values: {f.label}",
                f"The tender states different values: {values}.",
                "extraction",
                suggestion="Choose the correct value in the extraction review.",
            )
    for it in ext.line_items:
        if it.status == FieldStatus.conflict:
            c.add(
                "extraction_conflicts",
                it.id,
                "warning",
                f"Conflicting quantities: {it.description or 'item'}",
                " ".join(it.notes) or "This item appears more than once with different quantities.",
                "extraction",
                suggestion="Check the tender and correct the quantity.",
            )


def rule_line_items(c: _Ctx) -> None:
    if not c.q.line_items:
        c.add(
            "line_items",
            "none",
            "error",
            "No line items",
            "The quotation has no line items. Add them in the editor or in the extraction review.",
            "items",
        )


def rule_item_values(c: _Ctx) -> None:
    for it in c.q.line_items:
        label = _item_label(c.q, it.id)
        if not it.description:
            c.add(
                "item_values",
                f"{it.id}:description",
                "error",
                f"{label}: description missing",
                "Every line item needs a description.",
                "items",
                line_item_id=it.id,
            )
        if it.quantity is None:
            c.add(
                "item_values",
                f"{it.id}:quantity",
                "error",
                f"{label}: quantity missing",
                "Enter the quantity. TenderFlow does not invent quantities.",
                "items",
                line_item_id=it.id,
            )
        elif it.quantity < 0:
            c.add(
                "item_values",
                f"{it.id}:quantity",
                "error",
                f"{label}: negative quantity",
                "Quantities cannot be negative.",
                "items",
                line_item_id=it.id,
            )
        elif it.quantity == 0:
            c.add(
                "item_values",
                f"{it.id}:quantity",
                "warning",
                f"{label}: quantity is zero",
                "A zero quantity is unusual. Check whether the item should be removed.",
                "items",
                line_item_id=it.id,
            )
        if it.unit_price is None:
            c.add(
                "item_values",
                f"{it.id}:unit_price",
                "error",
                f"{label}: unit price missing",
                "This price is not in the tender or your price list, and TenderFlow does not estimate prices.",
                "items",
                line_item_id=it.id,
                suggestion="Enter the unit price in the editor.",
            )
        elif it.unit_price < 0:
            c.add(
                "item_values",
                f"{it.id}:unit_price",
                "error",
                f"{label}: negative unit price",
                "Unit prices cannot be negative.",
                "items",
                line_item_id=it.id,
            )
        elif it.unit_price == 0:
            c.add(
                "item_values",
                f"{it.id}:unit_price",
                "warning",
                f"{label}: unit price is zero",
                "A zero price means the item is offered free of charge. Confirm this is intended.",
                "items",
                line_item_id=it.id,
            )


def rule_item_arithmetic(c: _Ctx) -> None:
    for it in c.q.line_items:
        if it.amount_override is None or it.quantity is None or it.unit_price is None:
            continue
        expected = money(it.quantity * it.unit_price)
        if money(it.amount_override) != expected:
            c.add(
                "item_arithmetic",
                it.id,
                "error",
                f"{_item_label(c.q, it.id)}: amount does not match",
                f"{format_quantity(it.quantity)} × {format_money(it.unit_price)} = {format_money(expected)}, "
                f"but the amount entered is {format_money(it.amount_override)}.",
                "items",
                line_item_id=it.id,
                suggestion="Use the calculated amount, or correct the price or quantity.",
                fix=f"use_calculated_amount:{it.id}",
            )


def rule_totals(c: _Ctx) -> None:
    q = c.q
    if not q.line_items:
        return
    amounts = [it.amount for it in q.line_items]
    if any(a is None for a in amounts):
        missing = sum(1 for a in amounts if a is None)
        c.add(
            "totals",
            "pending",
            "error",
            "Totals cannot be calculated yet",
            f"{missing} line item(s) have no amount, so the subtotal and total are pending.",
            "totals",
            suggestion="Complete the missing quantities and prices.",
        )
        return
    expected_sub = money(sum((a for a in amounts if a is not None), Decimal("0")))
    if q.subtotal is None or money(q.subtotal) != expected_sub:
        c.add(
            "totals",
            "subtotal",
            "error",
            "Subtotal does not match the line amounts",
            f"The line amounts add up to {format_money(expected_sub)}, but the subtotal is {format_money(q.subtotal)}.",
            "totals",
        )
    if q.tax.enabled:
        if q.tax.rate is None:
            c.add(
                "totals",
                "tax-rate",
                "error",
                "Tax is enabled but has no rate",
                "Enter the tax rate in Settings or with an instruction such as “Set tax to 18%”.",
                "totals",
            )
            return
        expected_tax = money(expected_sub * q.tax.rate / Decimal("100"))
        if q.tax_amount is None or money(q.tax_amount) != expected_tax:
            c.add(
                "totals",
                "tax",
                "error",
                "Tax amount does not match the rate",
                f"{format_quantity(q.tax.rate)}% of {format_money(expected_sub)} is {format_money(expected_tax)}, "
                f"but the tax amount is {format_money(q.tax_amount)}.",
                "totals",
            )
        expected_total = money(expected_sub + expected_tax)
    else:
        expected_total = expected_sub
    if q.total is None or money(q.total) != expected_total:
        c.add(
            "totals",
            "total",
            "error",
            "Total does not match subtotal and tax",
            f"Expected {format_money(expected_total)}, but the total is {format_money(q.total)}.",
            "totals",
        )


def rule_currency(c: _Ctx) -> None:
    tender_cur = c.ext.get("currency")
    tender_code = tender_cur.normalized if tender_cur and tender_cur.normalized else None
    if not c.q.currency:
        hint = (
            f" The tender asks for prices in {tender_cur.value} ({tender_cur.sources[0].label() if tender_cur and tender_cur.sources else 'source unknown'})."
            if tender_code and tender_cur
            else ""
        )
        c.add(
            "currency",
            "missing",
            "error",
            "Currency not selected",
            "Choose the quotation currency explicitly." + hint,
            "details",
            field_key="currency",
            suggestion=f"Use {tender_code}" if tender_code else "Select a currency in Settings or the editor.",
            fix=f"set_currency:{tender_code}" if tender_code else None,
        )
    elif tender_code and detect_currency(c.q.currency) != tender_code and c.q.currency != tender_code:
        c.add(
            "currency",
            "mismatch",
            "warning",
            "Currency differs from the tender",
            f"The quotation is in {c.q.currency}, but the tender asks for {tender_code}.",
            "details",
            field_key="currency",
            fix=f"set_currency:{tender_code}",
            suggestion=f"Use {tender_code}",
        )


def rule_tax(c: _Ctx) -> None:
    if c.q.tax.enabled:
        return
    tax_note = c.ext.get("tax_instructions")
    extra = f" The tender says: “{tax_note.value}”." if tax_note and tax_note.value else ""
    c.add(
        "tax",
        "not-applied",
        "warning",
        "No tax applied",
        "TenderFlow never assumes a tax rate, so none was added."
        + extra
        + " Confirm your prices already include or exclude tax as required, or configure tax.",
        "totals",
        suggestion="Acknowledge if this is correct, or set a tax rate.",
    )


def rule_price_confirmation(c: _Ctx) -> None:
    pending = [
        it
        for it in c.q.line_items
        if it.unit_price is not None and it.origins.get("unit_price") == "price_list" and not it.price_confirmed
    ]
    if pending:
        nums = ", ".join(it.item_no for it in pending)
        c.add(
            "price_confirmation",
            "price-list",
            "warning",
            "Check prices matched from your price list",
            f"Item(s) {nums} were priced by matching names in your price list. Make sure each match is the right product.",
            "items",
            suggestion="Confirm the matched prices.",
            fix="confirm_prices",
        )


def rule_commitments(c: _Ctx) -> None:
    pending = [
        c.q.fields[k]
        for k in sorted(COMMITMENT_FIELDS)
        if k in c.q.fields and c.q.fields[k].value and not c.q.fields[k].confirmed
    ]
    if pending:
        names = ", ".join(f.label.lower() for f in pending)
        c.add(
            "commitments",
            "terms",
            "warning",
            "Confirm the commercial terms you are committing to",
            f"The {names} were copied from the tender's requirements. A quotation is your commitment — "
            "confirm each term or change it.",
            "terms",
            suggestion="Confirm the terms.",
            fix="confirm_terms",
        )


def rule_quantity_vs_tender(c: _Ctx) -> None:
    for it in c.q.line_items:
        if it.tender_quantity is not None and it.quantity is not None and it.quantity != it.tender_quantity:
            c.add(
                "quantity_vs_tender",
                it.id,
                "warning",
                f"{_item_label(c.q, it.id)}: quantity differs from the tender",
                f"The tender asks for {format_quantity(it.tender_quantity)}, the quotation offers {format_quantity(it.quantity)}.",
                "items",
                line_item_id=it.id,
            )


def rule_tender_items_quoted(c: _Ctx) -> None:
    ext = c.project.extraction
    if ext is None:
        return
    quoted = {it.tender_line_id for it in c.q.line_items if it.tender_line_id}
    for t_item in ext.line_items:
        if (t_item.description or t_item.quantity is not None) and t_item.id not in quoted:
            c.add(
                "tender_items_quoted",
                t_item.id,
                "warning",
                f"Tender item not quoted: {t_item.description or 'item'}",
                "This item is in the tender's schedule but not in the quotation.",
                "items",
                suggestion="Add it back, or acknowledge if you are intentionally not quoting it.",
            )
    added = [it for it in c.q.line_items if not it.tender_line_id]
    if added:
        c.add(
            "tender_items_quoted",
            "added",
            "info",
            "Items added by you",
            f"{len(added)} item(s) are not in the tender's schedule: "
            + ", ".join((it.description or "untitled")[:30] for it in added)
            + ".",
            "items",
        )


def rule_terms_vs_tender(c: _Ctx) -> None:
    delivery = c.q.fields.get("delivery_terms")
    req = c.ext.get("delivery_period")
    if delivery and delivery.value and req and req.normalized:
        offered = duration_days(delivery.value)
        if offered is not None and offered > int(req.normalized):
            c.add(
                "terms_vs_tender",
                "delivery",
                "warning",
                "Delivery period is longer than the tender allows",
                f"You offer {offered} days; the tender requires {req.value}.",
                "terms",
                field_key="delivery_terms",
            )
    validity = c.q.fields.get("validity_terms")
    vreq = c.ext.get("bid_validity")
    if validity and validity.value and vreq and vreq.normalized:
        offered_v = duration_days(validity.value)
        if offered_v is not None and offered_v < int(vreq.normalized):
            c.add(
                "terms_vs_tender",
                "validity",
                "warning",
                "Validity is shorter than the tender requires",
                f"You offer {offered_v} days; the tender requires {vreq.value}.",
                "terms",
                field_key="validity_terms",
            )


def rule_deadline(c: _Ctx) -> None:
    f = c.ext.get("submission_deadline")
    if not f or not f.normalized or f.status == FieldStatus.conflict:
        return
    try:
        deadline = datetime.fromisoformat(f.normalized if "T" in f.normalized else f.normalized + "T23:59")
    except ValueError:
        return
    now = datetime.now()
    if deadline < now:
        c.add(
            "deadline",
            "passed",
            "warning",
            "The submission deadline has passed",
            f"The tender deadline was {f.value}.",
            "buyer",
            field_key="submission_deadline",
        )
    elif deadline - now < timedelta(hours=48):
        c.add(
            "deadline",
            "soon",
            "info",
            "Submission deadline is within 48 hours",
            f"Deadline: {f.value}.",
            "buyer",
            field_key="submission_deadline",
        )


def rule_claims(c: _Ctx) -> None:
    for key, qf in c.q.fields.items():
        if not qf.value:
            continue
        if qf.origin == "ai_suggestion":
            c.add(
                "claims",
                f"ai:{key}",
                "warning",
                f"AI-suggested wording: {qf.label}",
                "This text was suggested by the external AI provider. Check it says only what you can commit to.",
                section_for_field(key),
                field_key=key,
            )
        if qf.origin in ("user", "ai_suggestion"):
            m = CLAIM_RE.search(qf.value)
            if m:
                c.add(
                    "claims",
                    f"claim:{key}",
                    "warning",
                    f"Unverified claim in {qf.label.lower()}",
                    f"“{m.group(0)}” is a claim TenderFlow cannot verify. Make sure you can provide evidence.",
                    section_for_field(key),
                    field_key=key,
                )
    for it in c.q.line_items:
        for attr in ("description", "specification"):
            value = getattr(it, attr)
            if value and it.origins.get(attr) in ("user", "ai_suggestion"):
                m = CLAIM_RE.search(value)
                if m:
                    c.add(
                        "claims",
                        f"claim:{it.id}:{attr}",
                        "warning",
                        f"Unverified claim in item {it.item_no}",
                        f"“{m.group(0)}” is a claim TenderFlow cannot verify.",
                        "items",
                        line_item_id=it.id,
                    )


def rule_eligibility(c: _Ctx) -> None:
    ext = c.project.extraction
    if ext is None:
        return
    elig = [r for r in ext.requirements if r.category == "eligibility"]
    if elig:
        c.add(
            "eligibility",
            "review",
            "info",
            f"{len(elig)} eligibility requirement(s) to check yourself",
            "TenderFlow lists eligibility requirements but does not check whether your company meets them.",
            "extraction",
        )


def rule_instruction_text(c: _Ctx) -> None:
    ext = c.project.extraction
    if ext is None or not ext.suspicious_text:
        return
    first = ext.suspicious_text[0]
    where = first.source.label() if first.source else "location unavailable"
    c.add(
        "instruction_text",
        "found",
        "info",
        "Instruction-like text found in the tender",
        f"{len(ext.suspicious_text)} passage(s), e.g. “{first.text[:90]}” ({where}). It was treated as document "
        "text only and did not change TenderFlow's behaviour.",
        "extraction",
    )


RULES: list[tuple[str, Callable[[_Ctx], None]]] = [
    ("mapping_confirmed", rule_mapping_confirmed),
    ("required_template_fields", rule_required_template_fields),
    ("extraction_reviewed", rule_extraction_reviewed),
    ("extraction_conflicts", rule_extraction_conflicts),
    ("line_items", rule_line_items),
    ("item_values", rule_item_values),
    ("item_arithmetic", rule_item_arithmetic),
    ("totals", rule_totals),
    ("currency", rule_currency),
    ("tax", rule_tax),
    ("price_confirmation", rule_price_confirmation),
    ("commitments", rule_commitments),
    ("quantity_vs_tender", rule_quantity_vs_tender),
    ("tender_items_quoted", rule_tender_items_quoted),
    ("terms_vs_tender", rule_terms_vs_tender),
    ("deadline", rule_deadline),
    ("claims", rule_claims),
    ("eligibility", rule_eligibility),
    ("instruction_text", rule_instruction_text),
]

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def validate(project: Project) -> ValidationReport | None:
    q = project.quotation
    if q is None:
        return None
    ctx = _Ctx(project, q)
    passed = 0
    for _name, rule in RULES:
        before = len(ctx.issues)
        rule(ctx)
        new = ctx.issues[before:]
        if not any(i.severity in ("error", "warning") for i in new):
            passed += 1
    issues = sorted(ctx.issues, key=lambda i: (SEVERITY_ORDER[i.severity], i.acknowledged))
    errors = sum(1 for i in issues if i.severity == "error")
    warnings = sum(1 for i in issues if i.severity == "warning")
    unack = sum(1 for i in issues if i.severity == "warning" and not i.acknowledged)
    return ValidationReport(
        issues=issues,
        checks_run=len(RULES),
        checks_passed=passed,
        errors=errors,
        warnings=warnings,
        infos=sum(1 for i in issues if i.severity == "info"),
        unacknowledged_warnings=unack,
        ready=errors == 0 and unack == 0,
        generated_at=utcnow(),
    )
