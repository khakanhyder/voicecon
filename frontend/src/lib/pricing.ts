/**
 * Live pricing for the marketing site. Prices, plan names, descriptions,
 * limits, features and the trial length are all edited in the admin console
 * (/admin/plans), so the landing page reads them from the public billing API
 * instead of hardcoding them. Server components fetch this with a short
 * revalidate window, so an admin change shows up within a minute.
 */

import { API_BASE } from '@/lib/constants'

/** Seconds a fetched price list is reused before the page asks the API again. */
export const PRICING_REVALIDATE = 60

export type Limits = Record<string, number>

export interface PricingPlan {
  slug: string | null
  name: string
  description: string | null
  price_monthly: number
  price_yearly: number | null
  features: Record<string, boolean>
  limits: Limits
  /** Price of a minute past the allowance; null when usage never overflows. */
  overage_per_minute?: number | null
  /** Badged "Most popular" on the pricing cards. */
  popular?: boolean
  /** The plan's support level, e.g. "Priority email support". */
  support?: string | null
}

export interface TrialOffer {
  days: number
  limits: Limits
  payment_provider: string | null
}

export interface PricingData {
  plans: PricingPlan[]
  trial: TrialOffer
}

// Used only when the API cannot be reached (for example during a Docker build
// with no network). The next revalidation replaces it with the real values.
// Mirrors backend/app/services/billing/catalog.py.
const STARTER_FEATURES = {
  inbound_calls: true, email: true, workflows: true, knowledge_base: true,
  analytics: true, call_recordings: true, phone_number_purchase: true,
}
const GROWTH_FEATURES = { ...STARTER_FEATURES, outbound_calls: true, crm_integrations: true, webhooks: true, api_access: true }
const SCALE_FEATURES = { ...GROWTH_FEATURES, outbound_campaigns: true, lead_scoring: true, workflow_scheduling: true, custom_voice: true }

const FALLBACK: PricingData = {
  trial: {
    days: 14,
    limits: {
      agents: 1, phone_numbers: 1, knowledge_bases: 1, workflows: 2, team_members: 2, api_keys: 0,
      minutes_per_month: 30, emails_per_month: 100, concurrent_calls: 2, custom_voices: 1,
    },
    payment_provider: 'polar',
  },
  plans: [
    {
      slug: 'starter',
      name: 'Starter',
      description: 'For a solo business owner who wants every call answered.',
      price_monthly: 49,
      price_yearly: 468,
      features: STARTER_FEATURES,
      limits: {
        agents: 1, phone_numbers: 1, knowledge_bases: 1, team_members: 2, workflows: 3, api_keys: 0, custom_voices: 0,
        concurrent_calls: 3, minutes_per_month: 200, emails_per_month: 500,
      },
      overage_per_minute: 0.3,
      support: 'Email support',
    },
    {
      slug: 'growth',
      name: 'Growth',
      description: 'For clinics, salons and restaurants handling calls all day.',
      price_monthly: 149,
      price_yearly: 1428,
      features: GROWTH_FEATURES,
      limits: {
        agents: 3, phone_numbers: 2, knowledge_bases: 5, team_members: 5, workflows: 15, api_keys: 3, custom_voices: 0,
        concurrent_calls: 5, minutes_per_month: 750, emails_per_month: 2000,
      },
      overage_per_minute: 0.25,
      popular: true,
      support: 'Priority email support',
    },
    {
      slug: 'scale',
      name: 'Scale',
      description: 'For sales teams running high call volume.',
      price_monthly: 349,
      price_yearly: 3348,
      features: SCALE_FEATURES,
      limits: {
        agents: 10, phone_numbers: 5, knowledge_bases: -1, team_members: 10, workflows: -1, api_keys: 10, custom_voices: 2,
        concurrent_calls: 15, minutes_per_month: 2000, emails_per_month: 5000,
      },
      overage_per_minute: 0.2,
      support: 'Chat support and an onboarding call',
    },
    {
      slug: 'agency',
      name: 'Agency',
      description: 'For agencies and resellers serving many clients.',
      price_monthly: 499,
      price_yearly: 4788,
      features: { ...SCALE_FEATURES, white_label: true },
      limits: {
        agents: -1, phone_numbers: 20, knowledge_bases: -1, team_members: 25, workflows: -1, api_keys: 25, custom_voices: 10,
        concurrent_calls: 30, minutes_per_month: 3000, emails_per_month: 20000,
      },
      overage_per_minute: 0.15,
      support: 'Slack support and an account manager',
    },
  ],
}

/**
 * Enterprise is sold by contract, not through checkout, so it is not a plan
 * the API returns. Its card only states terms that are negotiated rather than
 * built — no product feature is claimed that the app does not have.
 */
export const ENTERPRISE = {
  name: 'Enterprise',
  description: 'For high call volume and regulated businesses.',
  price: 'Custom',
  cta: 'Contact sales',
  href: 'mailto:support@voicecon.ai?subject=Voicecon%20Enterprise',
  bullets: [
    'Custom minute rates and concurrency',
    'Volume pricing for many agents and numbers',
    'Dedicated support team and uptime SLA',
  ],
} as const

async function getJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}/api/v1${path}`, { next: { revalidate: PRICING_REVALIDATE } })
    return res.ok ? ((await res.json()) as T) : null
  } catch {
    return null
  }
}

/** A plan as `GET /billing/plans` returns it (the fields pricing cards need). */
export interface ApiPlan {
  slug?: string | null
  name: string
  description: string | null
  price_monthly: number
  price_yearly: number | null
  /** What the backend enforces — the admin's feature toggles and limits. */
  entitlements?: {
    features?: Record<string, boolean>
    limits?: Limits
    overage?: { allowed?: boolean; per_minute?: number }
  }
  /** Marketing column: `support` and `popular` feed the cards. */
  features?: Record<string, unknown>
  overage_rate_per_minute?: number
}

/** Normalise an API plan into the shape the card copy is built from. */
export function toPricingPlan(p: ApiPlan): PricingPlan {
  const overage = p.entitlements?.overage
  const rate = overage?.per_minute ?? p.overage_rate_per_minute
  const support = p.features?.support
  return {
    slug: p.slug ?? null,
    name: p.name,
    description: p.description,
    price_monthly: Number(p.price_monthly),
    price_yearly: p.price_yearly == null ? null : Number(p.price_yearly),
    features: p.entitlements?.features ?? {},
    limits: p.entitlements?.limits ?? {},
    overage_per_minute: overage?.allowed && rate ? Number(rate) : null,
    popular: p.features?.popular === true,
    support: typeof support === 'string' && support.trim() ? support.trim() : null,
  }
}

/**
 * Card bullets for plans straight from `GET /billing/plans`, in display order.
 * Every pricing card in the app goes through this, so the landing page,
 * onboarding and the billing settings all say the same thing — and all of it
 * follows the limits and feature toggles set in /admin/plans. Only those: they
 * are what the backend enforces, whereas free-text bullets drift out of step
 * with them (they once said "unlimited minutes" beside a 500-minute limit).
 */
export function planCardBullets(plans: ApiPlan[]): string[][] {
  const normalised = plans.map(toPricingPlan)
  return normalised.map((plan, i) => planBullets(plan, normalised[i - 1]))
}

/**
 * The price a card shows for ``period``, or ``null`` when the plan has no
 * yearly price. The backend refuses yearly checkout without one, so a card
 * must never invent it from the monthly price.
 */
export function periodPrice(
  plan: Pick<PricingPlan, 'price_monthly' | 'price_yearly'>,
  period: 'monthly' | 'yearly'
): number | null {
  if (period === 'yearly') return plan.price_yearly == null ? null : Number(plan.price_yearly)
  return Number(plan.price_monthly)
}

/** Plans marked public and available in the admin, in their admin sort order. */
export async function getPricing(): Promise<PricingData> {
  const [plans, trial] = await Promise.all([
    getJson<ApiPlan[]>('/billing/plans'),
    getJson<TrialOffer>('/billing/trial-offer'),
  ])
  return {
    plans: plans?.length ? plans.map(toPricingPlan) : FALLBACK.plans,
    trial: trial ?? FALLBACK.trial,
  }
}

// ---- Turning limits and features into pricing-card copy ----

const UNLIMITED = -1

/** "10 agents", "1 agent", "unlimited agents"; null when the plan allows none. */
function count(n: number | undefined, singular: string, plural = `${singular}s`): string | null {
  if (n === undefined || n === 0) return null
  if (n === UNLIMITED) return `unlimited ${plural}`
  return `${n.toLocaleString('en-US')} ${n === 1 ? singular : plural}`
}

function joinList(parts: (string | null | false)[]): string | null {
  const items = parts.filter(Boolean) as string[]
  if (!items.length) return null
  const text = items.length === 1 ? items[0] : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** "$0.30", "$0.15", "$0.075". */
export function perMinute(rate: number): string {
  return `$${rate.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 3 })}`
}

function usageLines(limits: Limits, features: Record<string, boolean> | null, overage?: number | null): string[] {
  const minutes = limits.minutes_per_month
  const usage: (string | null)[] = []
  if (minutes === UNLIMITED) {
    usage.push('Unlimited call minutes')
  } else if (minutes > 0) {
    const included = `${count(minutes, 'call minute')} a month`
    usage.push(overage ? `${included}, then ${perMinute(overage)}/min` : included)
  }
  const lines = limits.concurrent_calls
  usage.push(lines === UNLIMITED ? 'Unlimited calls at once' : lines > 0 ? `${count(lines, 'call')} at once` : null)
  // Text messages are not part of any plan, so no SMS allowance is shown.
  const emails = !features || features.email ? count(limits.emails_per_month, 'email') : null
  usage.push(emails && `${emails.charAt(0).toUpperCase()}${emails.slice(1)} a month`)
  return usage.filter(Boolean) as string[]
}

// Only features the product actually delivers. Outbound campaigns, virtual
// meetings, lead scoring and white labelling are plan flags with no feature
// behind them yet, so they are never advertised here even when the admin
// switches them on.
function featureLines(f: Record<string, boolean>, limits: Limits): string[] {
  const calls =
    f.inbound_calls && f.outbound_calls
      ? 'Inbound and outbound calls, transfer to a human'
      : f.inbound_calls
        ? 'Inbound calls, answered 24/7'
        : f.outbound_calls
          ? 'Outbound calls and transfer to a human'
          : null
  const recordings =
    f.call_recordings && f.analytics
      ? 'Call recordings, transcripts and analytics'
      : f.call_recordings
        ? 'Call recordings and transcripts'
        : f.analytics
          ? 'Call analytics'
          : null
  return [
    calls,
    f.crm_integrations ? 'All integrations: CRMs, messaging and automation' : null,
    f.webhooks ? 'Webhooks and custom tools' : null,
    f.workflow_scheduling ? 'Scheduled workflows (hourly, daily, cron)' : null,
    f.custom_voice ? count(limits.custom_voices, 'custom voice') ?? null : null,
    recordings,
  ].filter(Boolean) as string[]
}

/** Whether allowance `a` is at least `b`, treating -1 as unlimited. */
function atLeast(a: number | undefined, b: number | undefined): boolean {
  if (b === undefined || b === 0) return true
  if (a === UNLIMITED) return true
  if (b === UNLIMITED) return false
  return (a ?? 0) >= b
}

const MARKETED = [
  'inbound_calls', 'outbound_calls', 'crm_integrations', 'workflow_scheduling', 'webhooks',
  'custom_voice', 'call_recordings', 'analytics',
]

/** Bullet points for a paid plan, built from its live limits and features. */
export function planBullets(plan: PricingPlan, previous?: PricingPlan): string[] {
  const { limits: l, features: f } = plan
  // "Everything in X" only when this plan really includes all of X's features
  // and at least X's allowances — otherwise the card contradicts itself
  // ("everything in Starter" beside fewer minutes than Starter).
  const includesPrevious =
    !!previous &&
    MARKETED.every((key) => !previous.features[key] || f[key]) &&
    Object.entries(previous.limits).every(([key, n]) => atLeast(l[key as keyof Limits], n))
  const shown = includesPrevious
    ? Object.fromEntries(
        MARKETED.map((key) => [
          key,
          // A bigger custom-voice allowance is news even when the flag is not.
          key === 'custom_voice'
            ? f[key] && (!previous!.features[key] || l.custom_voices !== previous!.limits.custom_voices)
            : f[key] && !previous!.features[key],
        ])
      )
    : f

  return [
    includesPrevious ? `Everything in ${previous!.name}, plus:` : null,
    joinList([
      count(l.agents, 'AI agent'),
      count(l.phone_numbers, 'phone number'),
      f.workflows && count(l.workflows, 'workflow'),
    ]),
    joinList([f.knowledge_base && count(l.knowledge_bases, 'knowledge base'), count(l.team_members, 'team seat')]),
    ...usageLines(l, f, plan.overage_per_minute),
    // Only Google Calendar books today; Calendly and Cal.com are read-only.
    includesPrevious ? null : 'Appointment booking with Google Calendar',
    ...featureLines(shown, l),
    f.api_access && l.api_keys === UNLIMITED ? 'Unlimited API keys' : f.api_access && l.api_keys > 0 ? `API access, up to ${l.api_keys.toLocaleString('en-US')} keys` : null,
    plan.support,
  ].filter(Boolean) as string[]
}

/** Bullet points for the card-free trial. */
export function trialBullets(trial: TrialOffer): string[] {
  const l = trial.limits
  const minutes = l.minutes_per_month
  return [
    `${trial.days} days, no credit card required`,
    minutes === UNLIMITED ? 'Unlimited test minutes' : minutes > 0 ? `${count(minutes, 'call minute')} included` : null,
    joinList([count(l.agents, 'agent'), count(l.knowledge_bases, 'knowledge base'), count(l.workflows, 'workflow')]),
    l.team_members === UNLIMITED ? 'Unlimited team members' : l.team_members ? `Up to ${count(l.team_members, 'team member')}` : null,
    'Every agent and workflow template',
  ].filter(Boolean) as string[]
}

/** Largest whole-percent saving yearly billing gives over twelve monthly payments. */
export function yearlySavingPercent(
  plans: Pick<PricingPlan, 'price_monthly' | 'price_yearly'>[]
): number {
  let best = 0
  for (const p of plans) {
    if (!p.price_monthly || !p.price_yearly) continue
    best = Math.max(best, Math.round((1 - p.price_yearly / (p.price_monthly * 12)) * 100))
  }
  return best
}

export function paymentProviderName(provider: string | null): string | null {
  if (provider === 'stripe') return 'Stripe'
  if (provider === 'polar') return 'Polar'
  return null
}

/** "1 agent, 1 knowledge base, 2 workflows and 2 team members" for prose. */
export function trialLimitsSentence(trial: TrialOffer): string | null {
  const l = trial.limits
  const text = joinList([
    count(l.agents, 'agent'),
    count(l.knowledge_bases, 'knowledge base'),
    count(l.workflows, 'workflow'),
    count(l.team_members, 'team member'),
  ])
  return text && text.charAt(0).toLowerCase() + text.slice(1)
}
