import { useEffect, useState } from 'react'

/** Tiny hash router: no dependency needed for a handful of routes, and refresh / back both work. */

export type StepKey = 'upload' | 'review' | 'mapping' | 'editor' | 'export'
export const STEPS: { key: StepKey; label: string }[] = [
  { key: 'upload', label: 'Upload documents' },
  { key: 'review', label: 'Review extracted data' },
  { key: 'mapping', label: 'Map fields' },
  { key: 'editor', label: 'Edit quotation' },
  { key: 'export', label: 'Validate & export' },
]

export type Route =
  | { name: 'overview' }
  | { name: 'projects' }
  | { name: 'new' }
  | { name: 'project'; id: string; step: StepKey; query: URLSearchParams }
  | { name: 'templates' }
  | { name: 'documents' }
  | { name: 'activity' }
  | { name: 'settings' }
  | { name: 'not_found'; path: string }

const STEP_KEYS = new Set(STEPS.map((s) => s.key))

export function parseHash(hash: string): Route {
  const raw = hash.replace(/^#/, '') || '/'
  const [pathPart, queryPart = ''] = raw.split('?')
  const parts = pathPart.split('/').filter(Boolean)
  const query = new URLSearchParams(queryPart)
  if (parts.length === 0) return { name: 'overview' }
  const [head, a, b] = parts
  switch (head) {
    case 'projects':
      return { name: 'projects' }
    case 'new':
      return { name: 'new' }
    case 'templates':
      return { name: 'templates' }
    case 'documents':
      return { name: 'documents' }
    case 'activity':
      return { name: 'activity' }
    case 'settings':
      return { name: 'settings' }
    case 'p':
      if (a && /^prj_[0-9a-f]{12}$/.test(a)) {
        const step = (b && STEP_KEYS.has(b as StepKey) ? b : 'upload') as StepKey
        return { name: 'project', id: a, step, query }
      }
      return { name: 'not_found', path: raw }
    default:
      return { name: 'not_found', path: raw }
  }
}

export function href(route: string): string {
  return `#${route.startsWith('/') ? route : `/${route}`}`
}

export function projectHref(id: string, step: StepKey, query?: Record<string, string>): string {
  const q = query ? `?${new URLSearchParams(query).toString()}` : ''
  return `#/p/${id}/${step}${q}`
}

export function navigate(to: string, replace = false): void {
  const target = to.startsWith('#') ? to : href(to)
  if (replace) {
    window.history.replaceState(null, '', target)
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  } else {
    window.location.hash = target
  }
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash))
  useEffect(() => {
    const onChange = () => setRoute(parseHash(window.location.hash))
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route
}

export function stepForStage(stage: string): StepKey {
  switch (stage) {
    case 'extraction':
      return 'review'
    case 'mapping':
      return 'mapping'
    case 'editor':
      return 'editor'
    case 'export':
      return 'export'
    default:
      return 'upload'
  }
}
