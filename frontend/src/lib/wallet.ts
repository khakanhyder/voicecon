/**
 * The prepaid wallet behind the Pay As You Go plan.
 *
 * The server owns every price: the rate per minute, the top-up bounds and the
 * phone-number fee all arrive in `GET /billing/wallet`. The only number this
 * side sends is how much the customer wants to add, and the server checks it.
 *
 * Like checkout, a top-up follows the active payment provider: `card` collects
 * the card here (Stripe), `hosted` sends the customer to the provider's page
 * (Polar) and the balance is credited by its webhook.
 */
import { useQuery, useQueryClient } from '@tanstack/react-query'
import type { Stripe } from '@stripe/stripe-js'
import { apiClient } from './api'
import { API_ENDPOINTS } from './constants'

export interface AutoRecharge {
  /** Can a saved card be charged automatically with the current provider? */
  supported: boolean
  enabled: boolean
  threshold: number | null
  amount: number | null
  card_brand: string | null
  card_last4: string | null
}

export interface Wallet {
  /** Is Pay As You Go on sale at all? When false, no wallet UI is shown. */
  available: boolean
  plan_id: string | null
  plan_name: string | null
  /** The workspace is on the prepaid plan now. */
  on_plan: boolean
  /** A paid subscription becomes Pay As You Go at this date. */
  switching_at: string | null

  balance: number
  /** Part of the balance reserved by calls in progress. */
  held: number
  currency: string
  per_minute: number
  /** Whole minutes the unreserved balance pays for; null when minutes are free. */
  minutes_left: number | null
  number_monthly_fee: number
  low_balance: number
  is_low: boolean
  is_empty: boolean

  topup: { presets: number[]; minimum: number; maximum: number }
  provider: 'stripe' | 'polar'
  checkout_mode: 'card' | 'hosted'
  /** Can a top-up be taken right now? */
  can_topup: boolean
  publishable_key: string | null

  auto_recharge: AutoRecharge
}

export type WalletTransactionType = 'topup' | 'usage' | 'number_fee' | 'refund' | 'adjustment'

export interface WalletTransaction {
  id: string
  type: WalletTransactionType
  /** Signed: positive added credit, negative spent it. */
  amount: number
  balance_after: number
  description: string | null
  created_at: string
  receipt_url: string | null
}

export interface WalletTransactionPage {
  items: WalletTransaction[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface TopupResult {
  status: 'succeeded' | 'processing'
  balance?: number
  /** This top-up also moved the workspace onto Pay As You Go. */
  activated?: boolean
}

interface TopupResponse extends Partial<TopupResult> {
  requires_action?: boolean
  client_secret?: string
  payment_intent_id?: string
}

export type TopupStatus = 'active' | 'pending' | 'open' | 'failed' | 'expired'

export interface AutoRechargeSettings {
  enabled: boolean
  threshold?: number
  amount?: number
}

export const WALLET_QUERY_KEY = ['billing', 'wallet'] as const
export const WALLET_TRANSACTIONS_KEY = ['billing', 'wallet', 'transactions'] as const

export const walletService = {
  async get(): Promise<Wallet> {
    const { data } = await apiClient.get<Wallet>(API_ENDPOINTS.WALLET)
    return data
  },

  async transactions(page = 1, pageSize = 10): Promise<WalletTransactionPage> {
    const { data } = await apiClient.get<WalletTransactionPage>(API_ENDPOINTS.WALLET_TRANSACTIONS, {
      params: { page, page_size: pageSize },
    })
    return data
  },

  /**
   * Add credit with a card (Stripe), start to finish. Resolves once the server
   * says where the payment stands; throws with a customer-readable message if
   * the card was not charged.
   *
   * Many cards need the bank's approval (3-D Secure): the first call then
   * answers "requires action", Stripe shows the bank's prompt, and the server
   * is asked to finish. The server is told how the prompt ended either way —
   * it re-checks with Stripe and never credits on this side's say-so.
   */
  async topUpWithCard(
    stripe: Stripe,
    params: {
      amount: number
      payment_method_id: string
      save_card?: boolean
      /** Also move the workspace onto Pay As You Go once the payment is in. */
      activate?: boolean
      auto_recharge?: AutoRechargeSettings
    }
  ): Promise<TopupResult> {
    const { data } = await apiClient.post<TopupResponse>(API_ENDPOINTS.WALLET_TOPUP, params)
    if (!data?.requires_action || !data.client_secret) return data as TopupResult

    const { error } = await stripe.confirmCardPayment(data.client_secret)
    try {
      const confirmed = await apiClient.post<TopupResponse>(API_ENDPOINTS.WALLET_TOPUP_CONFIRM, {
        payment_intent_id: data.payment_intent_id,
      })
      return confirmed.data as TopupResult
    } catch (err) {
      // Stripe's wording for a failed bank check is the more specific one.
      if (error?.message) throw new Error(error.message)
      throw err
    }
  },

  /**
   * Create a hosted top-up checkout (Polar) and navigate to it. Resolves only
   * on failure: on success the page is already leaving.
   */
  async startHostedTopup(params: {
    amount: number
    activate?: boolean
    /** Where to land once the credit is in, e.g. `/dashboard/settings/billing`. */
    return_path?: string
    /** Where the provider's back button goes. Defaults to the current page. */
    cancel_path?: string
  }): Promise<void> {
    const { data } = await apiClient.post<{ url: string; checkout_id: string }>(
      API_ENDPOINTS.WALLET_TOPUP_SESSION,
      {
        cancel_path:
          typeof window !== 'undefined' ? window.location.pathname + window.location.search : undefined,
        ...params,
      }
    )
    window.location.assign(data.url)
  },

  async topupStatus(checkoutId: string): Promise<TopupStatus> {
    const { data } = await apiClient.get<{ status: TopupStatus }>(API_ENDPOINTS.WALLET_TOPUP_STATUS(checkoutId))
    return data.status
  },

  async setAutoRecharge(settings: AutoRechargeSettings): Promise<Wallet> {
    const { data } = await apiClient.put<Wallet>(API_ENDPOINTS.WALLET_AUTO_RECHARGE, settings)
    return data
  },

  async removeCard(): Promise<Wallet> {
    const { data } = await apiClient.delete<Wallet>(API_ENDPOINTS.WALLET_CARD)
    return data
  },
}

/**
 * The workspace's wallet. Refetched on focus and on a slow timer while the
 * page is open, because the balance moves whenever a call ends — nothing the
 * person at the screen did.
 */
export function useWallet(options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: WALLET_QUERY_KEY,
    queryFn: walletService.get,
    staleTime: 15_000,
    refetchInterval: 60_000,
    retry: 1,
    enabled: options.enabled ?? true,
  })
}

/** Refetch everything that shows the balance, after a top-up or a settings change. */
export function useRefreshWallet() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: WALLET_QUERY_KEY })
}

/** "$12.50", "-$3.00". */
export function formatMoney(amount: number): string {
  const sign = amount < 0 ? '-' : ''
  return `${sign}$${Math.abs(amount).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

/** "+$25.00" / "-$1.05" for a ledger row. */
export function formatSigned(amount: number): string {
  return amount > 0 ? `+${formatMoney(amount)}` : formatMoney(amount)
}

export const TRANSACTION_LABELS: Record<string, string> = {
  topup: 'Credit added',
  usage: 'Call',
  number_fee: 'Phone number',
  refund: 'Refund',
  adjustment: 'Adjustment',
}

/** "About 28 minutes of calls" for a balance, or null when minutes are free. */
export function minutesLeftLabel(wallet: Pick<Wallet, 'minutes_left'>): string | null {
  const minutes = wallet.minutes_left
  if (minutes == null) return null
  if (minutes < 1) return 'Not enough for a call'
  return `About ${minutes.toLocaleString('en-US')} ${minutes === 1 ? 'minute' : 'minutes'} of calls`
}

/**
 * Whole call minutes `amount` pays for at `rate` a minute; null when it buys
 * none that can be counted (no rate, no amount). Worked out in whole
 * thousandths of a cent so 10 / 0.35 is 28, not 27 from a float.
 */
export function minutesFor(amount: number, rate: number): number | null {
  if (!(rate > 0) || !(amount > 0)) return null
  return Math.floor((Math.round(amount * 100) * 1000) / Math.round(rate * 100_000))
}

/**
 * Why a custom top-up amount cannot be used, in words for the customer; null
 * when it can. The server checks the same bounds — this only saves a round trip.
 */
export function topupAmountProblem(
  amount: number,
  bounds: Pick<Wallet['topup'], 'minimum' | 'maximum'>
): string | null {
  if (!Number.isFinite(amount) || amount <= 0) return 'Enter the amount you want to add.'
  if (amount < bounds.minimum) return `The smallest top-up is ${formatMoney(bounds.minimum)}.`
  if (amount > bounds.maximum) return `The largest single top-up is ${formatMoney(bounds.maximum)}.`
  return null
}
