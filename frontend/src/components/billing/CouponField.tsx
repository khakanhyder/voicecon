'use client'

import { useEffect, useRef, useState } from 'react'
import { Tag, X } from 'lucide-react'
import { getErrorMessage } from '@/lib/api'
import { billingService, type CouponQuote } from '@/lib/billing'

interface Props {
  billingPeriod: 'monthly' | 'yearly'
  /** A code the customer already entered (onboarding), tried before the referral's own. */
  initialCode?: string
  /** The applied coupon, or null when none applies. */
  onChange: (coupon: CouponQuote | null) => void
  disabled?: boolean
}

/**
 * Affiliate coupon entry for checkout.
 *
 * Prefills the coupon of the affiliate who referred this workspace, and
 * re-checks the applied code whenever the billing period changes — a coupon
 * can be annual-only, so switching to monthly may take it away again. The
 * server re-checks on checkout; this only keeps the price shown honest.
 */
export function CouponField({ billingPeriod, initialCode, onChange, disabled }: Props) {
  const [input, setInput] = useState(initialCode ?? '')
  const [applied, setApplied] = useState<CouponQuote | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)
  // The code to re-check on a period change: the applied one, else the typed one.
  const wanted = useRef<string | undefined>(initialCode || undefined)
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange

  const settle = (quote: CouponQuote | null, why: string | null) => {
    setApplied(quote)
    setMessage(why)
    onChangeRef.current(quote)
  }

  useEffect(() => {
    let active = true
    setChecking(true)
    billingService
      .checkCoupon(wanted.current, billingPeriod)
      .then((quote) => {
        if (!active) return
        if (quote.valid) {
          setInput(quote.code ?? '')
          wanted.current = quote.code ?? undefined
          settle(quote, null)
        } else {
          settle(null, wanted.current ? quote.message ?? null : null)
        }
      })
      .catch(() => active && settle(null, null))
      .finally(() => active && setChecking(false))
    return () => {
      active = false
    }
  }, [billingPeriod])

  const apply = async () => {
    const code = input.trim()
    if (!code) return
    setChecking(true)
    try {
      const quote = await billingService.checkCoupon(code, billingPeriod)
      wanted.current = code
      settle(quote.valid ? quote : null, quote.valid ? null : quote.message || "That coupon code isn't valid.")
    } catch (err) {
      settle(null, getErrorMessage(err, "We couldn't check that code. Please try again."))
    } finally {
      setChecking(false)
    }
  }

  const remove = () => {
    wanted.current = undefined
    setInput('')
    settle(null, null)
  }

  if (applied?.valid) {
    return (
      <div className="flex items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm">
        <span className="flex items-center gap-2 text-emerald-800">
          <Tag className="h-4 w-4" />
          <span>
            <span className="font-semibold">{applied.code}</span> · {applied.description}
          </span>
        </span>
        <button
          type="button"
          onClick={remove}
          disabled={disabled}
          className="rounded p-1 text-emerald-700 hover:bg-emerald-100"
          aria-label="Remove coupon"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-1.5">
      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              apply()
            }
          }}
          placeholder="Coupon code"
          aria-label="Coupon code"
          disabled={disabled || checking}
          className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm uppercase outline-none placeholder:normal-case focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
        />
        <button
          type="button"
          onClick={apply}
          disabled={disabled || checking || !input.trim()}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          {checking ? 'Checking…' : 'Apply'}
        </button>
      </div>
      {message && <p className="text-xs text-red-600">{message}</p>}
    </div>
  )
}
