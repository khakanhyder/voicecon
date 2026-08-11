/**
 * Component tests for the inline field-error message.
 *
 * This component exists to replace the browser's native validation bubble, and
 * the reasons it replaced it are all accessibility properties: the message must
 * be announced (`role="alert"`), it must be tied to its input
 * (`aria-describedby`), and the input must be marked invalid (`aria-invalid`).
 * Those are asserted here rather than the styling, because they are the part
 * that silently regresses.
 */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { FieldError, errorInputClass, fieldErrorProps } from './field-error'

describe('FieldError', () => {
  it('shows the message it is given', () => {
    render(<FieldError id="email-error" message="Enter a valid email address" />)

    expect(screen.getByText('Enter a valid email address')).toBeInTheDocument()
  })

  it('announces itself to a screen reader', () => {
    // Without role="alert" the message appears silently, and a screen-reader
    // user submitting a form learns nothing about why it failed.
    render(<FieldError id="email-error" message="Required" />)

    expect(screen.getByRole('alert')).toHaveTextContent('Required')
  })

  it('carries the id its input points at', () => {
    render(<FieldError id="password-error" message="Too short" />)

    expect(screen.getByRole('alert')).toHaveAttribute('id', 'password-error')
  })

  it('renders nothing when there is no message', () => {
    // A valid field must not leave an empty alert node behind — some screen
    // readers announce the empty region on focus.
    const { container } = render(<FieldError id="email-error" />)

    expect(container).toBeEmptyDOMElement()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('renders nothing for an empty-string message', () => {
    const { container } = render(<FieldError id="email-error" message="" />)

    expect(container).toBeEmptyDOMElement()
  })

  it('hides its icon from assistive technology', () => {
    // The icon is decorative; announced, it would read as noise before the text.
    const { container } = render(<FieldError id="e" message="Required" />)

    expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
  })
})

describe('fieldErrorProps', () => {
  it('marks the input invalid and points it at the message', () => {
    expect(fieldErrorProps('email', 'Required')).toEqual({
      'aria-invalid': true,
      'aria-describedby': 'email-error',
    })
  })

  it('sets nothing when the field is valid', () => {
    // `aria-invalid="false"` on every field is noise; absent is the correct
    // state for a field that has not failed.
    expect(fieldErrorProps('email', undefined)).toEqual({
      'aria-invalid': undefined,
      'aria-describedby': undefined,
    })
  })

  it('derives the id the same way FieldError expects', () => {
    // These two must agree or `aria-describedby` points at nothing. This test
    // is the contract between them.
    const props = fieldErrorProps('password', 'Too short')
    render(<FieldError id="password-error" message="Too short" />)

    expect(screen.getByRole('alert')).toHaveAttribute(
      'id',
      props['aria-describedby']
    )
  })
})

describe('an input wired up with both', () => {
  function Field({ message }: { message?: string }) {
    return (
      <div>
        <label htmlFor="email">Email</label>
        <input
          id="email"
          className={message ? errorInputClass : ''}
          {...fieldErrorProps('email', message)}
        />
        <FieldError id="email-error" message={message} />
      </div>
    )
  }

  it('associates the message with the field, so focus reads the reason', () => {
    render(<Field message="Enter a valid email address" />)

    // getByRole with `description` only matches when aria-describedby actually
    // resolves to the message element.
    expect(
      screen.getByRole('textbox', { description: 'Enter a valid email address' })
    ).toBeInvalid()
  })

  it('leaves a valid field unmarked', () => {
    render(<Field />)

    expect(screen.getByRole('textbox')).toBeValid()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('does not rely on colour alone to signal the error', () => {
    // The red border is paired with a text message and aria-invalid precisely
    // because colour is invisible to some users.
    render(<Field message="Required" />)

    expect(screen.getByRole('textbox')).toBeInvalid()
    expect(screen.getByRole('alert')).toBeVisible()
  })
})
