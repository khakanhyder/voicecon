/**
 * Unit tests for the Stripe.js loader.
 *
 * The behaviour that matters is the unconfigured case: with no publishable key
 * — or with the `pk_test_...` placeholder still in `.env.example` — the billing
 * page must fall back to the free-trial path rather than trying to mount a card
 * field that cannot work.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@stripe/stripe-js', () => ({
  loadStripe: vi.fn(async () => ({ id: 'stripe-instance' })),
}))

const ORIGINAL_KEY = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY

beforeEach(() => {
  vi.resetModules()
})

afterEach(() => {
  process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY = ORIGINAL_KEY
})

describe('isStripeConfigured', () => {
  it('is true for a real key', async () => {
    process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY = 'pk_test_51AbCdEf'
    const { isStripeConfigured } = await import('./stripe')

    expect(isStripeConfigured()).toBe(true)
  })

  it('is false when no key is set', async () => {
    delete process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY
    const { isStripeConfigured } = await import('./stripe')

    expect(isStripeConfigured()).toBe(false)
  })

  it('is false for the placeholder left in the example env file', async () => {
    // `pk_test_...` is a real-looking string that would otherwise pass a
    // truthiness check and send the user to a card form that cannot load.
    process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY = 'pk_test_...'
    const { isStripeConfigured } = await import('./stripe')

    expect(isStripeConfigured()).toBe(false)
  })

  it('is false for an empty key', async () => {
    process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY = ''
    const { isStripeConfigured } = await import('./stripe')

    expect(isStripeConfigured()).toBe(false)
  })
})

describe('getStripe', () => {
  it('resolves to null when unconfigured, rather than rejecting', async () => {
    // The caller awaits this on render; a rejection would surface as an
    // unhandled error instead of the free-trial fallback.
    delete process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY
    const { getStripe } = await import('./stripe')

    await expect(getStripe()).resolves.toBeNull()
  })

  it('loads Stripe once and reuses the promise', async () => {
    // Stripe.js injects a script tag; loading it per render would add one on
    // every mount.
    process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY = 'pk_test_51AbCdEf'
    const { loadStripe } = await import('@stripe/stripe-js')
    const { getStripe } = await import('./stripe')

    await getStripe()
    await getStripe()

    expect(loadStripe).toHaveBeenCalledTimes(1)
  })

  it('never calls Stripe with the placeholder key', async () => {
    process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY = 'pk_live_...'
    const { loadStripe } = await import('@stripe/stripe-js')
    const { getStripe } = await import('./stripe')

    await getStripe()

    expect(loadStripe).not.toHaveBeenCalled()
  })
})
