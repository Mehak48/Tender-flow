"""Rule-based tender extraction (pipeline stage 3).

Deterministic and explainable: every field records the rule that matched and the verbatim source block.
Nothing here is a probability — statuses are review labels (extracted / needs review / conflict / missing).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..models import (
    Candidate,
    DocumentRecord,
    ExtractedField,
    Extraction,
    FieldStatus,
    Requirement,
    RequirementCategory,
    SourceRef,
    SuspiciousText,
)
from ..parsing.types import Block, ParsedDocument
from ..storage import new_id
from .injection import find_instruction_like
from .line_items import extract_line_items
from .rules import (
    FIELD_SPECS,
    LABEL_ONLY_REGEXES,
    LABEL_REGEXES,
    SENTENCE_REGEXES,
    clean_value,
    strip_numbering,
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'])")
_REQUIREMENT = re.compile(r"\b(shall|must|is required to|are required to|mandatory|should)\b", re.I)
_ORG_WORDS = re.compile(
    r"\b(institute|university|authority|department|ministry|company|limited|ltd|corporation|board|council|"
    r"hospital|college|school|agency|directorate|commission|organi[sz]ation|bank|polytechnic)\b",
    re.I,
)
REQ_CATEGORIES: list[tuple[RequirementCategory, re.Pattern[str]]] = [
    (
        "eligibility",
        re.compile(
            r"\b(regist(ered|ration)|ntn|strn|gst|tax authority|experience|turnover|authori[sz]ation|"
            r"blacklist|certificat|licen[cs]e|affidavit|eligib|undertaking)",
            re.I,
        ),
    ),
    ("submission", re.compile(r"\b(submit|submission|sealed|envelope|deadline|bid security|earnest|receiv)", re.I)),
    ("delivery", re.compile(r"\b(deliver|installation|install|site|commission|dispatch)", re.I)),
    ("commercial", re.compile(r"\b(price|payment|tax|valid|currency|invoice|security|rupee|discount)", re.I)),
    ("technical", re.compile(r"\b(specification|warranty|complian|standard|model|brand|quality|test)", re.I)),
]


@dataclass
class _Cand:
    value: str
    normalized: str | None
    block: Block
    rule: str
    strength: str  # "label" | "sentence" | "heuristic"


class _RefFactory:
    def __init__(self, record: DocumentRecord, parsed: ParsedDocument) -> None:
        self.record = record
        self.blocks = {b.id: b for b in parsed.blocks}

    def __call__(self, block_id: str, column: int | None = None) -> SourceRef | None:
        b = self.blocks.get(block_id)
        if b is None:
            return None
        cell = None
        if b.cell_refs and column is not None and 0 <= column < len(b.cell_refs):
            cell = b.cell_refs[column]
        return SourceRef(
            document_id=self.record.id,
            document_name=self.record.filename,
            block_id=b.id,
            page=b.page,
            line=b.line,
            paragraph=b.paragraph,
            table=b.table,
            row=b.row,
            column=(column + 1) if column is not None else None,
            sheet=b.sheet,
            cell=cell,
            snippet=b.text[:300],
            precision="exact" if b.kind == "table_row" or b.page is not None or b.paragraph is not None else "block",
        )


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def _collect_candidates(parsed: ParsedDocument) -> dict[str, list[_Cand]]:
    found: dict[str, list[_Cand]] = {spec.key: [] for spec in FIELD_SPECS}

    def add(spec_key: str, raw: str, block: Block, rule: str, strength: str) -> None:
        spec = next(s for s in FIELD_SPECS if s.key == spec_key)
        value = clean_value(raw)
        if not value or len(value) < 2:
            return
        normalized = spec.normalizer(value) if spec.normalizer else None
        found[spec_key].append(_Cand(value, normalized, block, rule, strength))

    for block in parsed.blocks:
        if block.kind in ("paragraph", "heading"):
            text = strip_numbering(block.text)
            for spec in FIELD_SPECS:
                m = LABEL_REGEXES[spec.key].match(text)
                if m:
                    add(spec.key, m.group("v"), block, f"label:{spec.key}", "label")
            for sentence in _sentences(block.text):
                for spec in FIELD_SPECS:
                    for i, rx in enumerate(SENTENCE_REGEXES[spec.key]):
                        sm = rx.search(sentence)
                        if not sm:
                            continue
                        raw = strip_numbering(sentence) if spec.key == "tax_instructions" else sm.group("v")
                        add(spec.key, raw, block, f"sentence:{spec.key}:{i + 1}", "sentence")
        elif block.kind == "table_row" and block.cells:
            cells = block.cells
            for idx, cell in enumerate(cells):
                for spec in FIELD_SPECS:
                    if idx + 1 < len(cells) and cells[idx + 1] and LABEL_ONLY_REGEXES[spec.key].match(cell):
                        add(spec.key, cells[idx + 1], block, f"table-label:{spec.key}", "label")
                    else:
                        m = LABEL_REGEXES[spec.key].match(strip_numbering(cell))
                        if m:
                            add(spec.key, m.group("v"), block, f"label:{spec.key}", "label")
    return found


def _norm_key(c: _Cand) -> str:
    return c.normalized if c.normalized else re.sub(r"[^a-z0-9%]+", " ", c.value.lower()).strip()


def _norm_words(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", text.lower()).split())


def _heuristics(parsed: ParsedDocument, fields: dict[str, ExtractedField], make_ref: _RefFactory) -> None:
    """Weak fallbacks. Results are always marked needs_review, never extracted."""
    issuer = fields["issuer_name"]
    head = [b for b in parsed.blocks[:8] if b.kind in ("heading", "paragraph")]
    if issuer.status == FieldStatus.missing:
        for b in head:
            heading_like = (
                len(b.text) < 90
                and len(b.text.split()) <= 10
                and not b.text.rstrip().endswith((".", ";", ","))
                and (b.kind == "heading" or b.text.isupper())
            )
            if heading_like and _ORG_WORDS.search(b.text) and ":" not in b.text:
                issuer.value = b.text.title() if b.text.isupper() else b.text
                issuer.status = FieldStatus.needs_review
                issuer.rule = "heuristic:heading"
                issuer.note = "Guessed from a heading near the top of the document. Please confirm."
                ref = make_ref(b.id)
                issuer.sources = [ref] if ref else []
                break
    address = fields["issuer_address"]
    if address.status == FieldStatus.missing and issuer.value:
        target = _norm_words(issuer.value)
        for i, b in enumerate(head):
            heading = _norm_words(b.text)
            if heading and (target.startswith(heading) or heading.startswith(target)) and i + 1 < len(head):
                nxt = head[i + 1]
                if ":" not in nxt.text and len(nxt.text) < 150 and ("," in nxt.text or re.search(r"\d", nxt.text)):
                    address.value = nxt.text
                    address.status = FieldStatus.needs_review
                    address.rule = "heuristic:line-after-heading"
                    address.note = "Taken from the line below the organisation heading. Please confirm."
                    ref = make_ref(nxt.id)
                    address.sources = [ref] if ref else []
                break


def _requirements(parsed: ParsedDocument, make_ref: _RefFactory, suspicious_blocks: set[str]) -> list[Requirement]:
    reqs: list[Requirement] = []
    seen: set[str] = set()
    for block in parsed.blocks:
        if block.kind not in ("paragraph", "heading") or block.id in suspicious_blocks:
            continue
        for sentence in _sentences(block.text):
            if not _REQUIREMENT.search(sentence) or len(sentence) > 500 or find_instruction_like(sentence):
                continue
            text = strip_numbering(sentence)
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            category: RequirementCategory = "other"
            for cat, rx in REQ_CATEGORIES:
                if rx.search(text):
                    category = cat
                    break
            reqs.append(Requirement(id=new_id("rec"), category=category, text=text, source=make_ref(block.id)))
    return reqs


def extract_tender(parsed: ParsedDocument, record: DocumentRecord) -> Extraction:
    make_ref = _RefFactory(record, parsed)
    found = _collect_candidates(parsed)
    fields: dict[str, ExtractedField] = {}

    for spec in FIELD_SPECS:
        cands = found[spec.key]
        f = ExtractedField(key=spec.key, label=spec.label, section=spec.section, required=spec.required)  # type: ignore[arg-type]
        # De-duplicate identical values from the same block.
        unique: list[_Cand] = []
        seen_pairs: set[tuple[str, str]] = set()
        for c in cands:
            pair = (c.block.id, _norm_key(c))
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                unique.append(c)
        distinct: dict[str, list[_Cand]] = {}
        for c in unique:
            distinct.setdefault(_norm_key(c), []).append(c)
        if len(distinct) == 1:
            group = next(iter(distinct.values()))
            best = next((c for c in group if c.strength == "label"), group[0])
            f.value = best.value
            f.normalized = best.normalized
            f.status = FieldStatus.extracted
            f.rule = best.rule
            f.sources = [r for r in (make_ref(c.block.id) for c in group) if r is not None]
            if spec.normalizer and best.normalized is None:
                f.note = "The value was found but could not be interpreted automatically."
        elif len(distinct) > 1:
            f.status = FieldStatus.conflict
            f.value = None
            f.rule = "conflict"
            for group in distinct.values():
                c = next((x for x in group if x.strength == "label"), group[0])
                ref = make_ref(c.block.id)
                if ref is not None:
                    f.candidates.append(Candidate(value=c.value, source=ref))
            f.sources = [cand.source for cand in f.candidates]
            f.note = f"{len(distinct)} different values were found. Choose the correct one."
        fields[spec.key] = f

    _heuristics(parsed, fields, make_ref)

    suspicious: list[SuspiciousText] = []
    suspicious_blocks: set[str] = set()
    for block in parsed.blocks:
        for sentence in _sentences(block.text) if block.kind != "table_row" else [block.text]:
            names = find_instruction_like(sentence)
            if names:
                suspicious_blocks.add(block.id)
                suspicious.append(
                    SuspiciousText(
                        id=new_id("rec"), text=sentence[:400], pattern=", ".join(names), source=make_ref(block.id)
                    )
                )

    items, item_warnings = extract_line_items(parsed, make_ref)
    warnings = list(parsed.warnings) + item_warnings
    if suspicious:
        warnings.append(
            f"{len(suspicious)} instruction-like passage(s) found in the document. They were treated as plain "
            "document text and did not change how TenderFlow behaves."
        )
    return Extraction(
        document_id=record.id,
        fields=list(fields.values()),
        line_items=items,
        requirements=_requirements(parsed, make_ref, suspicious_blocks),
        suspicious_text=suspicious,
        warnings=warnings,
    )
