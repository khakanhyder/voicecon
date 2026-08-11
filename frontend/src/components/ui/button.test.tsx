/**
 * Component tests for the shared Button.
 *
 * Almost every screen renders this, so the properties worth pinning are the
 * ones a restyle can quietly break: it must stay a real `<button>` (keyboard
 * and form semantics come free from the element, not from CSS), it must forward
 * its ref, and `asChild` must not leak onto the DOM.
 */
import { createRef } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { Button } from './button'

describe('rendering', () => {
  it('renders its children inside a real button element', () => {
    render(<Button>Save changes</Button>)
    const button = screen.getByRole('button', { name: 'Save changes' })

    // A styled <div> would lose Enter/Space activation and form submission.
    expect(button.tagName).toBe('BUTTON')
  })

  it('merges a caller class instead of dropping the variant classes', () => {
    // `cn` exists to resolve Tailwind conflicts; a naive override would strip
    // the variant styling entirely.
    render(<Button className="w-full">Save</Button>)

    const button = screen.getByRole('button')
    expect(button).toHaveClass('w-full')
    expect(button.className.length).toBeGreaterThan('w-full'.length)
  })

  it('applies distinct classes per variant', () => {
    const { rerender } = render(<Button variant="default">x</Button>)
    const defaultClasses = screen.getByRole('button').className

    rerender(<Button variant="destructive">x</Button>)

    expect(screen.getByRole('button').className).not.toBe(defaultClasses)
  })

  it('applies distinct classes per size', () => {
    const { rerender } = render(<Button size="default">x</Button>)
    const defaultClasses = screen.getByRole('button').className

    rerender(<Button size="lg">x</Button>)

    expect(screen.getByRole('button').className).not.toBe(defaultClasses)
  })
})

describe('behaviour', () => {
  it('calls its handler when clicked', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Go</Button>)

    await user.click(screen.getByRole('button'))

    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('activates from the keyboard', async () => {
    // Free from the native element — worth asserting so it stays a button.
    const user = userEvent.setup()
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Go</Button>)

    await user.tab()
    await user.keyboard('{Enter}')

    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('does not fire while disabled', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    render(
      <Button disabled onClick={onClick}>
        Go
      </Button>
    )

    await user.click(screen.getByRole('button'))

    expect(screen.getByRole('button')).toBeDisabled()
    expect(onClick).not.toHaveBeenCalled()
  })

  it('defaults to type="submit" semantics inside a form', async () => {
    // Documents the native default: a bare <button> in a form submits it. Forms
    // in this app rely on that for Enter-to-submit.
    const user = userEvent.setup()
    const onSubmit = vi.fn((e: React.FormEvent) => e.preventDefault())
    render(
      <form onSubmit={onSubmit}>
        <Button>Submit</Button>
      </form>
    )

    await user.click(screen.getByRole('button'))

    expect(onSubmit).toHaveBeenCalledTimes(1)
  })

  it('can opt out of submitting with an explicit type', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn((e: React.FormEvent) => e.preventDefault())
    render(
      <form onSubmit={onSubmit}>
        <Button type="button">Just a button</Button>
      </form>
    )

    await user.click(screen.getByRole('button'))

    expect(onSubmit).not.toHaveBeenCalled()
  })
})

describe('props plumbing', () => {
  it('forwards its ref to the underlying element', () => {
    // Needed for focus management — the confirm modal and forms focus buttons
    // directly.
    const ref = createRef<HTMLButtonElement>()
    render(<Button ref={ref}>x</Button>)

    expect(ref.current).toBeInstanceOf(HTMLButtonElement)
  })

  it('passes arbitrary button attributes through', () => {
    render(<Button aria-label="Close panel" data-testid="close" />)

    expect(screen.getByTestId('close')).toHaveAccessibleName('Close panel')
  })

  it('does not leak asChild onto the DOM', () => {
    // React warns about unknown DOM attributes on every render; `asChild` is
    // part of the public prop type but this button always renders a <button>.
    const warn = vi.spyOn(console, 'error').mockImplementation(() => {})
    render(<Button asChild>x</Button>)

    expect(screen.getByRole('button')).not.toHaveAttribute('asChild')
    expect(warn).not.toHaveBeenCalled()
    warn.mockRestore()
  })
})
