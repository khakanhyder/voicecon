import { describe, expect, it } from 'vitest'
import { planBullets, type PricingPlan } from './pricing'

const features = {
  inbound_calls: true,
  outbound_calls: true,
  crm_integrations: true,
  webhooks: true,
  call_recordings: true,
  analytics: true,
}

function plan(name: string, limits: Record<string, number>, extra: Record<string, boolean> = {}): PricingPlan {
  return {
    slug: name.toLowerCase(),
    name,
    description: '',
    price_monthly: 100,
    price_yearly: null,
    features: { ...features, ...extra },
    limits,
  } as PricingPlan
}

describe('planBullets "Everything in" line', () => {
  const base = plan('Starter', { agents: 5, calls_per_month: 300, minutes_per_month: 500 })

  it('claims everything in the previous plan when features and allowances all grow', () => {
    const bigger = plan('Pro', { agents: 10, calls_per_month: 600, minutes_per_month: 1000 }, { workflow_scheduling: true })
    expect(planBullets(bigger, base)[0]).toBe('Everything in Starter')
  })

  it('does not claim it when an allowance is lower than the previous plan', () => {
    // QA M6: "Everything in Sales Chatbot" beside 200 calls vs Sales Chatbot's 300.
    const fewerCalls = plan('Pro', { agents: 10, calls_per_month: 200, minutes_per_month: 1000 })
    expect(planBullets(fewerCalls, base)).not.toContain('Everything in Starter')
  })

  it('treats unlimited as covering any finite allowance', () => {
    const unlimited = plan('Pro', { agents: -1, calls_per_month: -1, minutes_per_month: -1 })
    expect(planBullets(unlimited, base)[0]).toBe('Everything in Starter')
  })

  it('never advertises unshipped features', () => {
    const flagged = plan('Pro', { agents: 10 }, { virtual_meetings: true, lead_scoring: true, white_label: true })
    const text = planBullets(flagged).join(' ').toLowerCase()
    expect(text).not.toMatch(/meeting|lead scoring|white/)
  })
})
