import { useRef } from 'react'
import { api } from '../api/client'
import type { ProjectView } from '../api/types'
import { navigate, projectHref } from '../router'
import { PROJECT_EVENT } from './types'
import { Stepper } from './Stepper'
import { UploadStep } from './UploadStep'

/** "New quotation": the upload step before a project exists. The project is created on first upload. */
export function NewQuotation() {
  const pending = useRef<Promise<ProjectView> | null>(null)

  function ensureProject(): Promise<ProjectView> {
    if (!pending.current) {
      pending.current = api.createProject().catch((e) => {
        pending.current = null
        throw e
      })
    }
    return pending.current
  }

  function onProject(p: ProjectView) {
    // Another upload may still be running when the page switches to the project route: share the result.
    window.dispatchEvent(new CustomEvent(PROJECT_EVENT, { detail: p }))
    navigate(projectHref(p.id, 'upload'), true)
  }

  return (
    <>
      <div className="project-bar">
        <div>
          <strong>New quotation</strong>
          <span className="muted">Not saved until you add a document</span>
        </div>
        <a className="btn quiet small" href="#/projects">
          Back to My work
        </a>
      </div>
      <Stepper current="upload" project={null} />
      <UploadStep project={null} onProject={onProject} ensureProject={ensureProject} />
    </>
  )
}
