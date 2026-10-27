import { ACCEPT } from '../config'
import type { DocumentRole } from '../api/types'

export const ROLE_LABEL: Record<DocumentRole, string> = {
  tender: 'Tender document',
  template: 'Quotation template',
  price_list: 'Price list',
}

const LEGACY: Record<string, string> = {
  doc: 'Legacy .doc files are not supported. Save it as .docx first.',
  xls: 'Legacy .xls files are not supported. Save it as .xlsx first.',
  png: 'Images are not supported (no OCR in this prototype).',
  jpg: 'Images are not supported (no OCR in this prototype).',
  jpeg: 'Images are not supported (no OCR in this prototype).',
}

export function extensionOf(name: string): string {
  const i = name.lastIndexOf('.')
  return i >= 0 ? name.slice(i + 1).toLowerCase() : ''
}

export function acceptAttribute(role: DocumentRole): string {
  return ACCEPT[role].map((ext) => `.${ext}`).join(',')
}

export function formatsText(role: DocumentRole): string {
  return ACCEPT[role].map((ext) => ext.toUpperCase()).join(' or ')
}

/**
 * Quick client-side check so people get feedback before uploading. Returns an error message or null.
 * The backend validates again (extension, file signature, size) — this is only a convenience.
 */
export function validateFile(role: DocumentRole, file: { name: string; size: number }, maxMb: number): string | null {
  const ext = extensionOf(file.name)
  if (!ACCEPT[role].includes(ext)) {
    return LEGACY[ext] ?? `${ROLE_LABEL[role]} must be a ${formatsText(role)} file.`
  }
  if (file.size === 0) return 'The file is empty.'
  if (file.size > maxMb * 1024 * 1024) return `The file is larger than the ${maxMb} MB limit.`
  return null
}
