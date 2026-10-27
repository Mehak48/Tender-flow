import { useEffect, useState } from 'react'
import { Download, LayoutTemplate, Plus, Search } from 'lucide-react'
import { api, downloadUrl } from '../api/client'
import type { TemplateEntry } from '../api/types'
import { useApp } from '../components/AppContext'
import { Modal } from '../components/Modal'
import { Badge, Button, EmptyState, Loading, Notice, PageTitle } from '../components/ui'
import { ITEM_ATTRIBUTE_LABEL } from '../lib/labels'
import { relativeTime } from '../lib/format'
import { navigate, projectHref } from '../router'

export function Templates() {
  const { reportError } = useApp()
  const [entries, setEntries] = useState<TemplateEntry[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [inspect, setInspect] = useState<TemplateEntry | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  useEffect(() => {
    api
      .libraryTemplates()
      .then(setEntries)
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load templates.'))
  }, [])

  async function reuse(t: TemplateEntry) {
    setBusy(t.document.id)
    try {
      const p = await api.reuseTemplate(t.project_id, t.document.id)
      navigate(projectHref(p.id, 'upload'))
    } catch (e) {
      reportError(e)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="page">
      <PageTitle
        eyebrow="Library"
        title="Quotation templates"
        description="Templates you uploaded, with what TenderFlow detected in them. In this prototype templates are stored with each project; “Use for a new quotation” copies one into a new project."
        actions={
          <a className="btn primary" href="#/new">
            <Plus size={16} aria-hidden /> New quotation
          </a>
        }
      />
      {error && <Notice tone="error" title="Could not load templates">{error}</Notice>}
      {!entries && !error && <Loading />}
      {entries && entries.length === 0 && (
        <div className="card">
          <EmptyState
            icon={<LayoutTemplate size={32} aria-hidden />}
            title="No templates yet"
            action={
              <a className="btn primary" href="#/new">
                Upload a template
              </a>
            }
          >
            Upload your own .docx or .xlsx quotation template when you create a quotation. The sample project includes one.
          </EmptyState>
        </div>
      )}
      {entries && entries.length > 0 && (
        <div className="template-grid">
          {entries.map((t) => {
            const a = t.analysis
            return (
              <article className="template-card" key={t.document.id}>
                <div className="template-thumb" aria-hidden>
                  <div className="thumb-logo">{t.document.format.toUpperCase()} TEMPLATE</div>
                  <span>QUOTATION</span>
                  <i />
                  <i />
                  <i />
                </div>
                <div>
                  <Badge tone={a?.items_table ? 'lavender' : 'warning'}>{a?.items_table ? 'Items table found' : 'No items table'}</Badge>
                  <h3>{t.document.filename}</h3>
                  <p>
                    {a ? `${a.fields.length} fill-in fields` : 'Not analysed'} · uploaded {relativeTime(t.document.uploaded_at)}
                  </p>
                  <p className="tiny">Project: {t.project_name}</p>
                </div>
                <div className="card-actions">
                  <Button small onClick={() => setInspect(t)} icon={<Search size={13} aria-hidden />}>
                    Inspect
                  </Button>
                  <Button small kind="primary" busy={busy === t.document.id} onClick={() => void reuse(t)}>
                    Use for a new quotation
                  </Button>
                  <a className="icon-btn" href={downloadUrl(api.documentDownloadPath(t.project_id, t.document.id))} download={t.document.filename} aria-label={`Download ${t.document.filename}`}>
                    <Download size={15} />
                  </a>
                </div>
              </article>
            )
          })}
        </div>
      )}
      {inspect && inspect.analysis && (
        <Modal title={inspect.document.filename} onClose={() => setInspect(null)} wide>
          {inspect.analysis.warnings.length > 0 && (
            <Notice tone="warning">
              <ul>
                {inspect.analysis.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </Notice>
          )}
          <h3 className="small" style={{ margin: '14px 0 6px' }}>
            Fill-in fields
          </h3>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Field</th>
                  <th scope="col">Recognised as</th>
                  <th scope="col">Kind</th>
                  <th scope="col">Where</th>
                </tr>
              </thead>
              <tbody>
                {inspect.analysis.fields.map((f) => (
                  <tr key={f.id}>
                    <td>
                      {f.label} {f.required ? '' : <Badge>Optional</Badge>}
                    </td>
                    <td>{f.recognized ? <code className="mono">{f.key}</code> : <Badge tone="warning">Not recognised</Badge>}</td>
                    <td>{f.kind === 'placeholder' ? 'Placeholder' : 'Label + blank'}</td>
                    <td className="tiny">{f.locations.join(' · ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {inspect.analysis.items_table && (
            <>
              <h3 className="small" style={{ margin: '14px 0 6px' }}>
                Items table — {inspect.analysis.items_table.location}
              </h3>
              <p className="tiny muted">
                {inspect.analysis.items_table.columns
                  .map((c) => `${c.header || '(blank)'} → ${c.attribute ? ITEM_ATTRIBUTE_LABEL[c.attribute] : 'not used'}`)
                  .join(' · ')}
              </p>
            </>
          )}
        </Modal>
      )}
    </div>
  )
}
