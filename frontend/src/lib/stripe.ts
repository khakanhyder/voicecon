import { loadStripe, type Stripe } from '@stripe/stripe-js'

/**
 * Singleton Stripe.js loader. Uses the publishable key from the environment
 * (NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY). Returns null when no key is configured
 * so the billing page can fall back gracefully to the free-trial path.
 */
let stripePromise: Promise<Stripe | null> | null = null

export function getStripe(): Promise<Stripe | null> {
  const key = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY
  if (!key || key.includes('...')) {
    return Promise.resolve(null)
  }
  if (!stripePromise) {
    stripePromise = loadStripe(key)
  }
  return stripePromise
}

export const isStripeConfigured = (): boolean => {
  const key = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY
  return !!key && !key.includes('...')
}
