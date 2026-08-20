'use client'

import { forwardRef, useState, type InputHTMLAttributes, type ReactNode } from 'react'
import { Eye, EyeOff } from 'lucide-react'

import { cn } from '@/lib/utils'

interface PasswordInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  /** Decoration rendered inside the field on the left, e.g. a lock glyph. */
  leftIcon?: ReactNode
  /** Classes for the positioning wrapper, not the input. */
  containerClassName?: string
}

/**
 * A password field with a show/hide toggle.
 *
 * Exists because every screen used to build this by hand, and three of the
 * eight password fields in the app were built without the toggle at all — both
 * "confirm password" fields and all three fields on the profile screen. Confirm
 * fields are exactly where it matters most: the user is asked to retype
 * something they cannot read, and told only after submitting that the two did
 * not match.
 *
 * Each instance owns its own visibility, so revealing a password does not
 * reveal the confirmation beside it.
 */
export const PasswordInput = forwardRef<HTMLInputElement, PasswordInputProps>(
  function PasswordInput({ className, leftIcon, containerClassName, ...props }, ref) {
    const [visible, setVisible] = useState(false)

    return (
      <div className={cn('relative', containerClassName)}>
        {leftIcon}
        <input
          ref={ref}
          type={visible ? 'text' : 'password'}
          // Right padding comes last so it always survives the merge: without
          // it the text runs underneath the toggle.
          className={cn(className, 'pr-10')}
          {...props}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          disabled={props.disabled}
          // The label states what the button *does*, not what it shows, and
          // aria-pressed carries the current state — a screen reader user needs
          // to know whether their password is currently on screen.
          aria-label={visible ? 'Hide password' : 'Show password'}
          aria-pressed={visible}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 transition-colors hover:text-slate-600 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {visible ? (
            <EyeOff className="h-4 w-4" aria-hidden="true" />
          ) : (
            <Eye className="h-4 w-4" aria-hidden="true" />
          )}
        </button>
      </div>
    )
  }
)
