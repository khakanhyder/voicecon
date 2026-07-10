'use client'

import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  Elements,
  CardNumberElement,
  CardExpiryElement,
  CardCvcElement,
  useStripe,
  useElements,
} from '@stripe/react-stripe-js'
import type { StripeCardNumberElementOptions } from '@stripe/stripe-js'
import { VoiceconLogo } from '@/lib/icons'
import { BrandPanel } from '@/components/auth/BrandPanel'
import { getStripe, isStripeConfigured } from '@/lib/stripe'
import { onboardingService } from '@/lib/onboarding'
import { useOnboardingStore } from '@/store/onboardingStore'

const COUNTRIES = [
  'United States of America',
  'United Kingdom',
  'Canada',
  'Australia',
  'United Arab Emirates',
  'India',
  'Pakistan',
]

const stripeFieldStyle: StripeCardNumberElementOptions['style'] = {
  base: {
    color: '#ffffff',
    fontSize: '14px',
    fontFamily: 'inherit',
    '::placeholder': { color: 'rgba(255,255,255,0.5)' },
    iconColor: '#ffffff',
  },
  invalid: { color: '#fca5a5', iconColor: '#fca5a5' },
}

function priceFor(period: 'monthly' | 'yearly', monthly: number, yearly: number | null) {
  return period === 'yearly' ? (yearly ?? monthly * 12 * 0.75) : monthly
}

function nextPaymentDate(period: 'monthly' | 'yearly'): string {
  const d = new Date()
  if (period === 'yearly') d.setFullYear(d.getFullYear() + 1)
  else d.setMonth(d.getMonth() + 1)
  return d.toLocaleDateString('en-GB')
}

/** Order summary block reused in two places on the billing screen. */
function SummaryCard({
  planName,
  price,
  periodLabel,
  footer,
}: {
  planName: string
  price: number
  periodLabel: string
  footer?: React.ReactNode
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50/60 p-5">
      <div className="flex items-center justify-between border-b border-slate-200 pb-3">
        <span className="text-sm text-slate-600">Package Name</span>
        <span className="text-sm font-bold text-slate-900">{planName}</span>
      </div>
      <div className="flex items-center justify-between border-b border-slate-200 py-3">
        <span className="text-sm text-slate-600">Price</span>
        <span className="text-sm font-semibold text-slate-900">${price.toFixed(0)}</span>
      </div>
      <div className="flex items-center justify-between pt-3">
        <span className="text-sm text-slate-600">Total Amount</span>
        <span className="text-sm font-bold text-slate-900">{periodLabel}</span>
      </div>
      {footer}
    </div>
  )
}

function CheckoutForm() {
  const router = useRouter()
  const stripe = useStripe()
  const elements = useElements()
  const { selectedPlan, billingPeriod, setBillingPeriod, reset } = useOnboardingStore()
  const [country, setCountry] = useState(COUNTRIES[0])
  const [authorize, setAuthorize] = useState(false)
  const [agree, setAgree] = useState(false)
  const configured = isStripeConfigured()

  const price = selectedPlan
    ? priceFor(billingPeriod, selectedPlan.price_monthly, selectedPlan.price_yearly)
    : 0
  const periodLabel = billingPeriod === 'yearly' ? 'Billed Yearly' : 'Billed Monthly'

  const checkoutMutation = useMutation({
    mutationFn: async () => {
      if (!stripe || !elements || !selectedPlan) throw new Error('Stripe not ready')
      const cardNumber = elements.getElement(CardNumberElement)
      if (!cardNumber) throw new Error('Card details missing')

      const { error, paymentMethod } = await stripe.createPaymentMethod({
        type: 'card',
        card: cardNumber,
        billing_details: { address: { country: countryCode(country) } },
      })
      if (error) throw new Error(error.message || 'Invalid card details')

      return onboardingService.checkout({
        plan_id: selectedPlan.id,
        payment_method_id: paymentMethod.id,
        billing_period: billingPeriod,
      })
    },
    onSuccess: () => {
      reset()
      toast.success('Subscription activated! Welcome to Voicecon.')
      router.push('/dashboard')
    },
    onError: (err: any) =>
      toast.error(err.response?.data?.detail || err.message || 'Payment failed'),
  })

  const trialMutation = useMutation({
    mutationFn: () =>
      onboardingService.startTrial({ plan_id: selectedPlan?.id, billing_period: billingPeriod }),
    onSuccess: () => {
      reset()
      toast.success('Your 7-day free trial has started!')
      router.push('/dashboard')
    },
    onError: (err: any) => toast.error(err.response?.data?.detail || 'Could not start trial'),
  })

  const handleGetStarted = () => {
    if (!authorize || !agree) {
      toast.error('Please accept both agreements to continue')
      return
    }
    if (!configured) {
      toast.error('Card payments are not configured yet. Try the 7-day free trial instead.')
      return
    }
    checkoutMutation.mutate()
  }

  if (!selectedPlan) return null
  const busy = checkoutMutation.isPending || trialMutation.isPending

  return (
    <div className="flex flex-col py-6 lg:px-10">
      <div className="mb-5 flex items-center gap-2">
        <VoiceconLogo className="h-7 w-7" />
        <span className="text-xl font-bold text-slate-900">Voicecon</span>
      </div>
      <h1 className="text-[28px] font-medium md:font-bold text-slate-900">Billing</h1>

      {/* Package summary */}
      <div className="mt-5">
        <SummaryCard
          planName={selectedPlan.name}
          price={price}
          periodLabel={periodLabel}
          footer={
            <button
              type="button"
              onClick={() => setBillingPeriod(billingPeriod === 'monthly' ? 'yearly' : 'monthly')}
              className="mt-2 text-xs font-medium text-brand-700 underline underline-offset-2"
            >
              Change Frequency
            </button>
          }
        />
      </div>

      {/* Card form (dark) */}
      <div
        className="mt-5 rounded-2xl p-5 text-white"
        style={{ background: 'linear-gradient(160deg, #1f6a5f 0%, #15463f 100%)' }}
      >
        <label className="mb-1.5 block text-xs font-medium text-white/80">Card Number</label>
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-white/20 bg-white/5 px-3 py-2.5">
          <div className="flex-1">
            <CardNumberElement
              options={{ style: stripeFieldStyle, placeholder: 'Card Number' }}
            />
          </div>
          <span className="rounded bg-white px-1.5 py-0.5 text-[10px] font-bold text-blue-700">
            VISA
          </span>
        </div>

        <div className="mb-4 grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-white/80">Expiration date</label>
            <div className="rounded-lg border border-white/20 bg-white/5 px-3 py-2.5">
              <CardExpiryElement options={{ style: stripeFieldStyle }} />
            </div>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-white/80">Security code</label>
            <div className="rounded-lg border border-white/20 bg-white/5 px-3 py-2.5">
              <CardCvcElement options={{ style: stripeFieldStyle }} />
            </div>
          </div>
        </div>

        <label className="mb-1.5 block text-xs font-medium text-white/80">Country</label>
        <select
          value={country}
          onChange={(e) => setCountry(e.target.value)}
          className="w-full rounded-lg border border-white/20 bg-white/5 px-3 py-2.5 text-sm text-white outline-none [&>option]:text-slate-900"
        >
          {COUNTRIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>

        <p className="mt-3 text-[11px] leading-relaxed text-white/60">
          By providing your card information, you allow Voicecon to charge your card for future
          payments in accordance with their terms.
        </p>
        {!configured && (
          <p className="mt-2 rounded-md bg-amber-400/15 px-2.5 py-1.5 text-[11px] text-amber-200">
            Stripe test keys are not set yet — use the 7-day free trial below, or add your keys to
            enable card payments.
          </p>
        )}
      </div>

      {/* Order summary */}
      <div className="mt-6">
        <h2 className="mb-3 text-lg font-bold text-slate-900">Order Summary</h2>
        <SummaryCard
          planName={selectedPlan.name}
          price={price}
          periodLabel={periodLabel}
          footer={
            <p className="mt-2 text-xs italic text-brand-700">
              Your next payment will be on {nextPaymentDate(billingPeriod)}.
            </p>
          }
        />
      </div>

      {/* Agreements */}
      <div className="mt-5 space-y-3">
        <label className="flex cursor-pointer items-start gap-2.5 text-[12px] leading-snug text-slate-600">
          <input
            type="checkbox"
            checked={authorize}
            onChange={(e) => setAuthorize(e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
          />
          I authorize Voicecon to charge my payment method on a recurring basis according to the
          terms of my subscription plan. I understand I can cancel anytime.
        </label>
        <label className="flex cursor-pointer items-start gap-2.5 text-[12px] leading-snug text-slate-600">
          <input
            type="checkbox"
            checked={agree}
            onChange={(e) => setAgree(e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
          />
          I promise to play by the rules, telemarketing and data privacy laws included. I own my
          actions and let Voicecon off the hook for any mess I make.
        </label>
      </div>

      {/* Actions */}
      <div className="mt-5 flex flex-col gap-3 sm:flex-row">
        <button
          type="button"
          onClick={() => trialMutation.mutate()}
          disabled={busy}
          className="flex-1 rounded-lg bg-slate-900 px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-slate-800 disabled:opacity-60"
        >
          {trialMutation.isPending ? 'Starting…' : 'Try voicecon for 7 days'}
        </button>
        <button
          type="button"
          onClick={handleGetStarted}
          disabled={busy}
          className="flex-1 rounded-lg bg-brand-600 px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:opacity-60"
        >
          {checkoutMutation.isPending ? 'Processing…' : 'Get Started'}
        </button>
      </div>
      <p className="mt-3 text-[11px] text-slate-400">
        The trial will be converted to the selected subscription unless canceled before the end of
        the trial period.
      </p>
    </div>
  )
}

export default function BillingPage() {
  const router = useRouter()
  const { selectedPlan } = useOnboardingStore()
  const stripePromise = useMemo(() => getStripe(), [])

  // If the user lands here without choosing a plan, send them to pricing.
  useEffect(() => {
    if (!selectedPlan) router.replace('/onboarding/pricing')
  }, [selectedPlan, router])

  if (!selectedPlan) return null

  return (
    <div className="mx-auto grid min-h-[calc(100vh-3rem)] max-w-7xl grid-cols-1 items-stretch gap-4 overflow-hidden p-3 shadow-slate-200/60 md:rounded-3xl md:bg-white md:shadow-xl lg:grid-cols-2">
      <Elements stripe={stripePromise}>
        <CheckoutForm />
      </Elements>
      <div className="hidden lg:block">
        <BrandPanel />
      </div>
    </div>
  )
}

/** Minimal country-name → ISO code map for Stripe billing details. */
function countryCode(name: string): string {
  const map: Record<string, string> = {
    'United States of America': 'US',
    'United Kingdom': 'GB',
    Canada: 'CA',
    Australia: 'AU',
    'United Arab Emirates': 'AE',
    India: 'IN',
    Pakistan: 'PK',
  }
  return map[name] ?? 'US'
}
