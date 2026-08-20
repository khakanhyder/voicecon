/**
 * The password field's show/hide toggle.
 *
 * The behaviour worth pinning is that it stays a real masked `<input>` that
 * participates in a form, and that each field's visibility is its own — the
 * bug this component replaced was confirm-password fields shipped with no
 * toggle at all, which is the field you most need to read back.
 */
import { createRef } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { PasswordInput } from './password-input'

const toggle = () => screen.getByRole('button')

describe('PasswordInput', () => {
  it('masks the value until the toggle is pressed', async () => {
    const user = userEvent.setup()
    render(<PasswordInput aria-label="Password" data-testid="pw" />)

    expect(screen.getByTestId('pw')).toHaveAttribute('type', 'password')

    await user.click(toggle())
    expect(screen.getByTestId('pw')).toHaveAttribute('type', 'text')

    await user.click(toggle())
    expect(screen.getByTestId('pw')).toHaveAttribute('type', 'password')
  })

  it('announces what the button does and whether the password is showing', async () => {
    const user = userEvent.setup()
    render(<PasswordInput aria-label="Password" />)

    expect(toggle()).toHaveAccessibleName('Show password')
    expect(toggle()).toHaveAttribute('aria-pressed', 'false')

    await user.click(toggle())

    expect(toggle()).toHaveAccessibleName('Hide password')
    expect(toggle()).toHaveAttribute('aria-pressed', 'true')
  })

  it('keeps the typed value when visibility changes', async () => {
    const user = userEvent.setup()
    render(<PasswordInput aria-label="Password" data-testid="pw" />)

    await user.type(screen.getByTestId('pw'), 'hunter2')
    await user.click(toggle())

    expect(screen.getByTestId('pw')).toHaveValue('hunter2')
  })

  it('gives each field its own visibility', async () => {
    const user = userEvent.setup()
    render(
      <>
        <PasswordInput aria-label="Password" data-testid="pw" />
        <PasswordInput aria-label="Confirm password" data-testid="confirm" />
      </>
    )

    await user.click(screen.getAllByRole('button')[0])

    // Revealing one must not reveal the other.
    expect(screen.getByTestId('pw')).toHaveAttribute('type', 'text')
    expect(screen.getByTestId('confirm')).toHaveAttribute('type', 'password')
  })

  it('does not submit the form it sits in', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn((e) => e.preventDefault())
    render(
      <form onSubmit={onSubmit}>
        <PasswordInput aria-label="Password" />
      </form>
    )

    await user.click(toggle())

    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('cannot be typed into or toggled when disabled', async () => {
    const user = userEvent.setup()
    render(<PasswordInput aria-label="Password" data-testid="pw" disabled />)

    await user.type(screen.getByTestId('pw'), 'hunter2')
    await user.click(toggle())

    expect(screen.getByTestId('pw')).toHaveValue('')
    expect(screen.getByTestId('pw')).toHaveAttribute('type', 'password')
  })

  it('always reserves room for the toggle, whatever padding the caller passes', () => {
    // A caller's own `px-3` must not win and leave the text under the icon.
    render(<PasswordInput aria-label="Password" data-testid="pw" className="px-3" />)

    expect(screen.getByTestId('pw')).toHaveClass('pr-10')
  })

  it('forwards the ref and renders the left decoration', () => {
    const ref = createRef<HTMLInputElement>()
    render(
      <PasswordInput
        aria-label="Password"
        ref={ref}
        leftIcon={<span data-testid="lock">lock</span>}
      />
    )

    expect(ref.current).toBeInstanceOf(HTMLInputElement)
    expect(screen.getByTestId('lock')).toBeInTheDocument()
  })
})
