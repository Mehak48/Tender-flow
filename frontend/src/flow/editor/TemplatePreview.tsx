import { useEffect, useRef, useState } from 'react'
import { api, fetchBlob } from '../../api/client'
import type { XlsxGrid } from '../../api/types'
import { errorMessage } from '../../components/AppContext'
import { Loading, Notice } from '../../components/ui'

/**
 * Renders the quotation filled into the user's real template. For DOCX the backend generates a draft file
 * and docx-preview (Apache-2.0) renders it in the browser; for XLSX a simple cell grid is shown.
 * Rendering is approximate — Word/Excel remain the reference.
 */
export function TemplatePreview({ projectId, format, version }: { projectId: string; format: 'docx' | 'xlsx'; version: string | number }) {
  const container = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [error, setError] = useState<string | null>(null)
  const [grid, setGrid] = useState<XlsxGrid | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setState('loading')
      try {
        if (format === 'docx') {
          const blob = await fetchBlob(api.previewDocxPath(projectId))
          const { renderAsync } = await import('docx-preview')
          if (cancelled || !container.current) return
          container.current.innerHTML = ''
          await renderAsync(blob, container.current, undefined, {
            inWrapper: true,
            ignoreLastRenderedPageBreak: true,
            experimental: false,
            useBase64URL: true,
          })
        } else {
          const g = await api.previewXlsx(projectId)
          if (cancelled) return
          setGrid(g)
        }
        if (!cancelled) setState('ready')
      } catch (e) {
        if (!cancelled) {
          setError(errorMessage(e))
          setState('error')
        }
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [projectId, format, version])

  return (
    <div>
      <div style={{ maxWidth: 820, margin: '0 auto 10px' }}>
        <Notice tone="info">
          Preview of your template filled with the current draft. Missing values appear as [MISSING: …]. Layout rendering
          in the browser is approximate — open the exported file in Word or Excel for the exact result.
        </Notice>
      </div>
      {state === 'loading' && <Loading label="Filling your template…" />}
      {state === 'error' && <Notice tone="error" title="The template preview could not be rendered">{error}</Notice>}
      {format === 'docx' ? (
        <div ref={container} className="docx-render" style={{ display: state === 'ready' ? 'block' : 'none' }} />
      ) : (
        state === 'ready' &&
        grid && (
          <div className="grid-preview" style={{ background: '#fff', maxWidth: 1000, margin: '0 auto' }}>
            <table>
              <caption className="sr-only">Sheet {grid.sheet}</caption>
              <tbody>
                {grid.rows.map((row, r) => (
                  <tr key={r}>
                    <td className="muted tiny">{r + 1}</td>
                    {row.map((cell, c) => (
                      <td key={c} style={cell.startsWith('[MISSING') ? { background: 'var(--color-warning-soft)' } : undefined}>
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
    </div>
  )
}
