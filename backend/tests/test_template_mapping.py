"""Stage 5: template analysis and field mapping."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.errors import AppError
from app.mapping import apply_mapping_update, auto_mapping, build_view
from app.models import ColumnMappingRow, DocumentRecord, FieldMappingRow, TemplateAnalysis
from app.template_analysis import analyze_template


def _analyze(path: Path) -> TemplateAnalysis:
    fmt = path.suffix.lstrip(".")
    rec = DocumentRecord(
        id="doc_0123456789ab", role="template", filename=path.name, format=fmt, size_bytes=1, sha256="x"
    )  # type: ignore[arg-type]
    return analyze_template(path, rec)


def test_docx_template_fields_and_items_table(docs: dict[str, Path]) -> None:
    t = _analyze(docs["template_docx"])
    keys = {f.key for f in t.fields}
    for k in (
        "company_name",
        "quotation_number",
        "tender_reference",
        "buyer_name",
        "total",
        "delivery_terms",
        "prepared_by",
    ):
        assert k in keys, k
    company = next(f for f in t.fields if f.id == "ph:company_name")
    assert {"Header", "Footer"} <= set(company.locations)
    optional = next(f for f in t.fields if f.id == "ph:notes")
    assert optional.required is False
    signature = next(f for f in t.fields if f.key == "signature")
    assert signature.required is False
    assert t.items_table is not None
    attrs = [c.attribute for c in t.items_table.columns]
    assert attrs == ["item_no", "description", "specification", "quantity", "unit", "unit_price", "amount"]
    assert t.items_table.template_row == t.items_table.header_row + 1


def test_xlsx_template(docs: dict[str, Path]) -> None:
    t = _analyze(docs["template_xlsx"])
    assert t.format == "xlsx"
    assert t.items_table is not None and t.items_table.sheet == "Quotation" and t.items_table.header_row == 12
    assert any(f.kind == "label_blank" and f.key == "prepared_by" for f in t.fields)


def test_placeholder_row_template(docs: dict[str, Path]) -> None:
    t = _analyze(docs["template_rows_docx"])
    assert t.items_table is not None and t.items_table.mode == "placeholder_row"
    assert [c.attribute for c in t.items_table.columns] == ["description", "quantity", "unit_price", "amount"]


def test_template_without_items_warns_and_keeps_unknown_placeholders(docs: dict[str, Path]) -> None:
    t = _analyze(docs["template_no_items"])
    assert t.items_table is None
    assert any("No line-items table" in w for w in t.warnings)
    unknown = next(f for f in t.fields if f.id == "ph:favourite_colour")
    assert unknown.recognized is False and unknown.key is None


def test_auto_mapping_uses_exact_keys_only(docs: dict[str, Path]) -> None:
    t = _analyze(docs["template_no_items"])
    m = auto_mapping(t)
    rows = {r.target_field_id: r for r in m.fields}
    assert rows["ph:quotation_number"].source_key == "quotation_number"
    assert rows["ph:favourite_colour"].source_key is None
    view = build_view(m, t, {})
    assert "ph:favourite_colour" in view.unfilled_targets
    assert "ph:favourite_colour" in view.required_unfilled


def test_mapping_updates_are_validated(docs: dict[str, Path]) -> None:
    t = _analyze(docs["template_docx"])
    m = auto_mapping(t)
    m.confirmed = True
    apply_mapping_update(m, t, [FieldMappingRow(target_field_id="ph:notes", source_key="payment_terms")], [])
    assert next(r for r in m.fields if r.target_field_id == "ph:notes").status == "manual"
    assert m.confirmed is False  # any change requires re-confirmation
    with pytest.raises(AppError):
        apply_mapping_update(m, t, [FieldMappingRow(target_field_id="ph:does_not_exist", source_key=None)], [])
    with pytest.raises(AppError):
        apply_mapping_update(m, t, [FieldMappingRow(target_field_id="ph:notes", source_key="not_a_field")], [])
    sig = next(f for f in t.fields if f.key == "signature")
    with pytest.raises(AppError):
        apply_mapping_update(m, t, [FieldMappingRow(target_field_id=sig.id, source_key="prepared_by")], [])
    with pytest.raises(AppError):
        apply_mapping_update(m, t, [], [ColumnMappingRow(column_index=99, attribute="description")])
    apply_mapping_update(m, t, [], [ColumnMappingRow(column_index=2, attribute=None)])
    assert next(c for c in m.columns if c.column_index == 2).attribute is None


def test_mapping_api_flow(client, docs) -> None:  # type: ignore[no-untyped-def]
    from tests.conftest import new_project, upload

    pid = new_project(client)
    view = upload(client, pid, "template", docs["template_docx"]).json()
    mv = view["mapping"]
    assert mv["mapping"]["confirmed"] is False
    assert any(s["key"] == "company_name" for s in mv["sources"])
    r = client.put(
        f"/api/projects/{pid}/mapping", json={"fields": [{"target_field_id": "ph:notes", "source_key": None}]}
    )
    assert r.status_code == 200
    assert "ph:notes" in r.json()["mapping"]["unfilled_targets"]
    r = client.post(f"/api/projects/{pid}/mapping/confirm")
    assert r.json()["mapping"]["mapping"]["confirmed"] is True
    # Generating without a tender is refused with a clear message.
    r = client.post(f"/api/projects/{pid}/quotation/generate")
    assert r.status_code == 409 and "tender" in r.json()["error"]["message"].lower()
