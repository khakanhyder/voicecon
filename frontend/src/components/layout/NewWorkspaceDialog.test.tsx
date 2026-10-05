/**
 * The "New workspace" dialog replaced a native window.prompt. What matters:
 * a blank name never reaches the API, the name is sent trimmed, and an API
 * error stays inside the dialog instead of closing it.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const create = vi.hoisted(() => vi.fn())
vi.mock('@/lib/workspace', () => ({ workspaceService: { create } }))

import { NewWorkspaceDialog } from './NewWorkspaceDialog'

const onClose = vi.fn()
const onCreated = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
})

function renderDialog() {
  return render(<NewWorkspaceDialog open onClose={onClose} onCreated={onCreated} />)
}

describe('NewWorkspaceDialog', () => {
  it('keeps Create disabled until a non-blank name is typed', async () => {
    renderDialog()
    const submit = screen.getByRole('button', { name: /create workspace/i })
    expect(submit).toBeDisabled()
    await userEvent.type(screen.getByLabelText(/workspace name/i), '   ')
    expect(submit).toBeDisabled()
    expect(create).not.toHaveBeenCalled()
  })

  it('creates with the trimmed name and hands the result back', async () => {
    const created = { id: 'w2', name: 'Acme Dental' }
    create.mockResolvedValue(created)
    renderDialog()
    await userEvent.type(screen.getByLabelText(/workspace name/i), '  Acme Dental  {Enter}')
    expect(create).toHaveBeenCalledWith('Acme Dental')
    expect(onCreated).toHaveBeenCalledWith(created)
  })

  it('shows an API error inside the dialog', async () => {
    create.mockRejectedValue(new Error('You already have a workspace with that name.'))
    renderDialog()
    await userEvent.type(screen.getByLabelText(/workspace name/i), 'Vconekt LLC')
    await userEvent.click(screen.getByRole('button', { name: /create workspace/i }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(onCreated).not.toHaveBeenCalled()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('Cancel closes without creating', async () => {
    renderDialog()
    await userEvent.click(screen.getByRole('button', { name: /^cancel$/i }))
    expect(onClose).toHaveBeenCalled()
    expect(create).not.toHaveBeenCalled()
  })
})
