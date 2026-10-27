import { useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, Check, Info, RefreshCw } from 'lucide-react'
import { api } from '../api/client'
import type { ColumnMappingRow, FieldMappingRow, SourceValue, TemplateField } from '../api/types'
import { Modal } from '../components/Modal'
import { Badge, Button, Notice, OriginTag, PageTitle } from '../components/ui'
import { ITEM_ATTRIBUTE_LABEL } from '../lib/labels'
import { navigate, projectHref } from '../router'
import type { FlowProps } from './types'

const NEVER_FILL = new Set(['signature'])

export function MappingStep({ project, run, busy }: FlowProps) {
  const view = project.mapping!
  const template = project.template!
  const [confirmRegen, setConfirmRegen] = useState(false)
  const sourcesByKey = useMemo(() => new Map(view.sources.map((s) => [s.key, s])), [view.sources])
  const groups = useMemo(() => {
    const map = new Map<string, SourceValue[]>()
    for (const s of view.sources) map.set(s.group, [...(map.get(s.group) ?? []), s])
    return [...map.entries()]
  }, [view.sources])
  const tfById = useMemo(() => new Map(view.template_fields.map((t) => [t.id, t])), [view.template_fields])

  const mapped = view.mapping.fields.filter((r) => r.source_key).length
  const requiredUnfilled = view.required_unfilled.length
  const pricedItems = project.extraction?.line_items.length ?? 0
  const priceRows = project.price_list?.rows.length ?? 0

  const setField = (row: FieldMappingRow, sourceKey: string | null) =>
    run(() => api.updateMapping(project.id, [{ ...row, source_key: sourceKey }], []))
  const setColumn = (row: ColumnMappingRow, attribute: string | null) =>
    run(() => api.updateMapping(project.id, [], [{ ...row, attribute }]))

  async function confirmAndGenerate() {
    setConfirmRegen(false)
    const confirmed = await run(() => api.confirmMapping(project.id))
    if (!confirmed) return
    const generated = await run(() => api.generate(project.id), project.quotation ? 'Quotation regenerated' : 'Quotation generated')
    if (generated) navigate(projectHref(project.id, 'editor'))
  }

  const canContinue = view.mapping.confirmed && !!project.quotation && project.stale_reasons.length === 0
  return (
    <div className="flow-content mapping-page" style={{ paddingInline: 24 }}>
      <PageTitle
        eyebrow="Step 3 of 5"
        title="Map quotation data to your template"
        description={`Template: ${template.document_name}. Proposed connections use exact field names only — check them, change any that are wrong, then confirm.`}
        actions={
          <div className="summary-pills" aria-label="Mapping summary">
            <span>
              <b>{mapped}</b>mapped
            </span>
            <span>
              <b>{requiredUnfilled}</b>required unfilled
            </span>
            <span>
              <b>{view.unmapped_sources.length}</b>unused data
            </span>
          </div>
        }
      />
      {template.warnings.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <Notice tone="warning" title="About your template">
            <ul>
              {template.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </Notice>
        </div>
      )}
      <div className="mapping-layout">
        <div>
          <h2 className="section-title" style={{ marginBottom: 10 }}>
            Document fields
          </h2>
          <div className="mapping-head" aria-hidden>
            <span>Quotation data (source)</span>
            <span />
            <span>Your template field (destination)</span>
            <span>Status</span>
          </div>
          <div className="mapping-list">
            {view.mapping.fields.map((row) => {
              const tf = tfById.get(row.target_field_id)
              if (!tf) return null
              return (
                <MappingRow
                  key={row.target_field_id}
                  row={row}
                  tf={tf}
                  source={row.source_key ? sourcesByKey.get(row.source_key) ?? null : null}
                  groups={groups}
                  busy={busy}
                  onChange={(k) => void setField(row, k)}
                />
              )
            })}
          </div>

          <h2 className="section-title" style={{ margin: '28px 0 10px' }}>
            Line-item columns
          </h2>
          {template.items_table ? (
            <>
              <p className="small muted" style={{ marginTop: -4 }}>
                {template.items_table.location}: the row under the header is repeated for each of the {pricedItems} line items.
              </p>
              <div className="mapping-list">
                {view.mapping.columns.map((row) => {
                  const col = view.items_columns.find((c) => c.index === row.column_index)
                  const id = `col-${row.column_index}`
                  return (
                    <div className="mapping-row" key={row.column_index}>
                      <div className="map-cell">
                        <small>Line-item value</small>
                        <label htmlFor={id} className="sr-only">
                          Value for column {row.column_index + 1}
                        </label>
                        <select id={id} value={row.attribute ?? ''} disabled={busy} onChange={(e) => void setColumn(row, e.target.value || null)}>
                          <option value="">— Leave column empty —</option>
                          {Object.entries(ITEM_ATTRIBUTE_LABEL).map(([k, label]) => (
                            <option key={k} value={k}>
                              {label}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="connector" aria-hidden>
                        <span />
                        <i>
                          <ArrowRight size={13} />
                        </i>
                        <span />
                      </div>
                      <div className="map-cell">
                        <small>Column {row.column_index + 1}</small>
                        <strong>{col?.header || '(no header)'}</strong>
                      </div>
                      <StatusBadge status={row.status} required={false} />
                    </div>
                  )
                })}
              </div>
            </>
          ) : (
            <Notice tone="warning">No items table was found in the template, so line items cannot be written into it.</Notice>
          )}
        </div>

        <aside className="side-lists" aria-label="Mapping gaps">
          <div className="card flat">
            <strong className="small">Template fields with no data</strong>
            {view.unfilled_targets.length === 0 ? (
              <p className="tiny muted" style={{ margin: '6px 0 0' }}>
                Every template field receives a value source.
              </p>
            ) : (
              <ul>
                {view.unfilled_targets.map((id) => {
                  const tf = tfById.get(id)
                  return (
                    <li key={id}>
                      {tf?.label ?? id} {tf?.required ? <Badge tone="danger">Required</Badge> : <Badge>Optional</Badge>}
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
          <div className="card flat">
            <strong className="small">Data your template does not use</strong>
            {view.unmapped_sources.length === 0 ? (
              <p className="tiny muted" style={{ margin: '6px 0 0' }}>
                All available values are used.
              </p>
            ) : (
              <ul>
                {view.unmapped_sources.map((k) => (
                  <li key={k}>{sourcesByKey.get(k)?.label ?? k}</li>
                ))}
              </ul>
            )}
            <p className="tiny muted" style={{ margin: '6px 0 0' }}>
              That is fine — it is simply not part of your template.
            </p>
          </div>
          <Notice tone="warning" title="Unit prices are not in the tender">
            {priceRows > 0
              ? `They come from your price list (${priceRows} rows) when an item name matches, and need your confirmation. Unmatched items stay visibly blank for you to fill in.`
              : 'No price list was uploaded, so every unit price stays visibly blank for you to fill in. Nothing is estimated.'}
          </Notice>
        </aside>
      </div>

      <div className="flow-actions">
        <Button onClick={() => navigate(projectHref(project.id, 'review'))} icon={<ArrowLeft size={15} aria-hidden />}>
          Back
        </Button>
        <div className="right">
          {view.mapping.confirmed && (
            <Badge tone="success">
              <Check size={12} aria-hidden /> Mapping confirmed
            </Badge>
          )}
          {canContinue ? (
            <>
              <Button onClick={() => setConfirmRegen(true)} icon={<RefreshCw size={15} aria-hidden />}>
                Regenerate
              </Button>
              <Button kind="primary" onClick={() => navigate(projectHref(project.id, 'editor'))}>
                Continue to editor <ArrowRight size={15} aria-hidden />
              </Button>
            </>
          ) : (
            <Button
              kind="primary"
              busy={busy}
              onClick={() => (project.quotation ? setConfirmRegen(true) : void confirmAndGenerate())}
            >
              Confirm mapping & {project.quotation ? 'regenerate' : 'generate'} quotation <ArrowRight size={15} aria-hidden />
            </Button>
          )}
        </div>
      </div>
      {project.stale_reasons.length > 0 && project.quotation && (
        <div style={{ marginTop: 12 }}>
          <Notice tone="info" title="The current draft is out of date">
            <ul>
              {project.stale_reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </Notice>
        </div>
      )}
      {confirmRegen && (
        <Modal
          title="Regenerate the quotation?"
          onClose={() => setConfirmRegen(false)}
          actions={
            <>
              <Button onClick={() => setConfirmRegen(false)}>Cancel</Button>
              <Button kind="primary" busy={busy} onClick={() => void confirmAndGenerate()} icon={<RefreshCw size={15} aria-hidden />}>
                Regenerate
              </Button>
            </>
          }
        >
          <p className="small">
            The draft is rebuilt from the reviewed tender data, your template mapping, price list and settings. Edits made in
            the editor are replaced — you can bring them back with <strong>Undo</strong>.
          </p>
        </Modal>
      )}
      <p className="tiny muted" style={{ marginTop: 16, display: 'flex', gap: 6 }}>
        <Info size={13} aria-hidden /> Placeholders written as {'{{name?}}'} are optional. Signature fields are never filled.
      </p>
    </div>
  )
}

function StatusBadge({ status, required, never }: { status: FieldMappingRow['status']; required: boolean; never?: boolean }) {
  if (never) return <Badge>Never filled</Badge>
  if (status === 'auto') return <Badge tone="lavender">Auto-matched</Badge>
  if (status === 'manual') return <Badge tone="success">Chosen by you</Badge>
  return required ? <Badge tone="danger">Required · empty</Badge> : <Badge>Left empty</Badge>
}

function MappingRow({
  row,
  tf,
  source,
  groups,
  busy,
  onChange,
}: {
  row: FieldMappingRow
  tf: TemplateField
  source: SourceValue | null
  groups: [string, SourceValue[]][]
  busy: boolean
  onChange: (key: string | null) => void
}) {
  const never = !!tf.key && NEVER_FILL.has(tf.key)
  const id = `map-${tf.id}`
  const problem = !never && tf.required && !row.source_key
  return (
    <div className={`mapping-row ${problem ? 'problem' : ''}`}>
      <div className="map-cell">
        <small>Source</small>
        <label htmlFor={id} className="sr-only">
          Data for {tf.label}
        </label>
        {never ? (
          <strong className="muted">Left blank for you to sign</strong>
        ) : (
          <select id={id} value={row.source_key ?? ''} disabled={busy} onChange={(e) => onChange(e.target.value || null)}>
            <option value="">— Leave empty —</option>
            {groups.map(([group, items]) => (
              <optgroup key={group} label={group}>
                {items.map((s) => (
                  <option key={s.key} value={s.key}>
                    {s.label}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        )}
        {source && (
          <span className="value-preview" title={source.value ?? undefined}>
            <OriginTag origin={source.origin} /> {source.value ?? 'No value yet'}
          </span>
        )}
      </div>
      <div className="connector" aria-hidden>
        <span />
        <i>{row.source_key ? <Check size={13} /> : <ArrowRight size={13} />}</i>
        <span />
      </div>
      <div className="map-cell">
        <small>
          {tf.kind === 'placeholder' ? 'Placeholder' : 'Fill-in label'}
          {tf.required && !never ? ' · required' : ' · optional'}
        </small>
        <strong>{tf.label}</strong>
        <span className="value-preview">{tf.locations.slice(0, 3).join(' · ')}</span>
      </div>
      <StatusBadge status={row.status} required={tf.required} never={never} />
    </div>
  )
}
