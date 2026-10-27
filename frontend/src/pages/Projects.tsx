import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, Briefcase, FileText, Plus, Search, Trash2 } from 'lucide-react'
import { api } from '../api/client'
import type { ProjectSummary } from '../api/types'
import { useApp } from '../components/AppContext'
import { Modal } from '../components/Modal'
import { Badge, Button, EmptyState, Loading, Notice, PageTitle } from '../components/ui'
import { PROJECT_STATUS } from '../lib/labels'
import { relativeTime } from '../lib/format'
import { projectHref, stepForStage } from '../router'

export function ProjectTable({ projects, onChanged }: { projects: ProjectSummary[]; onChanged: () => void }) {
  const { notify, reportError } = useApp()
  const [toDelete, setToDelete] = useState<ProjectSummary | null>(null)
  const [busy, setBusy] = useState(false)

  async function remove() {
    if (!toDelete) return
    setBusy(true)
    try {
      await api.deleteProject(toDelete.id)
      notify(`Deleted “${toDelete.name}” and its files`)
      setToDelete(null)
      onChanged()
    } catch (e) {
      reportError(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Project</th>
              <th scope="col">Tender document</th>
              <th scope="col">Quotation template</th>
              <th scope="col">Last updated</th>
              <th scope="col">Status</th>
              <th scope="col">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {projects.map((p) => {
              const status = PROJECT_STATUS[p.status]
              const open = projectHref(p.id, stepForStage(p.stage))
              return (
                <tr key={p.id}>
                  <td>
                    <a className="file-cell" href={open} style={{ textDecoration: 'none', color: 'inherit' }}>
                      <span className="doc-mini" aria-hidden>
                        <FileText size={15} />
                      </span>
                      <span>
                        <strong>{p.name}</strong>
                        {p.is_sample && (
                          <>
                            {' '}
                            <Badge tone="lavender">Sample data</Badge>
                          </>
                        )}
                      </span>
                    </a>
                  </td>
                  <td>{p.tender_name ?? <span className="muted">Not uploaded</span>}</td>
                  <td>{p.template_name ?? <span className="muted">Not uploaded</span>}</td>
                  <td title={new Date(p.updated_at).toLocaleString()}>{relativeTime(p.updated_at)}</td>
                  <td>
                    <Badge tone={status.tone}>
                      {status.label}
                      {p.status === 'needs_attention' && p.errors ? ` · ${p.errors}` : ''}
                    </Badge>
                  </td>
                  <td>
                    <div className="cell-actions">
                      <a className="btn quiet small" href={open}>
                        Open <ArrowRight size={14} aria-hidden />
                      </a>
                      <button className="icon-btn" aria-label={`Delete ${p.name}`} onClick={() => setToDelete(p)}>
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {toDelete && (
        <Modal
          title="Delete this project?"
          onClose={() => setToDelete(null)}
          actions={
            <>
              <Button onClick={() => setToDelete(null)}>Cancel</Button>
              <Button kind="danger" busy={busy} onClick={remove} icon={<Trash2 size={15} aria-hidden />}>
                Delete permanently
              </Button>
            </>
          }
        >
          <p className="small">
            “{toDelete.name}” and all of its uploaded files and exports will be removed from this computer. This cannot be
            undone.
          </p>
        </Modal>
      )}
    </>
  )
}

export function Projects() {
  const { reportError } = useApp()
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')

  const load = () =>
    api
      .listProjects()
      .then((p) => {
        setProjects(p)
        setError(null)
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load projects.'))

  useEffect(() => {
    void load()
  }, [])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!projects) return []
    return q
      ? projects.filter((p) => [p.name, p.tender_name, p.template_name].some((v) => v?.toLowerCase().includes(q)))
      : projects
  }, [projects, query])

  const attention = projects?.filter((p) => p.status === 'needs_attention').length ?? 0
  const done = projects?.filter((p) => p.status === 'ready' || p.status === 'exported').length ?? 0

  return (
    <div className="page">
      <PageTitle
        eyebrow="Workspace"
        title="My work"
        description="Quotations in progress and completed, stored locally on this computer."
        actions={
          <a className="btn primary" href="#/new">
            <Plus size={16} aria-hidden /> New quotation
          </a>
        }
      />
      {error && (
        <Notice tone="error" title="Could not load projects" actions={<Button small onClick={() => void load()}>Retry</Button>}>
          {error}
        </Notice>
      )}
      {projects === null && !error && <Loading />}
      {projects && (
        <>
          <div className="stat-row">
            <div>
              <span>Projects</span>
              <strong>{projects.length}</strong>
              <small>Stored in the backend data folder</small>
            </div>
            <div>
              <span>Need attention</span>
              <strong>{attention}</strong>
              <small>Validation errors to resolve</small>
            </div>
            <div>
              <span>Ready or exported</span>
              <strong>{done}</strong>
              <small>No errors, warnings reviewed</small>
            </div>
          </div>
          {projects.length === 0 ? (
            <div className="card">
              <EmptyState
                icon={<Briefcase size={32} aria-hidden />}
                title="Nothing here yet"
                action={
                  <a className="btn primary" href="#/new">
                    Create your first quotation
                  </a>
                }
              >
                Projects appear here as soon as you upload a document.
              </EmptyState>
            </div>
          ) : (
            <>
              <div className="library-tools">
                <label className="search">
                  <Search size={16} aria-hidden />
                  <span className="sr-only">Search projects</span>
                  <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by project or file name" />
                </label>
              </div>
              {filtered.length === 0 ? (
                <p className="muted small">No project matches “{query}”.</p>
              ) : (
                <ProjectTable projects={filtered} onChanged={() => void load().catch(reportError)} />
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}
