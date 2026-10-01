import { test, expect } from '../support/mocks'
import { ALL_PERMISSIONS } from '../support/data'
import { enterDashboard } from '../support/session'

/**
 * Buying a plan from Settings → Billing.
 *
 * Two things went wrong here for a workspace admin on a free trial:
 *
 * - The checkout dialog was drawn inside the page instead of over it, so on
 *   the dashboard its backdrop stopped short of the top of the screen.
 * - Only the workspace owner may change the plan. An admin was still shown
 *   every "Upgrade" button, could type a card, and only then got a role error.
 */
const TRIAL = {
  status: 'trialing',
  is_trial: true,
  source: 'trial',
  plan_slug: 'growth',
  plan_name: 'Growth',
  days_remaining: 16,
}

const PLANS = [
  { id: 'plan-starter', slug: 'starter', tier: 1, name: 'Starter', price_monthly: 79, price_yearly: 790 },
  { id: 'plan-growth', slug: 'growth', tier: 2, name: 'Growth', price_monthly: 179, price_yearly: 1790 },
].map((plan) => ({
  description: `${plan.name} plan`,
  included_minutes: 1000,
  included_calls: 0,
  max_agents: 5,
  max_phone_numbers: 2,
  max_knowledge_bases: 5,
  overage_rate_per_minute: 0.1,
  overage_rate_per_call: 0,
  features: {},
  entitlements: { features: {}, limits: {} },
  trial_days: 30,
  is_trialable: true,
  is_active: true,
  is_public: true,
  ...plan,
}))

async function openBilling(
  page: import('@playwright/test').Page,
  api: import('../support/mocks').ApiMock,
  workspace: Record<string, unknown> = {},
) {
  await api.on('**/api/v1/billing/plans', { body: PLANS })
  await api.on('**/api/v1/billing/invoices', { body: [] })
  await api.on('**/api/v1/billing/usage', {
    body: {
      minutes_used: 0, minutes_included: 30, minutes_overage: 0,
      calls_used: 0, calls_included: -1, calls_overage: 0,
      estimated_overage_cost: 0, overage_allowed: false,
    },
  })
  await api.on('**/api/v1/billing/subscription', {
    body: {
      id: 'sub-1', plan_id: 'plan-growth', plan_name: 'Growth', status: 'trialing',
      billing_period: 'monthly', current_period_start: '2026-09-17T00:00:00Z',
      current_period_end: '2026-10-17T00:00:00Z', trial_end: '2026-10-17T00:00:00Z',
      canceled_at: null, current_period_minutes: 0, current_period_calls: 0,
    },
  })
  await api.on('**/api/v1/billing/config', {
    body: { provider: 'stripe', checkout_mode: 'card', configured: true, publishable_key: 'pk_test_ui' },
  })
  await api.on('**/api/v1/billing/coupon**', { body: { valid: false } })

  await enterDashboard(page, api, '/dashboard/settings/billing', { entitlements: TRIAL, workspace })
  await expect(page.getByRole('heading', { name: 'Available Plans' })).toBeVisible({ timeout: 30_000 })
}

for (const viewport of [
  { name: 'a laptop', width: 1366, height: 768 },
  { name: 'a short window', width: 1280, height: 420 },
  { name: 'a phone', width: 375, height: 667 },
]) {
  test(`the checkout dialog covers the whole screen and stays inside it on ${viewport.name}`, async ({ page, api }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    await openBilling(page, api)

    await page.getByRole('button', { name: 'Subscribe to Growth' }).click()
    const dialog = page.getByRole('dialog', { name: 'Subscribe to Growth' })
    await expect(dialog).toBeVisible()

    // Drawn over the page, not inside it: its backdrop starts at the very top
    // left of the screen and spans all of it.
    const backdrop = await dialog.evaluate((el) => {
      const overlay = el.parentElement!.parentElement!
      const box = overlay.getBoundingClientRect()
      return { x: box.x, y: box.y, width: box.width, height: box.height, inBody: overlay.parentElement === document.body }
    })
    expect(backdrop).toEqual({ x: 0, y: 0, width: viewport.width, height: viewport.height, inBody: true })

    // The top of the dialog is reachable: on screen now, or by scrolling the
    // backdrop when the dialog is taller than the window.
    await dialog.getByRole('heading', { name: 'Subscribe to Growth' }).scrollIntoViewIfNeeded()
    const box = (await dialog.boundingBox())!
    expect(box.y).toBeGreaterThanOrEqual(0)
    expect(box.x).toBeGreaterThanOrEqual(0)
    expect(box.x + box.width).toBeLessThanOrEqual(viewport.width)

    await dialog.getByRole('button', { name: 'Cancel' }).scrollIntoViewIfNeeded()
    await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeInViewport()
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).toHaveCount(0)
  })
}

test('an admin is told the owner changes the plan, and is offered no checkout', async ({ page, api }) => {
  await openBilling(page, api, {
    role: 'admin',
    is_owner: false,
    name: 'Diamant Versatile',
    owner_email: 'owner@example.com',
    permissions: ALL_PERMISSIONS.filter(
      (p) => !['billing:manage', 'team:manage_admins', 'workspace:delete'].includes(p),
    ),
  })

  const notice = page.getByRole('note').first()
  await expect(notice).toContainText('Only the workspace owner can change the plan')
  await expect(notice.getByRole('link', { name: 'owner@example.com' })).toBeVisible()

  // Plans stay visible, but nothing invites a purchase that would be refused.
  await expect(page.getByRole('heading', { name: 'Growth', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: /Subscribe to|Upgrade to|Get Started/ })).toHaveCount(0)
  const ownerOnly = page.getByRole('button', { name: 'Owner only' })
  await expect(ownerOnly).toHaveCount(2)
  await expect(ownerOnly.first()).toBeDisabled()
  await expect(page.getByRole('button', { name: 'End trial' })).toHaveCount(0)

  expect(api.callsOf('POST', '/billing/')).toHaveLength(0)
})

test('the owner on a trial sees the buttons that start a purchase', async ({ page, api }) => {
  await openBilling(page, api)

  await expect(page.getByRole('note')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Subscribe to Growth' })).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Upgrade to Starter' })).toBeEnabled()
  await expect(page.getByRole('button', { name: 'End trial' })).toBeVisible()
})
