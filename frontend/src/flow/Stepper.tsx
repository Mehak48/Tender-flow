import { Check } from 'lucide-react'
import type { ProjectView } from '../api/types'
import { STEPS, projectHref, type StepKey } from '../router'

export function stepAvailability(project: ProjectView | null): Record<StepKey, boolean> {
  const hasTender = !!project?.extraction
  const hasTemplate = !!project?.template
  const hasQuotation = !!project?.quotation
  return {
    upload: true,
    review: hasTender,
    mapping: hasTender && hasTemplate,
    editor: hasQuotation,
    export: hasQuotation,
  }
}

function stepDone(project: ProjectView | null, key: StepKey): boolean {
  if (!project) return false
  switch (key) {
    case 'upload':
      return project.documents.some((d) => d.role === 'tender') && project.documents.some((d) => d.role === 'template')
    case 'review':
      return !!project.extraction?.reviewed
    case 'mapping':
      return !!project.mapping?.mapping.confirmed && !!project.quotation
    case 'editor':
      return !!project.validation && project.validation.errors === 0
    case 'export':
      return project.exports.some((e) => !e.draft)
  }
}

export function Stepper({ current, project }: { current: StepKey; project: ProjectView | null }) {
  const available = stepAvailability(project)
  return (
    <nav className="stepper" aria-label="Quotation steps">
      <ol>
        {STEPS.map((s, i) => {
          const isCurrent = s.key === current
          const done = stepDone(project, s.key)
          const cls = isCurrent ? 'current' : done ? 'done' : available[s.key] ? '' : 'locked'
          const content = (
            <>
              <span className="dot">{done && !isCurrent ? <Check size={14} aria-hidden /> : i + 1}</span>
              <span className="label">{s.label}</span>
            </>
          )
          return (
            <li key={s.key} style={{ display: 'flex', alignItems: 'center' }}>
              {project && available[s.key] && !isCurrent ? (
                <a className={cls} href={projectHref(project.id, s.key)}>
                  {content}
                  {done && <span className="sr-only"> (completed)</span>}
                </a>
              ) : (
                <span className={`step ${cls}`} aria-current={isCurrent ? 'step' : undefined}>
                  {content}
                  {!available[s.key] && <span className="sr-only"> (not available yet)</span>}
                </span>
              )}
              {i < STEPS.length - 1 && <span className="line" aria-hidden />}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
