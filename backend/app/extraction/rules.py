"""Label/value and sentence rules for tender fields.

Each rule produces *candidates* (value + source block). The orchestrator decides the status:
one distinct value -> extracted, several -> conflict, weak heuristic only -> needs_review, none -> missing.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from .normalize import detect_currency, duration_days, normalize_datetime


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    section: str
    required: bool
    labels: tuple[str, ...]  # regex alternatives for "<label>: <value>"
    normalizer: Callable[[str], str | None] | None = None
    sentence_rules: tuple[str, ...] = ()  # regexes with a named group "v" searched inside sentences


def _days(text: str) -> str | None:
    d = duration_days(text)
    return str(d) if d is not None else None


_DATE_VALUE = (
    r"(?P<v>(?:\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\.?,?\s+\d{4}|[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4}|"
    r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}|\d{4}-\d{2}-\d{2})(?:,?\s*(?:at\s*)?\d{1,2}(?:[:.]\d{2})?\s*(?:a\.?m\.?|p\.?m\.?|hrs|hours)?)?)"
)

FIELD_SPECS: tuple[FieldSpec, ...] = (
    FieldSpec(
        "tender_reference",
        "Tender reference",
        "overview",
        True,
        (
            r"tender\s*(?:ref(?:erence)?\.?|no\.?|number|id)(?:\s*no\.?)?",
            r"(?:rfq|rfp|ifb|itb|eoi|nit)\s*(?:ref(?:erence)?\.?|no\.?|number)?",
            r"bid\s*(?:ref(?:erence)?\.?|no\.?|number)",
            r"(?:procurement|solicitation)\s*(?:ref(?:erence)?\.?|no\.?|number)",
        ),
    ),
    FieldSpec(
        "tender_title",
        "Tender title",
        "overview",
        True,
        (
            r"title(?:\s*of\s*(?:the\s*)?(?:tender|work|assignment))?",
            r"(?:name|subject)\s*of\s*(?:the\s*)?(?:work|tender|assignment|procurement|contract)",
            r"subject",
            r"tender\s*(?:title|for)",
        ),
    ),
    FieldSpec(
        "issuer_name",
        "Issuing organisation",
        "overview",
        True,
        (
            r"issued\s*by",
            r"(?:procuring|purchasing|contracting)\s*(?:agency|entity|organi[sz]ation|authority|department)",
            r"issuing\s*(?:authority|organi[sz]ation|office|agency)",
            r"(?:name\s*of\s*)?(?:the\s*)?(?:client|employer|purchaser)",
        ),
    ),
    FieldSpec("issuer_address", "Issuer address", "overview", False, (r"(?:office\s*)?address",)),
    FieldSpec(
        "issue_date",
        "Date of issue",
        "dates",
        False,
        (r"date\s*of\s*issue", r"issue\s*date", r"date\s*of\s*publication"),
        normalizer=normalize_datetime,
    ),
    FieldSpec(
        "submission_deadline",
        "Submission deadline",
        "dates",
        True,
        (
            r"(?:last|closing|final)\s*date(?:\s*and\s*time)?(?:\s*(?:for|of)\s*(?:the\s*)?(?:submission|receipt)"
            r"(?:\s*of\s*(?:the\s*)?(?:bids?|tenders?|proposals?|quotations?|offers?))?)?",
            r"(?:bid|tender|proposal|quotation|offer)?\s*submission\s*(?:deadline|date(?:\s*and\s*time)?|time)",
            r"deadline(?:\s*for\s*(?:the\s*)?submission(?:\s*of\s*(?:bids?|tenders?|quotations?))?)?",
            r"closing\s*(?:date|time)",
        ),
        normalizer=normalize_datetime,
        sentence_rules=(rf"(?:submission\s+)?deadline\s+(?:of|is|on|:)?\s*{_DATE_VALUE}",),
    ),
    FieldSpec(
        "bid_opening",
        "Bid opening",
        "dates",
        False,
        (r"(?:bid|tender|technical\s*bid)?\s*opening(?:\s*(?:date|time|date\s*and\s*time))?", r"date\s*of\s*opening"),
        normalizer=normalize_datetime,
    ),
    FieldSpec(
        "bid_validity",
        "Bid validity",
        "commercial",
        False,
        (
            r"(?:bid|tender|offer|quotation)\s*validity(?:\s*period)?",
            r"validity\s*(?:of\s*(?:bids?|offers?|quotations?))",
        ),
        normalizer=_days,
        sentence_rules=(
            r"(?:bids?|offers?|quotations?|tenders?|proposals?)\s+shall\s+remain\s+valid\s+for\s+(?P<v>[^.;]+)",
        ),
    ),
    FieldSpec(
        "delivery_period",
        "Delivery period",
        "delivery",
        False,
        (r"delivery\s*(?:period|time|schedule|timeline)", r"completion\s*(?:period|time)", r"lead\s*time"),
        normalizer=_days,
    ),
    FieldSpec(
        "delivery_location",
        "Delivery location",
        "delivery",
        False,
        (
            r"delivery\s*(?:location|address|place|point|site)",
            r"place\s*of\s*delivery",
            r"(?:project|installation)\s*site",
        ),
    ),
    FieldSpec(
        "payment_terms",
        "Payment terms",
        "commercial",
        False,
        (r"payment\s*(?:terms|schedule|conditions)", r"terms\s*of\s*payment", r"payment"),
    ),
    FieldSpec(
        "warranty",
        "Warranty requirement",
        "commercial",
        False,
        (r"warranty(?:\s*(?:period|terms|requirements?))?", r"guarantee\s*period"),
        normalizer=_days,
    ),
    FieldSpec(
        "bid_security",
        "Bid security",
        "commercial",
        False,
        (r"bid\s*security", r"earnest\s*money", r"tender\s*security"),
        sentence_rules=(r"(?:bid|tender)\s+security\s+of\s+(?P<v>[^.;]+?)\s+(?:shall|must|is)",),
    ),
    FieldSpec(
        "currency",
        "Currency of bid",
        "commercial",
        False,
        (r"currency(?:\s*of\s*(?:bid|quotation|tender))?",),
        normalizer=detect_currency,
        sentence_rules=(r"(?:quoted|stated|expressed|priced)\s+in\s+(?P<v>[A-Za-z .()]{2,40}?)(?:\s+and\b|[.,;]|$)",),
    ),
    FieldSpec(
        "tax_instructions",
        "Tax instructions",
        "commercial",
        False,
        (r"taxes?(?:\s*and\s*duties)?",),
        sentence_rules=(
            r"(?P<v>(?:inclusive|exclusive)\s+of\s+(?:all\s+)?(?:applicable\s+)?(?:taxes|tax|duties|gst|vat|sales\s+tax)[^.;]*)",
        ),
    ),
    FieldSpec(
        "contact",
        "Contact for queries",
        "overview",
        False,
        (
            r"contact(?:\s*(?:for\s*queries|person|details|e-?mail|information))?",
            r"queries\s*(?:to|may\s*be\s*sent\s*to)?",
            r"focal\s*person",
        ),
    ),
)

SPEC_BY_KEY = {spec.key: spec for spec in FIELD_SPECS}

_NUMBERING = re.compile(r"^\s*(?:\(?[0-9ivxIVX]+(?:\.[0-9]+)*[.)]?|[a-zA-Z][.)])\s+")
# "Label: value" or "Label - value" (a hyphen only counts with spaces around it: "Subject-matter" is not a label).
_SEP = r"(?:\s*:\s*|\s+[\-–—]\s+)"


def strip_numbering(text: str) -> str:
    return _NUMBERING.sub("", text, count=1)


def compile_label_regex(spec: FieldSpec) -> re.Pattern[str]:
    alternatives = "|".join(f"(?:{lab})" for lab in spec.labels)
    return re.compile(rf"^(?:{alternatives})\s*\.?{_SEP}(?P<v>.+)$", re.IGNORECASE)


LABEL_REGEXES = {spec.key: compile_label_regex(spec) for spec in FIELD_SPECS}
LABEL_ONLY_REGEXES = {
    spec.key: re.compile(rf"^(?:{'|'.join(f'(?:{lab})' for lab in spec.labels)})\s*\.?\s*:?\s*$", re.IGNORECASE)
    for spec in FIELD_SPECS
}
SENTENCE_REGEXES = {spec.key: [re.compile(r, re.IGNORECASE) for r in spec.sentence_rules] for spec in FIELD_SPECS}


def clean_value(value: str) -> str:
    v = value.strip().strip("-–—:;,").strip()
    v = re.sub(r"\s+", " ", v)
    if v.endswith(".") and not re.search(r"\b(?:no|ltd|pvt|co|inc|st|rs)\.$", v, re.IGNORECASE):
        v = v[:-1].rstrip()
    return v[:400]
