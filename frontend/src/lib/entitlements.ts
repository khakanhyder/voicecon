/**
 * Subscription entitlements — what the current workspace's plan allows.
 *
 * Mirrors the backend's `app/services/billing/catalog.py`. The server enforces
 * all of this independently; everything here is presentation only, so the UI can
 * disable a button rather than let the user click it into a 402.
 */
import { apiClient } from './api'

/** Effective subscription status, after the server applies trial expiry. */
export type SubscriptionStatus =
  | 'trialing'
  | 'active'
  | 'past_due'
  | 'grace'
  | 'expired'
  | 'canceled'
  | 'incomplete'

/** Feature keys. A public contract with the backend: add, never rename. */
export const FEATURES = {
  INBOUND_CALLS: 'inbound_calls',
  OUTBOUND_CALLS: 'outbound_calls',
  OUTBOUND_CAMPAIGNS: 'outbound_campaigns',
  SMS: 'sms',
  EMAIL: 'email',
  WORKFLOWS: 'workflows',
  WORKFLOW_SCHEDULING: 'workflow_scheduling',
  CRM_INTEGRATIONS: 'crm_integrations',
  KNOWLEDGE_BASE: 'knowledge_base',
  VIRTUAL_MEETINGS: 'virtual_meetings',
  LEAD_SCORING: 'lead_scoring',
  API_ACCESS: 'api_access',
  CUSTOM_VOICE: 'custom_voice',
  WHITE_LABEL: 'white_label',
  ANALYTICS: 'analytics',
  CALL_RECORDINGS: 'call_recordings',
  WEBHOOKS: 'webhooks',
} as const

export const LIMITS = {
  AGENTS: 'agents',
  PHONE_NUMBERS: 'phone_numbers',
  KNOWLEDGE_BASES: 'knowledge_bases',
  TEAM_MEMBERS: 'team_members',
  WORKFLOWS: 'workflows',
  API_KEYS: 'api_keys',
  MINUTES: 'minutes_per_month',
  CALLS: 'calls_per_month',
  SMS: 'sms_per_month',
  EMAILS: 'emails_per_month',
} as const

export type FeatureKey = (typeof FEATURES)[keyof typeof FEATURES]
export type LimitKey = (typeof LIMITS)[keyof typeof LIMITS]

export const FEATURE_LABELS: Record<string, string> = {
  [FEATURES.INBOUND_CALLS]: 'Inbound calls',
  [FEATURES.OUTBOUND_CALLS]: 'Outbound calls',
  [FEATURES.OUTBOUND_CAMPAIGNS]: 'Outbound campaigns',
  [FEATURES.SMS]: 'SMS messaging',
  [FEATURES.EMAIL]: 'Email sending',
  [FEATURES.WORKFLOWS]: 'Workflows',
  [FEATURES.WORKFLOW_SCHEDULING]: 'Scheduled & triggered workflows',
  [FEATURES.CRM_INTEGRATIONS]: 'CRM integrations',
  [FEATURES.KNOWLEDGE_BASE]: 'Knowledge base',
  [FEATURES.VIRTUAL_MEETINGS]: 'Virtual meetings & note taking',
  [FEATURES.LEAD_SCORING]: 'Lead scoring & data enrichment',
  [FEATURES.API_ACCESS]: 'Public API access',
  [FEATURES.CUSTOM_VOICE]: 'Custom voice cloning',
  [FEATURES.WHITE_LABEL]: 'White labelling',
  [FEATURES.ANALYTICS]: 'Analytics',
  [FEATURES.CALL_RECORDINGS]: 'Call recordings & transcripts',
  [FEATURES.WEBHOOKS]: 'Webhooks',
}

export const LIMIT_LABELS: Record<string, string> = {
  [LIMITS.AGENTS]: 'AI agents',
  [LIMITS.PHONE_NUMBERS]: 'phone numbers',
  [LIMITS.KNOWLEDGE_BASES]: 'knowledge bases',
  [LIMITS.TEAM_MEMBERS]: 'team members',
  [LIMITS.WORKFLOWS]: 'workflows',
  [LIMITS.API_KEYS]: 'API keys',
  [LIMITS.MINUTES]: 'minutes',
  [LIMITS.CALLS]: 'calls',
  [LIMITS.SMS]: 'SMS',
  [LIMITS.EMAILS]: 'emails',
}

export const PLAN_LABELS: Record<string, string> = {
  'sales-chatbot': 'Sales Chatbot',
  'voice-ai': 'Voice AI',
}

export interface Entitlements {
  status: SubscriptionStatus
  plan_id: string | null
  plan_slug: string | null
  plan_name: string | null
  plan_tier: number
  source: string | null
  billing_period: string | null

  is_live: boolean
  is_read_only: boolean
  is_trial: boolean
  in_grace: boolean
  has_subscription: boolean

  trial_end: string | null
  days_remaining: number | null
  trial_expiring_soon: boolean
  grace_period_end: string | null
  grace_days_remaining: number | null
  current_period_end: string | null
  cancel_at_period_end: boolean

  features: string[]
  limits: Record<string, number>
  usage: Record<string, number>
  overage_allowed: boolean

  /** May this account still start a free trial? One per account, ever. */
  trial_available: boolean
  /** The one free trial has been spent — by this workspace or this person. */
  trial_used: boolean
}

/** The structured body a 402 carries. See `app/core/entitlement_guard.py`. */
export interface EntitlementErrorBody {
  detail: string
  code: 'entitlement_required'
  reason: 'subscription_inactive' | 'feature_not_in_plan' | 'limit_exceeded' | 'read_only'
  status: SubscriptionStatus
  current_plan: string | null
  current_plan_name: string | null
  upgrade_url: string
  feature?: string
  feature_label?: string
  limit?: string
  limit_label?: string
  used?: number
  cap?: number
  required_plans?: string[]
  grace_period_end?: string
}

export interface SubscriptionEvent {
  id: string
  event_type: string
  from_status: string | null
  to_status: string | null
  actor_type: string
  created_at: string
  payload: Record<string, unknown>
}

export const entitlementService = {
  async get(refresh = false): Promise<Entitlements> {
    const { data } = await apiClient.get<Entitlements>('/api/v1/billing/entitlements', {
      params: refresh ? { refresh: true } : undefined,
    })
    return data
  },

  async events(limit = 50): Promise<SubscriptionEvent[]> {
    const { data } = await apiClient.get<SubscriptionEvent[]>('/api/v1/billing/events', {
      params: { limit },
    })
    return data
  },

  async startTrial(planId?: string) {
    const { data } = await apiClient.post('/api/v1/billing/trial', {
      plan_id: planId ?? null,
      billing_period: 'monthly',
    })
    return data
  },

  async changePlan(planId: string) {
    const { data } = await apiClient.post('/api/v1/billing/subscription/change-plan', {
      plan_id: planId,
    })
    return data
  },

  async reactivate() {
    const { data } = await apiClient.post('/api/v1/billing/subscription/reactivate')
    return data
  },

  async cancel(immediate = false) {
    await apiClient.delete('/api/v1/billing/subscription', { params: { immediate } })
  },
}

/** `-1` means unlimited, so a plain `used < cap` comparison would be wrong. */
export function isUnlimited(cap: number | undefined): boolean {
  return cap === -1
}

export function formatCap(cap: number | undefined): string {
  if (cap === undefined) return '0'
  return cap === -1 ? 'Unlimited' : String(cap)
}

/**
 * The one place that turns a status into a banner.
 *
 * Returns at most one banner, highest severity first — stacked billing banners
 * get ignored wholesale, so the rule is one or none.
 */
export type BannerTone = 'info' | 'warning' | 'danger'

export interface BillingBanner {
  tone: BannerTone
  title: string
  body: string
  cta: string
  dismissible: boolean
  key: string
}

export function billingBanner(ent: Entitlements | null): BillingBanner | null {
  if (!ent) return null

  if (ent.status === 'expired') {
    const wasTrial = ent.source === 'trial'
    return {
      key: 'expired',
      tone: 'danger',
      dismissible: false,
      title: wasTrial ? 'Your free trial has ended' : 'Your subscription has ended',
      body: 'Your agents are paused and calls are not being answered. Everything you built is kept — choose a plan to switch it back on.',
      cta: 'Choose a plan',
    }
  }

  if (ent.status === 'canceled') {
    return {
      key: 'canceled',
      tone: 'danger',
      dismissible: false,
      title: 'Your subscription has been cancelled',
      body: 'Your workspace is read-only. Reactivate to start answering calls again.',
      cta: 'Reactivate',
    }
  }

  if (ent.in_grace) {
    const days = ent.grace_days_remaining ?? 0
    return {
      key: 'grace',
      tone: 'danger',
      dismissible: false,
      title: 'Your trial has ended',
      body:
        days > 0
          ? `You have ${days} ${days === 1 ? 'day' : 'days'} before your phone number is released. Choose a plan to keep it.`
          : 'Your phone number is about to be released. Choose a plan to keep it.',
      cta: 'Choose a plan',
    }
  }

  if (ent.status === 'past_due') {
    return {
      key: 'past_due',
      tone: 'warning',
      dismissible: true,
      title: "We couldn't process your payment",
      body: "We'll retry your card over the next few days. Update your payment details to avoid interruption.",
      cta: 'Update payment method',
    }
  }

  if (ent.is_trial && ent.trial_expiring_soon) {
    const days = ent.days_remaining ?? 0
    return {
      key: `trial-ending-${days}`,
      tone: 'warning',
      dismissible: true,
      title:
        days <= 1
          ? 'Your free trial ends today'
          : `Your free trial ends in ${days} days`,
      body: 'Add a payment method to keep your phone number, your agents and everything you have built.',
      cta: 'Choose a plan',
    }
  }

  if (ent.cancel_at_period_end && ent.current_period_end) {
    const when = new Date(ent.current_period_end).toLocaleDateString(undefined, {
      month: 'long',
      day: 'numeric',
    })
    return {
      key: 'cancelling',
      tone: 'warning',
      dismissible: true,
      title: `Your subscription ends on ${when}`,
      body: 'You keep full access until then. Reactivate any time before that date.',
      cta: 'Reactivate',
    }
  }

  if (ent.is_trial) {
    const days = ent.days_remaining ?? 0
    return {
      key: 'trial',
      tone: 'info',
      dismissible: false,
      title: `Free trial — ${days} ${days === 1 ? 'day' : 'days'} left`,
      body: 'You have full access to every feature while you try Voicecon.',
      cta: 'Choose a plan',
    }
  }

  return null
}
