"""Canonical quotation fields and line-item attributes, with the label synonyms used to recognise them
in templates. This registry is the shared vocabulary between extraction, mapping, editing and export.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FieldDef:
    key: str
    label: str
    group: str  # company | details | buyer | terms | totals | authorization
    synonyms: tuple[str, ...] = field(default_factory=tuple)
    commitment: bool = False  # a contractual commitment: edits need explicit confirmation
    never_fill: bool = False  # e.g. signatures — TenderFlow never fills these


QUOTATION_FIELDS: dict[str, FieldDef] = {
    f.key: f
    for f in [
        FieldDef(
            "company_name",
            "Company name",
            "company",
            (
                "company",
                "company name",
                "supplier",
                "supplier name",
                "vendor",
                "vendor name",
                "bidder",
                "bidder name",
                "firm name",
                "from",
            ),
        ),
        FieldDef(
            "company_address",
            "Company address",
            "company",
            ("company address", "our address", "supplier address", "address"),
        ),
        FieldDef("company_phone", "Company phone", "company", ("phone", "tel", "telephone", "contact no", "mobile")),
        FieldDef("company_email", "Company email", "company", ("email", "e-mail", "company email")),
        FieldDef(
            "company_registration",
            "Registration / tax no.",
            "company",
            (
                "ntn",
                "strn",
                "gst no",
                "gst number",
                "registration",
                "registration no",
                "tax id",
                "vat no",
                "vat number",
                "company registration",
            ),
        ),
        FieldDef("quotation_title", "Quotation title", "details", ("quotation title", "title", "document title")),
        FieldDef(
            "quotation_number",
            "Quotation number",
            "details",
            (
                "quotation no",
                "quotation number",
                "quote no",
                "quote number",
                "quotation ref",
                "our ref",
                "our reference",
                "ref no",
            ),
        ),
        FieldDef("quotation_date", "Quotation date", "details", ("date", "quotation date", "quote date", "issue date")),
        FieldDef(
            "valid_until",
            "Valid until",
            "details",
            ("valid until", "valid till", "validity date", "expiry date", "expires"),
        ),
        FieldDef("currency", "Currency", "details", ("currency",)),
        FieldDef(
            "tender_reference",
            "Tender reference",
            "buyer",
            (
                "tender reference",
                "tender ref",
                "tender no",
                "tender number",
                "rfq no",
                "rfq number",
                "ifb no",
                "bid reference",
                "your ref",
                "your reference",
                "reference",
            ),
        ),
        FieldDef(
            "tender_title",
            "Tender title",
            "buyer",
            ("tender title", "subject", "project", "name of work", "tender for", "re"),
        ),
        FieldDef(
            "buyer_name",
            "Buyer / organisation",
            "buyer",
            (
                "buyer",
                "customer",
                "client",
                "prepared for",
                "bill to",
                "to",
                "procuring agency",
                "organisation",
                "organization",
                "attention",
            ),
        ),
        FieldDef("buyer_address", "Buyer address", "buyer", ("buyer address", "customer address", "client address")),
        FieldDef(
            "submission_deadline", "Submission deadline", "buyer", ("submission deadline", "closing date", "deadline")
        ),
        FieldDef(
            "delivery_terms",
            "Delivery terms",
            "terms",
            ("delivery", "delivery terms", "delivery period", "delivery time", "lead time"),
            commitment=True,
        ),
        FieldDef(
            "payment_terms", "Payment terms", "terms", ("payment", "payment terms", "terms of payment"), commitment=True
        ),
        FieldDef("warranty_terms", "Warranty", "terms", ("warranty", "warranty terms", "guarantee"), commitment=True),
        FieldDef(
            "validity_terms",
            "Quotation validity",
            "terms",
            ("validity", "offer validity", "bid validity", "quotation validity"),
            commitment=True,
        ),
        FieldDef("notes", "Notes", "terms", ("notes", "remarks", "note")),
        FieldDef(
            "subtotal", "Subtotal", "totals", ("subtotal", "sub total", "sub-total", "total before tax", "net amount")
        ),
        FieldDef("tax_label", "Tax label", "totals", ("tax label",)),
        FieldDef("tax_rate", "Tax rate", "totals", ("tax rate", "tax %", "gst %", "sales tax rate", "vat rate")),
        FieldDef("tax_amount", "Tax amount", "totals", ("tax", "tax amount", "gst", "sales tax", "vat")),
        FieldDef(
            "total",
            "Total",
            "totals",
            ("total", "grand total", "total amount", "net total", "quotation total", "amount payable", "total price"),
        ),
        FieldDef(
            "prepared_by",
            "Prepared by",
            "authorization",
            (
                "prepared by",
                "name",
                "authorized by",
                "authorised by",
                "authorized person",
                "authorised person",
                "contact person",
            ),
        ),
        FieldDef(
            "signature", "Signature", "authorization", ("signature", "sign", "signed", "stamp", "seal"), never_fill=True
        ),
    ]
}

FIELD_GROUP_LABELS = {
    "company": "Company header",
    "details": "Quotation details",
    "buyer": "Buyer information",
    "terms": "Commercial terms",
    "totals": "Totals",
    "authorization": "Authorization",
}

COMMITMENT_FIELDS = {k for k, f in QUOTATION_FIELDS.items() if f.commitment}


@dataclass(frozen=True)
class ItemAttrDef:
    key: str
    label: str
    synonyms: tuple[str, ...]


ITEM_ATTRIBUTES: dict[str, ItemAttrDef] = {
    a.key: a
    for a in [
        ItemAttrDef(
            "item_no",
            "Item no.",
            (
                "#",
                "no",
                "no.",
                "s.no",
                "s. no",
                "s no",
                "sr",
                "sr.",
                "sr no",
                "sr. no",
                "sl no",
                "item no",
                "serial",
                "serial no",
                "line",
            ),
        ),
        ItemAttrDef(
            "description",
            "Description",
            (
                "description",
                "item description",
                "item",
                "items",
                "particulars",
                "product",
                "product description",
                "goods",
                "equipment",
                "name of item",
                "service",
                "services",
            ),
        ),
        ItemAttrDef(
            "specification",
            "Specification",
            (
                "specification",
                "specifications",
                "technical specification",
                "technical specifications",
                "specs",
                "spec",
                "details",
                "features",
            ),
        ),
        ItemAttrDef(
            "quantity",
            "Quantity",
            (
                "qty",
                "qty.",
                "quantity",
                "required quantity",
                "quantities",
                "no of units",
                "no. of units",
                "units required",
            ),
        ),
        ItemAttrDef("unit", "Unit", ("unit", "uom", "u.o.m", "unit of measure", "unit of measurement", "units")),
        ItemAttrDef(
            "unit_price",
            "Unit price",
            ("unit price", "rate", "unit rate", "price", "unit cost", "price per unit", "unit price (pkr)"),
        ),
        ItemAttrDef(
            "amount",
            "Amount",
            ("amount", "total", "line total", "total price", "extended price", "total amount", "value"),
        ),
    ]
}


def norm_label(text: str) -> str:
    """Normalise a label for synonym matching: lowercase, drop punctuation except '#', collapse spaces."""
    t = text.lower().strip()
    t = re.sub(r"\(.*?\)", " ", t)  # "Unit Price (PKR)" -> "unit price"
    t = t.replace("&", " and ")
    t = re.sub(r"[^a-z0-9# ]+", " ", t)
    return " ".join(t.split())


_FIELD_SYNONYM_INDEX: dict[str, str] = {}
for _key, _def in QUOTATION_FIELDS.items():
    for _syn in (_def.key.replace("_", " "), _def.label, *_def.synonyms):
        _FIELD_SYNONYM_INDEX.setdefault(norm_label(_syn), _key)

_ITEM_SYNONYM_INDEX: dict[str, str] = {}
for _key, _adef in ITEM_ATTRIBUTES.items():
    for _syn in (_adef.key.replace("_", " "), _adef.label, *_adef.synonyms):
        _ITEM_SYNONYM_INDEX.setdefault(norm_label(_syn), _key)


def match_field_label(label: str) -> str | None:
    """Return the canonical field key for a template label such as 'Quotation No.:'."""
    n = norm_label(label)
    if not n:
        return None
    if n in _FIELD_SYNONYM_INDEX:
        return _FIELD_SYNONYM_INDEX[n]
    return None


def match_item_header(header: str) -> str | None:
    n = norm_label(header)
    if not n:
        return "item_no" if header.strip() == "#" else None
    if n in _ITEM_SYNONYM_INDEX:
        return _ITEM_SYNONYM_INDEX[n]
    # Accept common compound headers like "Item Description" or "Unit Price Rs".
    for prefix_key in ("unit price", "unit rate", "item description", "technical specification", "line total"):
        if n.startswith(prefix_key):
            return _ITEM_SYNONYM_INDEX[prefix_key]
    return None


def canonical_placeholder(key: str) -> str | None:
    k = key.strip().lower()
    if k in QUOTATION_FIELDS:
        return k
    return match_field_label(k.replace("_", " "))
