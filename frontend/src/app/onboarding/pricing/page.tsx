'use client'

import { useState, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery, useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { getErrorMessage } from '@/lib/api'
import { entitlementService } from '@/lib/entitlements'
import { Check, ArrowUpRight } from 'lucide-react'
import { VoiceconLogo, SalesChatbotIcon, VoiceAiIcon } from '@/lib/icons'
import { FREE_TRIAL_DAYS, QUERY_KEYS } from '@/lib/constants'
import { onboardingService, type SubscriptionPlan } from '@/lib/onboarding'
import {
  ENTERPRISE,
  isPrepaidPlan,
  paygBullets,
  perMinute,
  periodPrice,
  planCardBullets,
  splitPlans,
  toPricingPlan,
  yearlySavingPercent,
} from '@/lib/pricing'
import { useOnboardingStore } from '@/store/onboardingStore'
import { billingService } from '@/lib/billing'

/** Yearly falls back to monthly when the admin set no yearly price (monthly-only plan). */
function planPrice(plan: SubscriptionPlan, period: 'monthly' | 'yearly'): number {
  return periodPrice(plan, period) ?? plan.price_monthly
}

function billedYearly(plan: SubscriptionPlan, period: 'monthly' | 'yearly'): boolean {
  return period === 'yearly' && periodPrice(plan, 'yearly') !== null
}

function nextPaymentDate(period: 'monthly' | 'yearly'): string {
  const d = new Date()
  if (period === 'yearly') d.setFullYear(d.getFullYear() + 1)
  else d.setMonth(d.getMonth() + 1)
  return d.toLocaleDateString('en-GB')
}

export default function PricingPage() {
  const router = useRouter()
  const { selectedPlan, billingPeriod, promoCode, setSelectedPlan, setBillingPeriod, setPromoCode } =
    useOnboardingStore()
  const [promoInput, setPromoInput] = useState(promoCode)

  // A returning user whose trial is used up cannot "skip" into one; offer the
  // button only when the server would accept it. A failed lookup leaves it on
  // — the server refuses a second trial anyway.
  const { data: entitlements } = useQuery({
    queryKey: ['entitlements', 'onboarding'],
    queryFn: () => entitlementService.get(true),
    retry: false,
  })
  const trialUsed = entitlements?.trial_used ?? false

  const { data: allPlans = [], isLoading } = useQuery({
    queryKey: QUERY_KEYS.BILLING_PLANS,
    queryFn: onboardingService.getPlans,
  })
  // The subscriptions are the row of cards; Pay As You Go, which has no
  // monthly price, is a card of its own underneath.
  const { subscriptions: plans, prepaid: paygPlan } = useMemo(() => splitPlans(allPlans), [allPlans])

  // Default-select the "Most popular" plan (the last plan if none is marked).
  const popularId = useMemo(
    () => (plans.find((p) => p.features?.popular === true) ?? plans[plans.length - 1])?.id,
    [plans]
  )
  const activePlan = useMemo(() => {
    if (selectedPlan) return allPlans.find((p) => p.id === selectedPlan.id) ?? selectedPlan
    return plans.find((p) => p.id === popularId) ?? null
  }, [allPlans, plans, selectedPlan, popularId])
  const paygSelected = isPrepaidPlan(activePlan)
  const paygRate = paygPlan?.entitlements?.billing?.per_minute ?? 0

  const trialDays = activePlan?.trial_days ?? FREE_TRIAL_DAYS
  // Card copy, prices and the yearly saving all come from the admin's plans.
  const bulletsByPlan = useMemo(() => planCardBullets(plans), [plans])
  const yearlySaving = useMemo(() => yearlySavingPercent(plans), [plans])
  const anyYearly = plans.some((p) => p.price_yearly != null)

  const trialMutation = useMutation({
    mutationFn: () =>
      onboardingService.startTrial({ plan_id: activePlan?.id, billing_period: billingPeriod }),
    onSuccess: () => {
      toast.success(`Your ${trialDays}-day free trial has started!`)
      router.push('/dashboard')
    },
    onError: (err: any) => toast.error(getErrorMessage(err)),
  })

  const handleSelect = (plan: SubscriptionPlan) => setSelectedPlan(plan)

  const handleNext = () => {
    if (!activePlan) {
      toast.error('Please select a plan')
      return
    }
    setSelectedPlan(activePlan)
    router.push('/onboarding/billing')
  }

  // Applying credits a new workspace to the coupon's affiliate straight away,
  // so the referral holds even if the customer starts the free trial instead.
  const promoMutation = useMutation({
    mutationFn: (code: string) => billingService.applyCoupon(code, billingPeriod),
    onSuccess: (quote) => {
      setPromoCode(quote.code ?? '')
      setPromoInput(quote.code ?? '')
      toast.success(`Coupon ${quote.code} applied: ${quote.description}`)
    },
    onError: (err) => {
      setPromoCode('')
      toast.error(getErrorMessage(err, "That coupon code isn't valid."))
    },
  })

  const applyPromo = () => {
    const code = promoInput.trim()
    if (!code) {
      setPromoCode('')
      return
    }
    promoMutation.mutate(code)
  }

  const price = activePlan ? planPrice(activePlan, billingPeriod) : 0

  return (
    <div className="mx-auto max-w-7xl md:rounded-3xl md:bg-white py-8 md:shadow-xl shadow-slate-200/60 lg:px-14">
      {/* Header */}
      <div className="flex flex-col items-center text-center">
        <div className="mb-3 flex items-center gap-2">
          <VoiceconLogo className="h-7 w-7" />
          <span className="text-xl font-bold text-slate-900">Voicecon</span>
        </div>
        <h1 className="text-[28px] font-medium md:font-bold text-slate-900">Pricing and Plans</h1>
        <p className="mt-1 text-sm text-slate-500">Choose the plan that fits your team</p>

        {/* Billing toggle — only when some plan can actually be paid yearly */}
        {anyYearly && (
        <div className="mt-5 flex items-center gap-3">
          <span
            className={`text-sm font-medium ${billingPeriod === 'monthly' ? 'text-slate-900' : 'text-slate-400'}`}
          >
            Monthly
          </span>
          <button
            type="button"
            role="switch"
            aria-checked={billingPeriod === 'yearly'}
            onClick={() => setBillingPeriod(billingPeriod === 'monthly' ? 'yearly' : 'monthly')}
            className={`relative inline-flex h-7 w-14 flex-shrink-0 items-center rounded-full p-1 transition-colors duration-200 ${billingPeriod === 'yearly' ? 'bg-brand-600' : 'bg-slate-300'}`}
          >
            <span
              className={`inline-block h-5 w-5 transform rounded-full bg-white shadow-sm transition-transform duration-200 ${billingPeriod === 'yearly' ? 'translate-x-7' : 'translate-x-0'}`}
            />
          </button>
          <span
            className={`text-sm font-medium ${billingPeriod === 'yearly' ? 'text-slate-900' : 'text-slate-400'}`}
          >
            Yearly
          </span>
          {yearlySaving > 0 && (
            <span className="rounded-full bg-brand-600 px-2.5 py-0.5 text-xs font-semibold text-white">
              Save {yearlySaving}%
            </span>
          )}
        </div>
        )}
      </div>

      {/* Plan cards */}
      {isLoading ? (
        <div className="mt-8 flex justify-center py-10">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-brand-100 border-t-brand-600" />
        </div>
      ) : (
        <div className={`mt-8 grid grid-cols-1 gap-6 md:grid-cols-2 ${plans.length >= 4 ? 'xl:grid-cols-4' : plans.length === 3 ? 'xl:grid-cols-3' : ''}`}>
          {plans.map((plan, idx) => {
            const isSelected = activePlan?.id === plan.id
            const highlight = plan.id === popularId // styled (green) card like Figma
            const bullets = bulletsByPlan[idx] ?? []
            const yearly = billedYearly(plan, billingPeriod)
            return (
              <div
                key={plan.id}
                className={`relative flex flex-col rounded-2xl border p-7 transition-all ${
                  highlight
                    ? 'border-transparent bg-brand-700 text-white'
                    : 'border-slate-200 bg-[#F7F7F7] text-slate-900'
                } ${isSelected ? 'ring-2 ring-brand-500 ring-offset-2' : ''}`}
              >
                {highlight && (
                  <span className="absolute -top-3 left-7 rounded-full bg-white px-3 py-1 text-[11px] font-bold uppercase tracking-[0.08em] text-brand-700 shadow-sm ring-1 ring-brand-700/10">
                    Most popular
                  </span>
                )}
                <div className="flex items-center gap-2.5">
                  {highlight ? (
                    <VoiceAiIcon className="h-8 w-8" />
                  ) : (
                    <SalesChatbotIcon className="h-8 w-8" />
                  )}
                  <p className={`text-base font-medium ${highlight ? 'text-white' : 'text-brand-700'}`}>
                    {plan.name}
                  </p>
                </div>
                {plan.description && (
                  <p className={`mt-3 text-sm ${highlight ? 'text-white/80' : 'text-slate-500'}`}>
                    {plan.description}
                  </p>
                )}
                <p className={`mt-5 text-xl font-semibold ${highlight ? 'text-[#FFFFFF]' : 'text-[#333333]'}`}>
                  Starting from
                </p>
                <div className="mt-1 flex items-end gap-1.5">
                  <span className="text-[32px] font-bold">${planPrice(plan, billingPeriod).toFixed(0)}</span>
                  <span className={`pb-1 text-base font-normal ${highlight ? 'text-white' : 'text-[#333333]'}`}>
                    {yearly ? '/year' : '/month'}
                  </span>
                </div>
                {billingPeriod === 'yearly' && !yearly && (
                  <p className={`mt-1 text-xs ${highlight ? 'text-white/80' : 'text-slate-500'}`}>
                    Billed monthly — yearly billing isn&apos;t offered on this plan.
                  </p>
                )}

                <ul className="mt-5 flex-1 space-y-2.5">
                  {bullets.map((b) => (
                    <li key={b} className="flex items-start gap-2 text-sm md:text-base leading-snug">
                      <Check
                        className={`mt-0.5 h-4 w-4 flex-shrink-0 ${highlight ? 'text-white' : 'text-brand-600'}`}
                      />
                      <span className={highlight ? 'text-white/90' : 'text-slate-600'}>{b}</span>
                    </li>
                  ))}
                </ul>

                <button
                  type="button"
                  onClick={() => handleSelect(plan)}
                  className={`mt-6 flex items-center justify-center gap-1.5 rounded-lg border px-4 py-4 text-sm font-semibold transition-colors ${
                    highlight
                      ? 'border-transparent bg-white text-brand-700 hover:bg-white/90'
                      : isSelected
                        ? 'border-brand-600 bg-brand-50 text-brand-700'
                        : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  {isSelected ? 'Selected' : 'Select'}
                  <ArrowUpRight className="h-4 w-4" />
                </button>
              </div>
            )
          })}
        </div>
      )}

      {/* Pay As You Go: no monthly price, so it sits apart from the cards above. */}
      {!isLoading && paygPlan && (
        <div
          data-testid="payg-plan-card"
          className={`mt-6 flex flex-col gap-5 rounded-2xl border border-slate-200 bg-[#F7F7F7] p-7 text-slate-900 transition-all lg:flex-row lg:items-center lg:justify-between ${
            paygSelected ? 'ring-2 ring-brand-500 ring-offset-2' : ''
          }`}
        >
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <p className="text-base font-medium text-brand-700">{paygPlan.name}</p>
              <p>
                <span className="text-[26px] font-bold">{perMinute(paygRate)}</span>
                <span className="ml-1 text-base text-[#333333]">/minute</span>
                <span className="ml-3 rounded-full bg-brand-600 px-2.5 py-0.5 text-xs font-semibold text-white">
                  No monthly fee
                </span>
              </p>
            </div>
            {paygPlan.description && <p className="mt-2 text-sm text-slate-500">{paygPlan.description}</p>}
            <ul className="mt-4 grid gap-x-6 gap-y-2.5 sm:grid-cols-2">
              {paygBullets(toPricingPlan(paygPlan)).map((b) => (
                <li key={b} className="flex items-start gap-2 text-sm leading-snug md:text-base">
                  <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-brand-600" />
                  <span className="text-slate-600">{b}</span>
                </li>
              ))}
            </ul>
          </div>
          <button
            type="button"
            onClick={() => handleSelect(paygPlan)}
            className={`flex shrink-0 items-center justify-center gap-1.5 rounded-lg border px-8 py-4 text-sm font-semibold transition-colors lg:w-[200px] ${
              paygSelected
                ? 'border-brand-600 bg-brand-50 text-brand-700'
                : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
            }`}
          >
            {paygSelected ? 'Selected' : 'Select'}
            <ArrowUpRight className="h-4 w-4" />
          </button>
        </div>
      )}

      {!isLoading && plans.length > 0 && (
        <p className="mt-6 text-center text-sm text-slate-500">
          Need custom minute rates, higher concurrency or volume pricing?{' '}
          <a href={ENTERPRISE.href} className="font-semibold text-brand-700 underline underline-offset-2 hover:text-brand-800">
            Talk to us about {ENTERPRISE.name}
          </a>
        </p>
      )}

      {/* Skip for now — starts the free trial, so only while one is available. */}
      {!trialUsed && (
      <div className="mt-12 text-center">
        <button
          type="button"
          onClick={() => trialMutation.mutate()}
          disabled={trialMutation.isPending}
          className="text-xl font-medium text-[#0F6A59] underline underline-offset-4 hover:text-brand-800 disabled:opacity-60"
        >
          {trialMutation.isPending ? 'Starting trial…' : 'Skip for now'}
        </button>
      </div>
      )}

      {/* Promo code */}
      <div className="mt-6 border-t-[1.4px] border-[#0F6A59] pt-6">
        <label className="mb-1.5 block text-sm font-medium text-slate-600">Promo Code</label>
        <div className="flex gap-3">
          <input
            value={promoInput}
            onChange={(e) => setPromoInput(e.target.value)}
            placeholder="Enter a coupon code"
            className="flex-1 rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20"
          />
          <button
            type="button"
            onClick={applyPromo}
            disabled={promoMutation.isPending}
            className="rounded-lg bg-brand-600 px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:opacity-60"
          >
            {promoMutation.isPending ? 'Applying…' : 'Apply'}
          </button>
        </div>
      </div>

      {/* Order summary */}
      {activePlan && (
        <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50/60 p-6">
          <div className="flex items-center justify-between border-b border-slate-200 pb-4">
            <span className="text-sm text-slate-600">Package Name</span>
            <span className="text-sm font-bold text-slate-900">{activePlan.name}</span>
          </div>
          <div className="flex items-center justify-between border-b border-slate-200 py-4">
            <span className="text-sm text-slate-600">Price</span>
            <span className="text-sm font-semibold text-slate-900">
              {paygSelected ? `${perMinute(paygRate)} per minute` : `$${price.toFixed(0)}`}
            </span>
          </div>
          <div className="flex items-start justify-between pt-4">
            <div>
              <p className="text-sm text-slate-600">{paygSelected ? 'Credit to add' : 'Total Amount'}</p>
              <p className="mt-1 text-xs text-slate-400">
                {paygSelected ? (
                  'You choose how much credit to add on the next step. Nothing renews.'
                ) : (
                  <>
                    Your next payment will be on{' '}
                    {nextPaymentDate(billedYearly(activePlan, billingPeriod) ? 'yearly' : 'monthly')}.
                  </>
                )}
              </p>
            </div>
            <div className="flex flex-col items-end gap-3">
              <span className="text-lg font-bold text-brand-700">
                {paygSelected ? 'No monthly fee' : `$${price.toFixed(0)}`}
              </span>
              <button
                type="button"
                onClick={handleNext}
                className="rounded-lg bg-brand-700 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-800"
              >
                Next (Look it in)
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
