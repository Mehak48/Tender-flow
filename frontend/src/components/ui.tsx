import type { ReactNode } from 'react'
import { AlertTriangle, CheckCircle2, Info, Loader2, XCircle } from 'lucide-react'
import type { FieldStatus, Origin } from '../api/types'
import { ORIGIN_HELP, ORIGIN_LABEL, STATUS_META, type Tone } from '../lib/labels'

type ButtonKind = 'primary' | 'secondary' | 'quiet' | 'danger'

export function Button({
  children,
  kind = 'secondary',
  small,
  block,
  busy,
  icon,
  type = 'button',
  ...rest
}: {
  children?: ReactNode
  kind?: ButtonKind
  small?: boolean
  block?: boolean
  busy?: boolean
  icon?: ReactNode
  type?: 'button' | 'submit'
} & Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'type'>) {
  const cls = ['btn', kind !== 'secondary' ? kind : '', small ? 'small' : '', block ? 'block' : '', rest.className ?? '']
    .filter(Boolean)
    .join(' ')
  return (
    <button {...rest} type={type} className={cls} disabled={rest.disabled || busy} aria-busy={busy || undefined}>
      {busy ? <Loader2 size={15} className="spinner" aria-hidden /> : icon}
      {children}
    </button>
  )
}

export function Badge({ children, tone = 'neutral', title }: { children: ReactNode; tone?: Tone; title?: string }) {
  return (
    <span className={`badge ${tone}`} title={title}>
      <span className="badge-dot" aria-hidden />
      {children}
    </span>
  )
}

export function StatusBadge({ status }: { status: FieldStatus }) {
  const meta = STATUS_META[status]
  return <Badge tone={meta.tone}>{meta.label}</Badge>
}

export function OriginTag({ origin, detail }: { origin: Origin; detail?: string | null }) {
  return (
    <span className={`origin ${origin}`} title={detail ? `${ORIGIN_HELP[origin]} ${detail}` : ORIGIN_HELP[origin]}>
      {ORIGIN_LABEL[origin]}
    </span>
  )
}

export function PageTitle({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string
  title: string
  description?: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="page-title">
      <div>
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  )
}

const NOTICE_ICON = {
  info: <Info size={17} aria-hidden />,
  warning: <AlertTriangle size={17} aria-hidden />,
  error: <XCircle size={17} aria-hidden />,
  success: <CheckCircle2 size={17} aria-hidden />,
  neutral: <Info size={17} aria-hidden />,
}

export function Notice({
  tone = 'info',
  title,
  children,
  actions,
  role,
}: {
  tone?: 'info' | 'warning' | 'error' | 'success' | 'neutral'
  title?: ReactNode
  children?: ReactNode
  actions?: ReactNode
  role?: 'alert' | 'status'
}) {
  return (
    <div className={`notice ${tone === 'neutral' ? '' : tone}`} role={role ?? (tone === 'error' ? 'alert' : undefined)}>
      {NOTICE_ICON[tone]}
      <div>
        {title && <strong>{title}</strong>}
        {children && (typeof children === 'string' ? <p>{children}</p> : children)}
      </div>
      {actions && <div className="notice-actions">{actions}</div>}
    </div>
  )
}

export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon: ReactNode
  title: string
  children?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="empty-state">
      {icon}
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  )
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="loading-block" role="status">
      <Loader2 size={18} className="spinner" aria-hidden /> {label}
    </div>
  )
}

export function Toggle({
  checked,
  onChange,
  label,
  disabled,
  id,
}: {
  checked: boolean
  onChange: (value: boolean) => void
  label: string
  disabled?: boolean
  id?: string
}) {
  return (
    <label className="toggle" htmlFor={id}>
      <input id={id} type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <span className="track" aria-hidden />
      <span className="sr-only">{label}</span>
    </label>
  )
}
