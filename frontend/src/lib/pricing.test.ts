import { describe, expect, it } from 'vitest'
import { planBullets, toPricingPlan, trialBullets, type PricingPlan } from './pricing'

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
    expect(planBullets(bigger, base)[0]).toBe('Everything in Starter, plus:')
  })

  it('does not claim it when an allowance is lower than the previous plan', () => {
    // QA M6: "Everything in Sales Chatbot" beside 200 calls vs Sales Chatbot's 300.
    const fewerCalls = plan('Pro', { agents: 10, calls_per_month: 200, minutes_per_month: 1000 })
    expect(planBullets(fewerCalls, base)).not.toContain('Everything in Starter, plus:')
  })

  it('treats unlimited as covering any finite allowance', () => {
    const unlimited = plan('Pro', { agents: -1, calls_per_month: -1, minutes_per_month: -1 })
    expect(planBullets(unlimited, base)[0]).toBe('Everything in Starter, plus:')
  })

  it('never advertises unshipped features', () => {
    const flagged = plan('Pro', { agents: 10 }, { virtual_meetings: true, lead_scoring: true, white_label: true })
    const text = planBullets(flagged).join(' ').toLowerCase()
    expect(text).not.toMatch(/meeting|lead scoring|white/)
  })
})

describe('planBullets usage lines', () => {
  it('states the minute allowance and the overage rate', () => {
    const p = { ...plan('Growth', { minutes_per_month: 750 }), overage_per_minute: 0.25 }
    expect(planBullets(p)).toContain('750 call minutes a month, then $0.25/min')
  })

  it('omits the rate when usage never overflows', () => {
    expect(planBullets(plan('Growth', { minutes_per_month: 750 }))).toContain('750 call minutes a month')
  })

  it('says how many calls can run at once', () => {
    expect(planBullets(plan('Scale', { concurrent_calls: 15 }))).toContain('15 calls at once')
    expect(planBullets(plan('Solo', { concurrent_calls: 1 }))).toContain('1 call at once')
  })

  it('never mentions a per-call allowance', () => {
    const text = planBullets(plan('Old', { calls_per_month: 300, minutes_per_month: 500 })).join(' ')
    expect(text).not.toMatch(/300/)
  })

  it('lists custom voices only when the plan includes them', () => {
    expect(planBullets(plan('Scale', { custom_voices: 2 }, { custom_voice: true }))).toContain('2 custom voices')
    expect(planBullets(plan('Growth', { custom_voices: 2 }))).not.toContain('2 custom voices')
  })

  it('never mentions text messages, even for a stored SMS allowance', () => {
    const p = plan('Old', { sms_per_month: 500, emails_per_month: 2000 }, { sms: true, email: true })
    const bullets = planBullets(p)
    expect(bullets.join(' ')).not.toMatch(/text|sms/i)
    expect(bullets).toContain('2,000 emails a month')
  })

  it('ends with the support level', () => {
    const p = { ...plan('Growth', {}), support: 'Priority email support' }
    const bullets = planBullets(p)
    expect(bullets[bullets.length - 1]).toBe('Priority email support')
  })
})

describe('toPricingPlan', () => {
  it('reads popular, support and the overage rate from the API plan', () => {
    const p = toPricingPlan({
      name: 'Growth',
      description: null,
      price_monthly: 149,
      price_yearly: 1428,
      features: { popular: true, support: 'Priority email support' },
      entitlements: { features: {}, limits: {}, overage: { allowed: true, per_minute: 0.25 } },
    })
    expect(p.popular).toBe(true)
    expect(p.support).toBe('Priority email support')
    expect(p.overage_per_minute).toBe(0.25)
  })

  it('has no overage rate when the plan does not allow overage', () => {
    const p = toPricingPlan({
      name: 'X',
      description: null,
      price_monthly: 1,
      price_yearly: null,
      entitlements: { overage: { allowed: false, per_minute: 0.25 } },
    })
    expect(p.overage_per_minute).toBeNull()
    expect(p.popular).toBe(false)
  })
})

describe('trialBullets', () => {
  it('states the trial minute allowance', () => {
    const bullets = trialBullets({ days: 14, limits: { minutes_per_month: 30, agents: 1 }, payment_provider: null })
    expect(bullets[0]).toBe('14 days, no credit card required')
    expect(bullets).toContain('30 call minutes included')
  })
})
