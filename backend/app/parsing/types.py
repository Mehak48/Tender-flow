"""Format-independent representation of a parsed document (pipeline stage 2: parsing)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Block:
    """A unit of source text with as much location information as the parser can determine."""

    id: str
    kind: str  # "paragraph" | "heading" | "table_row" | "header" | "footer"
    text: str
    page: int | None = None
    line: int | None = None
    paragraph: int | None = None
    table: int | None = None  # 1-based (PDF: per page; DOCX/XLSX: document-wide)
    row: int | None = None  # 1-based row within the table (XLSX/CSV: sheet row)
    cells: list[str] | None = None
    cell_refs: list[str] | None = None  # XLSX column letters + row, e.g. ["A5", "B5"]
    sheet: str | None = None


@dataclass
class ParsedTable:
    index: int  # 1-based
    rows: list[list[str]]
    block_ids: list[str]  # block id of each row (same order as rows)
    page: int | None = None
    sheet: str | None = None


@dataclass
class ParsedDocument:
    format: str
    page_count: int | None
    blocks: list[Block] = field(default_factory=list)
    tables: list[ParsedTable] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def text_chars(self) -> int:
        return sum(len(b.text) for b in self.blocks)

    def block(self, block_id: str) -> Block | None:
        for b in self.blocks:
            if b.id == block_id:
                return b
        return None


def clean_text(value: object) -> str:
    """Collapse whitespace (including newlines inside table cells) into single spaces."""
    if value is None:
        return ""
    text = str(value).replace(" ", " ")
    return " ".join(text.split())
