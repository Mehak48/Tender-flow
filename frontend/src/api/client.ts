import { API_BASE } from '../config'
import type {
  ActivityEntry,
  ColumnMappingRow,
  EditOperation,
  EditResult,
  EvidenceResponse,
  ExportFormat,
  ExportResponse,
  FieldMappingRow,
  Health,
  LibraryDocument,
  ProjectSummary,
  ProjectView,
  SettingsView,
  TemplateEntry,
  XlsxGrid,
  AppSettings,
  DocumentRole,
} from './types'

/** An error the UI can show as-is: messages come from the backend and are written for people. */
export class ApiError extends Error {
  readonly code: string
  readonly status: number
  constructor(code: string, message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

export const OFFLINE_MESSAGE =
  'Cannot reach the TenderFlow backend. Start it with “uvicorn app.main:app --port 8000” in the backend folder.'

async function parseError(res: Response): Promise<ApiError> {
  try {
    const body = (await res.json()) as { error?: { code?: string; message?: string }; detail?: unknown }
    if (body.error?.message) return new ApiError(body.error.code ?? 'error', body.error.message, res.status)
  } catch {
    // fall through to the generic message
  }
  if (res.status === 502 || res.status === 503 || res.status === 504) {
    return new ApiError('offline', OFFLINE_MESSAGE, res.status)
  }
  return new ApiError('http_error', `The server answered with an error (HTTP ${res.status}).`, res.status)
}

export async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError('offline', OFFLINE_MESSAGE, 0)
  }
  if (!res.ok) throw await parseError(res)
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

/** Upload with real progress events (fetch cannot report upload progress). */
export function uploadDocument(
  projectId: string,
  role: DocumentRole,
  file: File,
  onProgress?: (fraction: number) => void,
): Promise<ProjectView> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${API_BASE}/api/projects/${projectId}/documents`)
    xhr.responseType = 'json'
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total)
    }
    xhr.onload = () => {
      const body = xhr.response as { error?: { code?: string; message?: string } } | ProjectView | null
      if (xhr.status >= 200 && xhr.status < 300 && body) {
        resolve(body as ProjectView)
      } else {
        const err = (body as { error?: { code?: string; message?: string } } | null)?.error
        reject(
          new ApiError(
            err?.code ?? 'upload_failed',
            err?.message ?? (xhr.status === 0 ? OFFLINE_MESSAGE : `Upload failed (HTTP ${xhr.status}).`),
            xhr.status,
          ),
        )
      }
    }
    xhr.onerror = () => reject(new ApiError('offline', OFFLINE_MESSAGE, 0))
    const form = new FormData()
    form.append('role', role)
    form.append('file', file)
    xhr.send(form)
  })
}

export async function fetchBlob(path: string): Promise<Blob> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`)
  } catch {
    throw new ApiError('offline', OFFLINE_MESSAGE, 0)
  }
  if (!res.ok) throw await parseError(res)
  return res.blob()
}

export const downloadUrl = (path: string): string => `${API_BASE}${path}`

const p = (id: string) => `/api/projects/${encodeURIComponent(id)}`

export const api = {
  health: () => request<Health>('GET', '/api/health'),
  settings: () => request<SettingsView>('GET', '/api/settings'),
  saveSettings: (s: Omit<AppSettings, 'updated_at'>) => request<SettingsView>('PUT', '/api/settings', s),
  deleteAllData: () => request<void>('DELETE', '/api/data?confirm=DELETE'),

  listProjects: () => request<ProjectSummary[]>('GET', '/api/projects'),
  createProject: (name?: string) => request<ProjectView>('POST', '/api/projects', { name }),
  createSampleProject: () => request<ProjectView>('POST', '/api/demo/project'),
  getProject: (id: string) => request<ProjectView>('GET', p(id)),
  renameProject: (id: string, name: string) => request<ProjectView>('PATCH', p(id), { name }),
  deleteProject: (id: string) => request<void>('DELETE', p(id)),
  loadSamples: (id: string) => request<ProjectView>('POST', `${p(id)}/samples`),
  deleteDocument: (id: string, docId: string) => request<ProjectView>('DELETE', `${p(id)}/documents/${docId}`),
  evidence: (id: string, docId: string, blockId?: string | null, page?: number | null) => {
    const q = new URLSearchParams()
    if (blockId) q.set('block_id', blockId)
    if (page) q.set('page', String(page))
    return request<EvidenceResponse>('GET', `${p(id)}/documents/${docId}/evidence?${q.toString()}`)
  },
  reuseTemplate: (id: string, docId: string) => request<ProjectView>('POST', `${p(id)}/documents/${docId}/reuse`),

  updateExtraction: (id: string, body: unknown) => request<ProjectView>('PUT', `${p(id)}/extraction`, body),
  confirmAllExtracted: (id: string) => request<ProjectView>('POST', `${p(id)}/extraction/confirm-all`),

  updateMapping: (id: string, fields: FieldMappingRow[], columns: ColumnMappingRow[]) =>
    request<ProjectView>('PUT', `${p(id)}/mapping`, { fields, columns }),
  confirmMapping: (id: string) => request<ProjectView>('POST', `${p(id)}/mapping/confirm`),

  generate: (id: string) => request<ProjectView>('POST', `${p(id)}/quotation/generate`),
  updateQuotation: (id: string, operations: EditOperation[], summary?: string) =>
    request<ProjectView>('PUT', `${p(id)}/quotation`, { operations, summary }),
  undo: (id: string) => request<ProjectView>('POST', `${p(id)}/quotation/undo`),
  proposeEdit: (id: string, instruction: string) =>
    request<EditResult>('POST', `${p(id)}/quotation/edits`, { instruction }),
  applyEdit: (id: string, editId: string, confirmMaterial: boolean) =>
    request<ProjectView>('POST', `${p(id)}/quotation/edits/${editId}/apply`, { confirm_material: confirmMaterial }),
  cancelEdit: (id: string, editId: string) => request<ProjectView>('POST', `${p(id)}/quotation/edits/${editId}/cancel`),
  quickFix: (id: string, fix: string) => request<ProjectView>('POST', `${p(id)}/quotation/fix`, { fix }),
  acknowledge: (id: string, issueId: string, acknowledged: boolean) =>
    request<ProjectView>('POST', `${p(id)}/validation/acknowledge`, { issue_id: issueId, acknowledged }),

  exportQuotation: (id: string, format: ExportFormat, draft: boolean) =>
    request<ExportResponse>('POST', `${p(id)}/export`, { format, draft }),
  deleteExport: (id: string, exportId: string) => request<ProjectView>('DELETE', `${p(id)}/exports/${exportId}`),
  exportDownloadPath: (id: string, exportId: string) => `${p(id)}/exports/${exportId}/download`,
  documentDownloadPath: (id: string, docId: string) => `${p(id)}/documents/${docId}/download`,
  previewDocxPath: (id: string) => `${p(id)}/preview/docx`,
  previewXlsx: (id: string) => request<XlsxGrid>('GET', `${p(id)}/preview/xlsx`),

  libraryTemplates: () => request<TemplateEntry[]>('GET', '/api/library/templates'),
  libraryDocuments: () => request<LibraryDocument[]>('GET', '/api/library/documents'),
  libraryActivity: () => request<ActivityEntry[]>('GET', '/api/library/activity'),
}
