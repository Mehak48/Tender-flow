import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { CheckCircle2, XCircle } from 'lucide-react'
import { ApiError, api } from '../api/client'
import type { Health } from '../api/types'

interface Toast {
  id: number
  message: string
  tone: 'success' | 'error'
}

interface AppState {
  health: Health | null
  backend: 'checking' | 'online' | 'offline'
  refreshHealth: () => Promise<void>
  notify: (message: string, tone?: 'success' | 'error') => void
  reportError: (error: unknown) => void
}

const Ctx = createContext<AppState | null>(null)

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Something went wrong.'
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [health, setHealth] = useState<Health | null>(null)
  const [backend, setBackend] = useState<AppState['backend']>('checking')
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(1)

  const refreshHealth = useCallback(async () => {
    try {
      const h = await api.health()
      setHealth(h)
      setBackend('online')
    } catch {
      setBackend('offline')
    }
  }, [])

  useEffect(() => {
    void refreshHealth()
    const timer = window.setInterval(() => void refreshHealth(), 30000)
    return () => window.clearInterval(timer)
  }, [refreshHealth])

  const notify = useCallback((message: string, tone: 'success' | 'error' = 'success') => {
    const id = nextId.current++
    setToasts((t) => [...t.slice(-2), { id, message, tone }])
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), tone === 'error' ? 6500 : 2800)
  }, [])

  const reportError = useCallback(
    (error: unknown) => {
      if (error instanceof ApiError && error.code === 'offline') setBackend('offline')
      notify(errorMessage(error), 'error')
    },
    [notify],
  )

  const value = useMemo(
    () => ({ health, backend, refreshHealth, notify, reportError }),
    [health, backend, refreshHealth, notify, reportError],
  )
  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="toast-stack" aria-live="polite" aria-atomic="false">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.tone === 'error' ? 'error' : ''}`} role={t.tone === 'error' ? 'alert' : 'status'}>
            {t.tone === 'error' ? <XCircle size={17} aria-hidden /> : <CheckCircle2 size={17} aria-hidden />}
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  )
}

export function useApp(): AppState {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useApp must be used inside <AppProvider>')
  return ctx
}
