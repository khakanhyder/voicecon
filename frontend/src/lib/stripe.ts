import { loadStripe, type Stripe } from '@stripe/stripe-js'

/**
 * Stripe.js loader.
 *
 * The publishable key comes from `GET /billing/config` (set in the admin
 * console), falling back to NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY. The build-time
 * value alone could not follow a key changed in the dashboard. Returns null
 * when no usable key exists so the page can fall back to the free trial.
 */
const loaders = new Map<string, Promise<Stripe | null>>()

function usable(key: string | null | undefined): key is string {
  return !!key && key.startsWith('pk_') && !key.includes('...')
}

export function getStripe(key?: string | null): Promise<Stripe | null> {
  const resolved = usable(key) ? key : process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY
  if (!usable(resolved)) {
    return Promise.resolve(null)
  }
  let loader = loaders.get(resolved)
  if (!loader) {
    loader = loadStripe(resolved)
    loaders.set(resolved, loader)
  }
  return loader
}

export const isStripeConfigured = (key?: string | null): boolean =>
  usable(key) || usable(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY)
