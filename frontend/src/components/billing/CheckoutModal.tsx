'use client'

import { useMemo, useState } from 'react'
import { Elements, CardElement, useStripe, useElements } from '@stripe/react-stripe-js'
import { toast } from 'sonner'
import { Lock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS, FREE_TRIAL_DAYS } from '@/lib/constants'
import { getStripe, isStripeConfigured } from '@/lib/stripe'
import { billingService, useBillingConfig } from '@/lib/billing'

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
  return period === 'yearly' ? yearly ?? Math.round(monthly * 12 * 0.85) : monthly
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
}

/** Stripe: the card is collected here. Must render inside <Elements>. */
function CardPayment({ plan, billingPeriod, price, busy, submitting, setSubmitting, onSuccess }: PayProps) {
  const stripe = useStripe()
  const elements = useElements()

  const pay = async () => {
    if (!stripe || !elements) {
      toast.error('Payment form is still loading')
      return
    }
    const card = elements.getElement(CardElement)
    if (!card) return
    setSubmitting(true)
    try {
      const { error, paymentMethod } = await stripe.createPaymentMethod({ type: 'card', card })
      if (error) throw new Error(error.message || 'Invalid card details')
      await apiClient.post(API_ENDPOINTS.BILLING_CHECKOUT, {
        plan_id: plan.id,
        payment_method_id: paymentMethod.id,
        billing_period: billingPeriod,
      })
      toast.success('Subscription activated!')
      onSuccess()
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <div className="rounded-lg border border-gray-300 p-3">
        <CardElement options={{ style: { base: { fontSize: '15px' } } }} />
      </div>
      <Button className="w-full bg-blue-600 hover:bg-blue-700" onClick={pay} disabled={busy}>
        {submitting ? 'Processing…' : `Pay $${price} & Subscribe`}
      </Button>
    </>
  )
}

/** Polar: the customer pays on Polar's hosted page and comes back. */
function HostedPayment({ plan, billingPeriod, price, busy, submitting, setSubmitting, returnPath }: PayProps) {
  const pay = async () => {
    setSubmitting(true)
    try {
      await billingService.startHostedCheckout({
        plan_id: plan.id,
        billing_period: billingPeriod,
        return_path: returnPath ?? window.location.pathname,
      })
    } catch (err) {
      toast.error(getErrorMessage(err))
      setSubmitting(false)
    }
  }

  return (
    <>
      <p className="flex items-start gap-2 rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm text-gray-700">
        <Lock className="mt-0.5 h-4 w-4 flex-shrink-0 text-gray-500" />
        You&apos;ll pay on our payment partner&apos;s secure checkout page, then come straight back here.
      </p>
      <Button className="w-full bg-blue-600 hover:bg-blue-700" onClick={pay} disabled={busy}>
        {submitting ? 'Opening checkout…' : `Continue to payment · $${price}`}
      </Button>
    </>
  )
}

export function CheckoutModal({ plan, billingPeriod, onClose, onSuccess, returnPath }: Props) {
  const { data: config, isLoading } = useBillingConfig()
  const [submitting, setSubmitting] = useState(false)
  const [startingTrial, setStartingTrial] = useState(false)

  const hosted = config?.checkout_mode === 'hosted'
  const stripePromise = useMemo(
    () => (config?.checkout_mode === 'card' ? getStripe(config.publishable_key) : null),
    [config?.checkout_mode, config?.publishable_key]
  )

  const price = priceFor(billingPeriod, plan.price_monthly, plan.price_yearly)
  const trialDays = plan.trial_days ?? FREE_TRIAL_DAYS
  const busy = submitting || startingTrial
  const configured =
    !!config?.configured && (hosted || isStripeConfigured(config?.publishable_key))

  const startTrial = async () => {
    setStartingTrial(true)
    try {
      // No `trial_days`: the server owns the length and ignores a client one.
      await apiClient.post(API_ENDPOINTS.BILLING_TRIAL, {
        plan_id: plan.id,
        billing_period: billingPeriod,
      })
      toast.success(`Your ${trialDays}-day free trial has started!`)
      onSuccess()
    } catch (err) {
      toast.error(getErrorMessage(err))
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
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <div className="space-y-4">
          <div>
            <h3 className="text-lg font-bold text-gray-900">Subscribe to {plan.name}</h3>
            <p className="text-sm text-gray-600">
              ${price}/{billingPeriod === 'yearly' ? 'year' : 'month'}, billed {billingPeriod}.
            </p>
          </div>

          {isLoading ? (
            <div className="flex h-20 items-center justify-center">
              <div className="h-7 w-7 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600" />
            </div>
          ) : !configured ? (
            <p className="rounded-lg border border-yellow-200 bg-yellow-50 p-3 text-sm text-yellow-800">
              Payments are not available right now. You can still start a free trial.
            </p>
          ) : hosted ? (
            <HostedPayment {...payProps} />
          ) : (
            <Elements key={config?.publishable_key ?? ''} stripe={stripePromise}>
              <CardPayment {...payProps} />
            </Elements>
          )}

          <div className="flex items-center gap-3">
            <Button variant="outline" className="flex-1" onClick={startTrial} disabled={busy}>
              {startingTrial ? 'Starting…' : `Start ${trialDays}-day free trial`}
            </Button>
            <Button variant="ghost" onClick={onClose} disabled={busy}>
              Cancel
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
