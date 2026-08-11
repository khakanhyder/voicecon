'use client'

/**
 * Shown in place of the buy-a-number flow when the plan does not include
 * purchasing.
 *
 * The free trial deliberately has no conversation limits — what it cannot do is
 * take on a phone number, because that is a recurring charge at the carrier
 * that outlives the trial. So rather than letting someone search, pick a
 * number and only then hit a wall, the whole purchase surface is replaced by
 * the thing that unblocks them.
 *
 * Upgrading happens here rather than on the billing page: sending someone away
 * to a different screen to buy, then back again to resume, loses most of them.
 */
import { useEffect, useState } from 'react'
import { ArrowRight, Check, Loader2, Lock } from 'lucide-react'

import { apiClient } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { cn } from '@/lib/utils'
import { useEntitlementStore } from '@/store/entitlementStore'
import { CheckoutModal, type CheckoutPlan } from './CheckoutModal'

interface Plan {
  id: string
  slug: string | null
  tier: number
  name: string
  description: string | null
  price_monthly: number
  price_yearly: number | null
  max_phone_numbers: number
  is_public: boolean
  is_active: boolean
}

type BillingPeriod = 'monthly' | 'yearly'

export function PhoneNumberPaywall({ onUpgraded }: { onUpgraded?: () => void }) {
  const refreshEntitlements = useEntitlementStore((s) => s.refresh)

  const [plans, setPlans] = useState<Plan[]>([])
  const [loading, setLoading] = useState(true)
  const [period, setPeriod] = useState<BillingPeriod>('monthly')
  const [checkoutPlan, setCheckoutPlan] = useState<CheckoutPlan | null>(null)

  useEffect(() => {
    let cancelled = false
    apiClient
      .get<Plan[]>(API_ENDPOINTS.BILLING_PLANS)
      .then((res) => {
        if (cancelled) return
        const usable = (res.data || [])
          .filter((plan) => plan.is_active && plan.is_public)
          .sort((a, b) => a.tier - b.tier)
        setPlans(usable)
      })
      .catch(() => {
        // The paywall is still useful without prices — the explanation and the
        // link to billing carry it. Failing to a blank panel would not be.
        if (!cancelled) setPlans([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const handleSuccess = async () => {
    setCheckoutPlan(null)
    // The 402 is served from a 30-second entitlement cache, so a purchase made
    // here is not visible to the next request until this refresh lands.
    await refreshEntitlements()
    onUpgraded?.()
  }

  return (
    <>
      <div className="rounded-[10px] border border-[#2E2E2E]/15 bg-white p-6 sm:p-8">
        <div className="flex items-start gap-4">
          <span className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl bg-[#106959]/10">
            <Lock className="h-5 w-5 text-[#106959]" />
          </span>
          <div className="min-w-0">
            <h3 className="text-[18px] font-bold tracking-tight text-[#000000]">
              Upgrade to add a phone number
            </h3>
            <p className="mt-1.5 text-[14px] leading-[1.6] text-black/60">
              Your free trial includes unlimited calls and minutes so you can build and test
              as much as you like. Buying a number bills monthly at the carrier, so it needs
              a paid plan — whether you use the Voicecon shared account or your own
              connected Twilio.
            </p>
          </div>
        </div>

        {plans.length > 1 && (
          <div className="mt-6 inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5">
            {(['monthly', 'yearly'] as BillingPeriod[]).map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setPeriod(option)}
                className={cn(
                  'rounded-md px-3.5 py-1.5 text-[13px] font-semibold capitalize transition-colors',
                  period === option
                    ? 'bg-white text-[#106959] shadow-sm'
                    : 'text-slate-500 hover:text-slate-700'
                )}
              >
                {option}
                {option === 'yearly' && (
                  <span className="ml-1.5 text-[11px] font-bold text-emerald-600">-25%</span>
                )}
              </button>
            ))}
          </div>
        )}

        {loading ? (
          <div className="mt-6 flex items-center gap-2 py-8 text-[14px] text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading plans…
          </div>
        ) : plans.length === 0 ? (
          <a
            href="/dashboard/settings/billing"
            className="mt-6 inline-flex h-11 items-center gap-2 rounded-[8px] bg-[#106959] px-5 text-[14px] font-semibold text-white transition-colors hover:bg-[#0c5044]"
          >
            Choose a plan
            <ArrowRight className="h-4 w-4" />
          </a>
        ) : (
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {plans.map((plan) => {
              const yearly = period === 'yearly' && plan.price_yearly != null
              const price = yearly ? plan.price_yearly! : plan.price_monthly
              return (
                <div
                  key={plan.id}
                  className="flex flex-col rounded-[10px] border border-slate-200 bg-[#0F6A590A] p-5"
                >
                  <p className="text-[15px] font-bold text-[#000000]">{plan.name}</p>
                  <p className="mt-1 flex items-baseline gap-1">
                    <span className="text-[26px] font-bold tracking-tight text-[#000000]">
                      ${Number(price).toFixed(0)}
                    </span>
                    <span className="text-[13px] text-black/50">
                      /{yearly ? 'year' : 'month'}
                    </span>
                  </p>
                  {plan.description && (
                    <p className="mt-2 text-[13px] leading-[1.55] text-black/60">
                      {plan.description}
                    </p>
                  )}
                  <p className="mt-3 flex items-center gap-1.5 text-[13px] font-medium text-[#106959]">
                    <Check className="h-3.5 w-3.5 flex-shrink-0" />
                    {plan.max_phone_numbers === 1
                      ? '1 phone number'
                      : `${plan.max_phone_numbers} phone numbers`}
                  </p>
                  <button
                    type="button"
                    onClick={() =>
                      setCheckoutPlan({
                        id: plan.id,
                        name: plan.name,
                        price_monthly: plan.price_monthly,
                        price_yearly: plan.price_yearly,
                      })
                    }
                    className="mt-auto pt-4"
                  >
                    <span className="flex h-10 w-full items-center justify-center gap-1.5 rounded-[8px] bg-[#106959] text-[14px] font-semibold text-white transition-colors hover:bg-[#0c5044]">
                      Upgrade
                      <ArrowRight className="h-3.5 w-3.5" />
                    </span>
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {checkoutPlan && (
        <CheckoutModal
          plan={checkoutPlan}
          billingPeriod={period}
          onClose={() => setCheckoutPlan(null)}
          onSuccess={handleSuccess}
        />
      )}
    </>
  )
}
