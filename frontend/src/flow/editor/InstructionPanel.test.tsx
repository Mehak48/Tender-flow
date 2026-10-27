import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AppProvider } from '../../components/AppContext'
import { InstructionPanel } from './InstructionPanel'
import type { EditProposal, ProjectView } from '../../api/types'

const proposal: EditProposal = {
  id: 'edt_0123456789ab',
  instruction: 'Set the unit price of item 4 to 95000',
  interpreted_as: 'Set the unit price of item 4 (Network rack) to 95000.',
  operations: [{ op: 'set_item', line_item_id: 'itm_0123456789ab', attribute: 'unit_price', value: '95000' }],
  changes: [
    { target: 'Item 4 · Unit price', before: null, after: '95,000.00' },
    { target: 'Total', before: 'Pending', after: '1,564,000.00' },
  ],
  material: true,
  material_reasons: ['changes a price, quantity or amount', 'changes the quotation total'],
  warnings: [],
  engine: 'rules',
  status: 'pending',
  ui_only: false,
  base_version: 1,
  created_at: '2026-10-27T10:00:00Z',
  resolved_at: null,
}

function project(pending: EditProposal[]): ProjectView {
  return {
    id: 'prj_0123456789ab',
    name: 'Test',
    is_sample: false,
    created_at: '2026-10-27T10:00:00Z',
    updated_at: '2026-10-27T10:00:00Z',
    stage: 'editor',
    documents: [],
    extraction: null,
    template: null,
    price_list: null,
    mapping: null,
    quotation: null,
    validation: null,
    pending_edits: pending,
    edit_history: [],
    undo_available: 0,
    exports: [],
    events: [],
    company_source: 'settings',
    stale_reasons: [],
    export_formats: ['docx'],
  }
}

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify({ status: 'ok', ai: { mode: 'local' } }), { status: 200 })),
  )
})
afterEach(() => vi.unstubAllGlobals())

describe('InstructionPanel', () => {
  it('shows before/after for a proposal and requires explicit confirmation for money changes', async () => {
    const run = vi.fn(async () => undefined)
    render(
      <AppProvider>
        <InstructionPanel project={project([proposal])} run={run} busy={false} open onClose={() => {}} onHighlight={() => {}} missingCount={0} />
      </AppProvider>,
    )
    expect(screen.getByText('Item 4 · Unit price')).toBeInTheDocument()
    expect(screen.getByText('1,564,000.00')).toBeInTheDocument()
    expect(screen.getByText(/changes a price, quantity or amount/)).toBeInTheDocument()
    const apply = screen.getByRole('button', { name: 'Apply change' })
    expect(apply).toBeDisabled()
    await userEvent.click(screen.getByLabelText('I have checked these values and want to apply them.'))
    expect(apply).toBeEnabled()
    await userEvent.click(apply)
    await waitFor(() => expect(run).toHaveBeenCalledTimes(1))
  })

  it('offers the supported example instructions when nothing is pending', async () => {
    render(
      <AppProvider>
        <InstructionPanel project={project([])} run={vi.fn()} busy={false} open onClose={() => {}} onHighlight={() => {}} missingCount={3} />
      </AppProvider>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Change the delivery period to 30 days.' }))
    expect(screen.getByLabelText('Instruction')).toHaveValue('Change the delivery period to 30 days.')
    expect(screen.getByText('3 values need your input')).toBeInTheDocument()
  })
})
