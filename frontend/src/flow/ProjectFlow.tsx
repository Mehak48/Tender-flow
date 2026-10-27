import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import { api } from '../api/client'
import type { ProjectView } from '../api/types'
import { useApp, errorMessage } from '../components/AppContext'
import { Badge, Button, Loading, Notice } from '../components/ui'
import { relativeTime } from '../lib/format'
import { navigate, projectHref, type StepKey } from '../router'
import { EditorStep } from './EditorStep'
import { ExtractionStep } from './ExtractionStep'
import { MappingStep } from './MappingStep'
import { ReviewExportStep } from './ReviewExportStep'
import { Stepper, stepAvailability } from './Stepper'
import { UploadStep } from './UploadStep'
import { PROJECT_EVENT, isProjectView, type FlowProps } from './types'

export function ProjectFlow({
  id,
  step,
  query,
  setCrumb,
}: {
  id: string
  step: StepKey
  query: URLSearchParams
  setCrumb: (c: string | null) => void
}) {
  const { notify, reportError } = useApp()
  const [project, setProject] = useState<ProjectView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [name, setName] = useState('')

  const load = useCallback(async () => {
    try {
      const p = await api.getProject(id)
      setProject(p)
      setName(p.name)
      setError(null)
    } catch (e) {
      setError(errorMessage(e))
    }
  }, [id])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    const onUpdate = (e: Event) => {
      const detail = (e as CustomEvent<ProjectView>).detail
      if (detail?.id === id) {
        setProject(detail)
        setName(detail.name)
      }
    }
    window.addEventListener(PROJECT_EVENT, onUpdate)
    return () => window.removeEventListener(PROJECT_EVENT, onUpdate)
  }, [id])

  useEffect(() => {
    if (project) setCrumb(project.name)
  }, [project, setCrumb])

  const update = useCallback((p: ProjectView) => {
    setProject(p)
    setName(p.name)
  }, [])

  const run = useCallback(
    async <T,>(fn: () => Promise<T>, success?: string): Promise<T | undefined> => {
      setBusy(true)
      try {
        const result = await fn()
        if (isProjectView(result)) update(result)
        else if (result && typeof result === 'object' && 'project' in result && isProjectView((result as { project: unknown }).project)) {
          update((result as unknown as { project: ProjectView }).project)
        }
        if (success) notify(success)
        return result
      } catch (e) {
        reportError(e)
        return undefined
      } finally {
        setBusy(false)
      }
    },
    [notify, reportError, update],
  )

  // Each step starts at the top of the page unless it was opened to focus a specific field.
  const focusParam = query.get('focus')
  useEffect(() => {
    if (!focusParam) window.scrollTo({ top: 0 })
  }, [step, focusParam])

  // Redirect to the furthest step that is available when a step is not reachable yet.
  useEffect(() => {
    if (!project) return
    const available = stepAvailability(project)
    if (!available[step]) {
      const fallback: StepKey = available.mapping ? 'mapping' : available.review ? 'review' : 'upload'
      navigate(projectHref(project.id, fallback), true)
    }
  }, [project, step])

  if (error) {
    return (
      <div className="page">
        <Notice
          tone="error"
          title="This project could not be opened"
          actions={
            <>
              <Button small onClick={() => void load()}>
                Retry
              </Button>
              <a className="btn small" href="#/projects">
                My work
              </a>
            </>
          }
        >
          {error}
        </Notice>
      </div>
    )
  }
  if (!project) return <Loading label="Opening project…" />

  async function rename() {
    const trimmed = name.trim()
    if (!project || !trimmed || trimmed === project.name) {
      setName(project?.name ?? '')
      return
    }
    await run(() => api.renameProject(project.id, trimmed), 'Project renamed')
  }

  const props: FlowProps = { project, setProject: update, run, busy, query }
  return (
    <>
      <div className="project-bar">
        <div>
          <a className="icon-btn" href="#/projects" aria-label="Back to My work">
            <ArrowLeft size={17} />
          </a>
          {project.is_sample && <Badge tone="lavender">Sample data</Badge>}
          <label className="sr-only" htmlFor="project-name">
            Project name
          </label>
          <input
            id="project-name"
            className="project-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onBlur={() => void rename()}
            onKeyDown={(e) => {
              if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
              if (e.key === 'Escape') {
                setName(project.name)
                ;(e.target as HTMLInputElement).blur()
              }
            }}
            maxLength={120}
            size={Math.min(60, Math.max(14, name.length + 2))}
          />
          <span className="muted tiny">Saved {relativeTime(project.updated_at)}</span>
        </div>
        {busy && (
          <span className="saving" role="status">
            Working…
          </span>
        )}
      </div>
      <Stepper current={step} project={project} />
      {step === 'upload' && (
        <UploadStep project={project} onProject={update} ensureProject={async () => project} />
      )}
      {step === 'review' && project.extraction && <ExtractionStep {...props} />}
      {step === 'mapping' && project.mapping && <MappingStep {...props} />}
      {step === 'editor' && project.quotation && <EditorStep {...props} />}
      {step === 'export' && project.quotation && <ReviewExportStep {...props} />}
    </>
  )
}
