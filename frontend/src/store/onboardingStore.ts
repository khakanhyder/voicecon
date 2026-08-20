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
  /**
   * Onboarding was finished in this session — trial started, or subscription paid.
   *
   * Tells the Billing page's "you have not picked a plan yet" guard the
   * difference between *never chose one* and *chose one and is now done*.
   * Without it, clearing the selection on success looked identical to arriving
   * with no plan, and the guard redirected the user to Pricing at the exact
   * moment they should have been landing on the dashboard.
   */
  completed: boolean
  setSelectedPlan: (plan: SubscriptionPlan | null) => void
  setBillingPeriod: (period: BillingPeriod) => void
  setPromoCode: (code: string) => void
  /** Clear the selection because onboarding *finished*, not because it lapsed. */
  finish: () => void
  reset: () => void
}

export const useOnboardingStore = create<OnboardingState>()(
  persist(
    (set) => ({
      selectedPlan: null,
      billingPeriod: 'monthly',
      promoCode: '',
      completed: false,
      // Picking a plan is re-entering the flow, so it clears any earlier finish.
      setSelectedPlan: (plan) => set({ selectedPlan: plan, completed: false }),
      setBillingPeriod: (period) => set({ billingPeriod: period }),
      setPromoCode: (code) => set({ promoCode: code }),
      finish: () =>
        set({ selectedPlan: null, billingPeriod: 'monthly', promoCode: '', completed: true }),
      reset: () =>
        set({ selectedPlan: null, billingPeriod: 'monthly', promoCode: '', completed: false }),
    }),
    {
      name: 'voicecon-onboarding',
      storage: createJSONStorage(() =>
        typeof window !== 'undefined' ? sessionStorage : (undefined as any)
      ),
      // `completed` is deliberately not persisted. It exists only to keep the
      // Billing guard quiet across the render between finishing and arriving at
      // the dashboard. Restoring it would mean a later visit to /onboarding/
      // billing with no plan selected renders nothing instead of redirecting.
      partialize: ({ selectedPlan, billingPeriod, promoCode }) => ({
        selectedPlan,
        billingPeriod,
        promoCode,
      }),
    }
  )
)
