'use client'

import { useEffect, useRef } from 'react'

interface OtpInputProps {
  value: string
  onChange: (value: string) => void
  /** Fired when the last box is filled, so the form can submit itself. */
  onComplete?: (value: string) => void
  length?: number
  disabled?: boolean
  autoFocus?: boolean
}

/**
 * One box per digit, as people expect from an emailed code.
 *
 * Handles the things that make a code field annoying otherwise: typing moves
 * forward, Backspace moves back, and pasting the whole code from the email
 * fills every box at once instead of landing in the first one.
 */
export function OtpInput({
  value,
  onChange,
  onComplete,
  length = 6,
  disabled,
  autoFocus,
}: OtpInputProps) {
  const refs = useRef<Array<HTMLInputElement | null>>([])

  useEffect(() => {
    if (autoFocus) refs.current[0]?.focus()
  }, [autoFocus])

  const digits = value.padEnd(length, ' ').slice(0, length).split('')

  const commit = (next: string) => {
    onChange(next)
    if (next.length === length) onComplete?.(next)
  }

  const setDigit = (index: number, digit: string) => {
    const chars = value.split('')
    chars[index] = digit
    // Trailing gaps would let a half-filled code read as complete.
    commit(chars.join('').replace(/\s/g, '').slice(0, length))
  }

  const handleChange = (index: number, raw: string) => {
    const digit = raw.replace(/\D/g, '').slice(-1)
    if (!digit) return
    setDigit(index, digit)
    if (index < length - 1) refs.current[index + 1]?.focus()
  }

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace') {
      e.preventDefault()
      if (value[index]) {
        commit(value.slice(0, index) + value.slice(index + 1))
      } else if (index > 0) {
        commit(value.slice(0, index - 1) + value.slice(index))
        refs.current[index - 1]?.focus()
      }
    } else if (e.key === 'ArrowLeft' && index > 0) {
      refs.current[index - 1]?.focus()
    } else if (e.key === 'ArrowRight' && index < length - 1) {
      refs.current[index + 1]?.focus()
    }
  }

  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault()
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, length)
    if (!pasted) return
    commit(pasted)
    refs.current[Math.min(pasted.length, length - 1)]?.focus()
  }

  return (
    <div className="flex gap-2" role="group" aria-label="Verification code">
      {Array.from({ length }).map((_, i) => (
        <input
          key={i}
          ref={(el) => {
            refs.current[i] = el
          }}
          type="text"
          inputMode="numeric"
          autoComplete={i === 0 ? 'one-time-code' : 'off'}
          maxLength={1}
          value={digits[i]?.trim() ?? ''}
          onChange={(e) => handleChange(i, e.target.value)}
          onKeyDown={(e) => handleKeyDown(i, e)}
          onPaste={handlePaste}
          onFocus={(e) => e.target.select()}
          disabled={disabled}
          aria-label={`Digit ${i + 1}`}
          className="h-12 w-full min-w-0 rounded-lg border border-slate-300 bg-white text-center text-lg font-bold text-slate-900 outline-none transition-all focus:border-[#243275] focus:ring-3 focus:ring-[#243275]/15 disabled:opacity-50"
        />
      ))}
    </div>
  )
}
