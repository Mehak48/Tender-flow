"""PDF parsing with pdfplumber (MIT). Page-aware: every block knows its page and first line number.

Ruled tables are detected with pdfplumber's line strategy and emitted as table rows; text outside the
tables is grouped into paragraphs. Pages without a text layer are reported (no OCR in this prototype).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pdfplumber
from pdfminer.pdfdocument import PDFEncryptionError, PDFPasswordIncorrect
from pdfminer.pdfparser import PDFSyntaxError

from ..errors import AppError
from .types import Block, ParsedDocument, ParsedTable, clean_text

_CONTINUATION_START = re.compile(r"^[a-z(]")
_TERMINAL = (".", ":", ";", "!", "?")
_LIST_START = re.compile(r"^(\d+(\.\d+)*[.)]?\s|[A-Z][A-Za-z ]{1,40}:|[-•*]\s)")
MAX_PAGES = 300


def _inside(bbox: tuple[float, float, float, float], obj: dict[str, Any]) -> bool:
    x0, top, x1, bottom = bbox
    cx = (obj["x0"] + obj["x1"]) / 2
    cy = (obj["top"] + obj["bottom"]) / 2
    return x0 <= cx <= x1 and top <= cy <= bottom


def parse_pdf(path: Path) -> ParsedDocument:
    try:
        pdf = pdfplumber.open(str(path))
    except (PDFPasswordIncorrect, PDFEncryptionError) as exc:
        raise AppError("encrypted_pdf", "Password-protected PDFs are not supported.") from exc
    except (PDFSyntaxError, ValueError, TypeError, KeyError) as exc:
        raise AppError("unreadable_pdf", "This PDF could not be read. It may be damaged.") from exc
    except Exception as exc:  # pdfminer raises a variety of exception types for broken files
        raise AppError("unreadable_pdf", "This PDF could not be read. It may be damaged.") from exc

    doc = ParsedDocument(format="pdf", page_count=0)
    try:
        pages = pdf.pages
        doc.page_count = len(pages)
        if len(pages) > MAX_PAGES:
            raise AppError("too_many_pages", f"PDFs with more than {MAX_PAGES} pages are not supported.")
        image_only_pages: list[int] = []
        for page_no, page in enumerate(pages, start=1):
            try:
                _parse_page(doc, page, page_no, image_only_pages)
            except AppError:
                raise
            except Exception:
                doc.warnings.append(f"Page {page_no} could not be parsed and was skipped.")
        if image_only_pages:
            pages_text = ", ".join(str(p) for p in image_only_pages[:10])
            doc.warnings.append(
                f"No text layer on page(s) {pages_text}. These look like scanned images; OCR is not "
                "implemented, so their content was not read."
            )
        if not doc.blocks:
            doc.warnings.append("No readable text was found in this PDF.")
    finally:
        pdf.close()
    return doc


def _parse_page(doc: ParsedDocument, page: Any, page_no: int, image_only_pages: list[int]) -> None:
    tables = page.find_tables()
    bboxes = [t.bbox for t in tables]
    entries: list[tuple[float, str, Any]] = []  # (top, kind, payload)

    for t_index, table in enumerate(tables, start=1):
        rows = [[clean_text(c) for c in row] for row in table.extract()]
        rows = [r for r in rows if any(r)]
        if rows:
            entries.append((table.bbox[1], "table", (t_index, rows)))

    def keep(obj: dict[str, Any]) -> bool:
        if obj.get("object_type") != "char":
            return True
        return not any(_inside(b, obj) for b in bboxes)

    text_page = page.filter(keep) if bboxes else page
    lines = text_page.extract_text_lines(layout=False, strip=True, return_chars=False)
    for line_no, line in enumerate(lines, start=1):
        text = clean_text(line.get("text"))
        if text:
            entries.append((float(line["top"]), "line", (line_no, text)))

    if not entries:
        if page.images:
            image_only_pages.append(page_no)
        return

    entries.sort(key=lambda e: e[0])
    para_lines: list[tuple[int, str]] = []
    para_counter = 0

    def flush() -> None:
        nonlocal para_counter
        if not para_lines:
            return
        para_counter += 1
        first_line = para_lines[0][0]
        text = " ".join(t for _, t in para_lines)
        doc.blocks.append(
            Block(id=f"p{page_no}-l{first_line}", kind="paragraph", text=text, page=page_no, line=first_line)
        )
        para_lines.clear()

    for _, kind, payload in entries:
        if kind == "line":
            line_no, text = payload
            if para_lines:
                prev = para_lines[-1][1]
                continues = (
                    not prev.endswith(_TERMINAL)
                    and _CONTINUATION_START.match(text) is not None
                    and _LIST_START.match(text) is None
                )
                if not continues:
                    flush()
            para_lines.append((line_no, text))
        else:
            flush()
            t_index, rows = payload
            table_no = len(doc.tables) + 1
            block_ids: list[str] = []
            for r_index, row in enumerate(rows, start=1):
                block_id = f"p{page_no}-t{t_index}-r{r_index}"
                block_ids.append(block_id)
                doc.blocks.append(
                    Block(
                        id=block_id,
                        kind="table_row",
                        text=" | ".join(c for c in row if c),
                        page=page_no,
                        table=t_index,
                        row=r_index,
                        cells=row,
                    )
                )
            doc.tables.append(ParsedTable(index=table_no, rows=rows, block_ids=block_ids, page=page_no))
    flush()
