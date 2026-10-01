import { apiClient } from './api'

export interface CompanyProfilePayload {
  company_name: string
  industry_type?: string
  company_size?: string
  company_url?: string
  assistant_name?: string
  preferred_language?: string
  assistant_instructions?: string
  phone_number?: string
}

export interface SubscriptionPlan {
  id: string
  name: string
  description: string | null
  price_monthly: number
  price_yearly: number | null
  included_minutes: number
  included_calls: number
  max_agents: number
  max_phone_numbers: number
  max_knowledge_bases: number
  features: { highlights?: string[] } & Record<string, unknown>
  /** The admin's feature toggles and limits — what the backend enforces. */
  entitlements?: { features?: Record<string, boolean>; limits?: Record<string, number> }
  trial_days: number
  is_active: boolean
  is_public: boolean
}

export interface SubscriptionResponse {
  id: string
  plan_id: string
  plan_name: string
  status: string
  billing_period: string
  current_period_start: string
  current_period_end: string
  trial_end: string | null
}

/**
 * The company profile captured at onboarding and editable afterwards from
 * Settings → Profile → Company Profile.
 */
export interface CompanyProfile {
  id: string
  organization_id: string
  company_name: string
  industry_type: string | null
  company_size: string | null
  company_url: string | null
  assistant_name: string | null
  preferred_language: string
  assistant_instructions: string | null
  phone_number: string | null
  onboarding_completed: boolean
  onboarding_step: string
}

export interface OnboardingStatus {
  onboarding_completed: boolean
  step: 'company' | 'pricing' | 'billing' | 'done'
  has_company_profile: boolean
  has_subscription: boolean
  company: CompanyProfile | null
}

// The option lists behind the company form's selects. Exported so the
// onboarding screen and the settings screen offer the same choices — two
// copies would drift, and a value saved on one screen would then be
// unselectable on the other.
export const INDUSTRY_TYPES = [
  'Business',
  'Real Estate',
  'Healthcare',
  'E-commerce',
  'Finance',
  'Education',
  'Technology',
  'Other',
]
export const COMPANY_SIZES = ['1 - 10', '10 - 40', '40 - 100', '100 - 500', '500+']
export const LANGUAGES = [
  'English',
  'Spanish',
  'French',
  'German',
  'Arabic',
  'Hindi',
  'Portuguese',
]

/**
 * Where a just-authenticated user belongs.
 *
 * The source of truth is the server's onboarding status, never "was this user
 * row created a moment ago" — a person who signed up with Apple or Google and
 * abandoned the flow is no longer new, but still has no company profile and no
 * plan, so the dashboard is the wrong place to drop them.
 *
 * `null` status means the status call failed; fall back to the sign-in
 * response's `is_new` so a transient error still routes somewhere sensible.
 */
export function onboardingRedirectPath(
  status: OnboardingStatus | null | undefined,
  fallback: { isNew?: boolean } = {},
): string {
  // An unrecognisable payload is treated the same as no answer at all: better
  // to fall back than to read a missing field as "not onboarded" and drag a
  // set-up account back through the flow.
  if (!status || typeof status.onboarding_completed !== 'boolean') {
    return fallback.isNew ? '/onboarding/company' : '/dashboard'
  }
  if (status.onboarding_completed) return '/dashboard'
  // The billing screen needs a plan picked in this session (it is held in
  // sessionStorage), so a user resuming later is sent to Pricing rather than
  // to Billing, which would immediately bounce them back to Pricing anyway.
  return status.step === 'pricing' || status.step === 'billing'
    ? '/onboarding/pricing'
    : '/onboarding/company'
}

export type BillingPeriod = 'monthly' | 'yearly'

export const onboardingService = {
  async getStatus(): Promise<OnboardingStatus> {
    const { data } = await apiClient.get('/api/v1/onboarding/status')
    return data
  },

  async saveCompany(payload: CompanyProfilePayload) {
    const { data } = await apiClient.post('/api/v1/onboarding/company', payload)
    return data
  },

  async getPlans(): Promise<SubscriptionPlan[]> {
    const { data } = await apiClient.get('/api/v1/billing/plans')
    return data
  },

  async getBillingConfig(): Promise<{ publishable_key: string | null; configured: boolean }> {
    const { data } = await apiClient.get('/api/v1/billing/config')
    return data
  },

  /** The trial's length is the server's to decide — see `plan.trial_days`. */
  async startTrial(params: {
    plan_id?: string
    billing_period?: BillingPeriod
  }): Promise<SubscriptionResponse> {
    const { data } = await apiClient.post('/api/v1/billing/trial', {
      plan_id: params.plan_id ?? null,
      billing_period: params.billing_period ?? 'monthly',
    })
    return data
  },
}
