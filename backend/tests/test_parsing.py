"""Stage 2: parsing keeps text and its location."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.errors import AppError
from app.parsing import parse_document


def test_pdf_is_page_aware_and_finds_the_table(docs: dict[str, Path]) -> None:
    parsed = parse_document(docs["tender_pdf"], "pdf")
    assert parsed.page_count == 3
    ref_block = next(b for b in parsed.blocks if b.text.startswith("Tender Reference"))
    assert ref_block.page == 1 and ref_block.line is not None
    assert len(parsed.tables) == 1
    table = parsed.tables[0]
    assert table.page == 2
    assert table.rows[0][:2] == ["Sr. No", "Item Description"]
    assert len(table.rows) == 6
    # Table text is not duplicated as paragraphs.
    assert not any(b.kind == "paragraph" and b.text.startswith("1 Managed network switch") for b in parsed.blocks)


def test_docx_paragraphs_and_tables_are_numbered(docs: dict[str, Path]) -> None:
    parsed = parse_document(docs["tender_docx"], "docx")
    para = next(b for b in parsed.blocks if b.text.startswith("Tender Reference"))
    assert para.paragraph is not None and para.page is None
    rows = [b for b in parsed.blocks if b.kind == "table_row"]
    assert rows[0].table == 1 and rows[0].row == 1
    assert rows[1].cells is not None and rows[1].cells[1] == "Managed network switch"


def test_xlsx_and_csv_rows_have_cell_references(docs: dict[str, Path]) -> None:
    x = parse_document(docs["prices_xlsx"], "xlsx")
    header = next(b for b in x.blocks if b.cells and b.cells[0] == "Item")
    assert header.sheet == "Prices" and header.cell_refs and header.cell_refs[0] == f"A{header.row}"
    c = parse_document(docs["prices_csv"], "csv")
    assert c.blocks[0].cells == ["Item", "Unit Price", "Unit"]


def test_blank_and_scanned_pdfs_are_reported_not_invented(docs: dict[str, Path]) -> None:
    blank = parse_document(docs["blank_pdf"], "pdf")
    assert blank.blocks == [] and any("No readable text" in w for w in blank.warnings)
    scanned = parse_document(docs["scanned_pdf"], "pdf")
    assert scanned.blocks == []
    assert any("OCR is not implemented" in w for w in scanned.warnings)


def test_malformed_files_raise_clear_errors(tmp_path: Path) -> None:
    bad_pdf = tmp_path / "bad.pdf"
    bad_pdf.write_bytes(b"%PDF-1.7\nnot really a pdf")
    with pytest.raises(AppError) as exc:
        parse_document(bad_pdf, "pdf")
    assert exc.value.code == "unreadable_pdf"
    bad_docx = tmp_path / "bad.docx"
    bad_docx.write_bytes(b"PK\x03\x04 broken zip")
    with pytest.raises(AppError):
        parse_document(bad_docx, "docx")
    bad_xlsx = tmp_path / "bad.xlsx"
    bad_xlsx.write_bytes(b"PK\x03\x04 broken zip")
    with pytest.raises(AppError):
        parse_document(bad_xlsx, "xlsx")
