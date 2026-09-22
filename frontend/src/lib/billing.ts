/**
 * Payment-provider aware billing calls.
 *
 * The backend decides where new checkouts go (admin console → Payment
 * provider). `stripe` collects the card inside the app; `polar` sends the
 * customer to Polar's hosted checkout and activates the plan from Polar's
 * webhook. Components ask `/billing/config` rather than assuming either.
 */
import { useQuery } from '@tanstack/react-query'
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
