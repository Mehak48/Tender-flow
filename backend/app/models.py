"""Pydantic models: the single source of truth for persisted data and API schemas.

Money and quantities are ``Decimal`` and are serialised as strings in JSON so no precision is lost.
Every value that ends up in a quotation records its ``origin`` so the UI can show where it came from.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    return datetime.now(UTC)


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=False)


# ---------------------------------------------------------------------------
# Source references
# ---------------------------------------------------------------------------


class SourceRef(Model):
    """Where a value was found. Fields that the parser could not determine stay ``None``."""

    document_id: str
    document_name: str
    block_id: str | None = None
    page: int | None = None  # 1-based (PDF)
    line: int | None = None  # 1-based line on the page (PDF)
    paragraph: int | None = None  # 1-based body paragraph (DOCX)
    table: int | None = None  # 1-based table index (PDF page-local / DOCX document-wide)
    row: int | None = None  # 1-based row within the table, or the sheet row (XLSX/CSV)
    column: int | None = None  # 1-based column
    sheet: str | None = None
    cell: str | None = None  # e.g. "B4"
    snippet: str = ""  # verbatim text excerpt from the source block (truncated)
    precision: Literal["exact", "block", "unavailable"] = "block"

    def label(self) -> str:
        parts: list[str] = []
        if self.sheet:
            parts.append(f"Sheet {self.sheet}")
        if self.cell:
            parts.append(f"cell {self.cell}")
        if self.page is not None:
            parts.append(f"Page {self.page}")
        if self.table is not None:
            parts.append(f"table {self.table}")
        if self.row is not None and not self.cell:
            parts.append(f"row {self.row}")
        if self.line is not None:
            parts.append(f"line {self.line}")
        if self.paragraph is not None:
            parts.append(f"paragraph {self.paragraph}")
        return ", ".join(parts) if parts else "Location unavailable"


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

DocumentRole = Literal["tender", "template", "price_list"]
DocumentFormat = Literal["pdf", "docx", "xlsx", "csv"]


class DocumentRecord(Model):
    id: str
    role: DocumentRole
    filename: str  # sanitised original filename, display only
    format: DocumentFormat
    size_bytes: int
    sha256: str
    uploaded_at: datetime = Field(default_factory=utcnow)
    parse_status: Literal["parsed", "failed"] = "parsed"
    parse_error: str | None = None
    page_count: int | None = None
    block_count: int = 0
    table_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class EvidenceBlock(Model):
    """A verbatim block of parsed source text, returned for the source-evidence panel."""

    id: str
    kind: str
    text: str
    page: int | None = None
    line: int | None = None
    paragraph: int | None = None
    table: int | None = None
    row: int | None = None
    sheet: str | None = None
    cells: list[str] | None = None


class EvidenceResponse(Model):
    document_id: str
    document_name: str
    page: int | None
    page_count: int | None
    blocks: list[EvidenceBlock]
    focus_block_id: str | None
    note: str | None = None


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


class FieldStatus(StrEnum):
    extracted = "extracted"  # matched by a rule, not yet reviewed by the user
    needs_review = "needs_review"  # matched by a weaker heuristic or ambiguous
    conflict = "conflict"  # different values found in different places
    missing = "missing"  # not found in the document
    confirmed = "confirmed"  # user confirmed the extracted value
    edited = "edited"  # user changed the value (counts as confirmed)


REVIEWED_STATUSES = {FieldStatus.confirmed, FieldStatus.edited}

ExtractionSection = Literal["overview", "dates", "commercial", "delivery", "eligibility"]


class Candidate(Model):
    value: str
    source: SourceRef


class ExtractedField(Model):
    key: str
    label: str
    section: ExtractionSection
    value: str | None = None
    normalized: str | None = None  # e.g. ISO datetime for deadlines, days for periods
    status: FieldStatus = FieldStatus.missing
    sources: list[SourceRef] = Field(default_factory=list)
    candidates: list[Candidate] = Field(default_factory=list)
    note: str | None = None
    required: bool = False
    rule: str | None = None  # name of the rule that matched (transparency)


class ExtractedLineItem(Model):
    id: str
    item_no: str | None = None
    description: str | None = None
    quantity: Decimal | None = None
    quantity_text: str | None = None  # raw text as written in the tender
    unit: str | None = None
    specification: str | None = None
    status: FieldStatus = FieldStatus.extracted
    source: SourceRef | None = None
    notes: list[str] = Field(default_factory=list)


RequirementCategory = Literal["eligibility", "technical", "submission", "commercial", "delivery", "other"]


class Requirement(Model):
    id: str
    category: RequirementCategory
    text: str
    source: SourceRef | None = None
    acknowledged: bool = False


class SuspiciousText(Model):
    """Instruction-like text found inside an uploaded document. It is treated as data only."""

    id: str
    text: str
    pattern: str
    source: SourceRef | None = None


class Extraction(Model):
    document_id: str
    engine: Literal["rules"] = "rules"
    fields: list[ExtractedField] = Field(default_factory=list)
    line_items: list[ExtractedLineItem] = Field(default_factory=list)
    requirements: list[Requirement] = Field(default_factory=list)
    suspicious_text: list[SuspiciousText] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    reviewed: bool = False
    reviewed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


# ---------------------------------------------------------------------------
# Price list (optional, user supplied)
# ---------------------------------------------------------------------------


class PriceListRow(Model):
    row: int
    name: str
    unit_price: Decimal
    unit: str | None = None
    currency: str | None = None


class PriceList(Model):
    document_id: str
    document_name: str
    rows: list[PriceListRow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Template analysis
# ---------------------------------------------------------------------------


class TemplateField(Model):
    id: str  # stable within one template, e.g. "ph:company_name" or "lbl:t2r3c2"
    key: str | None  # canonical quotation field key when recognised
    label: str
    kind: Literal["placeholder", "label_blank"]
    required: bool = True
    recognized: bool = False
    locations: list[str] = Field(default_factory=list)


class ItemColumn(Model):
    index: int  # 0-based column index in the items table
    header: str
    attribute: str | None = None  # recognised item attribute (description, quantity, ...)


class ItemsTableInfo(Model):
    location: str
    table_index: int | None = None  # DOCX: 0-based body table index
    sheet: str | None = None  # XLSX
    header_row: int  # DOCX: 0-based row index; XLSX: 1-based sheet row
    template_row: int  # first row that receives line items (same index base as header_row)
    columns: list[ItemColumn] = Field(default_factory=list)
    mode: Literal["placeholder_row", "header_detected"] = "header_detected"


class TemplateAnalysis(Model):
    document_id: str
    document_name: str
    format: Literal["docx", "xlsx"]
    fields: list[TemplateField] = Field(default_factory=list)
    items_table: ItemsTableInfo | None = None
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------


class FieldMappingRow(Model):
    """One destination field in the template and the quotation field that fills it."""

    target_field_id: str
    source_key: str | None = None  # canonical quotation field key, or None = leave empty
    status: Literal["auto", "manual", "unmapped"] = "unmapped"


class ColumnMappingRow(Model):
    """One column of the template's items table and the line-item attribute written into it."""

    column_index: int
    attribute: str | None = None
    status: Literal["auto", "manual", "unmapped"] = "unmapped"


class Mapping(Model):
    fields: list[FieldMappingRow] = Field(default_factory=list)
    columns: list[ColumnMappingRow] = Field(default_factory=list)
    confirmed: bool = False
    confirmed_at: datetime | None = None


# ---------------------------------------------------------------------------
# Company profile and settings
# ---------------------------------------------------------------------------


class CompanyProfile(Model):
    name: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    registration: str | None = None  # e.g. NTN / STRN / VAT number, as the user enters it
    prepared_by: str | None = None
    default_payment_terms: str | None = None
    default_delivery_terms: str | None = None
    default_warranty_terms: str | None = None
    default_validity_terms: str | None = None


class TaxSettings(Model):
    enabled: bool = False
    label: str | None = None
    rate: Decimal | None = None  # percent, e.g. Decimal("18")


class AppSettings(Model):
    company: CompanyProfile = Field(default_factory=CompanyProfile)
    default_currency: str | None = None  # ISO 4217 code chosen explicitly by the user
    tax: TaxSettings = Field(default_factory=TaxSettings)
    quotation_prefix: str = "QTN"
    use_external_ai: bool = False  # only effective when a provider is configured via environment
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Quotation
# ---------------------------------------------------------------------------

Origin = Literal[
    "extracted",  # copied from the tender document (has a source reference)
    "user",  # typed or confirmed by the user
    "calculated",  # computed by TenderFlow (totals, dates, generated numbers)
    "price_list",  # taken from the user's price list
    "company_profile",  # taken from Settings → Company profile
    "settings",  # taken from Settings defaults (currency, tax)
    "ai_suggestion",  # produced by the optional external AI provider
    "missing",  # no value available
]


class QField(Model):
    key: str
    label: str
    value: str | None = None
    origin: Origin = "missing"
    source: SourceRef | None = None
    confirmed: bool = False
    note: str | None = None


ItemAttribute = Literal["item_no", "description", "specification", "quantity", "unit", "unit_price", "amount"]


class QuotationLineItem(Model):
    id: str
    item_no: str
    description: str | None = None
    specification: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price: Decimal | None = None
    amount: Decimal | None = None  # calculated, or the user's override
    amount_override: Decimal | None = None
    origins: dict[str, Origin] = Field(default_factory=dict)
    source: SourceRef | None = None  # tender row this item came from
    price_note: str | None = None  # e.g. "Price list row 4 (exact match)"
    price_confirmed: bool = True
    reviewed: bool = False  # the tender row was confirmed in the extraction review
    tender_line_id: str | None = None
    tender_quantity: Decimal | None = None


class Quotation(Model):
    id: str
    version: int = 1
    fields: dict[str, QField] = Field(default_factory=dict)
    line_items: list[QuotationLineItem] = Field(default_factory=list)
    currency: str | None = None
    currency_origin: Origin = "missing"
    tax: TaxSettings = Field(default_factory=TaxSettings)
    tax_origin: Origin = "missing"
    subtotal: Decimal | None = None
    tax_amount: Decimal | None = None
    total: Decimal | None = None
    acknowledged_issue_ids: list[str] = Field(default_factory=list)
    source_versions: dict[str, str] = Field(default_factory=dict)  # inputs used, to detect stale drafts
    generated_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

Severity = Literal["error", "warning", "info"]
QuotationSection = Literal[
    "company", "details", "buyer", "items", "terms", "totals", "authorization", "mapping", "extraction"
]


class ValidationIssue(Model):
    id: str
    rule: str
    severity: Severity
    title: str
    message: str
    section: QuotationSection
    field_key: str | None = None
    line_item_id: str | None = None
    suggestion: str | None = None
    acknowledgeable: bool = False
    acknowledged: bool = False
    fix: str | None = None  # machine-readable quick fix id understood by the API, if any


class ValidationReport(Model):
    issues: list[ValidationIssue] = Field(default_factory=list)
    checks_run: int = 0
    checks_passed: int = 0
    errors: int = 0
    warnings: int = 0
    infos: int = 0
    unacknowledged_warnings: int = 0
    ready: bool = False
    generated_at: datetime = Field(default_factory=utcnow)


# ---------------------------------------------------------------------------
# Natural-language edits
# ---------------------------------------------------------------------------


class SetFieldOp(Model):
    op: Literal["set_field"] = "set_field"
    field_key: str
    value: str | None


class SetItemOp(Model):
    op: Literal["set_item"] = "set_item"
    line_item_id: str
    attribute: Literal["description", "specification", "quantity", "unit", "unit_price", "amount_override"]
    value: str | None


class AddItemOp(Model):
    op: Literal["add_item"] = "add_item"
    description: str
    specification: str | None = None
    quantity: str | None = None
    unit: str | None = None
    unit_price: str | None = None


class RemoveItemOp(Model):
    op: Literal["remove_item"] = "remove_item"
    line_item_id: str


class SetCurrencyOp(Model):
    op: Literal["set_currency"] = "set_currency"
    currency: str


class SetTaxOp(Model):
    op: Literal["set_tax"] = "set_tax"
    enabled: bool
    rate: str | None = None
    label: str | None = None


class HighlightMissingOp(Model):
    op: Literal["highlight_missing"] = "highlight_missing"


class ConfirmFieldsOp(Model):
    """Mark field values as checked by the user (manual action only, never proposed by AI)."""

    op: Literal["confirm_fields"] = "confirm_fields"
    field_keys: list[str]


class ConfirmPricesOp(Model):
    """Mark price-list matches as checked by the user (manual action only, never proposed by AI)."""

    op: Literal["confirm_prices"] = "confirm_prices"
    line_item_ids: list[str]


EditOperation = Annotated[
    SetFieldOp
    | SetItemOp
    | AddItemOp
    | RemoveItemOp
    | SetCurrencyOp
    | SetTaxOp
    | HighlightMissingOp
    | ConfirmFieldsOp
    | ConfirmPricesOp,
    Field(discriminator="op"),
]

AI_ALLOWED_OPS = {"set_field", "set_item", "add_item", "remove_item", "set_currency", "set_tax", "highlight_missing"}


class FieldChange(Model):
    target: str
    before: str | None = None
    after: str | None = None


class EditProposal(Model):
    id: str
    instruction: str
    interpreted_as: str
    operations: list[EditOperation] = Field(default_factory=list)
    changes: list[FieldChange] = Field(default_factory=list)
    material: bool = False
    material_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    engine: Literal["rules", "ai"] = "rules"
    status: Literal["pending", "applied", "cancelled"] = "pending"
    ui_only: bool = False  # e.g. highlight missing: no data change
    base_version: int = 1  # quotation version the preview was computed against
    created_at: datetime = Field(default_factory=utcnow)
    resolved_at: datetime | None = None


class EditRecord(Model):
    id: str
    kind: Literal["instruction", "manual", "undo", "regenerate", "quick_fix"]
    summary: str
    instruction: str | None = None
    changes: list[FieldChange] = Field(default_factory=list)
    engine: Literal["rules", "ai", "user", "system"] = "user"
    created_at: datetime = Field(default_factory=utcnow)


class QuotationSnapshot(Model):
    label: str
    quotation: Quotation
    created_at: datetime = Field(default_factory=utcnow)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

ExportFormat = Literal["docx", "xlsx", "pdf"]


class ExportCheck(Model):
    name: str
    passed: bool
    detail: str | None = None


class ExportArtifact(Model):
    id: str
    format: ExportFormat
    filename: str
    size_bytes: int
    sha256: str
    draft: bool
    errors_at_export: int = 0
    warnings_at_export: int = 0
    checks: list[ExportCheck] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


# ---------------------------------------------------------------------------
# Activity and project
# ---------------------------------------------------------------------------


class ActivityEvent(Model):
    id: str
    kind: str
    message: str
    created_at: datetime = Field(default_factory=utcnow)


ProjectStage = Literal["upload", "extraction", "mapping", "editor", "export"]


class Project(Model):
    id: str
    name: str
    is_sample: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    documents: list[DocumentRecord] = Field(default_factory=list)
    extraction: Extraction | None = None
    template: TemplateAnalysis | None = None
    price_list: PriceList | None = None
    mapping: Mapping | None = None
    company: CompanyProfile | None = None  # per-project profile (only the fictional sample sets it); None → Settings
    quotation: Quotation | None = None
    pending_edits: list[EditProposal] = Field(default_factory=list)
    edit_history: list[EditRecord] = Field(default_factory=list)
    undo_stack: list[QuotationSnapshot] = Field(default_factory=list)
    exports: list[ExportArtifact] = Field(default_factory=list)
    events: list[ActivityEvent] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API response views
# ---------------------------------------------------------------------------


class SourceValue(Model):
    key: str
    label: str
    group: str
    value: str | None
    origin: Origin


class MappingView(Model):
    mapping: Mapping
    sources: list[SourceValue]
    template_fields: list[TemplateField]
    items_columns: list[ItemColumn]
    unmapped_sources: list[str]  # source keys that have a value but no destination
    unfilled_targets: list[str]  # template field ids that receive nothing
    required_unfilled: list[str]


class ProjectSummary(Model):
    id: str
    name: str
    is_sample: bool
    created_at: datetime
    updated_at: datetime
    tender_name: str | None
    template_name: str | None
    stage: ProjectStage
    status: Literal["new", "in_review", "draft", "needs_attention", "ready", "exported"]
    errors: int | None = None
    warnings: int | None = None
    exports: int = 0


class ProjectView(Model):
    id: str
    name: str
    is_sample: bool
    created_at: datetime
    updated_at: datetime
    stage: ProjectStage
    documents: list[DocumentRecord]
    extraction: Extraction | None
    template: TemplateAnalysis | None
    price_list: PriceList | None
    mapping: MappingView | None
    quotation: Quotation | None
    validation: ValidationReport | None
    pending_edits: list[EditProposal]
    edit_history: list[EditRecord]
    undo_available: int
    exports: list[ExportArtifact]
    events: list[ActivityEvent]
    company_source: Literal["settings", "project_sample"]
    stale_reasons: list[str]
    export_formats: list[ExportFormat]
