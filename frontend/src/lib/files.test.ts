import { describe, expect, it } from 'vitest'
import { acceptAttribute, extensionOf, validateFile } from './files'

describe('validateFile', () => {
  it('accepts the supported formats for each role', () => {
    expect(validateFile('tender', { name: 'Tender.PDF', size: 1000 }, 25)).toBeNull()
    expect(validateFile('tender', { name: 'tender.docx', size: 1000 }, 25)).toBeNull()
    expect(validateFile('template', { name: 'template.xlsx', size: 1000 }, 25)).toBeNull()
    expect(validateFile('price_list', { name: 'prices.csv', size: 1000 }, 25)).toBeNull()
  })
  it('rejects unsupported formats with a role-specific message', () => {
    expect(validateFile('template', { name: 'template.pdf', size: 1000 }, 25)).toBe('Quotation template must be a DOCX or XLSX file.')
    expect(validateFile('tender', { name: 'tender', size: 1000 }, 25)).toMatch(/must be a PDF or DOCX file/)
  })
  it('explains legacy formats and images', () => {
    expect(validateFile('tender', { name: 'old.doc', size: 10 }, 25)).toMatch(/Save it as \.docx/)
    expect(validateFile('tender', { name: 'scan.jpg', size: 10 }, 25)).toMatch(/no OCR/)
  })
  it('rejects empty and oversized files', () => {
    expect(validateFile('tender', { name: 't.pdf', size: 0 }, 25)).toBe('The file is empty.')
    expect(validateFile('tender', { name: 't.pdf', size: 26 * 1024 * 1024 }, 25)).toBe('The file is larger than the 25 MB limit.')
  })
})

describe('helpers', () => {
  it('reads extensions and builds accept attributes', () => {
    expect(extensionOf('a.b.PDF')).toBe('pdf')
    expect(extensionOf('noext')).toBe('')
    expect(acceptAttribute('price_list')).toBe('.xlsx,.csv')
  })
})
