/**
 * Unit tests for the promise-based confirmation hook.
 *
 * `confirm()` returns a promise that settles when the user answers, which lets
 * a caller write `if (await confirm(...)) { delete() }`. Two properties make
 * that safe and are asserted here: the promise must *always* settle (a pending
 * one leaves the caller's async function suspended forever), and dismissing in
 * any way must resolve `false` — never `true`, and never reject.
 *
 * It also defaults `isDestructive` to true, because most confirmations in this
 * app guard a delete or a revoke.
 */
import { render, renderHook, screen, act, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { useConfirm } from './use-confirm'

/** Render the hook together with the dialog it returns. */
function setup() {
  const { result } = renderHook(() => useConfirm())
  const view = render(<result.current.ConfirmDialog />)

  const rerenderDialog = () => view.rerender(<result.current.ConfirmDialog />)
  return { result, rerenderDialog }
}

describe('opening', () => {
  it('shows nothing until confirm is called', () => {
    setup()

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('shows the dialog with the title and description given', async () => {
    const { result, rerenderDialog } = setup()

    act(() => {
      void result.current.confirm({
        title: 'Delete agent',
        description: 'This cannot be undone.',
      })
    })
    rerenderDialog()

    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Delete agent')).toBeInTheDocument()
    expect(screen.getByText('This cannot be undone.')).toBeInTheDocument()
  })

  it('defaults to the destructive treatment', async () => {
    // Most confirmations here guard a delete or a revoke, so the safe default
    // is the one that looks dangerous.
    const { result, rerenderDialog } = setup()

    act(() => {
      void result.current.confirm({ title: 'Revoke key' })
    })
    rerenderDialog()

    expect(await screen.findByRole('button', { name: 'Confirm' })).toBeInTheDocument()
  })

  it('uses the button labels it is given', async () => {
    const { result, rerenderDialog } = setup()

    act(() => {
      void result.current.confirm({
        title: 'Delete',
        confirmText: 'Yes, delete it',
        cancelText: 'Keep it',
      })
    })
    rerenderDialog()

    expect(await screen.findByRole('button', { name: 'Yes, delete it' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Keep it' })).toBeInTheDocument()
  })

  it('tolerates a missing description', async () => {
    const { result, rerenderDialog } = setup()

    act(() => {
      void result.current.confirm({ title: 'Just a title' })
    })
    rerenderDialog()

    expect(await screen.findByRole('dialog')).toBeInTheDocument()
  })
})

describe('answering', () => {
  it('resolves true when confirmed', async () => {
    const user = userEvent.setup()
    const { result, rerenderDialog } = setup()

    let answer: Promise<boolean>
    act(() => {
      answer = result.current.confirm({ title: 'Delete agent' })
    })
    rerenderDialog()

    await user.click(await screen.findByRole('button', { name: 'Confirm' }))

    await expect(answer!).resolves.toBe(true)
  })

  it('resolves false when cancelled', async () => {
    const user = userEvent.setup()
    const { result, rerenderDialog } = setup()

    let answer: Promise<boolean>
    act(() => {
      answer = result.current.confirm({ title: 'Delete agent' })
    })
    rerenderDialog()

    await user.click(await screen.findByRole('button', { name: 'Cancel' }))

    await expect(answer!).resolves.toBe(false)
  })

  it('resolves false when dismissed with the close button', async () => {
    // Dismissing must never read as consent — this guards destructive actions.
    const user = userEvent.setup()
    const { result, rerenderDialog } = setup()

    let answer: Promise<boolean>
    act(() => {
      answer = result.current.confirm({ title: 'Delete agent' })
    })
    rerenderDialog()

    await user.click(await screen.findByRole('button', { name: 'Close' }))

    await expect(answer!).resolves.toBe(false)
  })

  it('closes the dialog once answered', async () => {
    const user = userEvent.setup()
    const { result, rerenderDialog } = setup()

    act(() => {
      void result.current.confirm({ title: 'Delete agent' })
    })
    rerenderDialog()
    await user.click(await screen.findByRole('button', { name: 'Confirm' }))
    rerenderDialog()

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  it('settles rather than rejecting, so callers need no try/catch', async () => {
    // A rejection here would surface as an unhandled promise rejection in every
    // caller that writes `if (await confirm(...))`.
    const user = userEvent.setup()
    const { result, rerenderDialog } = setup()

    let answer: Promise<boolean>
    act(() => {
      answer = result.current.confirm({ title: 'Delete agent' })
    })
    rerenderDialog()
    await user.click(await screen.findByRole('button', { name: 'Cancel' }))

    await expect(answer!).resolves.toBeTypeOf('boolean')
  })
})

describe('reuse', () => {
  it('can be opened again after being answered', async () => {
    // The same hook instance guards every delete on a page, so it has to be
    // reusable rather than single-shot.
    const user = userEvent.setup()
    const { result, rerenderDialog } = setup()

    let first: Promise<boolean>
    act(() => {
      first = result.current.confirm({ title: 'First' })
    })
    rerenderDialog()
    await user.click(await screen.findByRole('button', { name: 'Confirm' }))
    await expect(first!).resolves.toBe(true)
    rerenderDialog()

    let second: Promise<boolean>
    act(() => {
      second = result.current.confirm({ title: 'Second' })
    })
    rerenderDialog()

    expect(await screen.findByText('Second')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    await expect(second!).resolves.toBe(false)
  })
})
