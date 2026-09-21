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
  providers: { id: string; label: string; configured: boolean }[]
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
  status: 'ok' | 'invalid' | 'not_configured' | 'error'
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
  app: { name: string; version: string; environment: string; debug: boolean }
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

  plans: () => get<{ plans: Plan[]; stripe_configured: boolean }>('/plans'),
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
}
