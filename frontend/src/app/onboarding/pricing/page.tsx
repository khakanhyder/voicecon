'use client'

import { useState, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery, useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Check, ArrowUpRight } from 'lucide-react'
import { VoiceconLogo, SalesChatbotIcon, VoiceAiIcon } from '@/lib/icons'
import { QUERY_KEYS } from '@/lib/constants'
import { onboardingService, type SubscriptionPlan } from '@/lib/onboarding'
import { useOnboardingStore } from '@/store/onboardingStore'

function planPrice(plan: SubscriptionPlan, period: 'monthly' | 'yearly'): number {
  if (period === 'yearly') return plan.price_yearly ?? plan.price_monthly * 12 * 0.75
  return plan.price_monthly
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

  const { data: plans = [], isLoading } = useQuery({
    queryKey: QUERY_KEYS.BILLING_PLANS,
    queryFn: onboardingService.getPlans,
  })

  // Default-select the highlighted (last) plan once loaded.
  const activePlan = useMemo(() => {
    if (selectedPlan) return plans.find((p) => p.id === selectedPlan.id) ?? selectedPlan
    return plans.length ? plans[plans.length - 1] : null
  }, [plans, selectedPlan])

  const trialMutation = useMutation({
    mutationFn: () =>
      onboardingService.startTrial({ plan_id: activePlan?.id, billing_period: billingPeriod }),
    onSuccess: () => {
      toast.success('Your 7-day free trial has started!')
      router.push('/dashboard')
    },
    onError: (err: any) => toast.error(err.response?.data?.detail || 'Could not start trial'),
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

  const applyPromo = () => {
    setPromoCode(promoInput)
    if (promoInput.trim()) toast.success(`Promo code "${promoInput}" applied`)
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

        {/* Billing toggle */}
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
          <span className="rounded-full bg-brand-600 px-2.5 py-0.5 text-xs font-semibold text-white">
            Save 25%
          </span>
        </div>
      </div>

      {/* Plan cards */}
      {isLoading ? (
        <div className="mt-8 flex justify-center py-10">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-brand-100 border-t-brand-600" />
        </div>
      ) : (
        <div className="mt-8 grid grid-cols-1 gap-8 md:grid-cols-2">
          {plans.map((plan, idx) => {
            const isSelected = activePlan?.id === plan.id
            const highlight = idx === plans.length - 1 // styled (green) card like Figma
            const bullets = (plan.features?.highlights as string[]) ?? []
            return (
              <div
                key={plan.id}
                className={`flex flex-col rounded-2xl border p-10 transition-all ${
                  highlight
                    ? 'border-transparent bg-brand-700 text-white'
                    : 'border-slate-200 bg-[#F7F7F7] text-slate-900'
                } ${isSelected ? 'ring-2 ring-brand-500 ring-offset-2' : ''}`}
              >
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
                <p className={`mt-5 text-xl font-semibold ${highlight ? 'text-[#FFFFFF]' : 'text-[#333333]'}`}>
                  Starting from
                </p>
                <div className="mt-1 flex items-end gap-1.5">
                  <span className="text-[32px] font-bold">${planPrice(plan, billingPeriod).toFixed(0)}</span>
                  <span className={`pb-1 text-base font-normal ${highlight ? 'text-white' : 'text-[#333333]'}`}>
                    {billingPeriod === 'yearly' ? '/year' : 'Setup fee'}
                  </span>
                </div>

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

      {/* Skip for now */}
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

      {/* Promo code */}
      <div className="mt-6 border-t-[1.4px] border-[#0F6A59] pt-6">
        <label className="mb-1.5 block text-sm font-medium text-slate-600">Promo Code</label>
        <div className="flex gap-3">
          <input
            value={promoInput}
            onChange={(e) => setPromoInput(e.target.value)}
            placeholder="Enter promo code (e.g. SAVE25)"
            className="flex-1 rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20"
          />
          <button
            type="button"
            onClick={applyPromo}
            className="rounded-lg bg-brand-600 px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-700"
          >
            Apply
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
            <span className="text-sm font-semibold text-slate-900">${price.toFixed(0)}</span>
          </div>
          <div className="flex items-start justify-between pt-4">
            <div>
              <p className="text-sm text-slate-600">Total Amount</p>
              <p className="mt-1 text-xs text-slate-400">
                Your next payment will be on {nextPaymentDate(billingPeriod)}.
              </p>
            </div>
            <div className="flex flex-col items-end gap-3">
              <span className="text-lg font-bold text-brand-700">${price.toFixed(0)}</span>
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
