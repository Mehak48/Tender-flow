"""XLSX and CSV parsing. Each non-empty row becomes a table-row block with sheet/cell references.

Workbooks are opened read-only with cached values (``data_only=True``); the original file is never
modified. Formulas that were never calculated by a spreadsheet application have no cached value and are
read as empty — this is reported as a warning.
"""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import InvalidFileException

from ..errors import AppError
from .types import Block, ParsedDocument, ParsedTable, clean_text

MAX_ROWS = 5000
MAX_COLS = 60


def _format_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return clean_text(value)


def parse_xlsx(path: Path) -> ParsedDocument:
    try:
        wb = load_workbook(str(path), read_only=True, data_only=True)
    except (InvalidFileException, zipfile.BadZipFile, KeyError, ValueError, OSError) as exc:
        raise AppError("unreadable_xlsx", "This Excel workbook could not be read. It may be damaged.") from exc
    except Exception as exc:
        raise AppError("unreadable_xlsx", "This Excel workbook could not be read. It may be damaged.") from exc

    doc = ParsedDocument(format="xlsx", page_count=None)
    try:
        for t_index, ws in enumerate(wb.worksheets, start=1):
            rows: list[list[str]] = []
            block_ids: list[str] = []
            for r_index, row in enumerate(ws.iter_rows(max_col=MAX_COLS, values_only=True), start=1):
                if r_index > MAX_ROWS:
                    doc.warnings.append(f"Sheet {ws.title}: only the first {MAX_ROWS} rows were read.")
                    break
                cells = [_format_value(v) for v in row]
                while cells and not cells[-1]:
                    cells.pop()
                if not any(cells):
                    continue
                block_id = f"s{t_index}-r{r_index}"
                rows.append(cells)
                block_ids.append(block_id)
                doc.blocks.append(
                    Block(
                        id=block_id,
                        kind="table_row",
                        text=" | ".join(c for c in cells if c),
                        table=t_index,
                        row=r_index,
                        sheet=ws.title,
                        cells=cells,
                        cell_refs=[f"{get_column_letter(i)}{r_index}" for i in range(1, len(cells) + 1)],
                    )
                )
            if rows:
                doc.tables.append(ParsedTable(index=t_index, rows=rows, block_ids=block_ids, sheet=ws.title))
    finally:
        wb.close()
    if not doc.blocks:
        doc.warnings.append("No values were found in this workbook.")
    return doc


def parse_csv(path: Path) -> ParsedDocument:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    doc = ParsedDocument(format="csv", page_count=None)
    rows: list[list[str]] = []
    block_ids: list[str] = []
    try:
        for r_index, row in enumerate(reader, start=1):
            if r_index > MAX_ROWS:
                doc.warnings.append(f"Only the first {MAX_ROWS} rows were read.")
                break
            cells = [clean_text(c) for c in row[:MAX_COLS]]
            if not any(cells):
                continue
            block_id = f"csv-r{r_index}"
            rows.append(cells)
            block_ids.append(block_id)
            doc.blocks.append(
                Block(
                    id=block_id,
                    kind="table_row",
                    text=" | ".join(c for c in cells if c),
                    table=1,
                    row=r_index,
                    cells=cells,
                    cell_refs=[f"{get_column_letter(i)}{r_index}" for i in range(1, len(cells) + 1)],
                )
            )
    except csv.Error as exc:
        raise AppError("unreadable_csv", "This CSV file could not be read.") from exc
    if rows:
        doc.tables.append(ParsedTable(index=1, rows=rows, block_ids=block_ids))
    else:
        doc.warnings.append("No values were found in this CSV file.")
    return doc
