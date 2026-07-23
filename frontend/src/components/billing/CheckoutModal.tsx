'use client'

import { useState } from 'react'
import { Elements, CardElement, useStripe, useElements } from '@stripe/react-stripe-js'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { getStripe, isStripeConfigured } from '@/lib/stripe'

export interface CheckoutPlan {
  id: string
  name: string
  price_monthly: number
  price_yearly: number | null
}

interface Props {
  plan: CheckoutPlan
  billingPeriod: 'monthly' | 'yearly'
  onClose: () => void
  onSuccess: () => void
}

function priceFor(period: 'monthly' | 'yearly', monthly: number, yearly: number | null) {
  return period === 'yearly' ? yearly ?? Math.round(monthly * 12 * 0.85) : monthly
}

function InnerForm({ plan, billingPeriod, onClose, onSuccess }: Props) {
  const stripe = useStripe()
  const elements = useElements()
  const [submitting, setSubmitting] = useState(false)
  const [startingTrial, setStartingTrial] = useState(false)

  const price = priceFor(billingPeriod, plan.price_monthly, plan.price_yearly)

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

  const startTrial = async () => {
    setStartingTrial(true)
    try {
      await apiClient.post(API_ENDPOINTS.BILLING_TRIAL, {
        plan_id: plan.id,
        billing_period: billingPeriod,
        trial_days: 7,
      })
      toast.success('Your 7-day free trial has started!')
      onSuccess()
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setStartingTrial(false)
    }
  }

  const busy = submitting || startingTrial
  const configured = isStripeConfigured()

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-bold text-gray-900">Subscribe to {plan.name}</h3>
        <p className="text-sm text-gray-600">
          ${price}/{billingPeriod === 'yearly' ? 'year' : 'month'}, billed {billingPeriod}.
        </p>
      </div>

      {configured ? (
        <>
          <div className="rounded-lg border border-gray-300 p-3">
            <CardElement options={{ style: { base: { fontSize: '15px' } } }} />
          </div>
          <Button className="w-full bg-blue-600 hover:bg-blue-700" onClick={pay} disabled={busy}>
            {submitting ? 'Processing…' : `Pay $${price} & Subscribe`}
          </Button>
        </>
      ) : (
        <p className="rounded-lg bg-yellow-50 border border-yellow-200 p-3 text-sm text-yellow-800">
          Card payments are not configured. You can still start a free trial.
        </p>
      )}

      <div className="flex items-center gap-3">
        <Button variant="outline" className="flex-1" onClick={startTrial} disabled={busy}>
          {startingTrial ? 'Starting…' : 'Start 7-day free trial'}
        </Button>
        <Button variant="ghost" onClick={onClose} disabled={busy}>
          Cancel
        </Button>
      </div>
    </div>
  )
}

export function CheckoutModal(props: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <Elements stripe={getStripe()}>
          <InnerForm {...props} />
        </Elements>
      </div>
    </div>
  )
}
