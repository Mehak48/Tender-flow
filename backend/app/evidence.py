"""Source evidence: verbatim text around a source reference, re-read from the stored original.

Parsed documents are cached in memory (small LRU) so clicking through sources stays fast.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from pathlib import Path

from .models import DocumentRecord, EvidenceBlock, EvidenceResponse
from .parsing import ParsedDocument, parse_document

_CACHE: OrderedDict[tuple[str, str], ParsedDocument] = OrderedDict()
_LOCK = threading.Lock()
_MAX = 8


def _parsed(path: Path, record: DocumentRecord) -> ParsedDocument:
    key = (record.id, record.sha256)
    with _LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
    parsed = parse_document(path, record.format)
    with _LOCK:
        _CACHE[key] = parsed
        while len(_CACHE) > _MAX:
            _CACHE.popitem(last=False)
    return parsed


def evidence(path: Path, record: DocumentRecord, block_id: str | None, page: int | None) -> EvidenceResponse:
    parsed = _parsed(path, record)
    focus = parsed.block(block_id) if block_id else None
    note = None
    if block_id and focus is None:
        note = "The exact source location could not be found in the stored document."
    if record.format == "pdf":
        target_page = focus.page if focus and focus.page else (page or 1)
        blocks = [b for b in parsed.blocks if b.page == target_page]
        if not blocks and parsed.page_count:
            note = note or "No text was extracted from this page."
    else:
        idx = parsed.blocks.index(focus) if focus else 0
        start = max(0, idx - 10)
        blocks = parsed.blocks[start : start + 24]
        target_page = None
    return EvidenceResponse(
        document_id=record.id,
        document_name=record.filename,
        page=target_page,
        page_count=parsed.page_count,
        blocks=[
            EvidenceBlock(
                id=b.id,
                kind=b.kind,
                text=b.text,
                page=b.page,
                line=b.line,
                paragraph=b.paragraph,
                table=b.table,
                row=b.row,
                sheet=b.sheet,
                cells=b.cells,
            )
            for b in blocks
        ],
        focus_block_id=focus.id if focus else None,
        note=note,
    )
