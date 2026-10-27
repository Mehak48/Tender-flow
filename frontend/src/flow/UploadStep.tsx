import { useState } from 'react'
import { ArrowRight, Lock, Sparkles, Trash2 } from 'lucide-react'
import { api, uploadDocument } from '../api/client'
import type { DocumentRecord, DocumentRole, ProjectView } from '../api/types'
import { useApp } from '../components/AppContext'
import { Badge, Button, Notice, PageTitle } from '../components/ui'
import { UploadSlot } from '../components/UploadSlot'
import { DEFAULT_MAX_UPLOAD_MB } from '../config'
import { formatsText } from '../lib/files'
import { navigate, projectHref } from '../router'

const CARDS: { role: DocumentRole; number: string; title: string; text: string; optional?: boolean }[] = [
  {
    role: 'tender',
    number: '01',
    title: 'Tender document',
    text: 'The document with the requirements, quantities, deadlines and terms. It is the source of truth.',
  },
  {
    role: 'template',
    number: '02',
    title: 'Quotation template',
    text: 'Your own format. Use {{placeholders}} or “Label: ____” blanks and an items table with a header row.',
  },
  {
    role: 'price_list',
    number: '03',
    title: 'Price list',
    text: 'Optional. Rows with an item name and unit price. Prices are matched by name and need your confirmation.',
    optional: true,
  },
]

/**
 * Step 1. Works with or without a project: the project is only created once the first file is added,
 * so abandoned "new quotation" screens never leave empty projects behind.
 */
export function UploadStep({
  project,
  onProject,
  ensureProject,
}: {
  project: ProjectView | null
  onProject: (p: ProjectView) => void
  ensureProject: () => Promise<ProjectView>
}) {
  const { health, notify, reportError } = useApp()
  const [sampleBusy, setSampleBusy] = useState(false)
  const [removing, setRemoving] = useState<string | null>(null)
  const maxMb = health?.limits.max_upload_mb ?? DEFAULT_MAX_UPLOAD_MB
  const docs: Partial<Record<DocumentRole, DocumentRecord>> = {}
  for (const d of project?.documents ?? []) docs[d.role] = d

  async function upload(role: DocumentRole, file: File, onProgress: (f: number) => void) {
    const p = await ensureProject()
    const updated = await uploadDocument(p.id, role, file, onProgress)
    onProject(updated)
    notify(`${file.name} was read`)
  }

  async function useSamples() {
    setSampleBusy(true)
    try {
      const p = await ensureProject()
      const updated = await api.loadSamples(p.id)
      onProject(updated)
      notify('Sample documents loaded (fictional data)')
    } catch (e) {
      reportError(e)
    } finally {
      setSampleBusy(false)
    }
  }

  async function remove(record: DocumentRecord) {
    if (!project) return
    setRemoving(record.id)
    try {
      onProject(await api.deleteDocument(project.id, record.id))
    } catch (e) {
      reportError(e)
    } finally {
      setRemoving(null)
    }
  }

  const ready = Boolean(docs.tender && docs.template)
  return (
    <div className="flow-content" style={{ paddingInline: 24 }}>
      <PageTitle
        eyebrow="Step 1 of 5"
        title="Add your source documents"
        description="TenderFlow reads the tender as the source of truth and keeps your quotation template's structure."
      />
      {project?.quotation && (
        <Notice tone="warning" title="A quotation draft already exists">
          Replacing a document marks the draft as out of date. You can regenerate it from the mapping step (your current
          draft stays available through Undo).
        </Notice>
      )}
      <div className="dual-upload" style={{ marginTop: project?.quotation ? 16 : 0 }}>
        {CARDS.map((card) => {
          const record = docs[card.role] ?? null
          return (
            <section className="upload-card" key={card.role} aria-labelledby={`card-${card.role}`}>
              <span className="number" aria-hidden>
                {card.number}
              </span>
              <h3 id={`card-${card.role}`}>
                {card.title} {card.optional && <Badge>Optional</Badge>}
              </h3>
              <p>{card.text}</p>
              <UploadSlot
                role={card.role}
                title={`Choose ${card.title.toLowerCase()}`}
                record={record}
                maxMb={maxMb}
                onUpload={(f, onProgress) => upload(card.role, f, onProgress)}
              />
              {record && (
                <>
                  <div className="file-facts">
                    {record.page_count !== null && <Badge>{record.page_count} pages</Badge>}
                    {card.role !== 'template' && <Badge>{record.block_count} text blocks</Badge>}
                    {card.role !== 'template' && record.table_count > 0 && (
                      <Badge>
                        {record.table_count} table{record.table_count === 1 ? '' : 's'}
                      </Badge>
                    )}
                    {card.role === 'template' && <Badge>{record.block_count} fill-in fields</Badge>}
                    {card.role === 'tender' && project?.extraction && (
                      <Badge tone="lavender">{project.extraction.line_items.length} line items found</Badge>
                    )}
                    {card.role === 'price_list' && project?.price_list && (
                      <Badge tone="lavender">{project.price_list.rows.length} priced rows</Badge>
                    )}
                  </div>
                  {record.warnings.length > 0 && (
                    <ul className="file-warnings">
                      {record.warnings.map((w) => (
                        <li key={w}>{w}</li>
                      ))}
                    </ul>
                  )}
                  <div>
                    <Button
                      kind="quiet"
                      small
                      busy={removing === record.id}
                      onClick={() => void remove(record)}
                      icon={<Trash2 size={14} aria-hidden />}
                    >
                      Remove file
                    </Button>
                  </div>
                </>
              )}
              {!record && <p className="tiny muted">Accepted: {formatsText(card.role)}</p>}
            </section>
          )
        })}
      </div>

      <div className="demo-banner">
        <Sparkles size={18} aria-hidden />
        <div>
          <strong>Try it with the sample documents</strong>
          <p>
            A fictional tender (PDF), a quotation template (DOCX) and a price list (XLSX). They go through exactly the same
            processing as your own files.
          </p>
        </div>
        <Button onClick={useSamples} busy={sampleBusy}>
          Load sample documents
        </Button>
      </div>

      <Notice tone="neutral">
        <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <Lock size={14} aria-hidden /> Files are stored on this computer in the backend data folder and are never sent to
          an external service in local mode. Review extracted information before generating a quotation.
        </span>
      </Notice>

      <div className="flow-actions">
        <span>{ready ? 'Both required documents are ready.' : 'The tender and the quotation template are both required.'}</span>
        <div className="right">
          <Button
            kind="primary"
            disabled={!ready || !project}
            onClick={() => project && navigate(projectHref(project.id, 'review'))}
          >
            Review extracted data <ArrowRight size={15} aria-hidden />
          </Button>
        </div>
      </div>
    </div>
  )
}
