import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, Check, CheckCheck, FileSearch, Info, Plus, ShieldAlert, Trash2, Undo2 } from 'lucide-react'
import { api } from '../api/client'
import type { ExtractedField, ExtractedLineItem, ExtractionSection, Requirement, SourceRef } from '../api/types'
import { errorMessage } from '../components/AppContext'
import { Badge, Button, Notice, StatusBadge } from '../components/ui'
import { REQUIREMENT_LABEL } from '../lib/labels'
import { formatQuantity, sourceLabel } from '../lib/format'
import { navigate, projectHref } from '../router'
import { EvidencePanel, type EvidenceState } from './EvidencePanel'
import type { FlowProps } from './types'

type SectionKey = ExtractionSection | 'items' | 'requirements' | 'suspicious'

const SECTIONS: { key: SectionKey; label: string }[] = [
  { key: 'overview', label: 'Tender overview' },
  { key: 'dates', label: 'Dates & deadlines' },
  { key: 'items', label: 'Line items' },
  { key: 'requirements', label: 'Requirements & eligibility' },
  { key: 'commercial', label: 'Commercial terms' },
  { key: 'delivery', label: 'Delivery' },
  { key: 'suspicious', label: 'Instruction-like text' },
]

function needsAttention(f: ExtractedField): boolean {
  return f.status === 'conflict' || f.status === 'needs_review' || (f.status === 'missing' && f.required)
}

export function ExtractionStep({ project, run, busy }: FlowProps) {
  const ext = project.extraction!
  const tenderDoc = project.documents.find((d) => d.role === 'tender')
  const [selected, setSelected] = useState<SectionKey>('overview')
  const [evidence, setEvidence] = useState<EvidenceState>({ loading: false, data: null, error: null, label: null })
  const [activeSource, setActiveSource] = useState<string | null>(null)
  const [evidenceOpen, setEvidenceOpen] = useState(false)

  const showSource = useCallback(
    async (src: SourceRef | null) => {
      if (!src) return
      setActiveSource(src.block_id)
      setEvidenceOpen(true)
      setEvidence((s) => ({ ...s, loading: true, error: null }))
      try {
        const data = await api.evidence(project.id, src.document_id, src.block_id, src.page)
        setEvidence({ loading: false, data, error: null, label: sourceLabel(src) })
      } catch (e) {
        setEvidence({ loading: false, data: null, error: errorMessage(e), label: null })
      }
    },
    [project.id],
  )

  // Show the first source straight away so the evidence panel is never an empty promise.
  useEffect(() => {
    const first = ext.fields.find((f) => f.sources.length > 0)?.sources[0]
    if (first && window.matchMedia?.('(min-width: 1201px)').matches) void showSource(first)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const bySection = useMemo(() => {
    const map: Record<string, ExtractedField[]> = {}
    for (const f of ext.fields) (map[f.section] ??= []).push(f)
    return map
  }, [ext.fields])

  const counts: Record<SectionKey, number> = {
    overview: (bySection.overview ?? []).filter(needsAttention).length,
    dates: (bySection.dates ?? []).filter(needsAttention).length,
    commercial: (bySection.commercial ?? []).filter(needsAttention).length,
    delivery: (bySection.delivery ?? []).filter(needsAttention).length,
    eligibility: 0,
    items: ext.line_items.filter((i) => i.status === 'needs_review' || i.status === 'conflict').length,
    requirements: ext.requirements.filter((r) => r.category === 'eligibility' && !r.acknowledged).length,
    suspicious: ext.suspicious_text.length,
  }
  const pendingConfirm =
    ext.fields.filter((f) => f.status === 'extracted' && f.value).length +
    ext.line_items.filter((i) => i.status === 'extracted').length
  const conflicts = ext.fields.filter((f) => f.status === 'conflict').length

  const updateField = (key: string, action: string, extra: Record<string, unknown> = {}) =>
    run(() => api.updateExtraction(project.id, { fields: [{ key, action, ...extra }] }))
  const updateItem = (body: Record<string, unknown>) => run(() => api.updateExtraction(project.id, { line_items: [body] }))

  function jump(key: SectionKey) {
    setSelected(key)
    document.getElementById(`sec-${key}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  async function continueToMapping() {
    const result = await run(() => api.updateExtraction(project.id, { mark_reviewed: true }))
    if (result) navigate(projectHref(project.id, 'mapping'))
  }

  const fieldProps = { activeSource, showSource, updateField, busy }
  return (
    <div className="workspace-grid">
      <aside className="workspace-panel" aria-label="Document outline">
        <span className="panel-label">Document outline</span>
        {SECTIONS.filter((s) => s.key !== 'suspicious' || ext.suspicious_text.length > 0).map((s, i) => (
          <button key={s.key} className={`outline-btn ${selected === s.key ? 'selected' : ''}`} onClick={() => jump(s.key)}>
            <span className="num">{i + 1}</span>
            {s.label}
            {counts[s.key] > 0 && <Badge tone={s.key === 'suspicious' ? 'lavender' : 'warning'}>{counts[s.key]}</Badge>}
          </button>
        ))}
      </aside>

      <section className="workspace-main" aria-labelledby="review-title">
        <div className="workspace-heading">
          <div>
            <span className="eyebrow">Step 2 of 5</span>
            <h1 id="review-title">Review extracted data</h1>
            <p>
              Found in <strong>{tenderDoc?.filename}</strong> by rule-based extraction. Confirm values against their source
              before mapping.
            </p>
          </div>
          <div className="estimate">
            <Info size={15} aria-hidden style={{ flex: 'none' }} />
            Status labels come from matching rules, not probabilities. “Found” values still need your confirmation.
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 16, flexWrap: 'wrap', alignItems: 'center' }}>
          <Button
            onClick={() => void run(() => api.confirmAllExtracted(project.id), 'Confirmed all found values')}
            disabled={pendingConfirm === 0}
            busy={busy}
            icon={<CheckCheck size={15} aria-hidden />}
          >
            Confirm all found values ({pendingConfirm})
          </Button>
          <Button kind="quiet" className="panel-toggle" onClick={() => setEvidenceOpen(true)} icon={<FileSearch size={15} aria-hidden />}>
            Show source
          </Button>
          {conflicts > 0 && <Badge tone="danger">{conflicts} conflict{conflicts > 1 ? 's' : ''} to resolve</Badge>}
        </div>
        {ext.warnings.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <Notice tone="warning" title="Notes from reading the document">
              <ul>
                {ext.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </Notice>
          </div>
        )}

        {(['overview', 'dates'] as const).map((key) => (
          <FieldSection key={key} id={key} title={SECTIONS.find((s) => s.key === key)!.label} fields={bySection[key] ?? []} {...fieldProps} />
        ))}

        <section className="review-section" id="sec-items" aria-labelledby="items-title">
          <header>
            <div>
              <h2 id="items-title">Line items</h2>
              <p>
                {ext.line_items.length} items from the schedule of requirements. Quantities must be numbers; anything else is
                flagged.
              </p>
            </div>
          </header>
          <LineItemsTable items={ext.line_items} busy={busy} activeSource={activeSource} showSource={showSource} updateItem={updateItem} />
        </section>

        <RequirementsSection
          requirements={ext.requirements}
          activeSource={activeSource}
          showSource={showSource}
          onToggle={(id, acknowledged) => run(() => api.updateExtraction(project.id, { requirements: [{ id, acknowledged }] }))}
        />

        {(['commercial', 'delivery'] as const).map((key) => (
          <FieldSection key={key} id={key} title={SECTIONS.find((s) => s.key === key)!.label} fields={bySection[key] ?? []} {...fieldProps} />
        ))}

        {ext.suspicious_text.length > 0 && (
          <section className="review-section" id="sec-suspicious" aria-labelledby="sus-title">
            <header>
              <div>
                <h2 id="sus-title">Instruction-like text</h2>
                <p>Text that looks like instructions to software. It was treated as plain document text and changed nothing.</p>
              </div>
            </header>
            <ul className="req-list">
              {ext.suspicious_text.map((s) => (
                <li key={s.id}>
                  <ShieldAlert size={16} aria-hidden style={{ color: 'var(--color-lavender-ink)', flex: 'none' }} />
                  <div>
                    “{s.text}”
                    <div className="tiny muted">Matched pattern: {s.pattern}</div>
                  </div>
                  {s.source && (
                    <button className={`source-link ${activeSource === s.source.block_id ? 'active' : ''}`} onClick={() => void showSource(s.source)}>
                      {sourceLabel(s.source)}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}

        <div className="flow-actions">
          <Button onClick={() => navigate(projectHref(project.id, 'upload'))} icon={<ArrowLeft size={15} aria-hidden />}>
            Back
          </Button>
          <div className="right">
            {conflicts > 0 && <span className="tiny muted">Unresolved conflicts will show as validation errors.</span>}
            <Button kind="primary" onClick={() => void continueToMapping()} busy={busy}>
              Mark as reviewed & continue <ArrowRight size={15} aria-hidden />
            </Button>
          </div>
        </div>
      </section>

      <EvidencePanel state={evidence} open={evidenceOpen} onClose={() => setEvidenceOpen(false)} />
    </div>
  )
}

function FieldSection({
  id,
  title,
  fields,
  ...rest
}: {
  id: string
  title: string
  fields: ExtractedField[]
  activeSource: string | null
  showSource: (s: SourceRef | null) => void
  updateField: (key: string, action: string, extra?: Record<string, unknown>) => Promise<unknown>
  busy: boolean
}) {
  if (fields.length === 0) return null
  const found = fields.filter((f) => f.value).length
  return (
    <section className="review-section" id={`sec-${id}`} aria-labelledby={`title-${id}`}>
      <header>
        <div>
          <h2 id={`title-${id}`}>{title}</h2>
          <p>
            {found} of {fields.length} found in the tender
          </p>
        </div>
      </header>
      <div className="field-grid">
        {fields.map((f) => (
          <FieldCard key={f.key} field={f} {...rest} />
        ))}
      </div>
    </section>
  )
}

function FieldCard({
  field,
  activeSource,
  showSource,
  updateField,
  busy,
}: {
  field: ExtractedField
  activeSource: string | null
  showSource: (s: SourceRef | null) => void
  updateField: (key: string, action: string, extra?: Record<string, unknown>) => Promise<unknown>
  busy: boolean
}) {
  const [value, setValue] = useState(field.value ?? '')
  useEffect(() => setValue(field.value ?? ''), [field.value])
  const inputId = `field-${field.key}`
  const cls = field.status === 'conflict' ? 'conflict' : needsAttention(field) ? 'attention' : ''

  function commit() {
    const next = value.trim()
    if (next === (field.value ?? '')) return
    void updateField(field.key, 'edit', { value: next || null })
  }

  return (
    <div className={`field-card ${cls}`}>
      <div className="field-card-head">
        <label htmlFor={inputId}>{field.label}</label>
        {field.required && (
          <span className="req" title="Required for the quotation">
            *
          </span>
        )}
        <StatusBadge status={field.status} />
      </div>
      {field.status === 'conflict' ? (
        <div className="candidate-list" role="group" aria-label={`Conflicting values for ${field.label}`}>
          {field.candidates.map((c, i) => (
            <div className="candidate" key={`${c.value}-${i}`}>
              <strong>{c.value}</strong>
              <button className={`source-link ${activeSource === c.source.block_id ? 'active' : ''}`} onClick={() => showSource(c.source)}>
                {sourceLabel(c.source)}
              </button>
              <Button small kind="primary" disabled={busy} onClick={() => void updateField(field.key, 'choose', { candidate_index: i })}>
                Use this
              </Button>
            </div>
          ))}
          <input
            id={inputId}
            className="input"
            placeholder="…or type the correct value"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()}
          />
        </div>
      ) : (
        <input
          id={inputId}
          className="input"
          value={value}
          placeholder={field.status === 'missing' ? 'Not found in the tender — enter it if you know it' : ''}
          onChange={(e) => setValue(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()}
        />
      )}
      {field.note && <span className="tiny muted">{field.note}</span>}
      <div className="field-card-foot">
        <span style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {field.sources.length === 0 && field.status !== 'conflict' && <span>No source location</span>}
          {field.status !== 'conflict' &&
            field.sources.map((s) => (
              <button key={s.block_id ?? s.snippet} className={`source-link ${activeSource === s.block_id ? 'active' : ''}`} onClick={() => showSource(s)}>
                <FileSearch size={12} aria-hidden /> {sourceLabel(s)}
              </button>
            ))}
        </span>
        <span>
          {(field.status === 'extracted' || field.status === 'needs_review') && field.value && (
            <Button small disabled={busy} onClick={() => void updateField(field.key, 'confirm')} icon={<Check size={13} aria-hidden />}>
              Confirm
            </Button>
          )}
          {(field.status === 'confirmed' || field.status === 'edited') && field.sources.length > 0 && (
            <Button small kind="quiet" disabled={busy} onClick={() => void updateField(field.key, 'unconfirm')} icon={<Undo2 size={13} aria-hidden />}>
              Unconfirm
            </Button>
          )}
        </span>
      </div>
    </div>
  )
}

function LineItemsTable({
  items,
  busy,
  activeSource,
  showSource,
  updateItem,
}: {
  items: ExtractedLineItem[]
  busy: boolean
  activeSource: string | null
  showSource: (s: SourceRef | null) => void
  updateItem: (body: Record<string, unknown>) => Promise<unknown>
}) {
  const [draft, setDraft] = useState({ description: '', quantity: '', unit: '' })
  return (
    <>
      <div className="table-wrap">
        <table className="data-table editable-table">
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">Description</th>
              <th scope="col">Specification</th>
              <th scope="col">Qty</th>
              <th scope="col">Unit</th>
              <th scope="col">Status</th>
              <th scope="col">Source</th>
              <th scope="col">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && (
              <tr>
                <td colSpan={8} className="muted">
                  No line items were recognised. Add them below.
                </td>
              </tr>
            )}
            {items.map((it, i) => (
              <tr key={it.id}>
                <td>{it.item_no ?? i + 1}</td>
                <td>
                  <CellInput label={`Description of item ${i + 1}`} value={it.description ?? ''} onCommit={(v) => updateItem({ id: it.id, action: 'edit', description: v })} />
                  {it.notes.length > 0 && <div className="tiny" style={{ color: 'var(--color-warning-ink)' }}>{it.notes.join(' ')}</div>}
                </td>
                <td>
                  <CellInput label={`Specification of item ${i + 1}`} value={it.specification ?? ''} onCommit={(v) => updateItem({ id: it.id, action: 'edit', specification: v })} />
                </td>
                <td style={{ width: 80 }}>
                  <CellInput
                    label={`Quantity of item ${i + 1}`}
                    value={formatQuantity(it.quantity) ?? it.quantity_text ?? ''}
                    onCommit={(v) => updateItem({ id: it.id, action: 'edit', quantity: v })}
                  />
                </td>
                <td style={{ width: 80 }}>
                  <CellInput label={`Unit of item ${i + 1}`} value={it.unit ?? ''} onCommit={(v) => updateItem({ id: it.id, action: 'edit', unit: v })} />
                </td>
                <td>
                  <StatusBadge status={it.status} />
                </td>
                <td>
                  {it.source ? (
                    <button className={`source-link ${activeSource === it.source.block_id ? 'active' : ''}`} onClick={() => showSource(it.source)}>
                      {sourceLabel(it.source)}
                    </button>
                  ) : (
                    <span className="tiny muted">Added by you</span>
                  )}
                </td>
                <td>
                  <div className="cell-actions">
                    {(it.status === 'extracted' || it.status === 'needs_review') && (
                      <button className="icon-btn" disabled={busy} aria-label={`Confirm item ${i + 1}`} onClick={() => void updateItem({ id: it.id, action: 'confirm' })}>
                        <Check size={16} />
                      </button>
                    )}
                    <button className="icon-btn" disabled={busy} aria-label={`Remove item ${i + 1}`} onClick={() => void updateItem({ id: it.id, action: 'delete' })}>
                      <Trash2 size={16} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <form
        className="library-tools"
        style={{ marginTop: 10, alignItems: 'flex-end' }}
        onSubmit={(e) => {
          e.preventDefault()
          if (!draft.description.trim()) return
          void updateItem({ action: 'add', ...draft }).then(() => setDraft({ description: '', quantity: '', unit: '' }))
        }}
      >
        <label className="field" style={{ flex: 2, minWidth: 200 }}>
          <span>Add a line item</span>
          <input className="input" placeholder="Description" value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} />
        </label>
        <label className="field" style={{ width: 110 }}>
          <span>Quantity</span>
          <input className="input" inputMode="decimal" value={draft.quantity} onChange={(e) => setDraft({ ...draft, quantity: e.target.value })} />
        </label>
        <label className="field" style={{ width: 110 }}>
          <span>Unit</span>
          <input className="input" value={draft.unit} onChange={(e) => setDraft({ ...draft, unit: e.target.value })} />
        </label>
        <Button type="submit" disabled={busy || !draft.description.trim()} icon={<Plus size={15} aria-hidden />}>
          Add
        </Button>
      </form>
    </>
  )
}

function CellInput({ value, onCommit, label }: { value: string; onCommit: (v: string) => Promise<unknown>; label: string }) {
  const [v, setV] = useState(value)
  useEffect(() => setV(value), [value])
  return (
    <input
      aria-label={label}
      value={v}
      onChange={(e) => setV(e.target.value)}
      onBlur={() => {
        if (v.trim() !== value.trim()) void onCommit(v.trim())
      }}
      onKeyDown={(e) => {
        if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
        if (e.key === 'Escape') setV(value)
      }}
    />
  )
}

function RequirementsSection({
  requirements,
  activeSource,
  showSource,
  onToggle,
}: {
  requirements: Requirement[]
  activeSource: string | null
  showSource: (s: SourceRef | null) => void
  onToggle: (id: string, acknowledged: boolean) => Promise<unknown>
}) {
  const groups = useMemo(() => {
    const order = ['eligibility', 'submission', 'technical', 'commercial', 'delivery', 'other']
    const map = new Map<string, Requirement[]>()
    for (const r of requirements) map.set(r.category, [...(map.get(r.category) ?? []), r])
    return order.filter((k) => map.has(k)).map((k) => [k, map.get(k)!] as const)
  }, [requirements])
  return (
    <section className="review-section" id="sec-requirements" aria-labelledby="req-title">
      <header>
        <div>
          <h2 id="req-title">Requirements & eligibility</h2>
          <p>
            Sentences with “shall / must / required”. TenderFlow lists them; it does not check whether your company meets them.
          </p>
        </div>
      </header>
      {requirements.length === 0 && <p className="muted small">No requirement sentences were found.</p>}
      {groups.map(([cat, reqs]) => (
        <div key={cat} style={{ marginBottom: 14 }}>
          <h3 className="small" style={{ margin: '0 0 6px' }}>
            {REQUIREMENT_LABEL[cat]} <span className="count">{reqs.length}</span>
          </h3>
          <ul className="req-list">
            {reqs.map((r) => (
              <li key={r.id}>
                <label className="checkbox" style={{ flex: 1 }}>
                  <input type="checkbox" checked={r.acknowledged} onChange={(e) => void onToggle(r.id, e.target.checked)} />
                  <span>
                    {r.text}
                    {cat === 'eligibility' && <span className="tiny muted"> — check this yourself</span>}
                  </span>
                </label>
                {r.source && (
                  <button className={`source-link ${activeSource === r.source.block_id ? 'active' : ''}`} onClick={() => showSource(r.source)}>
                    {sourceLabel(r.source)}
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  )
}
