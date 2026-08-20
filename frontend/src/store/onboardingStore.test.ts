/**
 * The onboarding selection store, and the distinction the Billing page depends on.
 *
 * Billing redirects to Pricing when no plan is selected. Finishing onboarding
 * also clears the selection — so without a way to tell "never chose one" from
 * "chose one and is done", starting a trial from the Billing page bounced the
 * user back to Pricing instead of landing them on the dashboard, even though
 * the trial had been created.
 */
import { beforeEach, describe, expect, it } from 'vitest'

import { useOnboardingStore } from './onboardingStore'

const store = () => useOnboardingStore.getState()

const plan = { id: 'plan-1', name: 'Voice AI' } as never

beforeEach(() => {
  store().reset()
})

describe('plan selection', () => {
  it('keeps the plan chosen on the pricing page', () => {
    store().setSelectedPlan(plan)
    expect(store().selectedPlan).toBe(plan)
  })

  it('starts with nothing selected and not completed', () => {
    expect(store().selectedPlan).toBeNull()
    expect(store().completed).toBe(false)
    expect(store().billingPeriod).toBe('monthly')
  })
})

describe('finish vs reset', () => {
  it('finish clears the selection and records that onboarding is done', () => {
    store().setSelectedPlan(plan)
    store().setBillingPeriod('yearly')

    store().finish()

    expect(store().selectedPlan).toBeNull()
    // The guard reads this to know the empty selection is the end state, not
    // an abandoned flow — the fix for the trial button bouncing to Pricing.
    expect(store().completed).toBe(true)
  })

  it('reset clears the selection without claiming onboarding finished', () => {
    store().setSelectedPlan(plan)
    store().finish()

    store().reset()

    expect(store().selectedPlan).toBeNull()
    expect(store().completed).toBe(false)
  })

  it('choosing a plan again re-enters the flow', () => {
    store().finish()
    expect(store().completed).toBe(true)

    store().setSelectedPlan(plan)

    expect(store().completed).toBe(false)
  })

  it('both clear the billing period back to monthly', () => {
    store().setBillingPeriod('yearly')
    store().finish()
    expect(store().billingPeriod).toBe('monthly')

    store().setBillingPeriod('yearly')
    store().reset()
    expect(store().billingPeriod).toBe('monthly')
  })
})

describe('persistence', () => {
  it('does not persist `completed`', () => {
    store().setSelectedPlan(plan)
    store().finish()

    const persisted = JSON.parse(sessionStorage.getItem('voicecon-onboarding') ?? '{}')

    // Restoring it would leave a later visit to /onboarding/billing rendering
    // nothing instead of redirecting to Pricing.
    expect(persisted.state).not.toHaveProperty('completed')
    expect(persisted.state).toHaveProperty('billingPeriod')
  })
})
