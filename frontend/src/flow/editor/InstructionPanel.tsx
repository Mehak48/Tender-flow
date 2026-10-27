import { useEffect, useState } from 'react'
import { ArrowRight, Eye, History, MessageSquareText, Sparkles, X } from 'lucide-react'
import { api } from '../../api/client'
import type { EditProposal, EditResponse, ProjectView } from '../../api/types'
import { useApp } from '../../components/AppContext'
import { Badge, Button, Notice } from '../../components/ui'
import { relativeTime } from '../../lib/format'
import type { FlowProps } from '../types'

const SUGGESTIONS = [
  'Change the delivery period to 30 days.',
  'Add a line item for the installation service.',
  'Rewrite the payment terms using the information I supplied.',
  'Highlight missing information.',
  'Change the quotation title to match the tender reference.',
  'Set the unit price of item 4 to 95000.',
]

const KIND_LABEL: Record<string, string> = {
  instruction: 'Instruction',
  manual: 'Edited',
  undo: 'Undo',
  regenerate: 'Regenerated',
  quick_fix: 'Quick fix',
}

export function InstructionPanel({
  project,
  run,
  busy,
  open,
  onClose,
  onHighlight,
  missingCount,
}: Pick<FlowProps, 'project' | 'run' | 'busy'> & {
  open: boolean
  onClose: () => void
  onHighlight: () => void
  missingCount: number
}) {
  const { health, notify } = useApp()
  const [tab, setTab] = useState<'edit' | 'history'>('edit')
  const [instruction, setInstruction] = useState('')
  const [response, setResponse] = useState<EditResponse | null>(null)
  const [checked, setChecked] = useState(false)

  const pending: EditProposal | null =
    response?.proposal && project.pending_edits.some((p) => p.id === response.proposal!.id)
      ? response.proposal
      : project.pending_edits[0] ?? null

  useEffect(() => setChecked(false), [pending?.id])

  async function preview() {
    const text = instruction.trim()
    if (!text) return
    const result = await run(() => api.proposeEdit(project.id, text))
    if (result) setResponse(result.response)
  }

  async function apply(p: EditProposal) {
    if (p.ui_only) {
      onHighlight()
      await run(() => api.applyEdit(project.id, p.id, false))
      setResponse(null)
      setInstruction('')
      return
    }
    const updated = await run<ProjectView>(() => api.applyEdit(project.id, p.id, p.material ? checked : false))
    if (updated) {
      notify('Change applied — Undo is available')
      setResponse(null)
      setInstruction('')
    }
  }

  async function cancel(p: EditProposal) {
    const updated = await run(() => api.cancelEdit(project.id, p.id))
    if (updated) setResponse(null)
  }

  const engineLabel = health?.ai.mode === 'external' ? `Rules first, then ${health.ai.model ?? 'external AI'}` : 'Local rules (no AI provider)'

  return (
    <aside className={`instruction-panel ${open ? 'open' : ''}`} aria-label="Edit with instructions">
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === 'edit'} onClick={() => setTab('edit')}>
          <MessageSquareText size={14} aria-hidden /> Edit with instructions
        </button>
        <button role="tab" aria-selected={tab === 'history'} onClick={() => setTab('history')}>
          <History size={14} aria-hidden /> History <span className="count">{project.edit_history.length}</span>
        </button>
        <button className="icon-btn panel-toggle" style={{ marginLeft: 'auto' }} onClick={onClose} aria-label="Close panel">
          <X size={16} />
        </button>
      </div>

      {tab === 'edit' && (
        <div role="tabpanel">
          <div className="ai-intro">
            <span>
              <Sparkles size={17} aria-hidden />
            </span>
            <div>
              <strong>Describe a controlled change</strong>
              <p>You see exactly what would change before anything is applied. Engine: {engineLabel}.</p>
            </div>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              void preview()
            }}
          >
            <label htmlFor="instruction" className="sr-only">
              Instruction
            </label>
            <textarea
              id="instruction"
              className="textarea"
              value={instruction}
              maxLength={500}
              placeholder="e.g. Change the delivery period to 30 days."
              onChange={(e) => setInstruction(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                  e.preventDefault()
                  void preview()
                }
              }}
            />
            <div className="instruction-foot">
              <span>{instruction.length}/500 · Ctrl+Enter to preview</span>
              <Button type="submit" kind="primary" small disabled={!instruction.trim()} busy={busy}>
                Preview change <ArrowRight size={14} aria-hidden />
              </Button>
            </div>
          </form>

          {response && !response.proposal && response.message && (
            <div style={{ marginTop: 14 }}>
              <Notice tone={response.understood ? 'info' : 'warning'} title={response.understood ? 'Understood, but nothing to change' : 'Not understood'}>
                {response.message}
              </Notice>
            </div>
          )}

          {pending && (
            <div className={`proposal ${pending.engine === 'ai' ? 'ai' : ''}`} aria-live="polite">
              <div className="proposal-head">
                <span>
                  <Eye size={15} aria-hidden /> Proposed change
                </span>
                <Badge tone="lavender">{pending.engine === 'ai' ? 'AI suggestion' : 'Rule-based'}</Badge>
              </div>
              <p>
                <strong>“{pending.instruction}”</strong>
                <br />
                {pending.interpreted_as}
              </p>
              {pending.changes.length > 0 && (
                <table className="changes">
                  <thead>
                    <tr>
                      <th scope="col">What</th>
                      <th scope="col">Before</th>
                      <th scope="col">After</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pending.changes.map((c, i) => (
                      <tr key={`${c.target}-${i}`}>
                        <td>{c.target}</td>
                        <td>{c.before ? <del>{c.before}</del> : <span className="muted">—</span>}</td>
                        <td>{c.after ? <ins>{c.after}</ins> : <span className="muted">(removed)</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {pending.ui_only && <p className="tiny muted">This only highlights fields in the preview. No data changes.</p>}
              {pending.warnings.map((w) => (
                <p key={w} className="tiny" style={{ color: 'var(--color-warning-ink)', margin: '6px 0 0' }}>
                  {w}
                </p>
              ))}
              {pending.material && (
                <div style={{ marginTop: 10 }}>
                  <Notice tone="warning">
                    <span>This change {pending.material_reasons.join(', ')}.</span>
                  </Notice>
                  <label className="checkbox" style={{ marginTop: 8 }}>
                    <input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} />
                    <span>I have checked these values and want to apply them.</span>
                  </label>
                </div>
              )}
              <div className="proposal-actions">
                <Button small onClick={() => void cancel(pending)} disabled={busy}>
                  Cancel
                </Button>
                <Button small kind="primary" onClick={() => void apply(pending)} disabled={busy || (pending.material && !checked)}>
                  {pending.ui_only ? 'Show missing fields' : 'Apply change'}
                </Button>
              </div>
            </div>
          )}

          {!pending && (
            <div className="suggestions">
              <span>Try an instruction</span>
              {(response && !response.understood && response.examples.length ? response.examples : SUGGESTIONS).map((s) => (
                <button key={s} type="button" onClick={() => setInstruction(s)}>
                  {s}
                </button>
              ))}
            </div>
          )}

          {missingCount > 0 && (
            <div className="warning-card">
              <span aria-hidden>!</span>
              <div>
                <strong>
                  {missingCount} value{missingCount > 1 ? 's' : ''} need your input
                </strong>
                <p>TenderFlow leaves unknown values empty instead of guessing.</p>
                <button type="button" className="link-btn" onClick={onHighlight}>
                  Highlight them in the preview
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {tab === 'history' && (
        <div role="tabpanel">
          {project.edit_history.length === 0 ? (
            <p className="small muted">No changes yet. Edits, instructions, quick fixes and undos appear here.</p>
          ) : (
            <ul className="history-list">
              {project.edit_history.map((r) => (
                <li key={r.id}>
                  <header>
                    <Badge tone={r.kind === 'undo' ? 'warning' : r.engine === 'ai' ? 'lavender' : 'neutral'}>{KIND_LABEL[r.kind] ?? r.kind}</Badge>
                    <time dateTime={r.created_at}>{relativeTime(r.created_at)}</time>
                  </header>
                  <div style={{ marginTop: 4 }}>{r.summary}</div>
                  {r.instruction && <div className="tiny muted">“{r.instruction}”</div>}
                  {r.changes.length > 0 && (
                    <details>
                      <summary>{r.changes.length} change(s)</summary>
                      <ul style={{ paddingLeft: 16, margin: '4px 0 0' }}>
                        {r.changes.map((c, i) => (
                          <li key={i}>
                            {c.target}: {c.before ?? '—'} → {c.after ?? '—'}
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </aside>
  )
}
