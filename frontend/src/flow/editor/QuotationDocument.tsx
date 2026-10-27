import { useEffect, useRef, useState } from 'react'
import { Check, Pencil, Plus, Trash2 } from 'lucide-react'
import type { EditOperation, Origin, Quotation, QuotationLineItem } from '../../api/types'
import { formatMoney, formatQuantity } from '../../lib/format'
import { DocField, OriginDot } from './DocField'

type Save = (ops: EditOperation[], summary: string) => Promise<unknown>
type ItemAttr = 'description' | 'specification' | 'quantity' | 'unit' | 'unit_price' | 'amount_override'

const COMMITMENT_KEYS = ['delivery_terms', 'payment_terms', 'warranty_terms', 'validity_terms'] as const

/** The quotation as a readable business document whose values can be edited in place. */
export function QuotationDocument({
  q,
  save,
  busy,
  currencies,
  focusItemId,
}: {
  q: Quotation
  save: Save
  busy: boolean
  currencies: string[]
  focusItemId: string | null
}) {
  const f = q.fields
  const setField = (key: string, label: string) => (value: string | null) =>
    save([{ op: 'set_field', field_key: key, value }], `${label} edited`)
  const company = f.company_name?.value ?? ''
  const initials =
    company
      .split(/\s+/)
      .filter((w) => /^[A-Za-z]/.test(w))
      .slice(0, 2)
      .map((w) => w[0]!.toUpperCase())
      .join('') || '—'
  const unconfirmedTerms = COMMITMENT_KEYS.filter((k) => f[k]?.value && !f[k]?.confirmed)

  return (
    <article className="quotation" aria-label="Quotation preview">
      <section id="sec-company" className="q-header">
        <div className="q-company">
          <span className="q-logo" aria-hidden>
            {initials}
          </span>
          <div className="q-company-lines">
            <strong style={{ fontSize: 15, color: '#222' }}>
              <DocField field={f.company_name} fieldKey="company_name" label="Company name" onSave={setField('company_name', 'Company name')} />
            </strong>
            <DocField field={f.company_address} fieldKey="company_address" label="Company address" onSave={setField('company_address', 'Company address')} />
            <span>
              <DocField field={f.company_phone} fieldKey="company_phone" label="Phone" onSave={setField('company_phone', 'Phone')} />
              {' · '}
              <DocField field={f.company_email} fieldKey="company_email" label="Email" onSave={setField('company_email', 'Email')} />
            </span>
            <span>
              Reg.{' '}
              <DocField
                field={f.company_registration}
                fieldKey="company_registration"
                label="Registration no."
                onSave={setField('company_registration', 'Registration no.')}
              />
            </span>
          </div>
        </div>
        <div className="q-meta" id="sec-details">
          <h2>
            <DocField field={f.quotation_title} fieldKey="quotation_title" label="Title" onSave={setField('quotation_title', 'Title')} />
          </h2>
          <dl>
            <dt>Quotation no.</dt>
            <dd>
              <DocField field={f.quotation_number} fieldKey="quotation_number" label="Quotation number" onSave={setField('quotation_number', 'Quotation number')} />
            </dd>
            <dt>Date</dt>
            <dd>
              <DocField field={f.quotation_date} fieldKey="quotation_date" label="Date" onSave={setField('quotation_date', 'Date')} />
            </dd>
            <dt>Valid until</dt>
            <dd>
              <DocField field={f.valid_until} fieldKey="valid_until" label="Valid until" onSave={setField('valid_until', 'Valid until')} />
            </dd>
            <dt>Currency</dt>
            <dd data-field="currency">
              <span className="df">
                <OriginDot origin={q.currency ? q.currency_origin : 'missing'} />
                <label className="sr-only" htmlFor="q-currency">
                  Currency
                </label>
                <select
                  id="q-currency"
                  value={q.currency ?? ''}
                  disabled={busy}
                  onChange={(e) => e.target.value && void save([{ op: 'set_currency', currency: e.target.value }], `Currency set to ${e.target.value}`)}
                  className={q.currency ? '' : 'df-missing'}
                  style={{ border: q.currency ? '1px solid #ddd' : undefined, borderRadius: 3, fontSize: 12, padding: '1px 4px', background: q.currency ? '#fff' : undefined }}
                >
                  <option value="">Choose…</option>
                  {currencies.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </span>
            </dd>
          </dl>
        </div>
      </section>

      <section id="sec-buyer" className="q-info">
        <div>
          <small>Prepared for</small>
          <strong style={{ display: 'block', fontSize: 13.5 }}>
            <DocField field={f.buyer_name} fieldKey="buyer_name" label="Buyer" onSave={setField('buyer_name', 'Buyer')} block />
          </strong>
          <DocField field={f.buyer_address} fieldKey="buyer_address" label="Buyer address" onSave={setField('buyer_address', 'Buyer address')} block />
        </div>
        <div>
          <small>Tender reference</small>
          <DocField field={f.tender_reference} fieldKey="tender_reference" label="Tender reference" onSave={setField('tender_reference', 'Tender reference')} block />
          <small style={{ marginTop: 10 }}>Subject</small>
          <DocField field={f.tender_title} fieldKey="tender_title" label="Subject" onSave={setField('tender_title', 'Subject')} block />
        </div>
      </section>

      <section id="sec-items">
        <ItemsTable q={q} save={save} busy={busy} focusItemId={focusItemId} />
      </section>

      <section id="sec-totals" className="q-totals" aria-label="Totals">
        <p>
          <span>Subtotal</span>
          <b>
            <OriginDot origin={q.subtotal ? 'calculated' : 'missing'} /> {formatMoney(q.subtotal) ?? 'Pending'}
          </b>
        </p>
        <p>
          <span>{q.tax.enabled ? f.tax_label?.value ?? 'Tax' : 'Tax'}</span>
          <b>{q.tax.enabled ? formatMoney(q.tax_amount) ?? 'Pending' : 'Not applied'}</b>
        </p>
        <p className="grand">
          <span>Total {q.currency ? `(${q.currency})` : ''}</span>
          <b>{formatMoney(q.total) ?? 'Pending'}</b>
        </p>
      </section>

      <section id="sec-terms" className="q-terms">
        <h3>
          Commercial terms{' '}
          {unconfirmedTerms.length > 0 && (
            <button
              type="button"
              className="link-btn"
              style={{ fontSize: 11.5, fontWeight: 600, marginLeft: 8 }}
              disabled={busy}
              onClick={() => void save([{ op: 'confirm_fields', field_keys: [...unconfirmedTerms] }], 'Commercial terms confirmed')}
            >
              Confirm {unconfirmedTerms.length === 1 ? 'this term' : `all ${unconfirmedTerms.length} terms`}
            </button>
          )}
        </h3>
        <div className="q-terms-grid">
          {(
            [
              ['delivery_terms', 'Delivery'],
              ['payment_terms', 'Payment'],
              ['warranty_terms', 'Warranty'],
              ['validity_terms', 'Validity'],
            ] as const
          ).map(([key, label]) => (
            <div key={key}>
              <div className="q-term-head">
                <small>{label}</small>
                {f[key]?.value && !f[key]?.confirmed && (
                  <button
                    type="button"
                    className="link-btn"
                    style={{ fontSize: 11 }}
                    disabled={busy}
                    onClick={() => void save([{ op: 'confirm_fields', field_keys: [key] }], `${label} confirmed`)}
                  >
                    <Check size={11} aria-hidden /> Confirm
                  </button>
                )}
              </div>
              <DocField field={f[key]} fieldKey={key} label={label} multiline block onSave={setField(key, label)} />
            </div>
          ))}
          <div style={{ gridColumn: '1 / -1' }}>
            <small>Notes</small>
            <DocField field={f.notes} fieldKey="notes" label="Notes" multiline block onSave={setField('notes', 'Notes')} />
          </div>
        </div>
      </section>

      <section id="sec-authorization" className="q-auth">
        <div>
          <small style={{ display: 'block', fontSize: 10.5, letterSpacing: 1, color: '#777', textTransform: 'uppercase' }}>Prepared by</small>
          <DocField field={f.prepared_by} fieldKey="prepared_by" label="Prepared by" onSave={setField('prepared_by', 'Prepared by')} />
        </div>
        <div className="q-signature">Signature — left blank. TenderFlow never signs on your behalf.</div>
      </section>

      <footer className="q-footer">
        <span>{company || 'Company name not set'}</span>
        <span>Draft preview · the export uses your template's layout</span>
      </footer>
    </article>
  )
}

function ItemsTable({ q, save, busy, focusItemId }: { q: Quotation; save: Save; busy: boolean; focusItemId: string | null }) {
  const [draft, setDraft] = useState({ description: '', quantity: '', unit: '', unit_price: '' })
  const focusRow = useRef<HTMLTableRowElement>(null)
  useEffect(() => {
    focusRow.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [focusItemId])
  const setItem = (it: QuotationLineItem, attribute: ItemAttr, label: string) => (value: string | null) =>
    save([{ op: 'set_item', line_item_id: it.id, attribute, value }], `Item ${it.item_no}: ${label} edited`)

  return (
    <>
      <table className="q-table">
        <colgroup>
          <col style={{ width: '4%' }} />
          <col style={{ width: '21%' }} />
          <col style={{ width: '24%' }} />
          <col style={{ width: '6%' }} />
          <col style={{ width: '8%' }} />
          <col style={{ width: '15%' }} />
          <col style={{ width: '17%' }} />
          <col style={{ width: '5%' }} />
        </colgroup>
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">Description</th>
            <th scope="col">Specification</th>
            <th scope="col" className="num">
              Qty
            </th>
            <th scope="col">Unit</th>
            <th scope="col" className="num">
              Unit price
            </th>
            <th scope="col" className="num">
              Amount
            </th>
            <th scope="col">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {q.line_items.length === 0 && (
            <tr>
              <td colSpan={8} style={{ color: '#888' }}>
                No line items. Add one below.
              </td>
            </tr>
          )}
          {q.line_items.map((it) => (
            <tr key={it.id} data-item={it.id} ref={it.id === focusItemId ? focusRow : undefined} className={it.id === focusItemId ? 'item-focus' : ''}>
              <td>{it.item_no}</td>
              <td>
                <ItemCell value={it.description} origin={it.origins.description} label={`Item ${it.item_no} description`} onSave={setItem(it, 'description', 'description')} />
              </td>
              <td>
                <ItemCell value={it.specification} origin={it.origins.specification} label={`Item ${it.item_no} specification`} onSave={setItem(it, 'specification', 'specification')} multiline />
              </td>
              <td className="num">
                <ItemCell
                  value={formatQuantity(it.quantity)}
                  origin={it.origins.quantity}
                  label={`Item ${it.item_no} quantity`}
                  numeric
                  onSave={setItem(it, 'quantity', 'quantity')}
                  hint={it.tender_quantity && it.quantity !== it.tender_quantity ? `Tender asks for ${formatQuantity(it.tender_quantity)}` : undefined}
                />
              </td>
              <td>
                <ItemCell value={it.unit} origin={it.origins.unit} label={`Item ${it.item_no} unit`} onSave={setItem(it, 'unit', 'unit')} />
              </td>
              <td className="num">
                <ItemCell
                  value={formatMoney(it.unit_price)}
                  rawValue={it.unit_price}
                  origin={it.origins.unit_price}
                  label={`Item ${it.item_no} unit price`}
                  numeric
                  onSave={setItem(it, 'unit_price', 'unit price')}
                  hint={it.price_note ?? undefined}
                />
                {it.unit_price !== null && !it.price_confirmed && (
                  <button
                    type="button"
                    className="link-btn"
                    style={{ fontSize: 10.5, display: 'block', marginLeft: 'auto' }}
                    disabled={busy}
                    title={it.price_note ?? undefined}
                    onClick={() => void save([{ op: 'confirm_prices', line_item_ids: [it.id] }], `Item ${it.item_no}: price confirmed`)}
                  >
                    Confirm match
                  </button>
                )}
              </td>
              <td className="num">
                <ItemCell
                  value={formatMoney(it.amount)}
                  rawValue={it.amount}
                  origin={it.origins.amount}
                  label={`Item ${it.item_no} amount`}
                  numeric
                  pendingText="Pending"
                  onSave={setItem(it, 'amount_override', 'amount')}
                  hint={it.amount_override !== null ? 'Amount entered by you — validation compares it with quantity × price.' : 'Calculated: quantity × unit price. Editing it sets a manual amount.'}
                />
              </td>
              <td>
                <button
                  type="button"
                  className="icon-btn"
                  style={{ width: 26, height: 26 }}
                  disabled={busy}
                  aria-label={`Remove item ${it.item_no}`}
                  onClick={() => void save([{ op: 'remove_item', line_item_id: it.id }], `Item ${it.item_no} removed`)}
                >
                  <Trash2 size={14} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <form
        className="q-add-item"
        style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center', fontFamily: 'var(--font-sans)' }}
        onSubmit={(e) => {
          e.preventDefault()
          if (!draft.description.trim()) return
          void save(
            [
              {
                op: 'add_item',
                description: draft.description.trim(),
                quantity: draft.quantity.trim() || null,
                unit: draft.unit.trim() || null,
                unit_price: draft.unit_price.trim() || null,
              },
            ],
            `Item added: ${draft.description.trim()}`,
          ).then(() => setDraft({ description: '', quantity: '', unit: '', unit_price: '' }))
        }}
      >
        <input className="input" style={{ flex: 2, minWidth: 160, minHeight: 32, fontSize: 12.5 }} placeholder="New item description" aria-label="New item description" value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} />
        <input className="input" style={{ width: 70, minHeight: 32, fontSize: 12.5 }} placeholder="Qty" aria-label="New item quantity" inputMode="decimal" value={draft.quantity} onChange={(e) => setDraft({ ...draft, quantity: e.target.value })} />
        <input className="input" style={{ width: 70, minHeight: 32, fontSize: 12.5 }} placeholder="Unit" aria-label="New item unit" value={draft.unit} onChange={(e) => setDraft({ ...draft, unit: e.target.value })} />
        <input className="input" style={{ width: 110, minHeight: 32, fontSize: 12.5 }} placeholder="Unit price" aria-label="New item unit price" inputMode="decimal" value={draft.unit_price} onChange={(e) => setDraft({ ...draft, unit_price: e.target.value })} />
        <button type="submit" className="btn small" disabled={busy || !draft.description.trim()}>
          <Plus size={14} aria-hidden /> Add item
        </button>
      </form>
    </>
  )
}

function ItemCell({
  value,
  rawValue,
  origin,
  label,
  onSave,
  numeric,
  multiline,
  hint,
  pendingText,
}: {
  value: string | null
  rawValue?: string | null
  origin: Origin | undefined
  label: string
  onSave: (v: string | null) => Promise<unknown>
  numeric?: boolean
  multiline?: boolean
  hint?: string
  pendingText?: string
}) {
  const [editing, setEditing] = useState(false)
  const editValue = (rawValue ?? value ?? '').replace(/,/g, '')
  const [draft, setDraft] = useState(editValue)
  useEffect(() => {
    if (!editing) setDraft(editValue)
  }, [editValue, editing])

  async function commit() {
    setEditing(false)
    const next = draft.trim()
    if (next === editValue.trim()) return
    await onSave(next || null)
  }

  if (editing) {
    const props = {
      autoFocus: true,
      className: 'df-input',
      'aria-label': label,
      value: draft,
      inputMode: numeric ? ('decimal' as const) : undefined,
      onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setDraft(e.target.value),
      onBlur: () => void commit(),
      onKeyDown: (e: React.KeyboardEvent) => {
        if (e.key === 'Escape') {
          setDraft(editValue)
          setEditing(false)
        } else if (e.key === 'Enter' && (!multiline || e.ctrlKey)) {
          e.preventDefault()
          ;(e.target as HTMLElement).blur()
        }
      },
    }
    return multiline ? <textarea {...props} rows={3} style={{ minHeight: 48 }} /> : <input {...props} style={{ textAlign: numeric ? 'right' : 'left' }} />
  }
  const o: Origin = value ? origin ?? 'user' : 'missing'
  return (
    <span className="df" style={{ justifyContent: numeric ? 'flex-end' : 'flex-start', width: '100%' }} title={hint}>
      <OriginDot origin={o} note={hint} />
      {value ? (
        <button type="button" className="df-value" onClick={() => setEditing(true)} aria-label={`Edit ${label}: ${value}`}>
          {value}
        </button>
      ) : (
        <button type="button" className="df-missing" onClick={() => setEditing(true)} aria-label={`Add ${label}`}>
          <Pencil size={10} aria-hidden /> {pendingText ?? 'Add'}
        </button>
      )}
    </span>
  )
}
