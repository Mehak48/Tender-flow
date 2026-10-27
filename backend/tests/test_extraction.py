"""Stage 3: rule-based extraction against fixtures with known expected values."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.extraction import extract_tender
from app.extraction.normalize import duration_days, normalize_datetime, parse_decimal, parse_quantity
from app.models import DocumentRecord, Extraction, FieldStatus
from app.parsing import parse_document

EXPECTED = {
    "tender_reference": "NPI/PROC/2026/017",
    "tender_title": "Supply and Installation of IT Network Equipment",
    "issuer_name": "Northfield Polytechnic Institute (Sample), Procurement Office",
    "payment_terms": "100% payment within 30 days after delivery, installation and acceptance",
    "contact": "procurement@northfield.example",
}
EXPECTED_ITEMS = [
    ("Managed network switch", Decimal("4"), "Nos"),
    ("Cat6 UTP cable", Decimal("6"), "Boxes"),
    ("Wireless access point", Decimal("8"), "Nos"),
    ("Network rack", Decimal("1"), "Nos"),
    ("Installation and configuration", Decimal("1"), "Lot"),
]


def _extract(path: Path, fmt: str) -> tuple[Extraction, object]:
    parsed = parse_document(path, fmt)
    record = DocumentRecord(
        id="doc_0123456789ab", role="tender", filename=path.name, format=fmt, size_bytes=1, sha256="x"
    )  # type: ignore[arg-type]
    return extract_tender(parsed, record), parsed


@pytest.mark.parametrize("key", ["tender_pdf", "tender_docx"])
def test_known_fields_are_extracted(docs: dict[str, Path], key: str) -> None:
    ext, _ = _extract(docs[key], "pdf" if key.endswith("pdf") else "docx")
    fields = {f.key: f for f in ext.fields}
    for k, value in EXPECTED.items():
        assert fields[k].value == value, k
        assert fields[k].status == FieldStatus.extracted
    assert fields["delivery_period"].normalized == "45"
    assert fields["warranty"].normalized == "365"
    assert fields["bid_validity"].normalized == "90"
    assert fields["currency"].normalized == "PKR"
    assert fields["bid_opening"].normalized == "2026-11-14T11:30"
    items = [(i.description, i.quantity, i.unit) for i in ext.line_items]
    assert items == EXPECTED_ITEMS


def test_extraction_never_marks_values_as_confirmed(docs: dict[str, Path]) -> None:
    ext, _ = _extract(docs["tender_pdf"], "pdf")
    assert all(f.status not in (FieldStatus.confirmed, FieldStatus.edited) for f in ext.fields)
    assert all(i.status not in (FieldStatus.confirmed, FieldStatus.edited) for i in ext.line_items)
    assert ext.reviewed is False


def test_conflicting_deadlines_are_flagged_with_both_sources(docs: dict[str, Path]) -> None:
    ext, _ = _extract(docs["tender_pdf"], "pdf")
    deadline = next(f for f in ext.fields if f.key == "submission_deadline")
    assert deadline.status == FieldStatus.conflict
    assert deadline.value is None  # an ambiguous value is not turned into a fact
    values = sorted(c.value for c in deadline.candidates)
    assert values == ["14 November 2026, 11:00 AM", "14 November 2026, 11:30 AM"]
    assert {c.source.page for c in deadline.candidates} == {1, 3}


def test_source_references_point_at_real_text(docs: dict[str, Path]) -> None:
    ext, parsed = _extract(docs["tender_pdf"], "pdf")
    blocks = {b.id: b for b in parsed.blocks}  # type: ignore[attr-defined]
    checked = 0
    for f in ext.fields:
        for src in f.sources:
            block = blocks[src.block_id]
            assert block.page == src.page
            assert src.snippet == block.text[:300]
            if f.value:
                assert f.value.split(" ")[0] in block.text
            checked += 1
    for item in ext.line_items:
        assert item.source is not None
        assert item.description and item.description in blocks[item.source.block_id].text
        checked += 1
    assert checked >= 15


def test_missing_fields_stay_missing(docs: dict[str, Path]) -> None:
    ext, _ = _extract(docs["tender_no_deadline"], "pdf")
    deadline = next(f for f in ext.fields if f.key == "submission_deadline")
    assert deadline.status == FieldStatus.missing and deadline.value is None and deadline.sources == []


def test_minimal_tender_reports_gaps(docs: dict[str, Path]) -> None:
    ext, _ = _extract(docs["tender_minimal"], "pdf")
    fields = {f.key: f for f in ext.fields}
    assert fields["tender_title"].value == "Office chairs"
    for key in ("tender_reference", "issuer_name", "submission_deadline", "payment_terms"):
        assert fields[key].status == FieldStatus.missing, key
    assert ext.line_items == []
    assert any("No line-item table" in w for w in ext.warnings)


def test_document_instructions_do_not_change_behaviour(docs: dict[str, Path]) -> None:
    ext, _ = _extract(docs["tender_malicious"], "pdf")
    assert len(ext.suspicious_text) >= 2
    patterns = " ".join(s.pattern for s in ext.suspicious_text)
    assert "override_instructions" in patterns and "concealment" in patterns
    # Nothing was confirmed, no price-like field exists, and the injected lines are not requirements.
    assert all(f.status != FieldStatus.confirmed for f in ext.fields)
    assert not any("ignore all previous" in r.text.lower() for r in ext.requirements)
    assert any("instruction-like" in w for w in ext.warnings)


def test_requirements_are_categorised(docs: dict[str, Path]) -> None:
    ext, _ = _extract(docs["tender_pdf"], "pdf")
    categories = [r.category for r in ext.requirements]
    assert categories.count("eligibility") == 4
    assert all(r.source is not None for r in ext.requirements)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("14 November 2026, 11:00 AM", "2026-11-14T11:00"),
        ("November 14, 2026 at 2:30 pm", "2026-11-14T14:30"),
        ("14/11/2026 1100 hrs", "2026-11-14T11:00"),
        ("2026-11-14", "2026-11-14"),
        ("next Tuesday", None),
    ],
)
def test_normalize_datetime(text: str, expected: str | None) -> None:
    assert normalize_datetime(text) == expected


@pytest.mark.parametrize(
    ("text", "days"),
    [("Within 45 days of PO", 45), ("one (1) year", 365), ("6 weeks", 42), ("two months", 60), ("ASAP", None)],
)
def test_duration_days(text: str, days: int | None) -> None:
    assert duration_days(text) == days


def test_number_parsing() -> None:
    assert parse_decimal("Rs. 1,250.50") == Decimal("1250.50")
    assert parse_decimal("abc") is None
    assert parse_quantity("6 Boxes") == (Decimal("6"), "Boxes")
    assert parse_quantity("As required") == (None, None)
