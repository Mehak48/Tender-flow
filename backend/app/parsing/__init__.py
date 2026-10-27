"""Document parsing entry point."""

from __future__ import annotations

from pathlib import Path

from ..errors import AppError
from .docx_parser import parse_docx
from .pdf import parse_pdf
from .types import Block, ParsedDocument, ParsedTable, clean_text
from .xlsx_parser import parse_csv, parse_xlsx

__all__ = ["Block", "ParsedDocument", "ParsedTable", "clean_text", "parse_document"]


def parse_document(path: Path, fmt: str) -> ParsedDocument:
    if fmt == "pdf":
        return parse_pdf(path)
    if fmt == "docx":
        return parse_docx(path)
    if fmt == "xlsx":
        return parse_xlsx(path)
    if fmt == "csv":
        return parse_csv(path)
    raise AppError("unsupported_format", "Unsupported document format.", 415)
