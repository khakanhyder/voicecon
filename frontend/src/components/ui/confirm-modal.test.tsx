/**
 * Component tests for the confirmation modal.
 *
 * This is the dialog that guards destructive actions — deleting an agent, a
 * workspace, a phone number. The behaviour worth pinning is that it cannot fire
 * its action by accident: the backdrop and the close button must cancel, never
 * confirm, and while a request is in flight every control must be inert so a
 * double-click cannot delete twice.
 *
 * Driven with `user-event` rather than `fireEvent`, so clicks go through the
 * same pointer sequence a real user produces.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ConfirmModal } from './confirm-modal'

const onConfirm = vi.fn()
const onCancel = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
})

function renderModal(props: Partial<React.ComponentProps<typeof ConfirmModal>> = {}) {
  return render(
    <ConfirmModal
      isOpen
      title="Delete agent"
      description="This cannot be undone."
      onConfirm={onConfirm}
      onCancel={onCancel}
      {...props}
    />
  )
}

describe('visibility', () => {
  it('renders nothing when closed', () => {
    renderModal({ isOpen: false })

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('shows the title and description when open', () => {
    renderModal()

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Delete agent')).toBeInTheDocument()
    expect(screen.getByText('This cannot be undone.')).toBeInTheDocument()
  })

  it('renders into a portal on document.body, above the page', () => {
    // The modal is used from deep inside scrolling, transformed containers; a
    // portal is what stops an ancestor's overflow or stacking context clipping it.
    const { container } = renderModal()

    expect(container).toBeEmptyDOMElement()
    expect(document.body).toContainElement(screen.getByRole('dialog'))
  })
})

describe('accessibility', () => {
  it('is a modal dialog labelled by its own title and description', () => {
    renderModal()
    const dialog = screen.getByRole('dialog')

    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toHaveAccessibleName('Delete agent')
    expect(dialog).toHaveAccessibleDescription('This cannot be undone.')
  })

  it('gives the icon-only close button a name', () => {
    // Without aria-label this button announces as "button" and nothing else.
    renderModal()

    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument()
  })
})

describe('choosing an action', () => {
  it('confirms when the confirm button is clicked', async () => {
    const user = userEvent.setup()
    renderModal({ confirmText: 'Delete' })

    await user.click(screen.getByRole('button', { name: 'Delete' }))

    expect(onConfirm).toHaveBeenCalledTimes(1)
    expect(onCancel).not.toHaveBeenCalled()
  })

  it('cancels when the cancel button is clicked', async () => {
    const user = userEvent.setup()
    renderModal({ cancelText: 'Keep it' })

    await user.click(screen.getByRole('button', { name: 'Keep it' }))

    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('cancels when the close button is clicked', async () => {
    const user = userEvent.setup()
    renderModal()

    await user.click(screen.getByRole('button', { name: 'Close' }))

    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('cancels when the backdrop is clicked', async () => {
    const user = userEvent.setup()
    renderModal()

    // Clicking outside must dismiss, and must never be read as confirmation —
    // this dialog guards destructive actions.
    await user.click(screen.getByRole('dialog').parentElement!)

    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('does not cancel when a click starts inside the dialog', async () => {
    const user = userEvent.setup()
    renderModal()

    await user.click(screen.getByText('This cannot be undone.'))

    expect(onCancel).not.toHaveBeenCalled()
  })
})

describe('labels', () => {
  it('defaults to generic Confirm and Cancel labels', () => {
    renderModal()

    expect(screen.getByRole('button', { name: 'Confirm' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
  })

  it('uses the labels it is given', () => {
    // A specific verb ("Delete agent") beats "Confirm" on a destructive dialog.
    renderModal({ confirmText: 'Delete agent', cancelText: 'Keep agent' })

    expect(screen.getByRole('button', { name: 'Delete agent' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Keep agent' })).toBeInTheDocument()
  })
})

describe('while the action is in flight', () => {
  it('disables every control', async () => {
    // A second click while the delete is still running would fire it twice.
    renderModal({ isLoading: true, confirmText: 'Delete' })

    expect(screen.getByRole('button', { name: 'Close' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled()
    expect(screen.getByRole('button', { name: /processing/i })).toBeDisabled()
  })

  it('shows progress in place of the confirm label', () => {
    renderModal({ isLoading: true, confirmText: 'Delete' })

    expect(screen.getByRole('button', { name: /processing/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument()
  })

  it('ignores a second confirm click', async () => {
    const user = userEvent.setup()
    renderModal({ isLoading: true })

    await user.click(screen.getByRole('button', { name: /processing/i }))

    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('ignores a backdrop click, so the dialog cannot be dismissed mid-request', async () => {
    const user = userEvent.setup()
    renderModal({ isLoading: true })

    await user.click(screen.getByRole('dialog').parentElement!)

    expect(onCancel).not.toHaveBeenCalled()
  })
})
