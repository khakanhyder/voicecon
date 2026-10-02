/**
 * Unit tests for the Pay As You Go wallet helpers and the pricing-card copy
 * built for the prepaid plan.
 *
 * The server owns every price and re-checks every amount; these cover what the
 * customer is *shown* — the minutes a top-up buys, the bounds message, which
 * button the plan card offers, and which banner an empty wallet gets.
 */
import { describe, expect, it } from 'vitest'

import { billingBanner, type Entitlements } from './entitlements'
import { paygActionFor, planActionFor } from './planActions'
import {
  isPrepaidPlan,
  paygBullets,
  planCardBullets,
  splitPlans,
  toPricingPlan,
  type ApiPlan,
} from './pricing'
import { formatMoney, formatSigned, minutesFor, minutesLeftLabel, topupAmountProblem } from './wallet'

const subscription = (name: string, minutes: number): ApiPlan => ({
  slug: name.toLowerCase(),
  name,
  description: '',
  price_monthly: 49,
  price_yearly: null,
  entitlements: {
    features: { inbound_calls: true, call_recordings: true, analytics: true },
    limits: { agents: 1, phone_numbers: 1, minutes_per_month: minutes, concurrent_calls: 3 },
    overage: { allowed: true, per_minute: 0.3 },
  },
})

const payg: ApiPlan = {
  slug: 'payg',
  name: 'Pay As You Go',
  description: 'No monthly fee.',
  price_monthly: 0,
  price_yearly: null,
  features: { support: 'Email support' },
  entitlements: {
    features: { inbound_calls: true, workflows: true, call_recordings: true, analytics: true },
    limits: { agents: 1, phone_numbers: 1, workflows: 3, minutes_per_month: -1, concurrent_calls: 2 },
    overage: { allowed: false },
    billing: { mode: 'prepaid', per_minute: 0.35, number_monthly_fee: 2, topup_min: 10, topup_presets: [10, 25, 50, 100] },
  },
}

function entitlements(overrides: Partial<Entitlements> = {}): Entitlements {
  return {
    status: 'active',
    plan_id: 'plan_payg',
    plan_slug: 'payg',
    plan_name: 'Pay As You Go',
    plan_tier: 0,
    source: 'wallet',
    billing_period: 'monthly',
    is_live: true,
    is_read_only: false,
    is_trial: false,
    in_grace: false,
    has_subscription: true,
    trial_end: null,
    days_remaining: null,
    trial_expiring_soon: false,
    grace_period_end: null,
    grace_days_remaining: null,
    current_period_end: null,
    cancel_at_period_end: false,
    features: [],
    limits: {},
    usage: {},
    overage_allowed: false,
    trial_available: false,
    trial_used: true,
    prepaid: true,
    wallet_balance: 25,
    wallet_low: false,
    wallet_empty: false,
    switching_to_prepaid: false,
    ...overrides,
  }
}

describe('minutesFor', () => {
  it('counts whole minutes without losing one to floating point', () => {
    expect(minutesFor(10, 0.35)).toBe(28)
    expect(minutesFor(25, 0.35)).toBe(71)
    expect(minutesFor(0.7, 0.35)).toBe(2)
    expect(minutesFor(3, 0.1)).toBe(30)
  })

  it('handles a rate with a fraction of a cent', () => {
    expect(minutesFor(15, 0.075)).toBe(200)
  })

  it('has no answer without a rate or an amount', () => {
    expect(minutesFor(10, 0)).toBeNull()
    expect(minutesFor(0, 0.35)).toBeNull()
    expect(minutesFor(Number.NaN, 0.35)).toBeNull()
  })
})

describe('topupAmountProblem', () => {
  const bounds = { minimum: 10, maximum: 1000 }

  it('accepts an amount inside the bounds', () => {
    expect(topupAmountProblem(10, bounds)).toBeNull()
    expect(topupAmountProblem(1000, bounds)).toBeNull()
    expect(topupAmountProblem(37.5, bounds)).toBeNull()
  })

  it('says what the smallest and largest top-ups are', () => {
    expect(topupAmountProblem(5, bounds)).toBe('The smallest top-up is $10.00.')
    expect(topupAmountProblem(5000, bounds)).toBe('The largest single top-up is $1,000.00.')
  })

  it('asks for an amount when there is none', () => {
    expect(topupAmountProblem(Number.NaN, bounds)).toBe('Enter the amount you want to add.')
    expect(topupAmountProblem(0, bounds)).toBe('Enter the amount you want to add.')
  })
})

describe('money formatting', () => {
  it('always shows cents and puts the sign before the symbol', () => {
    expect(formatMoney(25)).toBe('$25.00')
    expect(formatMoney(-1.05)).toBe('-$1.05')
    expect(formatMoney(1234.5)).toBe('$1,234.50')
  })

  it('marks a credit with a plus in the history', () => {
    expect(formatSigned(25)).toBe('+$25.00')
    expect(formatSigned(-0.35)).toBe('-$0.35')
  })

  it('describes what a balance buys', () => {
    expect(minutesLeftLabel({ minutes_left: 28 })).toBe('About 28 minutes of calls')
    expect(minutesLeftLabel({ minutes_left: 1 })).toBe('About 1 minute of calls')
    expect(minutesLeftLabel({ minutes_left: 0 })).toBe('Not enough for a call')
    expect(minutesLeftLabel({ minutes_left: null })).toBeNull()
  })
})

describe('the prepaid plan among the plan cards', () => {
  const plans = [subscription('Starter', 200), subscription('Growth', 750), payg]

  it('is recognised by its entitlements, not its slug or price', () => {
    expect(isPrepaidPlan(payg)).toBe(true)
    const renamed: ApiPlan = { ...payg, slug: 'flex', name: 'Flex' }
    expect(isPrepaidPlan(renamed)).toBe(true)
    expect(isPrepaidPlan(subscription('Free', 0))).toBe(false)
    expect(isPrepaidPlan(null)).toBe(false)
  })

  it('is split away from the subscriptions', () => {
    const { subscriptions, prepaid } = splitPlans(plans)
    expect(subscriptions.map((p) => p.name)).toEqual(['Starter', 'Growth'])
    expect(prepaid?.name).toBe('Pay As You Go')
    expect(splitPlans(plans.slice(0, 2)).prepaid).toBeNull()
  })

  it('carries its charges into the card model', () => {
    expect(toPricingPlan(payg).prepaid).toEqual({
      per_minute: 0.35,
      number_monthly_fee: 2,
      topup_min: 10,
      topup_presets: [10, 25, 50, 100],
    })
    expect(toPricingPlan(subscription('Starter', 200)).prepaid).toBeNull()
  })

  it('states the rate, no monthly fee, the top-up floor and the number fee', () => {
    const lines = paygBullets(toPricingPlan(payg))
    expect(lines[0]).toBe('$0.35 per call minute, paid from your balance')
    expect(lines).toContain('No monthly fee and nothing to cancel')
    expect(lines).toContain('Add credit from $10; it does not expire')
    expect(lines).toContain('Phone number $2 a month')
    expect(lines).toContain('2 calls at once')
    expect(lines).toContain('Email support')
    // Never an allowance: "unlimited call minutes" would read as free calls.
    expect(lines.join(' ')).not.toMatch(/unlimited call minutes/i)
  })

  it('does not mention a number fee when numbers are free', () => {
    const free = { ...payg, entitlements: { ...payg.entitlements, billing: { ...payg.entitlements!.billing, number_monthly_fee: 0 } } }
    expect(paygBullets(toPricingPlan(free)).join(' ')).not.toMatch(/Phone number \$/)
  })

  it('never becomes the plan a subscription includes "everything in"', () => {
    // Even listed first, the subscription after it keeps its own full copy.
    const [paygLines, starterLines, growthLines] = planCardBullets([payg, plans[0], plans[1]])
    expect(paygLines[0]).toMatch(/per call minute/)
    expect(starterLines.join(' ')).not.toMatch(/Everything in Pay As You Go/)
    expect(growthLines[0]).toBe('Everything in Starter, plus:')
  })
})

describe('paygActionFor', () => {
  it('a trial, a lapsed plan or a new workspace starts with a top-up', () => {
    expect(paygActionFor({ onPlan: false, switching: false, providerBilled: false })).toBe('start')
  })

  it('a paid subscription switches when its period ends', () => {
    expect(paygActionFor({ onPlan: false, switching: false, providerBilled: true })).toBe('switch')
  })

  it('a queued move says so instead of offering to switch again', () => {
    expect(paygActionFor({ onPlan: false, switching: true, providerBilled: true })).toBe('scheduled')
  })

  it('a workspace already on it sees its current plan', () => {
    expect(paygActionFor({ onPlan: true, switching: false, providerBilled: false })).toBe('current')
  })

  it('every subscription is an upgrade from Pay As You Go', () => {
    for (const tier of [1, 2, 3, 4]) {
      expect(
        planActionFor({
          planId: `plan_${tier}`,
          planTier: tier,
          currentPlanId: 'plan_payg',
          currentTier: 0,
          isLive: true,
          isTrial: false,
        }),
      ).toBe('upgrade')
    }
  })
})

describe('billingBanner on Pay As You Go', () => {
  it('shows nothing while there is credit', () => {
    expect(billingBanner(entitlements())).toBeNull()
  })

  it('an empty wallet is a banner that cannot be dismissed and asks for credit', () => {
    const banner = billingBanner(entitlements({ wallet_balance: 0, wallet_empty: true }))
    expect(banner).toMatchObject({ key: 'wallet_empty', tone: 'danger', dismissible: false, target: 'wallet', cta: 'Add credit' })
  })

  it('a low balance warns with what is left', () => {
    const banner = billingBanner(entitlements({ wallet_balance: 3.2, wallet_low: true }))
    expect(banner).toMatchObject({ key: 'wallet_low', tone: 'warning', dismissible: true, target: 'wallet' })
    expect(banner?.body).toContain('$3.20')
  })

  it('empty wins over low', () => {
    const banner = billingBanner(entitlements({ wallet_balance: 0, wallet_low: true, wallet_empty: true }))
    expect(banner?.key).toBe('wallet_empty')
  })

  it('a subscriber with spare credit gets no wallet banner', () => {
    const banner = billingBanner(
      entitlements({ prepaid: false, source: 'stripe', plan_slug: 'growth', wallet_balance: 0, wallet_empty: false }),
    )
    expect(banner).toBeNull()
  })

  it('a queued move to Pay As You Go is announced as a move, not a cancellation', () => {
    const banner = billingBanner(
      entitlements({
        prepaid: false,
        source: 'stripe',
        plan_slug: 'starter',
        cancel_at_period_end: true,
        current_period_end: '2026-11-01T00:00:00+00:00',
        switching_to_prepaid: true,
        wallet_balance: 0,
      }),
    )
    expect(banner).toMatchObject({ key: 'switching_to_prepaid', tone: 'info', target: 'wallet', cta: 'Add credit' })
    expect(banner?.title).toMatch(/Pay As You Go/)
  })

  it('an ordinary cancellation still says the subscription ends', () => {
    const banner = billingBanner(
      entitlements({
        prepaid: false,
        source: 'stripe',
        cancel_at_period_end: true,
        current_period_end: '2026-11-01T00:00:00+00:00',
        switching_to_prepaid: false,
      }),
    )
    expect(banner?.key).toBe('cancelling')
  })

  it('an expired account outranks any wallet state', () => {
    const banner = billingBanner(
      entitlements({ status: 'expired', is_live: false, prepaid: false, wallet_balance: 0 }),
    )
    expect(banner?.key).toBe('expired')
  })
})
