import { useId, useState, type DragEvent } from 'react'
import { AlertCircle, Check, Loader2, Upload } from 'lucide-react'
import type { DocumentRecord, DocumentRole } from '../api/types'
import { errorMessage } from './AppContext'
import { acceptAttribute, formatsText, validateFile } from '../lib/files'
import { formatBytes } from '../lib/format'

export type UploadHandler = (file: File, onProgress: (fraction: number) => void) => Promise<void>

/**
 * A real drop zone + file picker. Shows true upload progress, then "Reading…" while the backend parses,
 * then the parsed facts — or the backend's error message. Nothing here is simulated.
 */
export function UploadSlot({
  role,
  title,
  record,
  maxMb,
  onUpload,
  disabled,
  compact,
}: {
  role: DocumentRole
  title: string
  record: DocumentRecord | null
  maxMb: number
  onUpload: UploadHandler
  disabled?: boolean
  compact?: boolean
}) {
  const inputId = useId()
  const hintId = useId()
  const [dragging, setDragging] = useState(false)
  const [progress, setProgress] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handle(file: File | undefined) {
    if (!file || disabled) return
    const problem = validateFile(role, file, maxMb)
    if (problem) {
      setError(problem)
      return
    }
    setError(null)
    setProgress(0)
    try {
      await onUpload(file, (f) => setProgress(f))
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setProgress(null)
    }
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragging(false)
    void handle(e.dataTransfer.files?.[0])
  }

  const uploading = progress !== null
  const state = uploading ? '' : error ? 'failed' : record ? 'selected' : ''
  const formats = `${formatsText(role)} · max ${maxMb} MB`

  let headline = title
  let sub = 'Drag & drop or click to choose a file'
  if (uploading) {
    headline = progress !== null && progress < 1 ? `Uploading… ${Math.round((progress ?? 0) * 100)}%` : 'Reading the document…'
    sub = progress !== null && progress < 1 ? 'Sending the file to your local TenderFlow backend' : 'Extracting text and structure'
  } else if (error) {
    headline = 'Upload failed'
    sub = error
  } else if (record) {
    headline = record.filename
    const facts = [formatBytes(record.size_bytes), record.format.toUpperCase()]
    if (record.page_count) facts.push(`${record.page_count} pages`)
    sub = `${facts.join(' · ')} · Ready — click or drop to replace`
  }

  return (
    <div
      className={`upload-slot ${state} ${dragging ? 'dragging' : ''}`}
      onDragOver={(e) => {
        e.preventDefault()
        if (!disabled) setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      style={compact ? { minHeight: 96 } : undefined}
    >
      <span className="upload-icon" aria-hidden>
        {uploading ? (
          <Loader2 size={20} className="spinner" />
        ) : error ? (
          <AlertCircle size={20} />
        ) : record ? (
          <Check size={20} />
        ) : (
          <Upload size={20} />
        )}
      </span>
      <span className="upload-copy">
        <strong>{headline}</strong>
        <small role={error ? 'alert' : undefined}>{sub}</small>
        <em id={hintId}>{formats}</em>
        {uploading && (
          <span className="progress" aria-hidden>
            <i style={{ width: `${Math.round((progress ?? 0) * 100)}%` }} />
          </span>
        )}
      </span>
      <label htmlFor={inputId} className="sr-only">
        {record ? `Replace ${title.toLowerCase()}` : `Choose ${title.toLowerCase()}`}
      </label>
      <input
        id={inputId}
        type="file"
        accept={acceptAttribute(role)}
        disabled={disabled || uploading}
        aria-describedby={hintId}
        onChange={(e) => {
          const f = e.target.files?.[0]
          e.target.value = ''
          void handle(f)
        }}
      />
    </div>
  )
}
