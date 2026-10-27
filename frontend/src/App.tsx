import { useEffect, useState, type ReactNode } from 'react'
import {
  Activity,
  Briefcase,
  CircleHelp,
  CirclePlus,
  Cloud,
  FolderOpen,
  LayoutGrid,
  LayoutTemplate,
  Lock,
  Settings as SettingsIcon,
} from 'lucide-react'
import { APP_NAME, SHORT_TAGLINE } from './config'
import { AppProvider, useApp } from './components/AppContext'
import { Modal } from './components/Modal'
import { navigate, useRoute, type Route } from './router'
import { Overview } from './pages/Overview'
import { Projects } from './pages/Projects'
import { Templates } from './pages/Templates'
import { Documents } from './pages/Documents'
import { ActivityPage } from './pages/Activity'
import { SettingsPage } from './pages/Settings'
import { NewQuotation } from './flow/NewQuotation'
import { ProjectFlow } from './flow/ProjectFlow'
import { EmptyState } from './components/ui'
import { HowItWorks } from './components/HowItWorks'

const NAV: { name: Route['name']; label: string; href: string; icon: ReactNode; key?: string }[] = [
  { name: 'overview', label: 'Overview', href: '#/', icon: <LayoutGrid size={18} /> },
  { name: 'projects', label: 'My work', href: '#/projects', icon: <Briefcase size={18} /> },
  { name: 'new', label: 'New quotation', href: '#/new', icon: <CirclePlus size={18} />, key: 'N' },
  { name: 'templates', label: 'Templates', href: '#/templates', icon: <LayoutTemplate size={18} /> },
  { name: 'documents', label: 'Document library', href: '#/documents', icon: <FolderOpen size={18} /> },
  { name: 'activity', label: 'Activity history', href: '#/activity', icon: <Activity size={18} /> },
  { name: 'settings', label: 'Settings', href: '#/settings', icon: <SettingsIcon size={18} /> },
]

function pageTitle(route: Route): string {
  if (route.name === 'project') return 'Quotation'
  if (route.name === 'not_found') return 'Not found'
  return NAV.find((n) => n.name === route.name)?.label ?? APP_NAME
}

function Shell() {
  const route = useRoute()
  const { backend, health } = useApp()
  const [help, setHelp] = useState(false)
  const [crumb, setCrumb] = useState<string | null>(null)

  useEffect(() => {
    document.title = `${pageTitle(route)} · ${APP_NAME}`
    if (route.name !== 'project') setCrumb(null)
  }, [route])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      const typing = t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)
      if (typing || e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key === 'n' || e.key === 'N') {
        e.preventDefault()
        navigate('/new')
      } else if (e.key === '?') {
        setHelp(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const activeNav = route.name === 'project' ? 'projects' : route.name
  const external = health?.ai.mode === 'external'

  return (
    <div className="app">
      <aside className="sidebar" aria-label="Main navigation">
        <a className="brand" href="#/">
          <div className="brand-mark" aria-hidden>
            <span />
            <span />
          </div>
          <div>
            <strong>{APP_NAME}</strong>
            <small>{SHORT_TAGLINE}</small>
          </div>
        </a>
        <nav className="side-nav">
          {NAV.map((item) => (
            <a key={item.name} href={item.href} aria-current={activeNav === item.name ? 'page' : undefined} title={item.label}>
              {item.icon}
              <span>{item.label}</span>
              {item.key && <kbd className="nav-key">{item.key}</kbd>}
            </a>
          ))}
        </nav>
        <div className={`sidebar-note ${external ? 'external' : ''}`} title="AI processing mode">
          {external ? <Cloud size={16} aria-hidden /> : <Lock size={16} aria-hidden />}
          <div>
            <strong>{external ? 'External AI enabled' : 'Local mode'}</strong>
            <small>
              {external
                ? `Unrecognised edit instructions are sent to ${health?.ai.model ?? 'the configured model'}. Documents are not.`
                : 'Rule-based processing on this computer. No document leaves it.'}
            </small>
          </div>
        </div>
        <div className="sidebar-footer">
          {health ? `v${health.version} · MIT licensed` : 'MIT licensed'}
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <span>{APP_NAME}</span>
            <b aria-hidden>/</b>
            <strong>{crumb ?? pageTitle(route)}</strong>
          </div>
          <div className="top-actions">
            <span
              className={`status-pill ${backend === 'offline' ? 'offline' : backend === 'checking' ? 'checking' : ''}`}
              role="status"
              title={backend === 'offline' ? 'Start the backend: uvicorn app.main:app --port 8000' : 'Backend reachable'}
            >
              <i aria-hidden />
              {backend === 'online' ? 'Backend connected' : backend === 'offline' ? 'Backend offline' : 'Connecting…'}
            </span>
            <button className="icon-btn" aria-label="How TenderFlow works" onClick={() => setHelp(true)}>
              <CircleHelp size={19} />
            </button>
          </div>
        </header>
        <main id="main" tabIndex={-1}>
          <RouteView route={route} setCrumb={setCrumb} />
        </main>
      </div>
      {help && (
        <Modal title={`How ${APP_NAME} works`} onClose={() => setHelp(false)} wide>
          <HowItWorks />
        </Modal>
      )}
    </div>
  )
}

function RouteView({ route, setCrumb }: { route: Route; setCrumb: (c: string | null) => void }) {
  switch (route.name) {
    case 'overview':
      return <Overview />
    case 'projects':
      return <Projects />
    case 'new':
      return <NewQuotation />
    case 'project':
      return <ProjectFlow key={route.id} id={route.id} step={route.step} query={route.query} setCrumb={setCrumb} />
    case 'templates':
      return <Templates />
    case 'documents':
      return <Documents />
    case 'activity':
      return <ActivityPage />
    case 'settings':
      return <SettingsPage />
    default:
      return (
        <div className="page">
          <EmptyState icon={<FolderOpen size={32} />} title="Page not found" action={<a className="btn" href="#/">Go to overview</a>}>
            There is nothing at this address.
          </EmptyState>
        </div>
      )
  }
}

export default function App() {
  return (
    <AppProvider>
      <Shell />
    </AppProvider>
  )
}
