/**
 * Payment-provider aware billing calls.
 *
 * The backend decides where new checkouts go (admin console → Payment
 * provider). `stripe` collects the card inside the app; `polar` sends the
 * customer to Polar's hosted checkout and activates the plan from Polar's
 * webhook. Components ask `/billing/config` rather than assuming either.
 */
import { useQuery } from '@tanstack/react-query'
import type { Stripe } from '@stripe/stripe-js'
import { apiClient } from './api'
import { API_ENDPOINTS } from './constants'

export type PaymentProvider = 'stripe' | 'polar'

export interface BillingConfig {
  provider: PaymentProvider
  /** `card`: in-app Stripe card form. `hosted`: redirect to the provider. */
  checkout_mode: 'card' | 'hosted'
  /** Can the active provider take a payment right now? */
  configured: boolean
  /** Stripe publishable key; null unless Stripe is the provider. */
  publishable_key: string | null
}

export type CheckoutStatus = 'active' | 'pending' | 'open' | 'failed' | 'expired'

export const billingService = {
  async getConfig(): Promise<BillingConfig> {
    const { data } = await apiClient.get<BillingConfig>(API_ENDPOINTS.BILLING_CONFIG)
    return data
  },

  /**
   * Pay for a plan with a card (Stripe), start to finish. Resolves once the
   * subscription is active; throws with a customer-readable message if not.
   *
   * Every card form goes through here so they all handle the bank's approval
   * step the same way. Many cards (most European and South Asian ones) need
   * 3-D Secure: the first call then answers "requires action" instead of
   * activating, Stripe shows the bank's prompt, and the server is asked to
   * finish. The server is told how the prompt ended either way — it re-checks
   * with Stripe and clears up a payment that was not approved.
   */
  async payWithCard(
    stripe: Stripe,
    params: {
      plan_id: string
      payment_method_id: string
      billing_period: 'monthly' | 'yearly'
      coupon_code?: string
    }
  ): Promise<void> {
    const { data } = await apiClient.post<{
      requires_action?: boolean
      client_secret?: string
      stripe_subscription_id?: string
    }>(API_ENDPOINTS.BILLING_CHECKOUT, params)
    if (!data?.requires_action || !data.client_secret) return

    const { error } = await stripe.confirmCardPayment(data.client_secret)
    try {
      await apiClient.post(API_ENDPOINTS.BILLING_CHECKOUT_CONFIRM, {
        stripe_subscription_id: data.stripe_subscription_id,
      })
    } catch (err) {
      // Stripe's wording for a failed bank check is the more specific one.
      if (error?.message) throw new Error(error.message)
      throw err
    }
  },

  /**
   * Create a Polar checkout and navigate to it. Resolves only on failure: on
   * success the page is already leaving.
   */
  async startHostedCheckout(params: {
    plan_id: string
    billing_period: 'monthly' | 'yearly'
    /** Where to land once the subscription is live, e.g. `/dashboard`. */
    return_path?: string
    /** Where Polar's back button goes. Defaults to the current page. */
    cancel_path?: string
    /** An affiliate coupon, already checked with `checkCoupon`. */
    coupon_code?: string
  }): Promise<void> {
    const { data } = await apiClient.post<{ url: string; checkout_id: string }>(
      API_ENDPOINTS.BILLING_CHECKOUT_SESSION,
      {
        cancel_path:
          typeof window !== 'undefined' ? window.location.pathname + window.location.search : undefined,
        ...params,
      }
    )
    window.location.assign(data.url)
  },

  /**
   * Check an affiliate coupon for this workspace without applying it. With no
   * code, checks the coupon of the affiliate who referred the workspace, so
   * checkout can prefill it. Never throws for an unusable code: `valid` is
   * false and `message` says why, in words for the customer.
   */
  async checkCoupon(code: string | undefined, billingPeriod: 'monthly' | 'yearly'): Promise<CouponQuote> {
    const { data } = await apiClient.get<CouponQuote>(API_ENDPOINTS.BILLING_COUPON, {
      params: { code: code || undefined, billing_period: billingPeriod },
    })
    return data
  },

  /** Apply a coupon ahead of checkout; credits a new workspace to its affiliate. */
  async applyCoupon(code: string, billingPeriod: 'monthly' | 'yearly'): Promise<CouponQuote> {
    const { data } = await apiClient.post<CouponQuote>(API_ENDPOINTS.BILLING_COUPON_APPLY, {
      code,
      billing_period: billingPeriod,
    })
    return data
  },

  async checkoutStatus(checkoutId: string): Promise<CheckoutStatus> {
    const { data } = await apiClient.get<{ status: CheckoutStatus }>(
      API_ENDPOINTS.BILLING_CHECKOUT_STATUS(checkoutId)
    )
    return data.status
  },

  /** Open the provider's billing portal (card, invoices, receipts). */
  async openPortal(returnPath = '/dashboard/settings/billing'): Promise<void> {
    const { data } = await apiClient.post<{ url: string }>(API_ENDPOINTS.BILLING_PORTAL, {
      return_path: returnPath,
    })
    window.location.assign(data.url)
  },
}

/** Where checkout goes right now. Refetched on focus so an admin switch shows up. */
export function useBillingConfig() {
  return useQuery({
    queryKey: ['billing', 'config'],
    queryFn: billingService.getConfig,
    staleTime: 30_000,
    retry: 1,
  })
}

export interface CouponQuote {
  valid: boolean
  code?: string | null
  percent_off?: number | null
  /** `once` | `forever` | `repeating` */
  duration?: string | null
  duration_in_months?: number | null
  /** `yearly` (annual plans only) | `all` */
  applies_to?: string | null
  /** e.g. "20% off your first payment" */
  description?: string | null
  /** Why the code can't be used. */
  message?: string | null
}

/** The first payment after a coupon, rounded to cents. */
export function discountedPrice(price: number, coupon: CouponQuote | null | undefined): number {
  if (!coupon?.valid || !coupon.percent_off) return price
  return Math.round(price * (100 - coupon.percent_off)) / 100
}
