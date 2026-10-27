/**
 * TypeScript mirror of backend/app/models.py (the source of truth).
 * Decimal values arrive as strings and datetimes as ISO strings.
 */

export type DecimalString = string
export type ISODate = string

export interface SourceRef {
  document_id: string
  document_name: string
  block_id: string | null
  page: number | null
  line: number | null
  paragraph: number | null
  table: number | null
  row: number | null
  column: number | null
  sheet: string | null
  cell: string | null
  snippet: string
  precision: 'exact' | 'block' | 'unavailable'
}

export type DocumentRole = 'tender' | 'template' | 'price_list'
export type DocumentFormat = 'pdf' | 'docx' | 'xlsx' | 'csv'

export interface DocumentRecord {
  id: string
  role: DocumentRole
  filename: string
  format: DocumentFormat
  size_bytes: number
  sha256: string
  uploaded_at: ISODate
  parse_status: 'parsed' | 'failed'
  parse_error: string | null
  page_count: number | null
  block_count: number
  table_count: number
  warnings: string[]
}

export interface EvidenceBlock {
  id: string
  kind: string
  text: string
  page: number | null
  line: number | null
  paragraph: number | null
  table: number | null
  row: number | null
  sheet: string | null
  cells: string[] | null
}

export interface EvidenceResponse {
  document_id: string
  document_name: string
  page: number | null
  page_count: number | null
  blocks: EvidenceBlock[]
  focus_block_id: string | null
  note: string | null
}

export type FieldStatus = 'extracted' | 'needs_review' | 'conflict' | 'missing' | 'confirmed' | 'edited'
export type ExtractionSection = 'overview' | 'dates' | 'commercial' | 'delivery' | 'eligibility'

export interface Candidate {
  value: string
  source: SourceRef
}

export interface ExtractedField {
  key: string
  label: string
  section: ExtractionSection
  value: string | null
  normalized: string | null
  status: FieldStatus
  sources: SourceRef[]
  candidates: Candidate[]
  note: string | null
  required: boolean
  rule: string | null
}

export interface ExtractedLineItem {
  id: string
  item_no: string | null
  description: string | null
  quantity: DecimalString | null
  quantity_text: string | null
  unit: string | null
  specification: string | null
  status: FieldStatus
  source: SourceRef | null
  notes: string[]
}

export type RequirementCategory = 'eligibility' | 'technical' | 'submission' | 'commercial' | 'delivery' | 'other'

export interface Requirement {
  id: string
  category: RequirementCategory
  text: string
  source: SourceRef | null
  acknowledged: boolean
}

export interface SuspiciousText {
  id: string
  text: string
  pattern: string
  source: SourceRef | null
}

export interface Extraction {
  document_id: string
  engine: 'rules'
  fields: ExtractedField[]
  line_items: ExtractedLineItem[]
  requirements: Requirement[]
  suspicious_text: SuspiciousText[]
  warnings: string[]
  reviewed: boolean
  reviewed_at: ISODate | null
  created_at: ISODate
  updated_at: ISODate
}

export interface PriceListRow {
  row: number
  name: string
  unit_price: DecimalString
  unit: string | null
  currency: string | null
}

export interface PriceList {
  document_id: string
  document_name: string
  rows: PriceListRow[]
  warnings: string[]
}

export interface TemplateField {
  id: string
  key: string | null
  label: string
  kind: 'placeholder' | 'label_blank'
  required: boolean
  recognized: boolean
  locations: string[]
}

export interface ItemColumn {
  index: number
  header: string
  attribute: string | null
}

export interface ItemsTableInfo {
  location: string
  table_index: number | null
  sheet: string | null
  header_row: number
  template_row: number
  columns: ItemColumn[]
  mode: 'placeholder_row' | 'header_detected'
}

export interface TemplateAnalysis {
  document_id: string
  document_name: string
  format: 'docx' | 'xlsx'
  fields: TemplateField[]
  items_table: ItemsTableInfo | null
  warnings: string[]
}

export interface FieldMappingRow {
  target_field_id: string
  source_key: string | null
  status: 'auto' | 'manual' | 'unmapped'
}

export interface ColumnMappingRow {
  column_index: number
  attribute: string | null
  status: 'auto' | 'manual' | 'unmapped'
}

export interface Mapping {
  fields: FieldMappingRow[]
  columns: ColumnMappingRow[]
  confirmed: boolean
  confirmed_at: ISODate | null
}

export type Origin =
  | 'extracted'
  | 'user'
  | 'calculated'
  | 'price_list'
  | 'company_profile'
  | 'settings'
  | 'ai_suggestion'
  | 'missing'

export interface SourceValue {
  key: string
  label: string
  group: string
  value: string | null
  origin: Origin
}

export interface MappingView {
  mapping: Mapping
  sources: SourceValue[]
  template_fields: TemplateField[]
  items_columns: ItemColumn[]
  unmapped_sources: string[]
  unfilled_targets: string[]
  required_unfilled: string[]
}

export interface CompanyProfile {
  name: string | null
  address: string | null
  phone: string | null
  email: string | null
  registration: string | null
  prepared_by: string | null
  default_payment_terms: string | null
  default_delivery_terms: string | null
  default_warranty_terms: string | null
  default_validity_terms: string | null
}

export interface TaxSettings {
  enabled: boolean
  label: string | null
  rate: DecimalString | null
}

export interface AppSettings {
  company: CompanyProfile
  default_currency: string | null
  tax: TaxSettings
  quotation_prefix: string
  use_external_ai: boolean
  updated_at: ISODate | null
}

export interface QField {
  key: string
  label: string
  value: string | null
  origin: Origin
  source: SourceRef | null
  confirmed: boolean
  note: string | null
}

export interface QuotationLineItem {
  id: string
  item_no: string
  description: string | null
  specification: string | null
  quantity: DecimalString | null
  unit: string | null
  unit_price: DecimalString | null
  amount: DecimalString | null
  amount_override: DecimalString | null
  origins: Record<string, Origin>
  source: SourceRef | null
  price_note: string | null
  price_confirmed: boolean
  reviewed: boolean
  tender_line_id: string | null
  tender_quantity: DecimalString | null
}

export interface Quotation {
  id: string
  version: number
  fields: Record<string, QField>
  line_items: QuotationLineItem[]
  currency: string | null
  currency_origin: Origin
  tax: TaxSettings
  tax_origin: Origin
  subtotal: DecimalString | null
  tax_amount: DecimalString | null
  total: DecimalString | null
  acknowledged_issue_ids: string[]
  source_versions: Record<string, string>
  generated_at: ISODate
  updated_at: ISODate
}

export type Severity = 'error' | 'warning' | 'info'
export type QuotationSection =
  | 'company'
  | 'details'
  | 'buyer'
  | 'items'
  | 'terms'
  | 'totals'
  | 'authorization'
  | 'mapping'
  | 'extraction'

export interface ValidationIssue {
  id: string
  rule: string
  severity: Severity
  title: string
  message: string
  section: QuotationSection
  field_key: string | null
  line_item_id: string | null
  suggestion: string | null
  acknowledgeable: boolean
  acknowledged: boolean
  fix: string | null
}

export interface ValidationReport {
  issues: ValidationIssue[]
  checks_run: number
  checks_passed: number
  errors: number
  warnings: number
  infos: number
  unacknowledged_warnings: number
  ready: boolean
  generated_at: ISODate
}

export type EditOperation =
  | { op: 'set_field'; field_key: string; value: string | null }
  | {
      op: 'set_item'
      line_item_id: string
      attribute: 'description' | 'specification' | 'quantity' | 'unit' | 'unit_price' | 'amount_override'
      value: string | null
    }
  | {
      op: 'add_item'
      description: string
      specification?: string | null
      quantity?: string | null
      unit?: string | null
      unit_price?: string | null
    }
  | { op: 'remove_item'; line_item_id: string }
  | { op: 'set_currency'; currency: string }
  | { op: 'set_tax'; enabled: boolean; rate?: string | null; label?: string | null }
  | { op: 'highlight_missing' }
  | { op: 'confirm_fields'; field_keys: string[] }
  | { op: 'confirm_prices'; line_item_ids: string[] }

export interface FieldChange {
  target: string
  before: string | null
  after: string | null
}

export interface EditProposal {
  id: string
  instruction: string
  interpreted_as: string
  operations: EditOperation[]
  changes: FieldChange[]
  material: boolean
  material_reasons: string[]
  warnings: string[]
  engine: 'rules' | 'ai'
  status: 'pending' | 'applied' | 'cancelled'
  ui_only: boolean
  base_version: number
  created_at: ISODate
  resolved_at: ISODate | null
}

export interface EditRecord {
  id: string
  kind: 'instruction' | 'manual' | 'undo' | 'regenerate' | 'quick_fix'
  summary: string
  instruction: string | null
  changes: FieldChange[]
  engine: 'rules' | 'ai' | 'user' | 'system'
  created_at: ISODate
}

export type ExportFormat = 'docx' | 'xlsx' | 'pdf'

export interface ExportCheck {
  name: string
  passed: boolean
  detail: string | null
}

export interface ExportArtifact {
  id: string
  format: ExportFormat
  filename: string
  size_bytes: number
  sha256: string
  draft: boolean
  errors_at_export: number
  warnings_at_export: number
  checks: ExportCheck[]
  warnings: string[]
  created_at: ISODate
}

export interface ActivityEvent {
  id: string
  kind: string
  message: string
  created_at: ISODate
}

export type ProjectStage = 'upload' | 'extraction' | 'mapping' | 'editor' | 'export'

export interface ProjectSummary {
  id: string
  name: string
  is_sample: boolean
  created_at: ISODate
  updated_at: ISODate
  tender_name: string | null
  template_name: string | null
  stage: ProjectStage
  status: 'new' | 'in_review' | 'draft' | 'needs_attention' | 'ready' | 'exported'
  errors: number | null
  warnings: number | null
  exports: number
}

export interface ProjectView {
  id: string
  name: string
  is_sample: boolean
  created_at: ISODate
  updated_at: ISODate
  stage: ProjectStage
  documents: DocumentRecord[]
  extraction: Extraction | null
  template: TemplateAnalysis | null
  price_list: PriceList | null
  mapping: MappingView | null
  quotation: Quotation | null
  validation: ValidationReport | null
  pending_edits: EditProposal[]
  edit_history: EditRecord[]
  undo_available: number
  exports: ExportArtifact[]
  events: ActivityEvent[]
  company_source: 'settings' | 'project_sample'
  stale_reasons: string[]
  export_formats: ExportFormat[]
}

export interface EditResponse {
  understood: boolean
  message: string | null
  proposal: EditProposal | null
  examples: string[]
  engine: 'rules' | 'ai' | null
}

export interface EditResult {
  response: EditResponse
  project: ProjectView
}

export interface ExportResponse {
  artifact: ExportArtifact
  project: ProjectView
}

export interface AIStatus {
  mode: 'local' | 'external'
  configured: boolean
  enabled_in_settings: boolean
  provider: string | null
  model: string | null
  base_url_host: string | null
  api_key_present: boolean
}

export interface PdfStatus {
  available: boolean
  reason: string
}

export interface Health {
  status: 'ok'
  app_name: string
  tagline: string
  version: string
  ai: AIStatus
  pdf_export: PdfStatus
  limits: { max_upload_mb: number; formats: Record<DocumentRole, DocumentFormat[]> }
  currencies: string[]
  ocr: boolean
  storage: string
}

export interface SettingsView {
  settings: AppSettings
  supported_currencies: string[]
  ai: AIStatus
  pdf_export: PdfStatus
}

export interface TemplateEntry {
  project_id: string
  project_name: string
  document: DocumentRecord
  analysis: TemplateAnalysis | null
}

export interface LibraryDocument {
  project_id: string
  project_name: string
  kind: DocumentRole | 'export'
  id: string
  filename: string
  format: string
  size_bytes: number
  created_at: ISODate
  status: string
  download_url: string
}

export interface ActivityEntry {
  project_id: string
  project_name: string
  event: ActivityEvent
}

export interface XlsxGrid {
  sheet: string
  rows: string[][]
}
