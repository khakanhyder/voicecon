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
const FALLBACK: PricingData = {
  trial: {
    days: 30,
    limits: { agents: 1, knowledge_bases: 1, workflows: 2, team_members: 2, minutes_per_month: -1, calls_per_month: -1 },
    payment_provider: 'stripe',
  },
  plans: [
    {
      slug: 'sales-chatbot',
      name: 'Sales Chatbot',
      description: 'For a team putting its first agents on the phone.',
      price_monthly: 119,
      price_yearly: 1071,
      features: {
        inbound_calls: true, outbound_calls: true, sms: true, email: true, workflows: true,
        crm_integrations: true, knowledge_base: true, analytics: true, call_recordings: true, webhooks: true,
      },
      limits: {
        agents: 10, phone_numbers: 10, knowledge_bases: 10, team_members: 10, workflows: 10, api_keys: 100,
        minutes_per_month: -1, calls_per_month: -1, sms_per_month: 600, emails_per_month: 2500,
      },
    },
    {
      slug: 'voice-ai',
      name: 'Voice AI',
      description: 'For businesses running many agents across several teams.',
      price_monthly: 359,
      price_yearly: 3231,
      features: {
        inbound_calls: true, outbound_calls: true, sms: true, email: true, workflows: true, workflow_scheduling: true,
        crm_integrations: true, knowledge_base: true, analytics: true, call_recordings: true, webhooks: true,
      },
      limits: {
        agents: 30, phone_numbers: 30, knowledge_bases: 30, team_members: 30, workflows: 30, api_keys: 200,
        minutes_per_month: -1, calls_per_month: -1, sms_per_month: 1000, emails_per_month: 5000,
      },
    },
  ],
}

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
  entitlements?: { features?: Record<string, boolean>; limits?: Limits }
}

/** Normalise an API plan into the shape the card copy is built from. */
export function toPricingPlan(p: ApiPlan): PricingPlan {
  return {
    slug: p.slug ?? null,
    name: p.name,
    description: p.description,
    price_monthly: Number(p.price_monthly),
    price_yearly: p.price_yearly == null ? null : Number(p.price_yearly),
    features: p.entitlements?.features ?? {},
    limits: p.entitlements?.limits ?? {},
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

function usageLines(limits: Limits, features: Record<string, boolean> | null): string[] {
  const minutes = limits.minutes_per_month
  const calls = limits.calls_per_month
  const lines: (string | null)[] = []
  if (minutes === UNLIMITED && calls === UNLIMITED) {
    lines.push('Unlimited calls and minutes')
  } else {
    const usage = joinList([count(minutes, 'minute'), count(calls, 'call')])
    lines.push(usage && `${usage} a month`)
  }
  const messages = joinList([
    (!features || features.sms) && count(limits.sms_per_month, 'text'),
    (!features || features.email) && count(limits.emails_per_month, 'email'),
  ])
  lines.push(messages && `${messages} a month`)
  return lines.filter(Boolean) as string[]
}

// Only features the product actually delivers. Outbound campaigns, virtual
// meetings, lead scoring, voice cloning and white labelling are plan flags with
// no feature behind them yet, so they are never advertised here even when the
// admin switches them on.
function featureLines(f: Record<string, boolean>): string[] {
  const calls =
    f.inbound_calls && f.outbound_calls
      ? 'Inbound and outbound calls'
      : f.inbound_calls
        ? 'Inbound calls'
        : f.outbound_calls
          ? 'Outbound calls'
          : null
  const recordings =
    f.call_recordings && f.analytics
      ? 'Call recordings and analytics'
      : f.call_recordings
        ? 'Call recordings and transcripts'
        : f.analytics
          ? 'Call analytics'
          : null
  return [
    calls,
    f.crm_integrations ? 'CRM integrations' : null,
    f.workflow_scheduling ? 'Scheduled workflows (hourly, daily, cron)' : null,
    f.webhooks ? 'Webhooks' : null,
    recordings,
  ].filter(Boolean) as string[]
}

const MARKETED = ['inbound_calls', 'outbound_calls', 'crm_integrations', 'workflow_scheduling', 'webhooks', 'call_recordings', 'analytics']

/** Bullet points for a paid plan, built from its live limits and features. */
export function planBullets(plan: PricingPlan, previous?: PricingPlan): string[] {
  const { limits: l, features: f } = plan
  // "Everything in X" only when this plan really includes all of X's features.
  const includesPrevious =
    !!previous && MARKETED.every((key) => !previous.features[key] || f[key])
  const shown = includesPrevious
    ? Object.fromEntries(MARKETED.map((key) => [key, f[key] && !previous!.features[key]]))
    : f

  return [
    includesPrevious ? `Everything in ${previous!.name}` : null,
    joinList([
      count(l.agents, 'AI agent'),
      count(l.phone_numbers, 'phone number'),
      f.workflows && count(l.workflows, 'workflow'),
    ]),
    joinList([f.knowledge_base && count(l.knowledge_bases, 'knowledge base'), count(l.team_members, 'team member')]),
    ...usageLines(l, f),
    ...featureLines(shown),
    l.api_keys === UNLIMITED ? 'Unlimited API keys' : l.api_keys > 0 ? `Up to ${l.api_keys.toLocaleString('en-US')} API keys` : null,
  ].filter(Boolean) as string[]
}

/** Bullet points for the card-free trial. */
export function trialBullets(trial: TrialOffer): string[] {
  const l = trial.limits
  const unlimitedUsage = l.minutes_per_month === UNLIMITED && l.calls_per_month === UNLIMITED
  return [
    `${trial.days} days, no credit card required`,
    joinList([count(l.agents, 'agent'), count(l.knowledge_bases, 'knowledge base'), count(l.workflows, 'workflow')]),
    l.team_members === UNLIMITED ? 'Unlimited team members' : l.team_members ? `Up to ${count(l.team_members, 'team member')}` : null,
    unlimitedUsage ? 'Unlimited test calls and minutes' : null,
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
