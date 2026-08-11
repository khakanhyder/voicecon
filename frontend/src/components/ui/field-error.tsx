'use client'

import { AlertCircle } from 'lucide-react'

/**
 * The message under a field that failed validation.
 *
 * Replaces the browser's own "Please fill out this field." bubble, which the
 * forms used to fall back on. That bubble cannot be styled, disappears on the
 * next click, is worded by the browser rather than by us, only ever reports the
 * *first* invalid field, and — on a password input with a dotted placeholder —
 * tells the user to fill in a field that looks full.
 *
 * `role="alert"` so a screen reader announces it when it appears; the input
 * points at it with `aria-describedby`, so moving focus into the field reads
 * the reason as well as the label.
 */
export function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null

  return (
    <p id={id} role="alert" className="flex items-center gap-1.5 text-sm text-red-600">
      <AlertCircle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      {message}
    </p>
  )
}

/**
 * Border and ring for an input in the error state.
 *
 * Colour alone would not be enough — it fails for anyone who cannot see red —
 * which is why it always pairs with the message above and `aria-invalid`.
 */
export const errorInputClass =
  'border-red-500 focus:border-red-500 focus:ring-red-500/15'

/** Wire an input to its message: `{...fieldErrorProps('email', errors.email)}`. */
export function fieldErrorProps(name: string, message?: string) {
  return {
    'aria-invalid': message ? true : undefined,
    'aria-describedby': message ? `${name}-error` : undefined,
  } as const
}
