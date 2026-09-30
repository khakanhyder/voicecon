/**
 * Affiliate portal API client (`/api/v1/affiliate` + the affiliate auth routes).
 *
 * The portal is its own front door with its own session scope (lib/session.ts):
 * the backend refuses an affiliate token anywhere outside `/api/v1/affiliate`
 * (bar `/auth/logout`), and refuses app/admin tokens inside it. Every call goes
 * through the shared `apiClient`, which attaches the affiliate scope's token on
 * `/affiliate` pages and refreshes it on a 401. Affiliates have no workspace,
 * so the workspace header is skipped explicitly.
 */
import axios from 'axios'
import { apiClient } from '@/lib/api'
import { clearScope, getAccessToken, storeSession } from '@/lib/session'

const BASE = '/api/v1/affiliate'
const NO_WORKSPACE = { headers: { 'X-Skip-Workspace': '1' } }

// ---------- Types ----------

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export type StripeState = 'not_connected' | 'incomplete' | 'ready'

export interface StripeInfo {
  state: StripeState
  account_id: string | null
  country: string | null
  details_submitted: boolean
  transfers_enabled: boolean
  payouts_enabled: boolean
  checked_at: string | null
  /** False when the platform has not configured Stripe Connect yet. */
  connect_available: boolean
}

export interface Coupon {
  code: string
  percent_off: number
  /** `yearly` = annual plans only, `all` = every plan. */
  applies_to: 'yearly' | 'all' | string
  duration: string
  duration_in_months: number | null
  active: boolean
  description: string
}

/** Which payments earn this affiliate a commission. */
export type EarnsOn = 'yearly' | 'monthly' | 'both'

export interface Rules {
  billing_periods: EarnsOn
  /** Rate on annual payments. */
  commission_percent: number
  /** Rate on monthly payments (already resolved: equals the annual rate when not set separately). */
  commission_percent_monthly: number
  hold_days: number
  min_payout_amount: number
  /** 1 = first annual payment, N = first N, null = every renewal. */
  max_commission_payments: number | null
  /** The same, counted in monthly payments. */
  max_monthly_commission_payments: number | null
  referral_window_days: number | null
  cookie_days: number
  /** Plan names; empty means every plan qualifies. */
  eligible_plans: string[]
}

export interface Balance {
  pending: number
  available: number
  in_payout: number
  paid: number
  lifetime: number
}

export interface AffiliateMe {
  id: string
  name: string
  company: string | null
  email: string | null
  status: string
  referral_code: string
  links: { landing: string; signup: string }
  coupon: Coupon | null
  rules: Rules
  program_enabled: boolean
  stripe: StripeInfo
  stats: { clicks: number; clicks_30d: number; referrals: number; conversions: number }
  balance: Balance
  currency: string
}

export type ReferralStatus =
  | 'signed_up'
  | 'trial'
  | 'paying_monthly'
  | 'paying_annual'
  | 'canceled'
  | 'lapsed'

export interface Referral {
  id: string
  customer: string
  source: string
  status: ReferralStatus | string
  signed_up_at: string
  converted_at: string | null
  earned: number
}

export type CommissionStatus = 'pending' | 'approved' | 'paid' | 'reversed' | 'rejected'

export interface Commission {
  id: string
  kind: 'commission' | 'clawback' | 'adjustment' | string
  provider: string | null
  customer: string | null
  plan_slug: string | null
  billing_period: string | null
  billing_reason: string | null
  base_amount: number
  rate_percent: number
  amount: number
  original_amount: number
  refunded_fraction: number
  currency: string
  status: CommissionStatus | string
  note: string | null
  earned_at: string | null
  available_at: string | null
  approved_at: string | null
  paid_at: string | null
  payout_id: string | null
}

export interface Payout {
  id: string
  amount: number
  currency: string
  method: 'stripe' | 'manual' | string
  status: 'processing' | 'paid' | 'failed' | string
  reference: string | null
  commission_count: number
  created_at: string | null
  paid_at: string | null
}

export interface InviteInfo {
  email: string
  name: string
  needs_password: boolean
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  user: unknown
}

// ---------- Calls ----------

async function get<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const clean: Record<string, string | number> = {}
  for (const [k, v] of Object.entries(params || {})) if (v !== undefined && v !== '') clean[k] = v
  const { data } = await apiClient.get<T>(`${BASE}${path}`, { ...NO_WORKSPACE, params: clean })
  return data
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const { data } = await apiClient.post<T>(`${BASE}${path}`, body ?? {}, NO_WORKSPACE)
  return data
}

export const affiliateApi = {
  me: () => get<AffiliateMe>('/me'),
  referrals: (page = 1) => get<Page<Referral>>('/referrals', { page }),
  commissions: (page = 1, status?: CommissionStatus) =>
    get<Page<Commission>>('/commissions', { page, status }),
  payouts: (page = 1) => get<Page<Payout>>('/payouts', { page }),
  stripeConnect: (country: string) => post<{ url: string }>('/stripe/connect', { country }),
  stripeRefresh: () => post<StripeInfo>('/stripe/refresh'),
  stripeDashboard: () => post<{ url: string }>('/stripe/dashboard'),
}

/**
 * Auth calls for the portal. The anonymous ones (login, invite, password reset)
 * are posted with plain axios rather than `apiClient`, so a stale stored
 * session can never trigger the refresh-and-redirect path mid-form.
 */
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const anon = axios.create({ baseURL: API_BASE, headers: { 'Content-Type': 'application/json' } })

export const affiliateAuth = {
  isSignedIn: () => !!getAccessToken('affiliate'),

  async login(email: string, password: string): Promise<LoginResponse> {
    const { data } = await anon.post<LoginResponse>('/api/v1/auth/affiliate/login', { email, password })
    storeSession(data, 'affiliate')
    return data
  },

  async inviteInfo(token: string): Promise<InviteInfo> {
    const { data } = await anon.get<InviteInfo>('/api/v1/auth/affiliate/invite', { params: { token } })
    return data
  },

  async acceptInvite(token: string, password?: string): Promise<LoginResponse> {
    const { data } = await anon.post<LoginResponse>('/api/v1/auth/affiliate/accept-invite', {
      token,
      ...(password ? { password } : {}),
    })
    storeSession(data, 'affiliate')
    return data
  },

  async forgotPassword(email: string): Promise<{ message: string; debug_code?: string | null }> {
    const { data } = await anon.post('/api/v1/auth/password/forgot', { email })
    return data
  },

  /**
   * Set a new password with the emailed code.
   *
   * The reset endpoint answers with an *app*-scoped session. It is deliberately
   * discarded (never stored); the caller opens a portal session with
   * `login(email, newPassword)` afterwards.
   */
  async resetPassword(email: string, code: string, newPassword: string): Promise<void> {
    await anon.post('/api/v1/auth/password/reset', { email, code, new_password: newPassword })
  },

  /**
   * End the portal session. `/auth/logout` is scope-neutral on the server, and
   * it signs the *account* out everywhere (token_version bump).
   */
  async logout(): Promise<void> {
    try {
      await apiClient.post('/api/v1/auth/logout', {}, NO_WORKSPACE)
    } catch {
      // Signing out locally still has to happen.
    }
    clearScope('affiliate')
  },
}

// ---------- Formatting ----------

const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

export function money(value: number | null | undefined): string {
  return usd.format(Number(value || 0))
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

export const REFERRAL_STATUS_LABELS: Record<string, string> = {
  signed_up: 'Signed up',
  trial: 'On free trial',
  paying_monthly: 'Paying monthly',
  paying_annual: 'Paying annually',
  canceled: 'Canceled',
  lapsed: 'Lapsed',
}

export const COMMISSION_STATUS_LABELS: Record<string, string> = {
  pending: 'Pending',
  approved: 'Approved',
  paid: 'Paid',
  reversed: 'Reversed',
  rejected: 'Rejected',
}

export const KIND_LABELS: Record<string, string> = {
  commission: 'Commission',
  clawback: 'Clawback',
  adjustment: 'Adjustment',
}

/** Stripe/Polar billing reasons, phrased for a partner. */
export function billingReasonLabel(reason: string | null | undefined, period?: string | null): string | null {
  if (!reason) return null
  const kind = period === 'monthly' ? 'monthly' : 'annual'
  // Mirrors BASE_/PRORATION_BILLING_REASONS in backend services/affiliates/program.py.
  const labels: Record<string, string> = {
    subscription_create: `New ${kind} subscription`,
    subscription_cycle: period === 'monthly' ? 'Monthly renewal' : 'Annual renewal',
    subscription_update: 'Upgrade',
  }
  return labels[reason] ?? null
}

/** "annual plans" / "monthly plans" / "monthly and annual plans" */
export function earnsOnPhrase(earnsOn: EarnsOn | undefined): string {
  if (earnsOn === 'monthly') return 'monthly plans'
  if (earnsOn === 'both') return 'monthly and annual plans'
  return 'annual plans'
}
