/**
 * Unit tests for subscription entitlement helpers.
 *
 * `billingBanner` is the one place that turns a subscription status into a
 * banner, and its contract is "at most one, highest severity first" — stacked
 * billing banners get ignored wholesale. The precedence order is therefore the
 * thing worth pinning: most of these tests set up a state that satisfies *two*
 * rules and assert which one wins.
 */
import { describe, expect, it } from 'vitest'

import {
  billingBanner,
  formatCap,
  isUnlimited,
  type Entitlements,
  type SubscriptionStatus,
} from './entitlements'

/** A live, paid, unremarkable workspace — the state that shows no banner. */
function entitlements(overrides: Partial<Entitlements> = {}): Entitlements {
  return {
    status: 'active' as SubscriptionStatus,
    plan_id: 'plan_1',
    plan_slug: 'voice-ai',
    plan_name: 'Voice AI',
    plan_tier: 2,
    source: 'stripe',
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
    ...overrides,
  }
}

describe('isUnlimited', () => {
  it('treats -1 as unlimited', () => {
    // The sentinel exists because a plain `used < cap` would read -1 as "zero
    // allowed" and lock an unlimited plan out of its own features.
    expect(isUnlimited(-1)).toBe(true)
  })

  it('treats a real cap as limited', () => {
    expect(isUnlimited(0)).toBe(false)
    expect(isUnlimited(10)).toBe(false)
  })

  it('treats a missing cap as limited', () => {
    expect(isUnlimited(undefined)).toBe(false)
  })
})

describe('formatCap', () => {
  it('renders the unlimited sentinel as a word, not "-1"', () => {
    expect(formatCap(-1)).toBe('Unlimited')
  })

  it('renders a real cap as its number', () => {
    expect(formatCap(25)).toBe('25')
  })

  it('renders zero as zero rather than falling through to a default', () => {
    expect(formatCap(0)).toBe('0')
  })

  it('renders a missing cap as zero', () => {
    expect(formatCap(undefined)).toBe('0')
  })
})

describe('billingBanner', () => {
  it('shows nothing for a healthy paid workspace', () => {
    expect(billingBanner(entitlements())).toBeNull()
  })

  it('shows nothing when entitlements have not loaded yet', () => {
    // The dashboard renders before the fetch resolves; a null must not throw.
    expect(billingBanner(null)).toBeNull()
  })

  describe('expired', () => {
    it('is a non-dismissible danger banner', () => {
      const banner = billingBanner(entitlements({ status: 'expired' }))

      expect(banner?.key).toBe('expired')
      expect(banner?.tone).toBe('danger')
      expect(banner?.dismissible).toBe(false)
    })

    it('names a trial that ended when the subscription came from one', () => {
      const banner = billingBanner(
        entitlements({ status: 'expired', source: 'trial' })
      )

      expect(banner?.title).toMatch(/free trial has ended/i)
    })

    it('names a subscription that ended otherwise', () => {
      const banner = billingBanner(
        entitlements({ status: 'expired', source: 'stripe' })
      )

      expect(banner?.title).toMatch(/subscription has ended/i)
    })

    it('reassures the user their work is kept', () => {
      // This banner is shown at the worst moment; the copy has to say the data
      // is still there or it reads as "everything is gone".
      const banner = billingBanner(entitlements({ status: 'expired' }))

      expect(banner?.body).toMatch(/kept/i)
    })
  })

  describe('canceled', () => {
    it('is a non-dismissible danger banner offering reactivation', () => {
      const banner = billingBanner(entitlements({ status: 'canceled' }))

      expect(banner?.key).toBe('canceled')
      expect(banner?.tone).toBe('danger')
      expect(banner?.dismissible).toBe(false)
      expect(banner?.cta).toBe('Reactivate')
    })
  })

  describe('grace period', () => {
    it('counts down the days before the number is released', () => {
      const banner = billingBanner(
        entitlements({ in_grace: true, grace_days_remaining: 3 })
      )

      expect(banner?.key).toBe('grace')
      expect(banner?.body).toContain('3 days')
    })

    it('says "day" not "days" with one day left', () => {
      const banner = billingBanner(
        entitlements({ in_grace: true, grace_days_remaining: 1 })
      )

      expect(banner?.body).toContain('1 day ')
      expect(banner?.body).not.toContain('1 days')
    })

    it('drops the countdown entirely once it reaches zero', () => {
      // "0 days before your number is released" reads as a bug, so the copy
      // switches to an imminent warning instead.
      const banner = billingBanner(
        entitlements({ in_grace: true, grace_days_remaining: 0 })
      )

      expect(banner?.body).toMatch(/about to be released/i)
    })

    it('survives a missing day count', () => {
      const banner = billingBanner(
        entitlements({ in_grace: true, grace_days_remaining: null })
      )

      expect(banner?.key).toBe('grace')
      expect(banner?.body).not.toContain('null')
    })
  })

  describe('past due', () => {
    it('is a dismissible warning, since the card may still succeed', () => {
      const banner = billingBanner(entitlements({ status: 'past_due' }))

      expect(banner?.key).toBe('past_due')
      expect(banner?.tone).toBe('warning')
      expect(banner?.dismissible).toBe(true)
    })

    it('explains that retries are coming rather than implying shutdown', () => {
      const banner = billingBanner(entitlements({ status: 'past_due' }))

      expect(banner?.body).toMatch(/retry/i)
    })
  })

  describe('trial ending soon', () => {
    it('warns with the number of days left', () => {
      const banner = billingBanner(
        entitlements({
          status: 'trialing',
          is_trial: true,
          trial_expiring_soon: true,
          days_remaining: 3,
        })
      )

      expect(banner?.tone).toBe('warning')
      expect(banner?.title).toContain('3 days')
    })

    it('says "ends today" rather than "in 1 days" on the last day', () => {
      const banner = billingBanner(
        entitlements({
          status: 'trialing',
          is_trial: true,
          trial_expiring_soon: true,
          days_remaining: 1,
        })
      )

      expect(banner?.title).toMatch(/ends today/i)
    })

    it('keys on the day count so a new day re-shows a dismissed banner', () => {
      // Dismissal is stored against the key. A static key would hide the
      // warning for the rest of the trial after one dismissal.
      const threeDays = billingBanner(
        entitlements({
          is_trial: true,
          trial_expiring_soon: true,
          days_remaining: 3,
        })
      )
      const twoDays = billingBanner(
        entitlements({
          is_trial: true,
          trial_expiring_soon: true,
          days_remaining: 2,
        })
      )

      expect(threeDays?.key).not.toBe(twoDays?.key)
    })
  })

  describe('cancelling at period end', () => {
    it('states the end date and that access continues until then', () => {
      const banner = billingBanner(
        entitlements({
          cancel_at_period_end: true,
          current_period_end: '2026-09-15T00:00:00Z',
        })
      )

      expect(banner?.key).toBe('cancelling')
      expect(banner?.title).toMatch(/September 15|15 September/)
      expect(banner?.body).toMatch(/full access until then/i)
    })

    it('shows nothing when the end date is unknown', () => {
      // Without a date the title would read "ends on Invalid Date".
      const banner = billingBanner(
        entitlements({ cancel_at_period_end: true, current_period_end: null })
      )

      expect(banner).toBeNull()
    })
  })

  describe('healthy trial', () => {
    it('is an informational countdown', () => {
      const banner = billingBanner(
        entitlements({ status: 'trialing', is_trial: true, days_remaining: 10 })
      )

      expect(banner?.key).toBe('trial')
      expect(banner?.tone).toBe('info')
      expect(banner?.title).toContain('10 days')
    })

    it('singularises the last day', () => {
      const banner = billingBanner(
        entitlements({ is_trial: true, days_remaining: 1 })
      )

      expect(banner?.title).toContain('1 day')
      expect(banner?.title).not.toContain('1 days')
    })
  })

  describe('precedence — only the most severe banner is returned', () => {
    it('prefers expired over an active trial', () => {
      const banner = billingBanner(
        entitlements({ status: 'expired', is_trial: true, days_remaining: 5 })
      )

      expect(banner?.key).toBe('expired')
    })

    it('prefers cancelled over grace', () => {
      const banner = billingBanner(
        entitlements({ status: 'canceled', in_grace: true })
      )

      expect(banner?.key).toBe('canceled')
    })

    it('prefers grace over past due', () => {
      const banner = billingBanner(
        entitlements({ status: 'past_due', in_grace: true })
      )

      expect(banner?.key).toBe('grace')
    })

    it('prefers past due over a trial ending soon', () => {
      const banner = billingBanner(
        entitlements({
          status: 'past_due',
          is_trial: true,
          trial_expiring_soon: true,
          days_remaining: 2,
        })
      )

      expect(banner?.key).toBe('past_due')
    })

    it('prefers a trial ending soon over a scheduled cancellation', () => {
      const banner = billingBanner(
        entitlements({
          is_trial: true,
          trial_expiring_soon: true,
          days_remaining: 2,
          cancel_at_period_end: true,
          current_period_end: '2026-09-15T00:00:00Z',
        })
      )

      expect(banner?.key).toMatch(/^trial-ending/)
    })

    it('prefers the ending-soon warning over the healthy trial notice', () => {
      const banner = billingBanner(
        entitlements({
          is_trial: true,
          trial_expiring_soon: true,
          days_remaining: 2,
        })
      )

      expect(banner?.tone).toBe('warning')
    })
  })

  it('always returns a complete banner, never a partial one', () => {
    // Every field is rendered unconditionally, so a missing one shows as
    // "undefined" in the UI.
    const states: Partial<Entitlements>[] = [
      { status: 'expired' },
      { status: 'canceled' },
      { in_grace: true, grace_days_remaining: 2 },
      { status: 'past_due' },
      { is_trial: true, trial_expiring_soon: true, days_remaining: 2 },
      { cancel_at_period_end: true, current_period_end: '2026-09-15T00:00:00Z' },
      { is_trial: true, days_remaining: 9 },
    ]

    for (const state of states) {
      const banner = billingBanner(entitlements(state))

      expect(banner).not.toBeNull()
      expect(banner!.key).toBeTruthy()
      expect(banner!.title).toBeTruthy()
      expect(banner!.body).toBeTruthy()
      expect(banner!.cta).toBeTruthy()
      expect(['info', 'warning', 'danger']).toContain(banner!.tone)
    }
  })
})
