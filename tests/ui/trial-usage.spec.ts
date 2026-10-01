import { test, expect } from '../support/mocks'
import { enterDashboard } from '../support/session'

/**
 * Usage lives on the Billing page, not in the sidebar.
 *
 * A trial used to carry a "Trial usage" card pinned to the bottom of the
 * sidebar. On a short window it sat on top of the navigation, and it was the
 * only place the email allowance was shown at all. Both counters now sit with
 * the rest of the plan details under Settings → Billing.
 */
const TRIAL = {
  status: 'trialing',
  is_trial: true,
  plan_name: 'Starter',
  limits: { agents: 1, minutes_per_month: 30, emails_per_month: 100 },
  usage: { agents: 0, minutes_per_month: 12, emails_per_month: 40 },
}

test('trial usage is shown on the billing page and not in the sidebar', async ({ page, api }) => {
  await api.on('**/api/v1/billing/plans', { body: [] })
  await api.on('**/api/v1/billing/invoices', { body: [] })
  await api.on('**/api/v1/billing/usage', {
    body: {
      minutes_used: 12, minutes_included: 30, minutes_overage: 0,
      calls_used: 4, calls_included: -1, calls_overage: 0,
      estimated_overage_cost: 0, overage_allowed: false,
    },
  })

  await enterDashboard(page, api, '/dashboard/settings/billing', { entitlements: TRIAL })

  await expect(page.getByRole('heading', { name: 'Trial Usage' })).toBeVisible()
  await expect(page.getByText('Call Minutes')).toBeVisible()
  await expect(page.getByText('Emails', { exact: true })).toBeVisible()
  await expect(page.getByText('emails used this period')).toBeVisible()

  // The sidebar is navigation only.
  await expect(page.locator('aside').getByText(/trial usage/i)).toHaveCount(0)
})
