'use client'

import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
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
import { getErrorMessage } from '@/lib/api'
import { entitlementService } from '@/lib/entitlements'
import { useOnboardingStore } from '@/store/onboardingStore'
import { useEntitlementStore } from '@/store/entitlementStore'
import { FREE_TRIAL_DAYS } from '@/lib/constants'
import { Lock } from 'lucide-react'
import { billingService, useBillingConfig, type BillingConfig } from '@/lib/billing'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

// ISO 3166-1 alpha-2 codes; the display names come from Intl so they need no
// upkeep here. Stripe takes the code as-is for billing_details.address.country.
const POPULAR_COUNTRIES = ['US', 'GB', 'CA', 'AU', 'AE', 'IN', 'PK']
const ALL_COUNTRIES = (
  'AD AE AF AG AI AL AM AO AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BW BY BZ ' +
  'CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK ' +
  'FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GT GU GW GY HK HN HR HT HU ID IE IL IM IN IO IQ IR IS ' +
  'IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ' +
  'ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL ' +
  'PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SK SL SM SN SO SR SS ST SV SX SY SZ TC TD ' +
  'TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS XK YE YT ZA ZM ZW'
).split(' ')

const regionNames =
  typeof Intl !== 'undefined' && 'DisplayNames' in Intl
    ? new Intl.DisplayNames(['en'], { type: 'region' })
    : null

function countryName(code: string): string {
  if (code === 'US') return 'United States of America'
  return regionNames?.of(code) ?? code
}

const OTHER_COUNTRIES = ALL_COUNTRIES.filter((c) => !POPULAR_COUNTRIES.includes(c)).sort((a, b) =>
  countryName(a).localeCompare(countryName(b))
)

const stripeFieldStyle: StripeCardNumberElementOptions['style'] = {
  base: {
    color: '#ffffff',
    fontSize: '14px',
    fontFamily: 'inherit',
    // Each Stripe field is an iframe whose height comes from this line-height.
    // Left unset it collapses to the font's own leading, which is what made the
    // expiry and CVC boxes visibly shorter than the card number beside them.
    lineHeight: '24px',
    '::placeholder': { color: 'rgba(255,255,255,0.5)' },
    iconColor: '#ffffff',
  },
  invalid: { color: '#fca5a5', iconColor: '#fca5a5' },
}

/**
 * The shell around a Stripe field.
 *
 * A fixed height rather than padding: the three boxes wrap iframes of differing
 * intrinsic heights (the card number's also carries the card badge), so equal
 * padding did not produce equal boxes. Pinning the height and centring the
 * contents makes them match by construction.
 */
const cardFieldBox =
  'flex h-12 items-center rounded-lg border border-white/20 bg-white/5 px-3'

const countryGroupLabel = 'px-2 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-white/45'
const countryItem =
  'text-white/85 focus:bg-white/10 focus:text-white data-[state=checked]:text-white [&_svg]:text-emerald-300'

function priceFor(period: 'monthly' | 'yearly', monthly: number, yearly: number | null) {
  return period === 'yearly' && yearly != null ? yearly : monthly
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

function CheckoutForm({ config }: { config: BillingConfig }) {
  const router = useRouter()
  const stripe = useStripe()
  const elements = useElements()
  const { selectedPlan, billingPeriod: chosenPeriod, setBillingPeriod, finish } = useOnboardingStore()
  // Yearly only where the admin priced the plan yearly; the backend refuses a
  // yearly checkout without a yearly price, so never send one.
  const offersYearly = selectedPlan?.price_yearly != null
  const billingPeriod: 'monthly' | 'yearly' = chosenPeriod === 'yearly' && offersYearly ? 'yearly' : 'monthly'
  const [country, setCountry] = useState('US')
  const [authorize, setAuthorize] = useState(false)
  const [agree, setAgree] = useState(false)
  // Polar: the card is taken on Polar's hosted page, not in this form.
  const hosted = config.checkout_mode === 'hosted'
  const configured = config.configured && (hosted || isStripeConfigured(config.publishable_key))

  // A free trial is once per account. Ask the server rather than assuming, so a
  // returning user is told up front instead of discovering it through a 409 on
  // a button we should not have offered. If the lookup fails we leave the button
  // enabled — the server refuses anyway, and a failed read is no reason to
  // withhold a trial from someone genuinely entitled to one.
  const { data: entitlements } = useQuery({
    queryKey: ['entitlements', 'onboarding'],
    queryFn: () => entitlementService.get(true),
    retry: false,
  })
  const trialUsed = entitlements?.trial_used ?? false
  const queryClient = useQueryClient()

  // A plan persisted by an older session may predate the field, hence the fallback.
  const trialDays = selectedPlan?.trial_days ?? FREE_TRIAL_DAYS

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
        billing_details: { address: { country } },
      })
      if (error) throw new Error(error.message || 'Invalid card details')

      return onboardingService.checkout({
        plan_id: selectedPlan.id,
        payment_method_id: paymentMethod.id,
        billing_period: billingPeriod,
      })
    },
    onSuccess: async () => {
      // Re-read the plan before leaving. The entitlement store loads once per
      // session, so a workspace that was trialling a moment ago would otherwise
      // arrive at the dashboard still showing trial limits and the trial
      // banner until the next full page load. Clearing the selection waits
      // until after this — it unmounts the form, and there is no reason to
      // blank the page while a request is still in flight.
      await useEntitlementStore.getState().refresh()
      finish()
      toast.success('Subscription activated! Welcome to Voicecon.')
      router.push('/dashboard')
    },
    onError: (err: any) => {
      // 409 can mean the admin switched payment provider mid-checkout.
      if (err?.response?.status === 409) queryClient.invalidateQueries({ queryKey: ['billing', 'config'] })
      toast.error(getErrorMessage(err))
    },
  })

  // Leaves the page for Polar's checkout; the plan is activated by Polar's
  // webhook and /billing/return brings the customer on to the dashboard.
  const hostedMutation = useMutation({
    mutationFn: () => {
      if (!selectedPlan) throw new Error('Choose a plan first')
      return billingService.startHostedCheckout({
        plan_id: selectedPlan.id,
        billing_period: billingPeriod,
        return_path: '/dashboard',
        cancel_path: '/onboarding/billing',
      })
    },
    onError: (err: any) => {
      if (err?.response?.status === 409) queryClient.invalidateQueries({ queryKey: ['billing', 'config'] })
      toast.error(getErrorMessage(err))
    },
  })

  const trialMutation = useMutation({
    mutationFn: () =>
      onboardingService.startTrial({ plan_id: selectedPlan?.id, billing_period: billingPeriod }),
    onSuccess: () => {
      finish()
      toast.success(`Your ${trialDays}-day free trial has started!`)
      router.push('/dashboard')
    },
    onError: (err: any) => toast.error(getErrorMessage(err)),
  })

  const handleGetStarted = () => {
    if (!authorize || !agree) {
      toast.error('Please accept both agreements to continue')
      return
    }
    if (!configured) {
      toast.error(`Payments are not available yet. Try the ${trialDays}-day free trial instead.`)
      return
    }
    if (hosted) hostedMutation.mutate()
    else checkoutMutation.mutate()
  }

  if (!selectedPlan) return null
  // A successful hosted checkout keeps the button busy while the page leaves.
  const busy =
    checkoutMutation.isPending || trialMutation.isPending || hostedMutation.isPending || hostedMutation.isSuccess

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
            offersYearly && (
            <button
              type="button"
              onClick={() => setBillingPeriod(billingPeriod === 'monthly' ? 'yearly' : 'monthly')}
              className="mt-2 text-xs font-medium text-brand-700 underline underline-offset-2"
            >
              Change Frequency
            </button>
            )
          }
        />
      </div>

      {/* Payment: Polar's hosted page, or the in-app card form (Stripe) */}
      {hosted ? (
        <div
          className="mt-5 rounded-2xl p-5 text-white"
          style={{ background: 'linear-gradient(160deg, #1f6a5f 0%, #15463f 100%)' }}
        >
          <div className="flex items-start gap-3">
            <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-white/10">
              <Lock className="h-4 w-4" />
            </span>
            <div>
              <p className="text-sm font-semibold">Secure checkout</p>
              <p className="mt-1 text-[12px] leading-relaxed text-white/70">
                When you click Get Started you&apos;ll enter your card on our payment partner&apos;s
                secure page. Voicecon never sees or stores your card details. You&apos;ll come
                straight back here once payment is complete.
              </p>
            </div>
          </div>
          {!configured && (
            <p className="mt-3 rounded-md bg-amber-400/15 px-2.5 py-1.5 text-[11px] text-amber-200">
              Payments are not available yet. Use the {trialDays}-day free trial below.
            </p>
          )}
        </div>
      ) : (
      <div
        className="mt-5 rounded-2xl p-5 text-white"
        style={{ background: 'linear-gradient(160deg, #1f6a5f 0%, #15463f 100%)' }}
      >
        {/* Without a Stripe key the Elements never mount, so these boxes cannot take
            input; dim them rather than let them look usable. */}
        <div className={configured ? undefined : 'pointer-events-none opacity-50'} aria-disabled={!configured}>
        <label className="mb-1.5 block text-xs font-medium text-white/80">Card Number</label>
        <div className={`${cardFieldBox} mb-4 gap-2`}>
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
            <div className={cardFieldBox}>
              <div className="flex-1">
                <CardExpiryElement options={{ style: stripeFieldStyle }} />
              </div>
            </div>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-white/80">Security code</label>
            <div className={cardFieldBox}>
              <div className="flex-1">
                <CardCvcElement options={{ style: stripeFieldStyle }} />
              </div>
            </div>
          </div>
        </div>
        </div>

        <label className="mb-1.5 block text-xs font-medium text-white/80">Country</label>
        <Select value={country} onValueChange={setCountry}>
          <SelectTrigger
            aria-label="Country"
            className="h-12 rounded-lg border-white/20 bg-white/5 px-3 text-sm text-white transition-colors hover:border-white/35 hover:bg-white/10 focus:border-white/50 focus:ring-2 focus:ring-white/15 data-[state=open]:border-white/50 data-[state=open]:bg-white/10 [&>svg]:opacity-70"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="max-h-72 rounded-xl border-white/10 bg-[#15463f] text-white shadow-[0_18px_40px_-12px_rgba(0,0,0,0.55)]">
            <SelectGroup>
              <SelectLabel className={countryGroupLabel}>Popular</SelectLabel>
              {POPULAR_COUNTRIES.map((c) => (
                <SelectItem key={c} value={c} className={countryItem}>
                  {countryName(c)}
                </SelectItem>
              ))}
            </SelectGroup>
            <SelectSeparator className="mx-1 my-1.5 bg-white/10" />
            <SelectGroup>
              <SelectLabel className={countryGroupLabel}>All countries</SelectLabel>
              {OTHER_COUNTRIES.map((c) => (
                <SelectItem key={c} value={c} className={countryItem}>
                  {countryName(c)}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>

        <p className="mt-3 text-[11px] leading-relaxed text-white/60">
          By providing your card information, you allow Voicecon to charge your card for future
          payments in accordance with their terms.
        </p>
        {!configured && (
          <p className="mt-2 rounded-md bg-amber-400/15 px-2.5 py-1.5 text-[11px] text-amber-200">
            Card payments are not available yet. Use the {trialDays}-day free trial below.
          </p>
        )}
      </div>
      )}

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
          disabled={busy || trialUsed}
          title={trialUsed ? 'Your free trial has already been used' : undefined}
          className="flex-1 rounded-lg bg-slate-900 px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {trialUsed
            ? 'Free trial already used'
            : trialMutation.isPending
            ? 'Starting…'
            : `Try voicecon for ${trialDays} days`}
        </button>
        <button
          type="button"
          onClick={handleGetStarted}
          disabled={busy}
          className="flex-1 rounded-lg bg-brand-600 px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:opacity-60"
        >
          {checkoutMutation.isPending
            ? 'Processing…'
            : hostedMutation.isPending || hostedMutation.isSuccess
            ? 'Opening checkout…'
            : 'Get Started'}
        </button>
      </div>
      <p className="mt-3 text-[11px] text-slate-400">
        {trialUsed
          ? 'Your free trial has already been used — a free trial is available once per account. Choose a plan to continue.'
          : 'The free trial needs no card and never charges you. When it ends, choose a plan to keep your agents running.'}
      </p>
    </div>
  )
}

export default function BillingPage() {
  const router = useRouter()
  const { selectedPlan, completed } = useOnboardingStore()
  const { data: config } = useBillingConfig()
  // No Stripe instance in hosted mode: <Elements> accepts null, and the card
  // fields are not rendered then.
  const stripePromise = useMemo(
    () => (config?.checkout_mode === 'card' ? getStripe(config.publishable_key) : null),
    [config?.checkout_mode, config?.publishable_key]
  )

  // If the user lands here without choosing a plan, send them to pricing —
  // unless they have just finished, in which case the empty selection is the
  // expected end state and the page is on its way to the dashboard.
  useEffect(() => {
    if (!selectedPlan && !completed) router.replace('/onboarding/pricing')
  }, [selectedPlan, completed, router])

  if (!selectedPlan) return null
  if (!config) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-brand-100 border-t-brand-600" />
      </div>
    )
  }

  return (
    <div className="mx-auto grid min-h-[calc(100vh-3rem)] max-w-7xl grid-cols-1 items-stretch gap-4 overflow-hidden p-3 shadow-slate-200/60 md:rounded-3xl md:bg-white md:shadow-xl lg:grid-cols-2">
      {/* Keyed on the provider: Stripe's <Elements> must not change its stripe prop in place. */}
      <Elements key={`${config.checkout_mode}:${config.publishable_key ?? ''}`} stripe={stripePromise}>
        <CheckoutForm config={config} />
      </Elements>
      <div className="hidden lg:block">
        <BrandPanel />
      </div>
    </div>
  )
}
