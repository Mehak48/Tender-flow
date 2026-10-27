import { useEffect, useState } from 'react'
import { Save, Trash2 } from 'lucide-react'
import { api } from '../api/client'
import type { AppSettings, CompanyProfile, SettingsView } from '../api/types'
import { useApp } from '../components/AppContext'
import { Modal } from '../components/Modal'
import { Badge, Button, Loading, Notice, PageTitle, Toggle } from '../components/ui'
import { APP_NAME } from '../config'

type Tab = 'company' | 'defaults' | 'tax' | 'ai' | 'data' | 'about'

const TABS: { key: Tab; label: string }[] = [
  { key: 'company', label: 'Company profile' },
  { key: 'defaults', label: 'Quotation defaults' },
  { key: 'tax', label: 'Tax' },
  { key: 'ai', label: 'AI processing' },
  { key: 'data', label: 'Data & deletion' },
  { key: 'about', label: 'About & licences' },
]

const COMPANY_FIELDS: { key: keyof CompanyProfile; label: string; hint?: string; wide?: boolean }[] = [
  { key: 'name', label: 'Company name', wide: true },
  { key: 'address', label: 'Address', wide: true },
  { key: 'phone', label: 'Phone' },
  { key: 'email', label: 'Email' },
  { key: 'registration', label: 'Registration / tax number', hint: 'Exactly as it should appear, e.g. your NTN or VAT number.' },
  { key: 'prepared_by', label: 'Prepared by', hint: 'Name shown in the authorisation block. TenderFlow never adds a signature.' },
]

const TERM_FIELDS: { key: keyof CompanyProfile; label: string }[] = [
  { key: 'default_payment_terms', label: 'Default payment terms' },
  { key: 'default_delivery_terms', label: 'Default delivery terms' },
  { key: 'default_warranty_terms', label: 'Default warranty' },
  { key: 'default_validity_terms', label: 'Default quotation validity' },
]

export function SettingsPage() {
  const { notify, reportError, refreshHealth } = useApp()
  const [tab, setTab] = useState<Tab>('company')
  const [view, setView] = useState<SettingsView | null>(null)
  const [form, setForm] = useState<AppSettings | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [typed, setTyped] = useState('')
  const [projectCount, setProjectCount] = useState<number | null>(null)

  useEffect(() => {
    api
      .settings()
      .then((v) => {
        setView(v)
        setForm(v.settings)
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load settings.'))
    api.listProjects().then((p) => setProjectCount(p.length)).catch(() => setProjectCount(null))
  }, [])

  if (error) return <div className="page"><Notice tone="error" title="Could not load settings">{error}</Notice></div>
  if (!view || !form) return <Loading />

  const setCompany = (key: keyof CompanyProfile, value: string) =>
    setForm({ ...form, company: { ...form.company, [key]: value || null } })

  async function save() {
    if (!form) return
    setSaving(true)
    try {
      const { updated_at: _ignored, ...body } = form
      const v = await api.saveSettings(body)
      setView(v)
      setForm(v.settings)
      await refreshHealth()
      notify('Settings saved. New quotations use them; regenerate a draft to apply them to it.')
    } catch (e) {
      reportError(e)
    } finally {
      setSaving(false)
    }
  }

  async function deleteAll() {
    try {
      await api.deleteAllData()
      setConfirmDelete(false)
      setTyped('')
      notify('All local projects, files and settings were deleted')
      const v = await api.settings()
      setView(v)
      setForm(v.settings)
      setProjectCount(0)
    } catch (e) {
      reportError(e)
    }
  }

  const ai = view.ai
  return (
    <div className="page">
      <PageTitle
        eyebrow="Workspace"
        title="Settings & privacy"
        description="Defaults used when a quotation is generated. TenderFlow never assumes a currency, tax rate or company detail you have not entered."
        actions={
          tab !== 'data' && tab !== 'about' ? (
            <Button kind="primary" busy={saving} onClick={() => void save()} icon={<Save size={15} aria-hidden />}>
              Save settings
            </Button>
          ) : undefined
        }
      />
      <div className="settings-layout">
        <nav aria-label="Settings sections">
          {TABS.map((t) => (
            <button key={t.key} aria-current={tab === t.key} onClick={() => setTab(t.key)}>
              {t.label}
            </button>
          ))}
        </nav>
        <section>
          {tab === 'company' && (
            <>
              <span className="eyebrow">Your company</span>
              <h2>Company profile</h2>
              <p className="lead">Fills the company fields of your template. Leave a field empty and it is flagged as missing — never invented.</p>
              <div className="form-grid">
                {COMPANY_FIELDS.map((f) => (
                  <label key={f.key} className={`field ${f.wide ? 'span-2' : ''}`}>
                    <span>{f.label}</span>
                    <input className="input" value={form.company[f.key] ?? ''} onChange={(e) => setCompany(f.key, e.target.value)} />
                    {f.hint && <small>{f.hint}</small>}
                  </label>
                ))}
              </div>
            </>
          )}
          {tab === 'defaults' && (
            <>
              <span className="eyebrow">Quotation defaults</span>
              <h2>Currency, numbering and your standard terms</h2>
              <p className="lead">
                Your standard terms are used only when the tender does not state its own requirement. Tender requirements are
                proposed first and always need your confirmation.
              </p>
              <div className="form-grid">
                <label className="field">
                  <span>Default currency</span>
                  <select
                    className="select"
                    value={form.default_currency ?? ''}
                    onChange={(e) => setForm({ ...form, default_currency: e.target.value || null })}
                  >
                    <option value="">Not set — choose per quotation</option>
                    {view.supported_currencies.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                  <small>No currency is assumed. Validation asks for one if this is not set.</small>
                </label>
                <label className="field">
                  <span>Quotation number prefix</span>
                  <input className="input" value={form.quotation_prefix} maxLength={12} onChange={(e) => setForm({ ...form, quotation_prefix: e.target.value })} />
                  <small>Generated numbers look like {form.quotation_prefix || 'QTN'}-YYYYMMDD-XXXX. You can change each one.</small>
                </label>
                {TERM_FIELDS.map((f) => (
                  <label key={f.key} className="field span-2">
                    <span>{f.label}</span>
                    <textarea className="textarea" style={{ minHeight: 60 }} value={form.company[f.key] ?? ''} onChange={(e) => setCompany(f.key, e.target.value)} />
                  </label>
                ))}
              </div>
            </>
          )}
          {tab === 'tax' && (
            <>
              <span className="eyebrow">Tax</span>
              <h2>Optional tax settings</h2>
              <p className="lead">Off by default. TenderFlow never assumes a tax rate or a jurisdiction — enter your own if it applies.</p>
              <div className="setting-row">
                <div>
                  <strong>Apply tax to new quotations</strong>
                  <p>Calculated as subtotal × rate, rounded half-up to 2 decimals.</p>
                </div>
                <Toggle
                  id="tax-enabled"
                  label="Apply tax"
                  checked={form.tax.enabled}
                  onChange={(v) => setForm({ ...form, tax: { ...form.tax, enabled: v } })}
                />
              </div>
              <div className="form-grid" style={{ opacity: form.tax.enabled ? 1 : 0.55 }}>
                <label className="field">
                  <span>Tax label</span>
                  <input
                    className="input"
                    disabled={!form.tax.enabled}
                    placeholder="e.g. Sales tax, GST, VAT"
                    value={form.tax.label ?? ''}
                    onChange={(e) => setForm({ ...form, tax: { ...form.tax, label: e.target.value || null } })}
                  />
                </label>
                <label className="field">
                  <span>Rate (%)</span>
                  <input
                    className="input"
                    disabled={!form.tax.enabled}
                    inputMode="decimal"
                    value={form.tax.rate ?? ''}
                    onChange={(e) => setForm({ ...form, tax: { ...form.tax, rate: e.target.value.trim() || null } })}
                  />
                </label>
              </div>
            </>
          )}
          {tab === 'ai' && (
            <>
              <span className="eyebrow">Processing</span>
              <h2>AI processing</h2>
              <p className="lead">
                Extraction, arithmetic, validation and export never use AI. An optional OpenAI-compatible provider can translate
                edit instructions that the built-in rules do not understand into the same reviewable change previews.
              </p>
              <dl className="kv">
                <dt>Current mode</dt>
                <dd>
                  {ai.mode === 'external' ? <Badge tone="apricot">External provider in use</Badge> : <Badge tone="success">Local rules only</Badge>}
                </dd>
                <dt>Provider configured</dt>
                <dd>{ai.configured ? `Yes — ${ai.provider} · model ${ai.model} · host ${ai.base_url_host}` : 'No (set TENDERFLOW_AI_* in .env)'}</dd>
                <dt>API key present</dt>
                <dd>{ai.api_key_present ? 'Yes (never shown or sent to the browser)' : 'No'}</dd>
              </dl>
              <div className="setting-row" style={{ marginTop: 16 }}>
                <div>
                  <strong>Use the external provider for unrecognised instructions</strong>
                  <p>
                    Sends the instruction plus the quotation's non-company fields and line items (which may include tender text)
                    to {ai.base_url_host ?? 'the provider'}. Uploaded files are never sent. Changes are still previewed and need your approval.
                  </p>
                </div>
                <Toggle
                  id="use-ai"
                  label="Use external AI provider"
                  checked={form.use_external_ai}
                  disabled={!ai.configured}
                  onChange={(v) => setForm({ ...form, use_external_ai: v })}
                />
              </div>
              {!ai.configured && (
                <Notice tone="info" title="How to configure a provider">
                  Copy <code>.env.example</code> to <code>.env</code> in the project folder, set TENDERFLOW_AI_PROVIDER, _BASE_URL and
                  _MODEL (and _API_KEY if needed), then restart the backend. A local server such as Ollama keeps everything on
                  your computer. This integration is unit-tested against a mocked provider only.
                </Notice>
              )}
            </>
          )}
          {tab === 'data' && (
            <>
              <span className="eyebrow">Privacy</span>
              <h2>Data & deletion</h2>
              <p className="lead">Everything is stored on the computer running the backend. Nothing is sent to analytics or logging services.</p>
              <dl className="kv">
                <dt>Location</dt>
                <dd>
                  <code>backend/data/</code> (or the folder set in TENDERFLOW_DATA_DIR)
                </dd>
                <dt>Projects stored</dt>
                <dd>{projectCount ?? '—'}</dd>
                <dt>Uploaded originals</dt>
                <dd>Kept unchanged; exports are written to separate files.</dd>
              </dl>
              <div className="setting-row" style={{ marginTop: 16 }}>
                <div>
                  <strong>Delete all local data</strong>
                  <p>Removes every project, uploaded file, export and these settings. This cannot be undone.</p>
                </div>
                <Button kind="danger" onClick={() => setConfirmDelete(true)} icon={<Trash2 size={15} aria-hidden />}>
                  Delete everything
                </Button>
              </div>
            </>
          )}
          {tab === 'about' && (
            <>
              <span className="eyebrow">About</span>
              <h2>{APP_NAME}</h2>
              <p className="lead">An open-source hackathon prototype (MIT licence). It prepares drafts for human review; it does not submit bids.</p>
              <dl className="kv">
                <dt>PDF export</dt>
                <dd>{view.pdf_export.available ? 'Available (LibreOffice found)' : view.pdf_export.reason}</dd>
                <dt>OCR</dt>
                <dd>Not implemented — scanned PDFs without a text layer cannot be read.</dd>
                <dt>Third-party software</dt>
                <dd>
                  React, Vite, Tailwind CSS, lucide-react (ISC), docx-preview (Apache-2.0), DM Sans & Manrope fonts (OFL), FastAPI,
                  pdfplumber, python-docx, openpyxl. Full list in the README.
                </dd>
              </dl>
            </>
          )}
        </section>
      </div>
      {confirmDelete && (
        <Modal
          title="Delete all local data?"
          onClose={() => setConfirmDelete(false)}
          actions={
            <>
              <Button onClick={() => setConfirmDelete(false)}>Cancel</Button>
              <Button kind="danger" disabled={typed !== 'DELETE'} onClick={() => void deleteAll()}>
                Delete everything
              </Button>
            </>
          }
        >
          <p className="small">Type DELETE to confirm. All projects, files, exports and settings on this computer will be removed.</p>
          <label className="field">
            <span>Confirmation</span>
            <input className="input" value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="DELETE" />
          </label>
        </Modal>
      )}
    </div>
  )
}
