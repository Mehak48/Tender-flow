import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DocField } from './DocField'
import type { QField } from '../../api/types'

const field = (value: string | null, origin: QField['origin'] = 'extracted'): QField => ({
  key: 'delivery_terms',
  label: 'Delivery terms',
  value,
  origin: value ? origin : 'missing',
  source: null,
  confirmed: false,
  note: null,
})

describe('DocField', () => {
  it('shows a visible marker instead of leaving a missing value blank', async () => {
    const onSave = vi.fn(async () => undefined)
    render(<DocField field={field(null)} fieldKey="delivery_terms" label="Delivery" onSave={onSave} />)
    const add = screen.getByRole('button', { name: 'Add Delivery' })
    expect(screen.getByRole('img', { name: 'Needs input' })).toBeInTheDocument()
    await userEvent.click(add)
    await userEvent.type(screen.getByLabelText('Delivery'), '  Within 30 days  {Enter}')
    expect(onSave).toHaveBeenCalledWith('Within 30 days')
  })

  it('does not save when the value is unchanged or editing is cancelled', async () => {
    const onSave = vi.fn(async () => undefined)
    render(<DocField field={field('Within 45 days')} fieldKey="delivery_terms" label="Delivery" onSave={onSave} />)
    expect(screen.getByRole('img', { name: 'From tender' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Edit Delivery/ }))
    await userEvent.keyboard('{Enter}')
    await userEvent.click(screen.getByRole('button', { name: /Edit Delivery/ }))
    await userEvent.type(screen.getByLabelText('Delivery'), ' changed{Escape}')
    expect(onSave).not.toHaveBeenCalled()
    expect(screen.getByText('Within 45 days')).toBeInTheDocument()
  })
})
