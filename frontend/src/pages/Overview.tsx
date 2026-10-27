import { useEffect, useState } from 'react'
import { ArrowRight, Calculator, CircleHelp, FileSearch, FolderOpen, Plus, ShieldCheck, Sparkles } from 'lucide-react'
import { api, uploadDocument } from '../api/client'
import type { DocumentRole, ProjectSummary } from '../api/types'
import { useApp } from '../components/AppContext'
import { Button, EmptyState, Loading, Notice, PageTitle } from '../components/ui'
import { UploadSlot } from '../components/UploadSlot'
import { APP_NAME, DEFAULT_MAX_UPLOAD_MB, TAGLINE } from '../config'
import { formatDate } from '../lib/format'
import { navigate, projectHref } from '../router'
import { ProjectTable } from './Projects'

export function Overview() {
  const { health, reportError } = useApp()
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [sampleBusy, setSampleBusy] = useState(false)
  const maxMb = health?.limits.max_upload_mb ?? DEFAULT_MAX_UPLOAD_MB

  useEffect(() => {
    api
      .listProjects()
      .then(setProjects)
      .catch((e) => setLoadError(e instanceof Error ? e.message : 'Could not load projects.'))
  }, [])

  async function startWith(role: DocumentRole, file: File, onProgress: (f: number) => void) {
    const project = await api.createProject()
    await uploadDocument(project.id, role, file, onProgress)
    navigate(projectHref(project.id, 'upload'))
  }

  async function sample() {
    setSampleBusy(true)
    try {
      const project = await api.createSampleProject()
      navigate(projectHref(project.id, 'review'))
    } catch (e) {
      reportError(e)
    } finally {
      setSampleBusy(false)
    }
  }

  return (
    <div className="page">
      <PageTitle
        eyebrow={formatDate(new Date())}
        title={`Welcome to ${APP_NAME}`}
        description={`${TAGLINE} Turn a tender into a quotation in your own template — every value traceable, nothing invented.`}
        actions={
          <>
            <a className="btn" href="#/templates">
              Browse templates
            </a>
            <a className="btn primary" href="#/new">
              <Plus size={16} aria-hidden /> Create quotation
            </a>
          </>
        }
      />

      <section className="quick-start" aria-labelledby="qs-title">
        <div className="quick-head">
          <div>
            <span className="section-kicker">Quick start</span>
            <h2 id="qs-title">Compile a new quotation</h2>
            <p>Drop your files here, or try the full workflow with the fictional sample documents.</p>
          </div>
        </div>
        <div className="upload-grid">
          <UploadSlot role="tender" title="Tender document" record={null} maxMb={maxMb} onUpload={(f, p) => startWith('tender', f, p)} />
          <div className="transfer" aria-hidden>
            <ArrowRight size={18} />
            Extract & map
          </div>
          <UploadSlot role="template" title="Your quotation template" record={null} maxMb={maxMb} onUpload={(f, p) => startWith('template', f, p)} />
        </div>
        <div className="quick-footer">
          <span>
            <CircleHelp size={15} aria-hidden /> Scanned PDFs without a text layer cannot be read (no OCR in this prototype).
          </span>
          <Button kind="primary" onClick={sample} busy={sampleBusy} icon={<Sparkles size={16} aria-hidden />}>
            Try the sample project
          </Button>
        </div>
      </section>

      <section className="how" aria-label="How it works">
        <strong>How it works</strong>
        {['Upload', 'Review', 'Map', 'Edit', 'Validate & export'].map((s, i) => (
          <div key={s}>
            <span>{i + 1}</span>
            {s}
            {i < 4 && <ArrowRight size={14} aria-hidden style={{ color: '#a69fa9' }} />}
          </div>
        ))}
      </section>

      <section className="principles" aria-label="Product principles">
        <div className="principle">
          <FileSearch size={18} aria-hidden />
          <div>
            <strong>Source-linked</strong>
            <span>Every extracted value shows the page and line it came from.</span>
          </div>
        </div>
        <div className="principle">
          <Calculator size={18} aria-hidden />
          <div>
            <strong>Deterministic checks</strong>
            <span>Totals and validation are plain code — never an AI guess.</span>
          </div>
        </div>
        <div className="principle">
          <ShieldCheck size={18} aria-hidden />
          <div>
            <strong>You approve every change</strong>
            <span>Prices, taxes and commitments are never invented or silently changed.</span>
          </div>
        </div>
      </section>

      <section className="section-block" aria-labelledby="recent-title">
        <div className="section-head">
          <div>
            <h2 id="recent-title">Recent work</h2>
            <p>Projects are stored on this computer in the backend data folder.</p>
          </div>
          {projects && projects.length > 0 && (
            <a className="btn quiet" href="#/projects">
              View all <ArrowRight size={14} aria-hidden />
            </a>
          )}
        </div>
        {loadError ? (
          <Notice tone="error" title="Could not load your projects">
            {loadError}
          </Notice>
        ) : projects === null ? (
          <Loading />
        ) : projects.length === 0 ? (
          <div className="card">
            <EmptyState
              icon={<FolderOpen size={32} aria-hidden />}
              title="No quotations yet"
              action={
                <div style={{ display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap' }}>
                  <a className="btn primary" href="#/new">
                    Create quotation
                  </a>
                  <Button onClick={sample} busy={sampleBusy}>
                    Load the sample project
                  </Button>
                </div>
              }
            >
              Start with your own tender and template, or explore with the fictional sample documents.
            </EmptyState>
          </div>
        ) : (
          <ProjectTable projects={projects.slice(0, 5)} onChanged={() => api.listProjects().then(setProjects).catch(reportError)} />
        )}
      </section>
    </div>
  )
}
