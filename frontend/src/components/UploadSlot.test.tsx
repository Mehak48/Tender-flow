import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { UploadSlot } from './UploadSlot'
import type { DocumentRecord } from '../api/types'

describe('UploadSlot', () => {
  it('rejects an unsupported file before uploading and explains why', async () => {
    const onUpload = vi.fn()
    render(<UploadSlot role="template" title="Quotation template" record={null} maxMb={25} onUpload={onUpload} />)
    const input = screen.getByLabelText(/choose quotation template/i)
    await userEvent.upload(input, new File(['%PDF-1.4'], 'template.pdf', { type: 'application/pdf' }), { applyAccept: false })
    expect(onUpload).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent('Quotation template must be a DOCX or XLSX file.')
  })

  it('uploads a valid file and shows the backend error if processing fails', async () => {
    const onUpload = vi.fn(async (_file: File, onProgress: (f: number) => void) => {
      onProgress(0.5)
      throw new Error('This Word template could not be read. It may be damaged.')
    })
    render(<UploadSlot role="template" title="Quotation template" record={null} maxMb={25} onUpload={onUpload} />)
    const file = new File(['PK..'], 'template.docx')
    await userEvent.upload(screen.getByLabelText(/choose quotation template/i), file)
    expect(onUpload).toHaveBeenCalledWith(file, expect.any(Function))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('could not be read'))
    expect(screen.getByText('Upload failed')).toBeInTheDocument()
  })

  it('shows facts about an uploaded document', () => {
    const record: DocumentRecord = {
      id: 'doc_0123456789ab',
      role: 'tender',
      filename: 'tender.pdf',
      format: 'pdf',
      size_bytes: 5691,
      sha256: 'x',
      uploaded_at: '2026-10-27T10:00:00Z',
      parse_status: 'parsed',
      parse_error: null,
      page_count: 3,
      block_count: 43,
      table_count: 1,
      warnings: [],
    }
    render(<UploadSlot role="tender" title="Tender document" record={record} maxMb={25} onUpload={vi.fn()} />)
    expect(screen.getByText('tender.pdf')).toBeInTheDocument()
    expect(screen.getByText(/3 pages/)).toBeInTheDocument()
    expect(screen.getByLabelText(/replace tender document/i)).toBeInTheDocument()
  })
})
