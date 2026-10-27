import { useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, ArrowLeft, Check, CircleCheck, Download, Eye, Info, Trash2, Wrench, X } from 'lucide-react'
import { api, downloadUrl, fetchBlob } from '../api/client'
import type { ExportArtifact, ExportFormat, ValidationIssue } from '../api/types'
import { errorMessage, useApp } from '../components/AppContext'
import { Modal } from '../components/Modal'
import { Badge, Button, Loading, Notice, PageTitle } from '../components/ui'
import { SECTION_LABEL, SEVERITY_META } from '../lib/labels'
import { formatBytes, relativeTime } from '../lib/format'
import { navigate, projectHref } from '../router'
import { TemplatePreview } from './editor/TemplatePreview'
import type { FlowProps } from './types'

type Filter = 'all' | 'error' | 'warning' | 'info' | 'acknowledged'

const QUOTATION_SECTIONS = new Set(['company', 'details', 'buyer', 'items', 'terms', 'totals', 'authorization'])

function fixLabel(fix: string): string {
  if (fix === 'confirm_mapping') return 'Confirm mapping'
  if (fix === 'confirm_prices') return 'Confirm matched prices'
  if (fix === 'confirm_terms') return 'Confirm the terms'
  if (fix.startsWith('set_currency:')) return `Use ${fix.split(':')[1]}`
  if (fix.startsWith('use_calculated_amount:')) return 'Use calculated amount'
  return 'Apply fix'
}

function baseFilename(number: string | null | undefined): string {
  const cleaned = (number ?? 'Quotation').replace(/[^A-Za-z0-9._-]+/g, '_').replace(/^[._-]+|[._-]+$/g, '')
  return (cleaned || 'Quotation').slice(0, 60)
}

export function ReviewExportStep({ project, run, busy }: FlowProps) {
  const { health } = useApp()
  const report = project.validation!
  const q = project.quotation!
  const [filter, setFilter] = useState<Filter>('all')
  const [format, setFormat] = useState<ExportFormat>(project.export_formats[0] ?? 'docx')
  const [lastExport, setLastExport] = useState<ExportArtifact | null>(null)
  const [preview, setPreview] = useState<'template' | ExportArtifact | null>(null)
  const pdfAvailable = health?.pdf_export.available ?? false

  const visible = useMemo(
    () =>
      report.issues.filter((i) =>
        filter === 'all'
          ? true
          : filter === 'acknowledged'
            ? i.acknowledged
            : i.severity === filter && !(filter === 'warning' && i.acknowledged),
      ),
    [report.issues, filter],
  )
  const ackCount = report.issues.filter((i) => i.acknowledged).length

  function goTo(issue: ValidationIssue) {
    if (issue.section === 'mapping') return navigate(projectHref(project.id, 'mapping'))
    if (issue.section === 'extraction') return navigate(projectHref(project.id, 'review'))
    const focus = issue.line_item_id
      ? `item:${issue.line_item_id}`
      : issue.field_key
        ? `field:${issue.field_key}`
        : QUOTATION_SECTIONS.has(issue.section)
          ? `section:${issue.section}`
          : ''
    navigate(projectHref(project.id, 'editor', focus ? { focus } : undefined))
  }

  async function doExport(draft: boolean) {
    const result = await run(() => api.exportQuotation(project.id, format, draft), draft ? 'Draft exported' : 'Quotation exported')
    if (result) setLastExport(result.artifact)
  }

  const mapping = project.mapping
  const targets = mapping?.mapping.fields.filter((r) => r.source_key) ?? []
  const filled = targets.filter((r) => q.fields[r.source_key!]?.value).length
  const instructionEdits = project.edit_history.filter((r) => r.kind === 'instruction').length
  const fileBase = baseFilename(q.fields.quotation_number?.value)
  const pct = report.checks_run ? Math.round((report.checks_passed / report.checks_run) * 100) : 0
  const ringColor = report.ready ? '#6f9b74' : report.errors ? '#d97b6c' : '#e9a574'

  return (
    <div className="review-page">
      <PageTitle
        eyebrow="Step 5 of 5"
        title="Validate and export"
        description="Deterministic checks run on every change. Resolve errors, review warnings, then export into your own template."
        actions={
          <Button onClick={() => navigate(projectHref(project.id, 'editor'))} icon={<ArrowLeft size={15} aria-hidden />}>
            Return to editor
          </Button>
        }
      />
      <div className="review-summary" role="status">
        <div>
          <span
            className="score"
            style={{ background: `conic-gradient(${ringColor} ${pct}%, var(--color-silver) 0)` }}
            aria-label={`${report.checks_passed} of ${report.checks_run} checks passed`}
          >
            <span style={{ background: '#fff', width: 44, height: 44, borderRadius: '50%', display: 'grid', placeItems: 'center' }}>
              {report.checks_passed}/{report.checks_run}
            </span>
          </span>
          <div>
            <strong>{report.ready ? 'Ready to export' : report.errors ? 'Not ready — errors to resolve' : 'Review the remaining warnings'}</strong>
            <p>
              {report.ready
                ? 'No errors, and every warning has been reviewed by you.'
                : `${report.errors} error(s) must be fixed; ${report.unacknowledged_warnings} warning(s) need a decision. Draft export is available for internal review.`}
            </p>
          </div>
        </div>
        <span>
          <b>{report.errors}</b>Errors
        </span>
        <span>
          <b>{report.warnings}</b>Warnings
        </span>
        <span>
          <b>{ackCount}</b>Acknowledged
        </span>
      </div>

      <div className="review-grid">
        <section aria-label="Validation findings">
          <div className="tabs" role="tablist">
            {(
              [
                ['all', 'All', report.issues.length],
                ['error', 'Errors', report.errors],
                ['warning', 'Warnings', report.unacknowledged_warnings],
                ['info', 'Notes', report.infos],
                ['acknowledged', 'Acknowledged', ackCount],
              ] as const
            ).map(([key, label, count]) => (
              <button key={key} role="tab" aria-selected={filter === key} onClick={() => setFilter(key)}>
                {label} <span className="count">{count}</span>
              </button>
            ))}
          </div>
          {visible.length === 0 && (
            <div style={{ padding: 20 }} className="muted small">
              {filter === 'all' ? 'No findings — every check passed.' : 'Nothing in this list.'}
            </div>
          )}
          {visible.map((issue) => (
            <div className={`finding ${issue.severity} ${issue.acknowledged ? 'acknowledged' : ''}`} key={issue.id}>
              <span className="finding-icon" aria-hidden>
                {issue.acknowledged ? <Check size={15} /> : issue.severity === 'error' ? <X size={15} /> : issue.severity === 'warning' ? <AlertTriangle size={14} /> : <Info size={14} />}
              </span>
              <div>
                <div className="finding-meta">
                  <Badge tone={SEVERITY_META[issue.severity].tone}>{SEVERITY_META[issue.severity].label}</Badge>
                  <span>{SECTION_LABEL[issue.section]}</span>
                  {issue.acknowledged && <Badge tone="success">Acknowledged by you</Badge>}
                </div>
                <h3>{issue.title}</h3>
                <p>{issue.message}</p>
                {issue.suggestion && <p className="suggestion">Suggestion: {issue.suggestion}</p>}
                <div className="finding-actions">
                  {issue.fix && (
                    <Button small kind="primary" disabled={busy} icon={<Wrench size={13} aria-hidden />} onClick={() => void run(() => api.quickFix(project.id, issue.fix!), `Done: ${fixLabel(issue.fix!)}`)}>
                      {fixLabel(issue.fix)}
                    </Button>
                  )}
                  <Button small onClick={() => goTo(issue)}>
                    {issue.section === 'mapping' ? 'Open mapping' : issue.section === 'extraction' ? 'Open extraction review' : 'Go to field'}
                  </Button>
                  {issue.acknowledgeable && (
                    <Button
                      small
                      kind="quiet"
                      disabled={busy}
                      onClick={() => void run(() => api.acknowledge(project.id, issue.id, !issue.acknowledged))}
                    >
                      {issue.acknowledged ? 'Re-open' : 'Acknowledge'}
                    </Button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </section>

        <aside className="export-card" aria-label="Export">
          <Button block kind="quiet" icon={<Eye size={15} aria-hidden />} onClick={() => setPreview('template')}>
            Preview in your template
          </Button>
          <h3 style={{ marginTop: 10 }}>
            {fileBase}
            {report.ready ? '' : '_DRAFT'}.{format}
          </h3>
          <p className="tiny muted" style={{ margin: 0 }}>
            Template: {project.template?.document_name}
          </p>
          <div className="format-options" role="radiogroup" aria-label="Export format">
            {project.export_formats.map((f) => {
              const disabled = f === 'pdf' && !pdfAvailable
              return (
                <label key={f} className={`format-option ${disabled ? 'disabled' : ''}`}>
                  <input type="radio" name="format" value={f} checked={format === f} disabled={disabled} onChange={() => setFormat(f)} />
                  <span>
                    <strong>{f.toUpperCase()}</strong>
                    <small>
                      {f === 'pdf'
                        ? disabled
                          ? health?.pdf_export.reason ?? 'PDF export is not available.'
                          : 'Converted from your filled template with LibreOffice.'
                        : 'Your template, filled in. Formatting preserved.'}
                    </small>
                  </span>
                </label>
              )
            })}
          </div>
          <div className="export-status">
            {report.ready ? <Badge tone="success">Ready</Badge> : <Badge tone="warning">Review required</Badge>}
            <span>{report.ready ? 'Final export available' : 'Draft export only — marked DRAFT'}</span>
          </div>
          <dl>
            <dt>Source tender</dt>
            <dd>{project.documents.find((d) => d.role === 'tender')?.filename ?? '—'}</dd>
            <dt>Template fields filled</dt>
            <dd>
              {filled} of {targets.length}
            </dd>
            <dt>Line items</dt>
            <dd>{q.line_items.length}</dd>
            <dt>Instruction edits applied</dt>
            <dd>{instructionEdits}</dd>
            <dt>Exports so far</dt>
            <dd>{project.exports.length}</dd>
          </dl>
          {project.edit_history.length > 0 && (
            <div className="changed">
              <strong>What changed recently</strong>
              {project.edit_history.slice(0, 3).map((r) => (
                <p key={r.id}>✓ {r.summary}</p>
              ))}
            </div>
          )}
          {report.ready ? (
            <Button block kind="primary" busy={busy} icon={<Download size={15} aria-hidden />} onClick={() => void doExport(false)}>
              Export {format.toUpperCase()}
            </Button>
          ) : (
            <>
              <Button block busy={busy} icon={<Download size={15} aria-hidden />} onClick={() => void doExport(true)}>
                Export draft for internal review
              </Button>
              <Button block kind="primary" disabled title="Resolve the errors and review the warnings first">
                Export final (not ready)
              </Button>
            </>
          )}

          {lastExport && (
            <div style={{ marginTop: 14 }}>
              <Notice tone="success" title={`${lastExport.filename} created`}>
                <span className="tiny">
                  {formatBytes(lastExport.size_bytes)} · re-opened and checked on the server
                </span>
                <ul className="checks">
                  {lastExport.checks.map((c) => (
                    <li key={c.name} className={c.passed ? 'pass' : 'fail'}>
                      {c.passed ? <CircleCheck size={13} aria-hidden /> : <AlertTriangle size={13} aria-hidden />}
                      <span>
                        {c.name}
                        {c.detail ? ` — ${c.detail}` : ''}
                      </span>
                    </li>
                  ))}
                </ul>
                {lastExport.warnings.map((w) => (
                  <p key={w} className="tiny">
                    {w}
                  </p>
                ))}
                <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                  <a className="btn small primary" href={downloadUrl(api.exportDownloadPath(project.id, lastExport.id))} download={lastExport.filename}>
                    <Download size={14} aria-hidden /> Download
                  </a>
                  {lastExport.format === 'docx' && (
                    <Button small onClick={() => setPreview(lastExport)}>
                      Preview file
                    </Button>
                  )}
                </div>
              </Notice>
            </div>
          )}

          {project.exports.length > 0 && (
            <div style={{ marginTop: 14 }}>
              <strong className="small">Previous exports</strong>
              <ul className="export-list">
                {project.exports.map((e) => (
                  <li key={e.id}>
                    <Badge tone={e.draft ? 'warning' : 'success'}>{e.draft ? 'Draft' : 'Final'}</Badge>
                    <span>
                      {e.filename}
                      <span className="muted"> · {relativeTime(e.created_at)}</span>
                    </span>
                    <a className="icon-btn" href={downloadUrl(api.exportDownloadPath(project.id, e.id))} download={e.filename} aria-label={`Download ${e.filename}`}>
                      <Download size={14} />
                    </a>
                    <button className="icon-btn" aria-label={`Delete ${e.filename}`} disabled={busy} onClick={() => void run(() => api.deleteExport(project.id, e.id), 'Export deleted')}>
                      <Trash2 size={14} />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>
      </div>

      {preview && (
        <Modal title={preview === 'template' ? 'Preview in your template' : `Preview: ${preview.filename}`} onClose={() => setPreview(null)} wide>
          {preview === 'template' ? (
            <TemplatePreview projectId={project.id} format={project.template?.format ?? 'docx'} version={`${q.version}-${q.updated_at}`} />
          ) : (
            <ExportedDocx path={api.exportDownloadPath(project.id, preview.id)} />
          )}
        </Modal>
      )}
    </div>
  )
}

function ExportedDocx({ path }: { path: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const blob = await fetchBlob(path)
        const { renderAsync } = await import('docx-preview')
        if (cancelled || !ref.current) return
        await renderAsync(blob, ref.current, undefined, { inWrapper: true, useBase64URL: true })
        if (!cancelled) setState('ready')
      } catch (e) {
        if (!cancelled) {
          setError(errorMessage(e))
          setState('error')
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [path])
  return (
    <>
      {state === 'loading' && <Loading label="Rendering the exported file…" />}
      {state === 'error' && <Notice tone="error">{error}</Notice>}
      <div ref={ref} className="docx-render" style={{ display: state === 'ready' ? 'block' : 'none' }} />
    </>
  )
}
