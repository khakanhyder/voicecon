import { test, expect } from '../support/mocks'
import { enterDashboard } from '../support/session'

/**
 * Plan cards follow the plan the workspace is on.
 *
 * A workspace paying for Agency used to see "Get Started" on Starter, Growth and
 * Scale. Now: its own plan says Current Plan, anything above says Upgrade, and
 * anything below is disabled — never an offer to buy it.
 */
const PLANS = [
  { id: 'p-starter', slug: 'starter', name: 'Starter', tier: 1, price_monthly: 59 },
  { id: 'p-growth', slug: 'growth', name: 'Growth', tier: 2, price_monthly: 179 },
  { id: 'p-scale', slug: 'scale', name: 'Scale', tier: 3, price_monthly: 349 },
  { id: 'p-agency', slug: 'agency', name: 'Agency', tier: 4, price_monthly: 499 },
].map((p) => ({
  ...p, description: `${p.name} plan`, price_yearly: p.price_monthly * 10,
  included_minutes: 100, included_calls: -1, max_agents: 1, max_phone_numbers: 1,
  max_knowledge_bases: 1, overage_rate_per_minute: 0.3, overage_rate_per_call: 0,
  features: {}, entitlements: { features: {}, limits: {} },
  trial_days: 7, is_trialable: true, is_active: true, is_public: true,
}))

const subscription = (planId: string, extra: Record<string, unknown> = {}) => ({
  id: 'sub-1', plan_id: planId, plan_name: 'x', status: 'active', billing_period: 'monthly',
  current_period_start: '2026-09-29T00:00:00Z', current_period_end: '2026-10-29T00:00:00Z',
  trial_end: null, scheduled_plan_id: null, scheduled_plan_name: null, canceled_at: null,
  current_period_minutes: 0, current_period_calls: 0, ...extra,
})

/** What each of the four cards offers, in order, as the buttons read. */
async function buttons(page: any, api: any, current: string | null, entitlements: Record<string, unknown> = {}) {
  const plan = PLANS.find((p) => p.slug === current)
  await api.on('**/api/v1/billing/plans', { body: PLANS })
  await api.on('**/api/v1/billing/invoices', { body: [] })
  await api.on('**/api/v1/billing/usage', {
    body: { minutes_used: 0, minutes_included: 100, minutes_overage: 0, calls_used: 0, calls_included: -1, calls_overage: 0, estimated_overage_cost: 0 },
  })
  await api.on('**/api/v1/billing/subscription', { body: plan ? subscription(plan.id) : null })
  await enterDashboard(page, api, '/dashboard/settings/billing', {
    entitlements: {
      plan_id: plan?.id ?? null, plan_slug: current, plan_name: plan?.name ?? null,
      plan_tier: plan?.tier ?? 0, source: 'stripe', is_live: !!plan, ...entitlements,
    },
  })
  await expect(page.getByRole('heading', { name: 'Available Plans' })).toBeVisible({ timeout: 30_000 })
  const cards = page.locator('#available-plans h3').filter({ hasText: /^(Starter|Growth|Scale|Agency)$/ })
  await expect(cards).toHaveCount(4)
  const out: string[] = []
  for (const name of ['Starter', 'Growth', 'Scale', 'Agency']) {
    const card = page.locator('#available-plans div.flex-col', { has: page.getByRole('heading', { name, exact: true }) }).last()
    out.push((await card.getByRole('button').last().innerText()).trim())
  }
  return out
}

const CASES: [string, string[]][] = [
  ['starter', ['Current Plan', 'Upgrade to Growth', 'Upgrade to Scale', 'Upgrade to Agency']],
  ['growth', ['Included in your plan', 'Current Plan', 'Upgrade to Scale', 'Upgrade to Agency']],
  ['scale', ['Included in your plan', 'Included in your plan', 'Current Plan', 'Upgrade to Agency']],
  ['agency', ['Included in your plan', 'Included in your plan', 'Included in your plan', 'Current Plan']],
]

for (const [current, expected] of CASES) {
  test(`on ${current}: ${expected.join(' / ')}`, async ({ page, api }) => {
    expect(await buttons(page, api, current)).toEqual(expected)
  })
}

test('a subscription billed outside Stripe/Polar (staff-granted) is treated the same', async ({ page, api }) => {
  // This is what showed "Get Started" on every card for an Agency workspace.
  expect(await buttons(page, api, 'agency', { source: 'comp' })).toEqual(CASES[3][1])
})

test('a workspace with no live plan is still offered Get Started', async ({ page, api }) => {
  expect(await buttons(page, api, null, { status: 'expired' })).toEqual(Array(4).fill('Get Started'))
})
