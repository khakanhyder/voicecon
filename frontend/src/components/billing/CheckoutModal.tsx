'use client'

import { useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Elements, CardElement, useStripe, useElements } from '@stripe/react-stripe-js'
import { toast } from 'sonner'
import { Lock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ModalOverlay } from '@/components/ui/modal-overlay'
import { apiClient, getErrorMessage } from '@/lib/api'
import { BillingOwnerNotice, useBillingAccess } from '@/components/billing/BillingOwnerNotice'
import { API_ENDPOINTS, FREE_TRIAL_DAYS } from '@/lib/constants'
import { getStripe, isStripeConfigured } from '@/lib/stripe'
import { billingService, discountedPrice, useBillingConfig, type CouponQuote } from '@/lib/billing'
import { CouponField } from '@/components/billing/CouponField'
import { useEntitlementStore } from '@/store/entitlementStore'

export interface CheckoutPlan {
  id: string
  name: string
  price_monthly: number
  price_yearly: number | null
  /** From `GET /billing/plans`. Falls back to `FREE_TRIAL_DAYS` when absent. */
  trial_days?: number
}

interface Props {
  plan: CheckoutPlan
  billingPeriod: 'monthly' | 'yearly'
  onClose: () => void
  onSuccess: () => void
  /** Where to land after a hosted (Polar) checkout. Defaults to the current page. */
  returnPath?: string
}

function priceFor(period: 'monthly' | 'yearly', monthly: number, yearly: number | null) {
  return period === 'yearly' && yearly != null ? yearly : monthly
}

/**
 * A 409 from checkout can mean the admin switched payment provider while this
 * form was open ("Checkout now goes through …"). Refetch the config so the
 * right form replaces this one, rather than waiting for a window refocus.
 */
function useRefreshConfigOnConflict() {
  const queryClient = useQueryClient()
  return (err: unknown) => {
    if ((err as { response?: { status?: number } })?.response?.status === 409) {
      queryClient.invalidateQueries({ queryKey: ['billing', 'config'] })
    }
  }
}

interface PayProps {
  plan: CheckoutPlan
  billingPeriod: 'monthly' | 'yearly'
  price: number
  busy: boolean
  setSubmitting: (v: boolean) => void
  submitting: boolean
  onSuccess: () => void
  returnPath?: string
  couponCode?: string
  /** Shows a payment problem inside the dialog, where it stays readable. */
  onError: (message: string | null) => void
}

/** Stripe: the card is collected here. Must render inside <Elements>. */
function CardPayment({ plan, billingPeriod, price, busy, submitting, setSubmitting, onSuccess, couponCode, onError }: PayProps) {
  const stripe = useStripe()
  const elements = useElements()
  const refreshConfigOnConflict = useRefreshConfigOnConflict()

  const pay = async () => {
    if (!stripe || !elements) {
      toast.error('Payment form is still loading')
      return
    }
    const card = elements.getElement(CardElement)
    if (!card) return
    setSubmitting(true)
    onError(null)
    try {
      const { error, paymentMethod } = await stripe.createPaymentMethod({ type: 'card', card })
      if (error) throw new Error(error.message || 'Invalid card details')
      await billingService.payWithCard(stripe, {
        plan_id: plan.id,
        payment_method_id: paymentMethod.id,
        billing_period: billingPeriod,
        coupon_code: couponCode,
      })
      toast.success(`You're subscribed to ${plan.name}. The new limits are active now.`)
      onSuccess()
    } catch (err) {
      refreshConfigOnConflict(err)
      onError(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <div className="rounded-lg border border-gray-300 p-3">
        <CardElement options={{ style: { base: { fontSize: '15px' } } }} />
      </div>
      <Button className="w-full bg-[#106959] text-white hover:bg-[#0c5044]" onClick={pay} disabled={busy}>
        {submitting ? 'Processing…' : `Pay $${price} & Subscribe`}
      </Button>
      <p className="flex items-center justify-center gap-1.5 text-xs text-gray-500">
        <Lock className="h-3 w-3" aria-hidden="true" />
        Card details go straight to Stripe. Your bank may ask you to approve the payment.
      </p>
    </>
  )
}

/** Polar: the customer pays on Polar's hosted page and comes back. */
function HostedPayment({ plan, billingPeriod, price, busy, submitting, setSubmitting, returnPath, couponCode, onError }: PayProps) {
  const refreshConfigOnConflict = useRefreshConfigOnConflict()
  const pay = async () => {
    setSubmitting(true)
    onError(null)
    try {
      await billingService.startHostedCheckout({
        plan_id: plan.id,
        billing_period: billingPeriod,
        return_path: returnPath ?? window.location.pathname,
        coupon_code: couponCode,
      })
    } catch (err) {
      refreshConfigOnConflict(err)
      onError(getErrorMessage(err))
      setSubmitting(false)
    }
  }

  return (
    <>
      <p className="flex items-start gap-2 rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm text-gray-700">
        <Lock className="mt-0.5 h-4 w-4 flex-shrink-0 text-gray-500" />
        You&apos;ll pay on our payment partner&apos;s secure checkout page, then come straight back here.
      </p>
      <Button className="w-full bg-[#106959] text-white hover:bg-[#0c5044]" onClick={pay} disabled={busy}>
        {submitting ? 'Opening checkout…' : `Continue to payment · $${price}`}
      </Button>
    </>
  )
}

export function CheckoutModal({ plan, billingPeriod: requestedPeriod, onClose, onSuccess, returnPath }: Props) {
  // Yearly only where the admin priced the plan yearly — the backend refuses a
  // yearly checkout without a yearly price, so bill monthly instead.
  const billingPeriod: 'monthly' | 'yearly' =
    requestedPeriod === 'yearly' && plan.price_yearly != null ? 'yearly' : 'monthly'
  const { data: config, isLoading } = useBillingConfig()
  const [submitting, setSubmitting] = useState(false)
  const [startingTrial, setStartingTrial] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Only the owner may buy; the API would answer 403 after the card was typed.
  const { canManage } = useBillingAccess()
  // Only offer the trial to a workspace that can still start one; for anyone
  // else (a running, lapsed or used-up trial) the only possible answer is 409.
  const trialAvailable = useEntitlementStore((s) => !!s.entitlements?.trial_available)

  const hosted = config?.checkout_mode === 'hosted'
  const stripePromise = useMemo(
    () => (config?.checkout_mode === 'card' ? getStripe(config.publishable_key) : null),
    [config?.checkout_mode, config?.publishable_key]
  )

  // <Elements> never surfaces a failed Stripe.js load; without this the modal
  // shows an empty card box and "Pay" does nothing useful.
  const [stripeFailed, setStripeFailed] = useState(false)
  useEffect(() => {
    if (!stripePromise) return
    let active = true
    setStripeFailed(false)
    stripePromise
      .then((stripe) => active && !stripe && setStripeFailed(true))
      .catch(() => active && setStripeFailed(true))
    return () => {
      active = false
    }
  }, [stripePromise])

  const listPrice = priceFor(billingPeriod, plan.price_monthly, plan.price_yearly)
  const [coupon, setCoupon] = useState<CouponQuote | null>(null)
  const price = discountedPrice(listPrice, coupon)
  const trialDays = plan.trial_days ?? FREE_TRIAL_DAYS
  const busy = submitting || startingTrial
  const configured =
    !!config?.configured && (hosted || isStripeConfigured(config?.publishable_key))

  const startTrial = async () => {
    setStartingTrial(true)
    setError(null)
    try {
      // No `trial_days`: the server owns the length and ignores a client one.
      await apiClient.post(API_ENDPOINTS.BILLING_TRIAL, {
        plan_id: plan.id,
        billing_period: billingPeriod,
      })
      toast.success(`Your ${trialDays}-day free trial has started!`)
      onSuccess()
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setStartingTrial(false)
    }
  }

  const payProps: PayProps = {
    plan,
    billingPeriod,
    price,
    busy,
    submitting,
    setSubmitting,
    onSuccess,
    returnPath,
    couponCode: coupon?.code ?? undefined,
    onError: setError,
  }

  return (
    // No backdrop close: a stray click outside would throw away a typed card.
    <ModalOverlay onClose={onClose} busy={busy} closeOnBackdrop={false} className="bg-black/40">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="checkout-modal-title"
        className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl"
      >
        <div className="space-y-4">
          <div>
            <h3 id="checkout-modal-title" className="text-lg font-bold text-gray-900">Subscribe to {plan.name}</h3>
            <p className="text-sm text-gray-600">
              {price !== listPrice ? (
                <>
                  <span className="mr-1 text-gray-400 line-through">${listPrice}</span>
                  ${price} due today, billed {billingPeriod}.
                </>
              ) : (
                <>
                  ${price}/{billingPeriod === 'yearly' ? 'year' : 'month'}, billed {billingPeriod}.
                </>
              )}
            </p>
          </div>

          {canManage && configured && !isLoading && (
            <CouponField billingPeriod={billingPeriod} onChange={setCoupon} disabled={busy} />
          )}

          {!canManage ? (
            <BillingOwnerNotice />
          ) : isLoading ? (
            <div className="flex h-20 items-center justify-center">
              <div className="h-7 w-7 animate-spin rounded-full border-4 border-gray-200 border-t-[#106959]" />
            </div>
          ) : !configured ? (
            <p className="rounded-lg border border-yellow-200 bg-yellow-50 p-3 text-sm text-yellow-800">
              Payments are not available right now.
              {trialAvailable ? ' You can still start a free trial.' : ' Please try again later.'}
            </p>
          ) : hosted ? (
            <HostedPayment {...payProps} />
          ) : stripeFailed ? (
            <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
              The secure payment form couldn&apos;t load. Check your connection or disable any
              content blocker for this site, then close this window and try again.
            </p>
          ) : (
            <Elements key={config?.publishable_key ?? ''} stripe={stripePromise}>
              <CardPayment {...payProps} />
            </Elements>
          )}

          {error && (
            <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
              {error}
            </p>
          )}

          <div className="flex items-center gap-3">
            {canManage && trialAvailable && (
              <Button variant="outline" className="flex-1" onClick={startTrial} disabled={busy}>
                {startingTrial ? 'Starting…' : `Start ${trialDays}-day free trial`}
              </Button>
            )}
            <Button variant="ghost" className={canManage && trialAvailable ? '' : 'ml-auto'} onClick={onClose} disabled={busy}>
              {canManage ? 'Cancel' : 'Close'}
            </Button>
          </div>
        </div>
      </div>
    </ModalOverlay>
  )
}
