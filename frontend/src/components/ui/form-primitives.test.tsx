/**
 * Component tests for the form and layout primitives: Input, Label, Textarea,
 * Alert and Card.
 *
 * These are thin wrappers over native elements, and that is precisely the
 * property worth guarding. Their value is that they stay real `<input>`,
 * `<label>` and `<textarea>` elements — label/control association, disabled
 * semantics and form participation all come from the element, not the styling.
 * A refactor into styled `<div>`s would look identical and break all of it.
 */
import { createRef } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { Alert, AlertDescription, AlertTitle } from './alert'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './card'
import { Input } from './input'
import { Label } from './label'
import { Textarea } from './textarea'

describe('Input', () => {
  it('renders a real input the user can type into', async () => {
    const user = userEvent.setup()
    render(<Input aria-label="Email" />)

    await user.type(screen.getByRole('textbox'), 'user@example.com')

    expect(screen.getByRole('textbox')).toHaveValue('user@example.com')
  })

  it('passes the type through', () => {
    // The type drives the mobile keyboard and password masking.
    render(<Input type="password" aria-label="Password" data-testid="pw" />)

    expect(screen.getByTestId('pw')).toHaveAttribute('type', 'password')
  })

  it('cannot be typed into when disabled', async () => {
    const user = userEvent.setup()
    render(<Input disabled aria-label="Email" />)

    await user.type(screen.getByRole('textbox'), 'hello')

    expect(screen.getByRole('textbox')).toHaveValue('')
    expect(screen.getByRole('textbox')).toBeDisabled()
  })

  it('forwards its ref, so forms can focus it', () => {
    // react-hook-form focuses the first invalid field through this ref.
    const ref = createRef<HTMLInputElement>()
    render(<Input ref={ref} aria-label="Email" />)

    expect(ref.current).toBeInstanceOf(HTMLInputElement)
  })

  it('keeps the caller class alongside its own', () => {
    render(<Input className="border-red-500" aria-label="Email" />)

    const input = screen.getByRole('textbox')
    expect(input).toHaveClass('border-red-500')
    expect(input.className.length).toBeGreaterThan('border-red-500'.length)
  })

  it('carries validation attributes through to the DOM', () => {
    // `field-error` sets exactly these; if they were swallowed, the error
    // message would never be associated with the field.
    render(<Input aria-label="Email" aria-invalid aria-describedby="email-error" />)

    expect(screen.getByRole('textbox')).toBeInvalid()
    expect(screen.getByRole('textbox')).toHaveAttribute('aria-describedby', 'email-error')
  })
})

describe('Label', () => {
  it('associates with its control by htmlFor', () => {
    // The association is what makes the accessible name work and what lets a
    // click on the text focus the field.
    render(
      <>
        <Label htmlFor="email">Email address</Label>
        <Input id="email" />
      </>
    )

    expect(screen.getByLabelText('Email address')).toBe(screen.getByRole('textbox'))
  })

  it('focuses its control when clicked', async () => {
    const user = userEvent.setup()
    render(
      <>
        <Label htmlFor="email">Email address</Label>
        <Input id="email" />
      </>
    )

    await user.click(screen.getByText('Email address'))

    expect(screen.getByRole('textbox')).toHaveFocus()
  })

  it('forwards its ref', () => {
    const ref = createRef<HTMLLabelElement>()
    render(<Label ref={ref}>Email</Label>)

    expect(ref.current).toBeInstanceOf(HTMLLabelElement)
  })
})

describe('Textarea', () => {
  it('accepts multi-line input', async () => {
    const user = userEvent.setup()
    render(<Textarea aria-label="Prompt" />)

    await user.type(screen.getByRole('textbox'), 'line one{Enter}line two')

    expect(screen.getByRole('textbox')).toHaveValue('line one\nline two')
  })

  it('is a real textarea, not a growing input', () => {
    render(<Textarea aria-label="Prompt" />)

    expect(screen.getByRole('textbox').tagName).toBe('TEXTAREA')
  })

  it('reports changes to its handler', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<Textarea aria-label="Prompt" onChange={onChange} />)

    await user.type(screen.getByRole('textbox'), 'hi')

    expect(onChange).toHaveBeenCalled()
  })

  it('forwards its ref', () => {
    const ref = createRef<HTMLTextAreaElement>()
    render(<Textarea ref={ref} aria-label="Prompt" />)

    expect(ref.current).toBeInstanceOf(HTMLTextAreaElement)
  })
})

describe('Alert', () => {
  it('announces itself as an alert', () => {
    // Alerts carry errors and billing warnings; without the role they appear
    // silently to a screen-reader user.
    render(
      <Alert>
        <AlertTitle>Payment failed</AlertTitle>
        <AlertDescription>We could not charge your card.</AlertDescription>
      </Alert>
    )

    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('Payment failed')
    expect(alert).toHaveTextContent('We could not charge your card.')
  })

  it('styles the destructive variant differently', () => {
    const { rerender } = render(<Alert>default</Alert>)
    const defaultClasses = screen.getByRole('alert').className

    rerender(<Alert variant="destructive">bad news</Alert>)

    expect(screen.getByRole('alert').className).not.toBe(defaultClasses)
  })

  it('renders its title as a heading element', () => {
    render(
      <Alert>
        <AlertTitle>Heads up</AlertTitle>
      </Alert>
    )

    expect(screen.getByText('Heads up').tagName).toMatch(/^H\d$/)
  })
})

describe('Card', () => {
  it('renders its header and body content', () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Voice AI</CardTitle>
          <CardDescription>$99 per month</CardDescription>
        </CardHeader>
        <CardContent>Everything included.</CardContent>
      </Card>
    )

    expect(screen.getByText('Voice AI')).toBeInTheDocument()
    expect(screen.getByText('$99 per month')).toBeInTheDocument()
    expect(screen.getByText('Everything included.')).toBeInTheDocument()
  })

  it('forwards a ref to the outer element', () => {
    const ref = createRef<HTMLDivElement>()
    render(<Card ref={ref}>x</Card>)

    expect(ref.current).toBeInstanceOf(HTMLDivElement)
  })

  it('accepts arbitrary DOM props', () => {
    render(<Card data-testid="plan-card" aria-label="Plan" />)

    expect(screen.getByTestId('plan-card')).toHaveAttribute('aria-label', 'Plan')
  })
})
