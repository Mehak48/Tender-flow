import { useEffect, useRef } from 'react'
import { FileText, X } from 'lucide-react'
import type { EvidenceResponse } from '../api/types'
import { Badge, Loading, Notice } from '../components/ui'

export interface EvidenceState {
  loading: boolean
  data: EvidenceResponse | null
  error: string | null
  label: string | null
}

/** Verbatim text from the stored original around a source reference. The referenced block is highlighted. */
export function EvidencePanel({
  state,
  open,
  onClose,
}: {
  state: EvidenceState
  open: boolean
  onClose: () => void
}) {
  const focusRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLElement>(null)
  useEffect(() => {
    // Scroll the panel (not the page) so the highlighted source block is visible.
    const panel = panelRef.current
    const target = focusRef.current
    if (!panel || !target) return
    const top = target.getBoundingClientRect().top - panel.getBoundingClientRect().top + panel.scrollTop
    panel.scrollTo({ top: Math.max(0, top - panel.clientHeight / 3), behavior: 'smooth' })
  }, [state.data])
  const d = state.data
  return (
    <aside ref={panelRef} className={`evidence ${open ? 'open' : ''}`} aria-label="Source evidence" aria-live="polite">
      <div className="evidence-head">
        <span>
          <strong>Source evidence</strong>
          <small>
            {d ? d.document_name : 'Select a source link to see the original text'}
            {d?.page ? ` · page ${d.page}${d.page_count ? ` of ${d.page_count}` : ''}` : ''}
          </small>
        </span>
        <span style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {d && <Badge tone="lavender">{state.label ?? 'Original text'}</Badge>}
          <button className="icon-btn panel-toggle" onClick={onClose} aria-label="Close source evidence">
            <X size={16} />
          </button>
        </span>
      </div>
      {state.loading && <Loading label="Reading the original…" />}
      {state.error && (
        <div style={{ marginTop: 12 }}>
          <Notice tone="error">{state.error}</Notice>
        </div>
      )}
      {!state.loading && !d && !state.error && (
        <div className="paper" style={{ display: 'grid', placeItems: 'center', color: '#888', textAlign: 'center' }}>
          <div>
            <FileText size={28} aria-hidden />
            <p>Click a “Page …” link next to any value to see exactly where it was found.</p>
          </div>
        </div>
      )}
      {d && !state.loading && (
        <>
          {d.note && (
            <div style={{ marginTop: 12 }}>
              <Notice tone="warning">{d.note}</Notice>
            </div>
          )}
          <div className="paper">
            {d.blocks.length === 0 && <p>No text was extracted from this part of the document.</p>}
            {d.blocks.map((b) => {
              const focused = b.id === d.focus_block_id
              const loc = b.line ? `line ${b.line}` : b.paragraph ? `paragraph ${b.paragraph}` : b.row ? `row ${b.row}` : ''
              return (
                <div
                  key={b.id}
                  ref={focused ? focusRef : undefined}
                  className={`evidence-block ${b.kind} ${focused ? 'focus' : ''}`}
                  aria-current={focused ? 'true' : undefined}
                >
                  {loc && <span className="loc">{loc}</span>}
                  {b.cells ? b.cells.filter(Boolean).join('  |  ') : b.text}
                </div>
              )
            })}
          </div>
          <div className="evidence-foot">The highlighted text is quoted verbatim from your uploaded file.</div>
        </>
      )}
    </aside>
  )
}
