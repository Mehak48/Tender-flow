import type { FieldStatus, Origin, ProjectSummary, QuotationSection, Severity } from '../api/types'

export type Tone = 'neutral' | 'lavender' | 'success' | 'warning' | 'danger' | 'apricot'

export const STATUS_META: Record<FieldStatus, { label: string; tone: Tone }> = {
  extracted: { label: 'Found · not confirmed', tone: 'lavender' },
  needs_review: { label: 'Needs review', tone: 'warning' },
  conflict: { label: 'Conflict', tone: 'danger' },
  missing: { label: 'Not found', tone: 'neutral' },
  confirmed: { label: 'Confirmed', tone: 'success' },
  edited: { label: 'Edited by you', tone: 'success' },
}

export const ORIGIN_LABEL: Record<Origin, string> = {
  extracted: 'From tender',
  user: 'Entered by you',
  calculated: 'Calculated',
  price_list: 'Your price list',
  company_profile: 'Company profile',
  settings: 'Your settings',
  ai_suggestion: 'AI suggestion',
  missing: 'Needs input',
}

export const ORIGIN_HELP: Record<Origin, string> = {
  extracted: 'Copied from the tender document — click the source to see where.',
  user: 'Typed or changed by you.',
  calculated: 'Computed by TenderFlow (totals, dates, generated numbers).',
  price_list: 'Taken from the price list you uploaded.',
  company_profile: 'From Settings → Company profile.',
  settings: 'From your Settings defaults.',
  ai_suggestion: 'Suggested by the external AI provider and applied by you.',
  missing: 'No value yet. TenderFlow never invents one.',
}

export const SEVERITY_META: Record<Severity, { label: string; tone: Tone }> = {
  error: { label: 'Error', tone: 'danger' },
  warning: { label: 'Warning', tone: 'warning' },
  info: { label: 'Note', tone: 'lavender' },
}

export const SECTION_LABEL: Record<QuotationSection, string> = {
  company: 'Company header',
  details: 'Quotation details',
  buyer: 'Buyer information',
  items: 'Items & pricing',
  terms: 'Commercial terms',
  totals: 'Totals',
  authorization: 'Authorization',
  mapping: 'Field mapping',
  extraction: 'Extracted tender data',
}

export const PROJECT_STATUS: Record<ProjectSummary['status'], { label: string; tone: Tone }> = {
  new: { label: 'New', tone: 'neutral' },
  in_review: { label: 'In review', tone: 'lavender' },
  draft: { label: 'Draft', tone: 'neutral' },
  needs_attention: { label: 'Needs attention', tone: 'warning' },
  ready: { label: 'Ready to export', tone: 'success' },
  exported: { label: 'Exported', tone: 'success' },
}

export const ITEM_ATTRIBUTE_LABEL: Record<string, string> = {
  item_no: 'Item no.',
  description: 'Description',
  specification: 'Specification',
  quantity: 'Quantity',
  unit: 'Unit',
  unit_price: 'Unit price',
  amount: 'Amount',
}

export const REQUIREMENT_LABEL: Record<string, string> = {
  eligibility: 'Eligibility & compliance',
  submission: 'Submission',
  commercial: 'Commercial',
  delivery: 'Delivery',
  technical: 'Technical',
  other: 'Other',
}
