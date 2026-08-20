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

export type BillingPeriod = 'monthly' | 'yearly'

/** A carrier account numbers can be bought on during onboarding. */
export interface TelephonyProvider {
  slug: string
  name: string
  source: 'integration' | 'platform'
  connection_id: string | null
  connection_name: string | null
  is_default?: boolean
}

export interface AvailableNumber {
  phone_number: string
  friendly_name: string
  provider: string
  locality: string | null
  region: string | null
  capabilities: Record<string, boolean>
  monthly_cost: number | null
  setup_cost: number | null
  currency: string | null
}

export interface ClaimedNumber {
  phone_number_id: string
  phone_number: string
  provider: string
  source: 'integration' | 'platform'
  account_name: string
  agent_id: string
  agent_name: string
  agent_created: boolean
}

export const onboardingService = {
  async getStatus(): Promise<OnboardingStatus> {
    const { data } = await apiClient.get('/api/v1/onboarding/status')
    return data
  },

  async saveCompany(payload: CompanyProfilePayload) {
    const { data } = await apiClient.post('/api/v1/onboarding/company', payload)
    return data
  },

  /**
   * Accounts this user can buy a number on. Empty means neither Voicecon's
   * shared Twilio nor a carrier of their own is available, so the onboarding
   * screen falls back to typing a contact number.
   */
  async getPhoneProviders(): Promise<TelephonyProvider[]> {
    const { data } = await apiClient.get('/api/v1/phone-numbers/providers')
    return Array.isArray(data) ? data : []
  },

  async searchPhoneNumbers(params: {
    country_code: string
    area_code?: string
    provider?: string
    connection_id?: string | null
    limit?: number
  }): Promise<AvailableNumber[]> {
    const query = new URLSearchParams({
      country_code: params.country_code,
      limit: String(params.limit ?? 6),
    })
    if (params.area_code) query.set('area_code', params.area_code)
    if (params.provider) query.set('provider', params.provider)
    if (params.connection_id) query.set('connection_id', params.connection_id)

    const { data } = await apiClient.get(`/api/v1/phone-numbers/search?${query}`)
    return Array.isArray(data) ? data : []
  },

  /** Buys the number and attaches it to the assistant being described. */
  async claimPhoneNumber(payload: {
    phone_number: string
    provider?: string
    connection_id?: string | null
    country_code?: string
    area_code?: string
    monthly_cost?: number | null
    assistant_name?: string
    assistant_instructions?: string
  }): Promise<ClaimedNumber> {
    const { data } = await apiClient.post('/api/v1/onboarding/phone-number', payload)
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

  async checkout(params: {
    plan_id: string
    payment_method_id: string
    billing_period: BillingPeriod
  }): Promise<SubscriptionResponse> {
    const { data } = await apiClient.post('/api/v1/billing/checkout', params)
    return data
  },
}
