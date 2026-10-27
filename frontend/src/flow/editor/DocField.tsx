import { useEffect, useRef, useState } from 'react'
import { Pencil } from 'lucide-react'
import type { Origin, QField } from '../../api/types'
import { ORIGIN_HELP, ORIGIN_LABEL } from '../../lib/labels'

export function OriginDot({ origin, note }: { origin: Origin; note?: string | null }) {
  const label = `${ORIGIN_LABEL[origin]}${note ? ` — ${note}` : ''}`
  return <span className={`origin-dot ${origin}`} title={`${label}. ${ORIGIN_HELP[origin]}`} aria-label={ORIGIN_LABEL[origin]} role="img" />
}

/**
 * A value inside the document preview that can be edited in place. Missing values are never left blank:
 * they show a visible "Add …" marker, mirroring the [MISSING: …] marker used in draft exports.
 */
export function DocField({
  field,
  fieldKey,
  label,
  multiline,
  readOnly,
  onSave,
  display,
  block,
}: {
  field: QField | undefined
  fieldKey: string
  label: string
  multiline?: boolean
  readOnly?: boolean
  onSave: (value: string | null) => Promise<unknown>
  display?: (value: string) => string
  block?: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(field?.value ?? '')
  const ref = useRef<HTMLInputElement & HTMLTextAreaElement>(null)
  useEffect(() => {
    if (!editing) setDraft(field?.value ?? '')
  }, [field?.value, editing])
  useEffect(() => {
    if (editing) ref.current?.focus()
  }, [editing])

  const value = field?.value ?? null
  const origin: Origin = field?.origin ?? 'missing'

  async function commit() {
    setEditing(false)
    const next = draft.trim()
    if (next === (value ?? '')) return
    await onSave(next || null)
  }

  if (editing && !readOnly) {
    const common = {
      ref,
      className: 'df-input',
      value: draft,
      'aria-label': label,
      onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setDraft(e.target.value),
      onBlur: () => void commit(),
      onKeyDown: (e: React.KeyboardEvent) => {
        if (e.key === 'Escape') {
          setDraft(value ?? '')
          setEditing(false)
        } else if (e.key === 'Enter' && (!multiline || e.ctrlKey || e.metaKey)) {
          e.preventDefault()
          ;(e.target as HTMLElement).blur()
        }
      },
    }
    return (
      <span className={`df ${block ? 'block' : ''}`} data-field={fieldKey}>
        {multiline ? <textarea {...common} rows={3} /> : <input {...common} />}
      </span>
    )
  }

  return (
    <span className={`df ${block ? 'block' : ''}`} data-field={fieldKey}>
      <OriginDot origin={origin} note={field?.note} />
      {value ? (
        readOnly ? (
          <span title={field?.note ?? undefined}>{display ? display(value) : value}</span>
        ) : (
          <button
            type="button"
            className="df-value"
            onClick={() => setEditing(true)}
            aria-label={`Edit ${label}: ${display ? display(value) : value}`}
            title={`Edit ${label}${field?.note ? ` — ${field.note}` : ''}`}
          >
            {display ? display(value) : value}
          </button>
        )
      ) : readOnly ? (
        <span className="df-missing">{field?.note ? 'Pending' : `No ${label.toLowerCase()}`}</span>
      ) : (
        <button type="button" className="df-missing" onClick={() => setEditing(true)} aria-label={`Add ${label}`}>
          <Pencil size={11} aria-hidden /> Add {label.toLowerCase()}
        </button>
      )}
    </span>
  )
}
