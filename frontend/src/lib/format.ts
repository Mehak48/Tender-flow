/** Display formatting. Money arrives as decimal strings and is never converted through floats for maths. */

export function formatMoney(value: string | null | undefined): string | null {
  if (value === null || value === undefined || value === '') return null
  const negative = value.trim().startsWith('-')
  const [intRaw, fracRaw = ''] = value.replace('-', '').trim().split('.')
  if (!/^\d+$/.test(intRaw) || (fracRaw && !/^\d+$/.test(fracRaw))) return value
  const frac = (fracRaw + '00').slice(0, 2)
  const grouped = intRaw.replace(/^0+(?=\d)/, '').replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return `${negative ? '-' : ''}${grouped}.${frac}`
}

export function formatQuantity(value: string | null | undefined): string | null {
  if (value === null || value === undefined || value === '') return null
  if (!value.includes('.')) return value
  const trimmed = value.replace(/0+$/, '').replace(/\.$/, '')
  return trimmed || '0'
}

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(bytes < 10 * 1024 ? 1 : 0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export function formatDate(iso: string | Date): string {
  const d = typeof iso === 'string' ? new Date(iso) : iso
  if (Number.isNaN(d.getTime())) return String(iso)
  return d.toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
}

export function relativeTime(iso: string, now: Date = new Date()): string {
  const d = new Date(iso)
  const seconds = Math.round((now.getTime() - d.getTime()) / 1000)
  if (Number.isNaN(seconds)) return iso
  if (seconds < 45) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  const days = Math.round(hours / 24)
  if (days === 1) return 'yesterday'
  if (days < 7) return `${days} days ago`
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`
}

export function sourceLabel(src: {
  page: number | null
  line: number | null
  paragraph: number | null
  table: number | null
  row: number | null
  sheet: string | null
  cell: string | null
} | null): string {
  if (!src) return 'Source unavailable'
  const parts: string[] = []
  if (src.sheet) parts.push(`Sheet ${src.sheet}`)
  if (src.cell) parts.push(`cell ${src.cell}`)
  if (src.page !== null) parts.push(`Page ${src.page}`)
  if (src.table !== null) parts.push(`table ${src.table}`)
  if (src.row !== null && !src.cell) parts.push(`row ${src.row}`)
  if (src.line !== null) parts.push(`line ${src.line}`)
  if (src.paragraph !== null) parts.push(`paragraph ${src.paragraph}`)
  return parts.length ? parts.join(', ') : 'Location unavailable'
}
