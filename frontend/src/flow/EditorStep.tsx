import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowRight, Download, Minus, PanelRightOpen, Plus, Undo2 } from 'lucide-react'
import { api } from '../api/client'
import type { EditOperation, QuotationSection } from '../api/types'
import { useApp } from '../components/AppContext'
import { Badge, Button, Notice } from '../components/ui'
import { ORIGIN_LABEL, SECTION_LABEL } from '../lib/labels'
import { navigate, projectHref } from '../router'
import { InstructionPanel } from './editor/InstructionPanel'
import { QuotationDocument } from './editor/QuotationDocument'
import { TemplatePreview } from './editor/TemplatePreview'
import type { FlowProps } from './types'

const DOC_SECTIONS: QuotationSection[] = ['company', 'details', 'buyer', 'items', 'totals', 'terms', 'authorization']
const ZOOMS = [70, 85, 100, 115]

export function EditorStep({ project, run, busy, query }: FlowProps) {
  const { health, notify } = useApp()
  const q = project.quotation!
  const report = project.validation
  const [view, setView] = useState<'data' | 'template'>('data')
  const [zoom, setZoom] = useState(100)
  const [showOrigins, setShowOrigins] = useState(true)
  const [highlight, setHighlight] = useState(false)
  const [panelOpen, setPanelOpen] = useState(false)
  const [section, setSection] = useState<QuotationSection>('company')
  const canvasRef = useRef<HTMLDivElement>(null)
  const focus = query.get('focus')
  const focusItemId = focus?.startsWith('item:') ? focus.slice(5) : null

  const counts = useMemo(() => {
    const c: Partial<Record<QuotationSection, number>> = {}
    for (const i of report?.issues ?? []) {
      if (i.severity === 'info' || i.acknowledged) continue
      c[i.section] = (c[i.section] ?? 0) + 1
    }
    return c
  }, [report])

  const mappedKeys = useMemo(
    () => new Set(project.mapping?.mapping.fields.map((r) => r.source_key).filter(Boolean) as string[]),
    [project.mapping],
  )
  const missingCount =
    Object.values(q.fields).filter((f) => !f.value && mappedKeys.has(f.key) && !['subtotal', 'total', 'tax_amount'].includes(f.key)).length +
    q.line_items.filter((it) => it.unit_price === null || it.quantity === null || !it.description).length +
    (q.currency ? 0 : 1)

  // Navigate to a field/item/section requested by the validation workspace (?focus=...).
  useEffect(() => {
    if (!focus) return
    const [kind, value] = focus.split(/:(.*)/s)
    let el: HTMLElement | null = null
    if (kind === 'field') el = document.querySelector(`[data-field="${CSS.escape(value)}"]`)
    else if (kind === 'item') el = document.querySelector(`[data-item="${CSS.escape(value)}"]`)
    else if (kind === 'section') el = document.getElementById(`sec-${value}`)
    if (!el) return
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    const host = el.closest('section') ?? el
    host.classList.add('flash')
    const t = window.setTimeout(() => host.classList.remove('flash'), 1700)
    const button = el.querySelector('button')
    button?.focus({ preventScroll: true })
    return () => window.clearTimeout(t)
  }, [focus])

  function jump(s: QuotationSection) {
    setSection(s)
    setView('data')
    window.setTimeout(() => document.getElementById(`sec-${s}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 0)
  }

  const save = (ops: EditOperation[], summary: string) => run(() => api.updateQuotation(project.id, ops, summary))

  async function undo() {
    const last = project.edit_history.find((r) => r.kind !== 'undo')
    const result = await run(() => api.undo(project.id))
    if (result) notify(last ? `Undone: ${last.summary}` : 'Last change undone')
  }

  const status = report?.ready ? <Badge tone="success">Ready to export</Badge> : <Badge tone="lavender">Draft</Badge>
  const templateFormat = project.template?.format ?? 'docx'
  const numberText = q.fields.quotation_number?.value ?? 'Quotation'

  return (
    <div>
      <h1 className="sr-only">Edit quotation</h1>
      <div className="editor-toolbar">
        <div>
          {status}
          <span>
            {numberText}.{templateFormat}
          </span>
          {busy ? <span className="saving">Saving…</span> : <span className="saved">✓ All changes saved</span>}
        </div>
        <div>
          <Button icon={<Undo2 size={15} aria-hidden />} disabled={project.undo_available === 0 || busy} onClick={() => void undo()}>
            Undo
          </Button>
          <Button onClick={() => navigate(projectHref(project.id, 'export'))}>
            Validate{' '}
            {report && report.errors > 0 ? (
              <Badge tone="danger">{report.errors}</Badge>
            ) : report && report.unacknowledged_warnings > 0 ? (
              <Badge tone="warning">{report.unacknowledged_warnings}</Badge>
            ) : (
              <Badge tone="success">0</Badge>
            )}
          </Button>
          <Button kind="primary" icon={<Download size={15} aria-hidden />} onClick={() => navigate(projectHref(project.id, 'export'))}>
            Review & export
          </Button>
          <Button kind="quiet" className="panel-toggle" icon={<PanelRightOpen size={15} aria-hidden />} onClick={() => setPanelOpen(true)}>
            Instructions
          </Button>
        </div>
      </div>
      {project.stale_reasons.length > 0 && (
        <div style={{ padding: '10px 18px', background: 'var(--color-surface)' }}>
          <Notice
            tone="warning"
            title="This draft is out of date"
            actions={
              <a className="btn small" href={projectHref(project.id, 'mapping')}>
                Review & regenerate
              </a>
            }
          >
            {project.stale_reasons.join(' ')}
          </Notice>
        </div>
      )}
      <div className="editor-grid">
        <aside className="editor-left" aria-label="Quotation sections">
          <span className="panel-label">Document outline</span>
          {DOC_SECTIONS.map((s, i) => (
            <button key={s} className={`outline-btn ${section === s ? 'selected' : ''}`} onClick={() => jump(s)}>
              <span className="num">{i + 1}</span>
              {SECTION_LABEL[s]}
              {(counts[s] ?? 0) > 0 && <Badge tone="warning">{counts[s]}</Badge>}
            </button>
          ))}
          {report && (
            <div className="validation-mini">
              <div className="row">
                <span>Validation</span>
                <strong>
                  {report.errors} error{report.errors === 1 ? '' : 's'}
                </strong>
              </div>
              <progress value={report.checks_passed} max={report.checks_run} aria-label="Checks passed" />
              <small className="muted">
                {report.checks_passed} of {report.checks_run} checks passed
              </small>
              <div style={{ marginTop: 8 }}>
                <a className="btn quiet small" href={projectHref(project.id, 'export')}>
                  Review findings <ArrowRight size={13} aria-hidden />
                </a>
              </div>
            </div>
          )}
        </aside>

        <section className={`canvas ${highlight ? 'highlight-missing' : ''} ${showOrigins ? '' : 'hide-origins'}`} ref={canvasRef} aria-label="Quotation preview">
          <div className="canvas-tools">
            <div className="segmented" role="group" aria-label="Preview mode">
              <button aria-pressed={view === 'data'} onClick={() => setView('data')}>
                Editable draft
              </button>
              <button aria-pressed={view === 'template'} onClick={() => setView('template')}>
                In your template
              </button>
            </div>
            {view === 'data' && (
              <div>
                <label className="checkbox" style={{ fontSize: 11.5 }}>
                  <input type="checkbox" checked={showOrigins} onChange={(e) => setShowOrigins(e.target.checked)} />
                  Show value origins
                </label>
                <label className="checkbox" style={{ fontSize: 11.5, marginLeft: 8 }}>
                  <input type="checkbox" checked={highlight} onChange={(e) => setHighlight(e.target.checked)} />
                  Highlight missing
                </label>
              </div>
            )}
            {view === 'data' && (
              <div>
                <button className="icon-btn" aria-label="Zoom out" disabled={zoom === ZOOMS[0]} onClick={() => setZoom(ZOOMS[Math.max(0, ZOOMS.indexOf(zoom) - 1)])}>
                  <Minus size={14} />
                </button>
                <span aria-live="polite">{zoom}%</span>
                <button
                  className="icon-btn"
                  aria-label="Zoom in"
                  disabled={zoom === ZOOMS[ZOOMS.length - 1]}
                  onClick={() => setZoom(ZOOMS[Math.min(ZOOMS.length - 1, ZOOMS.indexOf(zoom) + 1)])}
                >
                  <Plus size={14} />
                </button>
              </div>
            )}
          </div>
          {view === 'data' ? (
            <>
              {showOrigins && (
                <div className="origin-legend" style={{ maxWidth: 760, margin: '0 auto 10px' }} aria-label="Legend">
                  {(['extracted', 'user', 'price_list', 'company_profile', 'calculated', 'ai_suggestion', 'missing'] as const).map((o) => (
                    <span key={o}>
                      <span className={`origin-dot ${o}`} aria-hidden /> {ORIGIN_LABEL[o]}
                    </span>
                  ))}
                </div>
              )}
              <div className="doc-scale" style={{ transform: zoom === 100 ? undefined : `scale(${zoom / 100})` }}>
                <QuotationDocument
                  q={q}
                  save={save}
                  busy={busy}
                  currencies={health?.currencies ?? (q.currency ? [q.currency] : [])}
                  focusItemId={focusItemId}
                />
              </div>
            </>
          ) : (
            <TemplatePreview projectId={project.id} format={templateFormat} version={`${q.version}-${q.updated_at}`} />
          )}
        </section>

        <InstructionPanel
          project={project}
          run={run}
          busy={busy}
          open={panelOpen}
          onClose={() => setPanelOpen(false)}
          onHighlight={() => {
            setHighlight(true)
            setView('data')
            setPanelOpen(false)
          }}
          missingCount={missingCount}
        />
      </div>
    </div>
  )
}
