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

export interface OnboardingStatus {
  onboarding_completed: boolean
  step: 'company' | 'pricing' | 'billing' | 'done'
  has_company_profile: boolean
  has_subscription: boolean
  company: Record<string, unknown> | null
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

  async startTrial(params: {
    plan_id?: string
    billing_period?: BillingPeriod
    trial_days?: number
  }): Promise<SubscriptionResponse> {
    const { data } = await apiClient.post('/api/v1/billing/trial', {
      plan_id: params.plan_id ?? null,
      billing_period: params.billing_period ?? 'monthly',
      trial_days: params.trial_days ?? 7,
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
