/**
 * Onboarding selection store — keeps the plan chosen on the Pricing page so the
 * Billing page (and a refresh of it) can show the right order summary.
 * Persisted to sessionStorage so it survives a page reload during onboarding.
 */
import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { BillingPeriod, SubscriptionPlan } from '@/lib/onboarding'

interface OnboardingState {
  selectedPlan: SubscriptionPlan | null
  billingPeriod: BillingPeriod
  promoCode: string
  setSelectedPlan: (plan: SubscriptionPlan | null) => void
  setBillingPeriod: (period: BillingPeriod) => void
  setPromoCode: (code: string) => void
  reset: () => void
}

export const useOnboardingStore = create<OnboardingState>()(
  persist(
    (set) => ({
      selectedPlan: null,
      billingPeriod: 'monthly',
      promoCode: '',
      setSelectedPlan: (plan) => set({ selectedPlan: plan }),
      setBillingPeriod: (period) => set({ billingPeriod: period }),
      setPromoCode: (code) => set({ promoCode: code }),
      reset: () => set({ selectedPlan: null, billingPeriod: 'monthly', promoCode: '' }),
    }),
    {
      name: 'voicecon-onboarding',
      storage: createJSONStorage(() =>
        typeof window !== 'undefined' ? sessionStorage : (undefined as any)
      ),
    }
  )
)
