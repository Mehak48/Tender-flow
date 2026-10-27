import { ORIGIN_HELP, ORIGIN_LABEL } from '../lib/labels'
import type { Origin } from '../api/types'
import { OriginTag } from './ui'

const STEPS = [
  ['Upload', 'Add the tender (PDF/DOCX), your own quotation template (DOCX/XLSX) and, optionally, your price list (XLSX/CSV).'],
  ['Review', 'Check what was found in the tender. Every value links to the exact page and line it came from. Conflicts and gaps are flagged, never guessed.'],
  ['Map', 'Confirm which data goes into which field of your template. Unit prices come only from your price list or from you.'],
  ['Edit', 'Change the draft directly or with an instruction such as “Change the delivery period to 30 days”. You see a preview before anything changes, and you can undo.'],
  ['Validate & export', 'Deterministic checks (arithmetic, missing values, commitments) run on every change. Export a DOCX/XLSX in your template, or PDF when LibreOffice is installed.'],
]

const ORIGINS: Origin[] = ['extracted', 'user', 'price_list', 'company_profile', 'calculated', 'ai_suggestion', 'missing']

export function HowItWorks() {
  return (
    <div className="small">
      <ol style={{ paddingLeft: 18, margin: '8px 0 16px' }}>
        {STEPS.map(([title, text]) => (
          <li key={title} style={{ marginBottom: 8 }}>
            <strong>{title}.</strong> {text}
          </li>
        ))}
      </ol>
      <h3 style={{ fontSize: 14, margin: '0 0 8px' }}>Where each value comes from</h3>
      <dl className="kv">
        {ORIGINS.map((o) => (
          <div key={o} style={{ display: 'contents' }}>
            <dt>
              <OriginTag origin={o} />
            </dt>
            <dd>{ORIGIN_HELP[o]}</dd>
          </div>
        ))}
      </dl>
      <p className="muted" style={{ marginTop: 16 }}>
        TenderFlow prepares drafts for your review. It does not submit bids, verify eligibility or make commitments on
        your behalf. Keyboard: <kbd>N</kbd> new quotation, <kbd>?</kbd> this help.
      </p>
      <span className="sr-only">{Object.values(ORIGIN_LABEL).join(', ')}</span>
    </div>
  )
}
