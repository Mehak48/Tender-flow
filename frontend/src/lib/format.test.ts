import { describe, expect, it } from 'vitest'
import { formatBytes, formatMoney, formatQuantity, plural, relativeTime, sourceLabel } from './format'

describe('formatMoney', () => {
  it('groups thousands and always shows two decimals without float maths', () => {
    expect(formatMoney('1564000')).toBe('1,564,000.00')
    expect(formatMoney('185000.5')).toBe('185,000.50')
    expect(formatMoney('0.30')).toBe('0.30')
    expect(formatMoney('-1250.75')).toBe('-1,250.75')
    expect(formatMoney('9007199254740993.10')).toBe('9,007,199,254,740,993.10')
  })
  it('returns null for missing values and leaves non-numbers untouched', () => {
    expect(formatMoney(null)).toBeNull()
    expect(formatMoney('')).toBeNull()
    expect(formatMoney('n/a')).toBe('n/a')
  })
})

describe('formatQuantity', () => {
  it('trims trailing zeros only after a decimal point', () => {
    expect(formatQuantity('4')).toBe('4')
    expect(formatQuantity('10')).toBe('10')
    expect(formatQuantity('2.50')).toBe('2.5')
    expect(formatQuantity('3.000')).toBe('3')
    expect(formatQuantity(null)).toBeNull()
  })
})

describe('formatBytes', () => {
  it('uses readable units', () => {
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(5 * 1024)).toBe('5.0 KB')
    expect(formatBytes(38 * 1024)).toBe('38 KB')
    expect(formatBytes(3.2 * 1024 * 1024)).toBe('3.2 MB')
  })
})

describe('relativeTime', () => {
  const now = new Date('2026-10-27T12:00:00Z')
  it('describes recent times', () => {
    expect(relativeTime('2026-10-27T11:59:40Z', now)).toBe('just now')
    expect(relativeTime('2026-10-27T11:40:00Z', now)).toBe('20 min ago')
    expect(relativeTime('2026-10-27T09:00:00Z', now)).toBe('3 h ago')
    expect(relativeTime('2026-10-26T10:00:00Z', now)).toBe('yesterday')
  })
})

describe('sourceLabel', () => {
  const base = { page: null, line: null, paragraph: null, table: null, row: null, sheet: null, cell: null }
  it('builds a human-readable location', () => {
    expect(sourceLabel({ ...base, page: 3, line: 7 })).toBe('Page 3, line 7')
    expect(sourceLabel({ ...base, page: 2, table: 1, row: 4 })).toBe('Page 2, table 1, row 4')
    expect(sourceLabel({ ...base, sheet: 'Prices', cell: 'B4', row: 4 })).toBe('Sheet Prices, cell B4')
    expect(sourceLabel({ ...base, paragraph: 12 })).toBe('paragraph 12')
  })
  it('says so when the location is unknown', () => {
    expect(sourceLabel(base)).toBe('Location unavailable')
    expect(sourceLabel(null)).toBe('Source unavailable')
  })
})

describe('plural', () => {
  it('handles one and many', () => {
    expect(plural(1, 'item')).toBe('1 item')
    expect(plural(3, 'item')).toBe('3 items')
  })
})
