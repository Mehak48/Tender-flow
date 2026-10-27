import type { ProjectView } from '../api/types'

/** Window event used to share a freshly uploaded project with an already-mounted project page. */
export const PROJECT_EVENT = 'tenderflow:project-updated'

export interface FlowProps {
  project: ProjectView
  setProject: (p: ProjectView) => void
  /** Run an API call with busy state + error toast. Resolves to undefined when the call failed. */
  run: <T>(fn: () => Promise<T>, success?: string) => Promise<T | undefined>
  busy: boolean
  query: URLSearchParams
}

export function isProjectView(value: unknown): value is ProjectView {
  return !!value && typeof value === 'object' && 'documents' in value && 'stage' in value && 'id' in value
}
