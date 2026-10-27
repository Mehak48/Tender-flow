import { useEffect, useState } from 'react'
import { Activity, Check, Download, FileText, RefreshCw, Sparkles, Undo2, Wrench } from 'lucide-react'
import { api } from '../api/client'
import type { ActivityEntry } from '../api/types'
import { EmptyState, Loading, Notice, PageTitle } from '../components/ui'
import { relativeTime } from '../lib/format'
import { projectHref } from '../router'

function iconFor(kind: string) {
  if (kind.startsWith('export')) return <Download size={16} />
  if (kind === 'edit_applied') return <Sparkles size={16} />
  if (kind === 'undo') return <Undo2 size={16} />
  if (kind === 'quick_fix') return <Wrench size={16} />
  if (kind === 'quotation_generated') return <RefreshCw size={16} />
  if (kind.includes('confirmed') || kind.includes('reviewed') || kind.includes('acknowledged')) return <Check size={16} />
  return <FileText size={16} />
}

export function ActivityPage() {
  const [entries, setEntries] = useState<ActivityEntry[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    api
      .libraryActivity()
      .then(setEntries)
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load activity.'))
  }, [])
  return (
    <div className="page">
      <PageTitle
        eyebrow="Audit trail"
        title="Activity history"
        description="What happened in each project — uploads, reviews, confirmations, edits, undos and exports — newest first."
      />
      {error && <Notice tone="error" title="Could not load activity">{error}</Notice>}
      {!entries && !error && <Loading />}
      {entries && entries.length === 0 && (
        <div className="card">
          <EmptyState icon={<Activity size={32} aria-hidden />} title="No activity yet">
            Actions you take in a project are recorded here.
          </EmptyState>
        </div>
      )}
      {entries && entries.length > 0 && (
        <ul className="activity-list">
          {entries.map((e) => (
            <li key={e.event.id}>
              <span className="activity-icon" aria-hidden>
                {iconFor(e.event.kind)}
              </span>
              <div>
                <strong>{e.event.message}</strong>
                <p>
                  <a href={projectHref(e.project_id, 'upload')}>{e.project_name}</a>
                </p>
              </div>
              <time dateTime={e.event.created_at} title={new Date(e.event.created_at).toLocaleString()}>
                {relativeTime(e.event.created_at)}
              </time>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
