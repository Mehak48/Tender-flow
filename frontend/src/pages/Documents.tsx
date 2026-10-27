import { useEffect, useMemo, useState } from 'react'
import { Download, FileText, FolderOpen, Search } from 'lucide-react'
import { api, downloadUrl } from '../api/client'
import type { LibraryDocument } from '../api/types'
import { Badge, EmptyState, Loading, Notice, PageTitle } from '../components/ui'
import { formatBytes, relativeTime } from '../lib/format'
import { projectHref } from '../router'

const KIND_LABEL: Record<LibraryDocument['kind'], string> = {
  tender: 'Tender',
  template: 'Template',
  price_list: 'Price list',
  export: 'Generated quotation',
}

export function Documents() {
  const [docs, setDocs] = useState<LibraryDocument[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [kind, setKind] = useState<'all' | LibraryDocument['kind']>('all')

  useEffect(() => {
    api
      .libraryDocuments()
      .then(setDocs)
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load documents.'))
  }, [])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return (docs ?? []).filter(
      (d) => (kind === 'all' || d.kind === kind) && (!q || d.filename.toLowerCase().includes(q) || d.project_name.toLowerCase().includes(q)),
    )
  }, [docs, query, kind])

  return (
    <div className="page">
      <PageTitle
        eyebrow="Workspace"
        title="Document library"
        description="Every uploaded file and every generated quotation, stored locally. Originals are never modified."
      />
      {error && <Notice tone="error" title="Could not load documents">{error}</Notice>}
      {!docs && !error && <Loading />}
      {docs && docs.length === 0 && (
        <div className="card">
          <EmptyState icon={<FolderOpen size={32} aria-hidden />} title="No documents yet" action={<a className="btn primary" href="#/new">Create quotation</a>}>
            Uploaded tenders, templates, price lists and exported quotations will be listed here.
          </EmptyState>
        </div>
      )}
      {docs && docs.length > 0 && (
        <>
          <div className="library-tools">
            <label className="search">
              <Search size={16} aria-hidden />
              <span className="sr-only">Search documents</span>
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by file or project" />
            </label>
            <label className="sr-only" htmlFor="doc-kind">
              Document type
            </label>
            <select id="doc-kind" className="select" value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}>
              <option value="all">All document types</option>
              <option value="tender">Tenders</option>
              <option value="template">Templates</option>
              <option value="price_list">Price lists</option>
              <option value="export">Generated quotations</option>
            </select>
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">File name</th>
                  <th scope="col">Project</th>
                  <th scope="col">Type</th>
                  <th scope="col">Size</th>
                  <th scope="col">Added</th>
                  <th scope="col">Status</th>
                  <th scope="col">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={7} className="muted">
                      No document matches the filters.
                    </td>
                  </tr>
                )}
                {filtered.map((d) => (
                  <tr key={`${d.kind}-${d.id}`}>
                    <td>
                      <span className="file-cell">
                        <span className="doc-mini" aria-hidden>
                          <FileText size={15} />
                        </span>
                        <strong>{d.filename}</strong>
                      </span>
                    </td>
                    <td>
                      <a href={projectHref(d.project_id, d.kind === 'export' ? 'export' : 'upload')}>{d.project_name}</a>
                    </td>
                    <td>{KIND_LABEL[d.kind]}</td>
                    <td>{formatBytes(d.size_bytes)}</td>
                    <td title={new Date(d.created_at).toLocaleString()}>{relativeTime(d.created_at)}</td>
                    <td>
                      <Badge tone={d.status === 'Final' ? 'success' : d.status === 'Draft' || d.status.includes('warnings') ? 'warning' : 'neutral'}>
                        {d.status}
                      </Badge>
                    </td>
                    <td>
                      <div className="cell-actions">
                        <a className="icon-btn" href={downloadUrl(d.download_url)} download={d.filename} aria-label={`Download ${d.filename}`}>
                          <Download size={16} />
                        </a>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
