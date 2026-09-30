/**
 * Platform admin API client (`/api/v1/admin`).
 *
 * Every call goes through the shared `apiClient`, so token refresh works the
 * same as the rest of the app. The admin API ignores the workspace header —
 * it is not workspace-scoped — so requests skip it explicitly.
 */
import { apiClient } from '@/lib/api'

const BASE = '/api/v1/admin'
const NO_WORKSPACE = { headers: { 'X-Skip-Workspace': '1' } }

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export type Query = Record<string, string | number | boolean | undefined | null>

function clean(params?: Query) {
  if (!params) return undefined
  const out: Record<string, string | number | boolean> = {}
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') out[k] = v
  }
  return out
}

async function get<T>(path: string, params?: Query): Promise<T> {
  const { data } = await apiClient.get<T>(`${BASE}${path}`, { ...NO_WORKSPACE, params: clean(params) })
  return data
}

async function send<T>(method: 'post' | 'put' | 'patch' | 'delete', path: string, body?: unknown): Promise<T> {
  const { data } = await apiClient.request<T>({ method, url: `${BASE}${path}`, data: body, ...NO_WORKSPACE })
  return data
}

// ---------- Types ----------

export interface SubscriptionView {
  id: string
  status: string
  stored_status: string
  source: string
  billing_period: string
  plan: { id: string; name: string; slug: string } | null
  trial_end: string | null
  current_period_start: string | null
  current_period_end: string | null
  grace_period_end: string | null
  cancel_at_period_end: boolean
  stripe_customer_id: string | null
  stripe_subscription_id: string | null
  polar_customer_id: string | null
  polar_subscription_id: string | null
  usage: { minutes: number; calls: number; sms: number; emails: number }
  created_at: string | null
}

export interface Overview {
  kpis: {
    users_total: number
    users_new_7d: number
    organizations_total: number
    organizations_suspended: number
    agents_total: number
    phone_numbers_active: number
    calls_24h: number
    calls_30d: number
    failed_calls_24h: number
    minutes_30d: number
    mrr: number
    open_payment_failures: number
    broken_connections: number
    failed_workflow_runs_24h: number
  }
  subscriptions: Record<string, number>
  calls_daily: { date: string; calls: number; minutes: number }[]
  signups_daily: { date: string; users: number }[]
  recent_organizations: {
    id: string
    name: string
    is_active: boolean
    created_at: string
    owner: { id: string; email: string; full_name: string | null }
    subscription: SubscriptionView | null
  }[]
  providers: {
    id: string
    label: string
    configured: boolean
    /** Payment providers only: is this the one new checkouts use? */
    active_payment_provider?: boolean
    /** An unused payment provider: missing keys are not a problem. */
    optional?: boolean
  }[]
  generated_at: string
}

export interface SettingEntry {
  key: string
  label: string
  kind: 'secret' | 'string' | 'text' | 'url' | 'bool' | 'int' | 'choice'
  description: string
  placeholder: string
  choices: string[]
  is_secret: boolean
  source: 'database' | 'environment' | 'unset'
  has_env_value: boolean
  error: string | null
  updated_at: string | null
  updated_by: string | null
  value: string | number | boolean | null
  hint: string | null
}

export interface SettingGroup {
  id: string
  label: string
  description: string
  icon: string
  test: string | null
  docs_url: string | null
  settings: SettingEntry[]
}

export interface SettingsResponse {
  groups: SettingGroup[]
  encryption_ready: boolean
  runtime: {
    overrides_applied: number
    errors: Record<string, string>
    loaded_at: string | null
    checked_at: string | null
    poll_interval_seconds: number
  }
}

export interface CheckResult {
  /** `incomplete`: the credential works but the provider still can't be used (e.g. keys from different modes). */
  status: 'ok' | 'invalid' | 'incomplete' | 'not_configured' | 'error'
  message: string
  latency_ms: number | null
}

export interface OrgRow {
  id: string
  name: string
  slug: string
  is_active: boolean
  created_at: string
  owner: { id: string; email: string; full_name: string | null }
  members: number
  agents: number
  phone_numbers: number
  calls_30d: number
  subscription: SubscriptionView | null
}

export interface OrgDetail {
  id: string
  name: string
  slug: string
  is_active: boolean
  billing_email: string | null
  created_at: string
  owner: { id: string; email: string; full_name: string | null } | null
  members: {
    user_id: string
    email: string
    full_name: string | null
    role: string
    is_active: boolean
    joined_at: string | null
    last_login_at: string | null
  }[]
  subscription: SubscriptionView | null
  override: {
    overrides: { features?: Record<string, boolean>; limits?: Record<string, number> }
    reason: string | null
    expires_at: string | null
    active: boolean
    updated_at: string | null
  } | null
  entitlements: {
    status: string
    plan_name: string | null
    features: string[]
    limits: Record<string, number>
    usage: Record<string, number>
  } | null
  usage: Record<string, number>
  recent_calls: {
    id: string
    direction: string
    status: string
    from_number: string
    to_number: string
    agent_name: string | null
    duration_seconds: number | null
    created_at: string
  }[]
  events: {
    id: string
    event_type: string
    from_status: string | null
    to_status: string | null
    actor_type: string
    created_at: string
  }[]
}

export interface Catalog {
  features: { key: string; label: string }[]
  limits: { key: string; label: string }[]
  unlimited: number
}

export interface UserRow {
  id: string
  email: string
  full_name: string | null
  auth_provider: string
  is_active: boolean
  is_verified: boolean
  is_platform_admin: boolean
  organizations: number
  locked_for_seconds: number
  created_at: string
  last_login_at: string | null
  deleted_at: string | null
}

export interface UserDetail extends UserRow {
  company_name: string | null
  phone_number: string | null
  timezone: string
  email_verified_at: string | null
  memberships: {
    organization_id: string
    organization_name: string
    organization_active: boolean
    role: string
    joined_at: string | null
  }[]
}

export interface Plan {
  id: string
  slug: string | null
  name: string
  description: string | null
  tier: number
  price_monthly: number
  price_yearly: number | null
  currency: string
  stripe_product_id: string
  stripe_price_id: string
  stripe_price_id_yearly: string | null
  polar_product_id: string | null
  polar_product_id_yearly: string | null
  trial_days: number
  is_trialable: boolean
  is_active: boolean
  is_public: boolean
  sort_order: number
  admin_managed: boolean
  highlights: string[]
  features: Record<string, boolean>
  limits: Record<string, number>
  subscribers: number
  created_at: string
}

export interface PaymentFailureRow {
  id: string
  organization_id: string
  organization_name: string
  failure_code: string | null
  failure_message: string
  amount_due: number | null
  currency: string | null
  hosted_invoice_url: string | null
  customer_notified: boolean
  resolved: boolean
  resolved_at: string | null
  resolution_notes: string | null
  created_at: string
}

export interface BillingEventRow {
  id: string
  organization_id: string
  organization_name: string
  event_type: string
  from_status: string | null
  to_status: string | null
  actor_type: string
  stripe_event_id: string | null
  created_at: string
}

export interface CallRow {
  id: string
  organization_id: string
  organization_name: string
  agent_name: string | null
  direction: string
  status: string
  from_number: string
  to_number: string
  duration_seconds: number | null
  cost_total: number | null
  has_recording: boolean
  has_transcript: boolean
  created_at: string
}

export interface CallDetail {
  id: string
  organization_id: string
  organization_name: string
  agent_name: string | null
  direction: string
  status: string
  from_number: string
  to_number: string
  provider: string | null
  provider_call_sid: string | null
  started_at: string | null
  answered_at: string | null
  ended_at: string | null
  duration_seconds: number | null
  billable_duration_seconds: number | null
  recording_url: string | null
  transcript: string | null
  transcript_json: unknown
  summary: string | null
  sentiment_label: string | null
  costs: Record<string, number | null>
  created_at: string
}

export interface NumberRow {
  id: string
  phone_number: string
  organization_id: string
  organization_name: string
  organization_active: boolean
  agent_name: string | null
  provider: string
  provider_sid: string | null
  bring_your_own: boolean
  status: string
  monthly_cost: number | null
  created_at: string
}

export interface ConnectionRow {
  id: string
  organization_id: string
  organization_name: string
  connector_name: string
  connector_slug: string
  name: string | null
  status: string
  last_error: string | null
  error_count: number
  token_expires_at: string | null
  last_sync_at: string | null
  updated_at: string | null
}

export interface WorkflowRunRow {
  id: string
  workflow_id: string
  workflow_name: string
  trigger_type: string
  organization_id: string
  organization_name: string
  status: string
  error_message: string | null
  steps_executed: number
  steps_failed: number
  duration_ms: number | null
  started_at: string
}

export interface SystemHealth {
  app: { name: string; version: string; environment: string; debug: boolean; payment_provider: 'stripe' | 'polar' }
  database: { ok: boolean; latency_ms?: number; error?: string }
  redis: { ok: boolean; configured: boolean; latency_ms?: number; error?: string }
  schedulers: { name: string; running: boolean }[]
  runtime_settings: SettingsResponse['runtime']
  providers: Overview['providers']
  bootstrap: { key: string; ok: boolean; note: string }[]
  email_provider: string
}

export interface AuditRow {
  id: string
  actor_email: string | null
  action: string
  target_type: string | null
  target_id: string | null
  summary: string | null
  details: unknown
  ip_address: string | null
  created_at: string
}

// ---------- Affiliates ----------

export type AffiliateStatus = 'invited' | 'active' | 'suspended'
export type StripeConnectState = 'not_connected' | 'incomplete' | 'ready'

export interface AffiliateProgram {
  enabled: boolean
  default_commission_percent: number
  hold_days: number
  min_payout_amount: number
  cookie_days: number
  /** null = no limit. */
  referral_window_days: number | null
  /** null = every annual renewal. */
  max_commission_payments: number | null
  /** For affiliates who earn on monthly plans. null = every month. */
  max_monthly_commission_payments: number | null
  /** Empty = every plan. */
  eligible_plan_slugs: string[]
  plans: { slug: string; name: string; has_yearly: boolean; is_active?: boolean }[]
  stripe_connect_ready: boolean
  payment_provider: 'stripe' | 'polar'
  updated_at: string | null
}

export type AffiliateProgramUpdate = Omit<
  AffiliateProgram,
  'plans' | 'stripe_connect_ready' | 'payment_provider' | 'updated_at'
>

/** Which payments earn an affiliate commission. */
export type CommissionBillingPeriods = 'yearly' | 'monthly' | 'both'

export const COMMISSION_PERIOD_LABELS: Record<CommissionBillingPeriods, string> = {
  yearly: 'Annual plans only',
  monthly: 'Monthly plans only',
  both: 'Monthly and annual plans',
}

export interface AffiliateCoupon {
  code: string
  percent_off: number
  applies_to: 'yearly' | 'all'
  duration: 'once' | 'forever' | 'repeating'
  duration_in_months: number | null
  active: boolean
  description: string
}

export interface AffiliateStripe {
  state: StripeConnectState
  account_id: string | null
  country: string | null
  details_submitted: boolean
  transfers_enabled: boolean
  payouts_enabled: boolean
  checked_at: string | null
  connect_available: boolean
}

export interface AffiliateBalance {
  pending: number
  available: number
  in_payout: number
  paid: number
  lifetime: number
}

export interface AffiliateRow {
  id: string
  user_id: string
  email: string | null
  name: string
  company: string | null
  status: AffiliateStatus
  referral_code: string
  links: { landing: string; signup: string }
  coupon: AffiliateCoupon | null
  commission_billing_periods: CommissionBillingPeriods
  /** Rate on annual payments. */
  commission_percent: number
  /** Rate on monthly payments; null = same as the annual rate. */
  commission_percent_monthly: number | null
  custom_max_payments: boolean
  max_commission_payments: number | null
  max_monthly_commission_payments: number | null
  discount_percent: number
  discount_applies_to: 'yearly' | 'all'
  discount_duration: 'once' | 'forever' | 'repeating'
  discount_duration_months: number | null
  stripe: AffiliateStripe
  notes: string | null
  has_password: boolean
  invited_at: string | null
  activated_at: string | null
  created_at: string | null
  balance: AffiliateBalance
  stats: { referrals: number; conversions: number; clicks: number; clicks_30d: number }
}

export interface AffiliateDetail extends AffiliateRow {
  payout: {
    available: number
    min_payout_amount: number
    meets_minimum: boolean
    stripe_ready: boolean
    /** Payouts still in flight. */
    processing: number
  }
  /** Only on create. */
  invite_url?: string
  invite_sent?: boolean
}

export interface AffiliateTermsBody {
  name?: string
  company?: string | null
  commission_billing_periods?: CommissionBillingPeriods
  commission_percent?: number | null
  commission_percent_monthly?: number | null
  referral_code?: string | null
  coupon_code?: string | null
  discount_percent?: number | null
  discount_applies_to?: 'yearly' | 'all'
  discount_duration?: 'once' | 'forever' | 'repeating'
  discount_duration_months?: number | null
  custom_max_payments?: boolean
  max_commission_payments?: number | null
  max_monthly_commission_payments?: number | null
  notes?: string | null
}

export interface AffiliateCreateBody extends AffiliateTermsBody {
  email: string
  name: string
  send_invite: boolean
}

export interface AffiliateUpdateBody extends AffiliateTermsBody {
  /** Clears the coupon entirely (`coupon_code: null` alone means "unchanged"). */
  remove_coupon?: boolean
}

export type CommissionStatus = 'pending' | 'approved' | 'paid' | 'reversed' | 'rejected'

export interface AffiliateCommission {
  id: string
  kind: 'commission' | 'clawback' | 'adjustment'
  provider: string
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
  status: CommissionStatus
  note: string | null
  earned_at: string | null
  available_at: string | null
  approved_at: string | null
  paid_at: string | null
  payout_id: string | null
  // List endpoint only.
  affiliate_id?: string
  affiliate_name?: string | null
  organization_id?: string | null
  organization_name?: string | null
  external_ref?: string | null
}

export interface AffiliatePayout {
  id: string
  amount: number
  currency: string
  method: 'stripe' | 'manual'
  status: 'processing' | 'paid' | 'failed'
  reference: string | null
  commission_count: number
  created_at: string | null
  paid_at: string | null
  affiliate_id: string
  stripe_transfer_id: string | null
  note: string | null
  failure_reason: string | null
  /** List endpoint only. */
  affiliate_name?: string | null
}

export interface AffiliateReferral {
  id: string
  organization_id: string
  organization_name: string | null
  email: string | null
  source: 'link' | 'coupon'
  status: 'signed_up' | 'trial' | 'paying_monthly' | 'paying_annual' | 'canceled' | 'lapsed'
  signed_up_at: string | null
  converted_at: string | null
  earned: number
}

// ---------- Client ----------

export const adminApi = {
  me: () => get<{ id: string; email: string; full_name: string | null }>('/me'),
  overview: () => get<Overview>('/overview'),

  settings: () => get<SettingsResponse>('/settings'),
  saveSetting: (key: string, value: unknown) => send<SettingEntry>('put', `/settings/${key}`, { value }),
  resetSetting: (key: string) => send<SettingEntry>('delete', `/settings/${key}`),
  testProvider: (provider: string) => send<CheckResult>('post', `/settings/test/${provider}`),

  organizations: (params: Query) => get<Page<OrgRow>>('/organizations', params),
  organization: (id: string) => get<OrgDetail>(`/organizations/${id}`),
  suspendOrg: (id: string, reason?: string) => send('post', `/organizations/${id}/suspend`, { reason }),
  activateOrg: (id: string, reason?: string) => send('post', `/organizations/${id}/activate`, { reason }),
  extendTrial: (id: string, days: number, reason?: string) =>
    send('post', `/organizations/${id}/extend-trial`, { days, reason }),
  grantPlan: (id: string, planId: string, reason?: string) =>
    send('post', `/organizations/${id}/grant-plan`, { plan_id: planId, reason }),
  endManualPlan: (id: string, reason?: string) => send('post', `/organizations/${id}/end-manual-plan`, { reason }),
  setOverride: (
    id: string,
    body: { features: Record<string, boolean>; limits: Record<string, number>; reason?: string; expires_at?: string | null }
  ) => send('put', `/organizations/${id}/override`, body),
  resetUsage: (id: string, reason?: string) => send('post', `/organizations/${id}/reset-usage`, { reason }),
  catalog: () => get<Catalog>('/catalog'),

  users: (params: Query) => get<Page<UserRow>>('/users', params),
  user: (id: string) => get<UserDetail>(`/users/${id}`),
  updateUser: (id: string, body: Partial<Pick<UserRow, 'is_active' | 'is_verified' | 'is_platform_admin'>>) =>
    send<UserRow>('patch', `/users/${id}`, body),
  signOutUser: (id: string) => send('post', `/users/${id}/sign-out`),
  unlockUser: (id: string) => send('post', `/users/${id}/unlock`),
  deleteUser: (id: string) => send<{ ok: boolean; workspaces_deactivated: number }>('delete', `/users/${id}`),

  plans: () =>
    get<{ plans: Plan[]; stripe_configured: boolean; polar_configured: boolean; payment_provider: 'stripe' | 'polar' }>('/plans'),
  syncPlanToPolar: (id: string) => send<Plan>('post', `/plans/${id}/polar-sync`),
  updatePlan: (id: string, body: Partial<Plan>) => send<Plan>('patch', `/plans/${id}`, body),
  setTrialLength: (days: number) => send<{ days: number; plans_updated: number }>('put', '/plans/trial', { days }),

  paymentFailures: (params: Query) => get<Page<PaymentFailureRow>>('/billing/payment-failures', params),
  resolvePaymentFailure: (id: string, notes?: string) =>
    send('post', `/billing/payment-failures/${id}/resolve`, { notes }),
  billingEvents: (params: Query) => get<Page<BillingEventRow>>('/billing/events', params),
  reconcile: () => send<{ report: string; changed: number }>('post', '/billing/reconcile'),

  calls: (params: Query) => get<Page<CallRow>>('/calls', params),
  call: (id: string) => get<CallDetail>(`/calls/${id}`),
  phoneNumbers: (params: Query) => get<Page<NumberRow>>('/phone-numbers', params),
  connections: (params: Query) => get<Page<ConnectionRow>>('/integrations/connections', params),
  workflowRuns: (params: Query) => get<Page<WorkflowRunRow>>('/workflows/runs', params),

  health: () => get<SystemHealth>('/system/health'),
  auditLogs: (params: Query) => get<Page<AuditRow>>('/audit-logs', params),

  affiliateProgram: () => get<AffiliateProgram>('/affiliates/program'),
  updateAffiliateProgram: (body: AffiliateProgramUpdate) => send<AffiliateProgram>('put', '/affiliates/program', body),
  affiliates: (params: Query) => get<Page<AffiliateRow>>('/affiliates', params),
  affiliate: (id: string) => get<AffiliateDetail>(`/affiliates/${id}`),
  createAffiliate: (body: AffiliateCreateBody) => send<AffiliateDetail>('post', '/affiliates', body),
  updateAffiliate: (id: string, body: AffiliateUpdateBody) => send<AffiliateDetail>('patch', `/affiliates/${id}`, body),
  setAffiliateStatus: (id: string, status: 'active' | 'suspended') =>
    send<AffiliateDetail>('post', `/affiliates/${id}/status`, { status }),
  resendAffiliateInvite: (id: string) =>
    send<{ invite_url: string; invite_sent: boolean }>('post', `/affiliates/${id}/invite`),
  affiliateReferrals: (id: string, params?: Query) => get<Page<AffiliateReferral>>(`/affiliates/${id}/referrals`, params),
  affiliateCommissions: (params: Query) => get<Page<AffiliateCommission>>('/affiliates/commissions', params),
  approveAffiliateCommission: (id: string) =>
    send<AffiliateCommission>('post', `/affiliates/commissions/${id}/approve`),
  rejectAffiliateCommission: (id: string, reason: string) =>
    send<AffiliateCommission>('post', `/affiliates/commissions/${id}/reject`, { reason }),
  createAffiliateAdjustment: (body: { affiliate_id: string; amount: number; note: string }) =>
    send<AffiliateCommission>('post', '/affiliates/commissions', body),
  affiliatePayouts: (params: Query) => get<Page<AffiliatePayout>>('/affiliates/payouts', params),
  createAffiliatePayout: (
    id: string,
    body: { method: 'stripe' | 'manual'; reference?: string | null; note?: string | null; ignore_minimum?: boolean }
  ) => send<AffiliatePayout>('post', `/affiliates/${id}/payouts`, body),
  resumeAffiliatePayout: (id: string) => send<AffiliatePayout>('post', `/affiliates/payouts/${id}/resume`),
}
