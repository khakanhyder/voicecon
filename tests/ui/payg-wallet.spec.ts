import { test, expect } from '../support/mocks'
import { ALL_PERMISSIONS } from '../support/data'
import { enterDashboard } from '../support/session'

/**
 * Pay As You Go on Settings → Billing.
 *
 * The plan has no monthly price, so it is a card of its own beside the
 * subscriptions, and what its button does depends on where the workspace is
 * coming from. Money is added through a top-up dialog; the balance, the
 * low-balance banner and the history all come from the wallet endpoints.
 *
 * Top-ups here go through the hosted (Polar) path, which needs no card
 * iframe: the amount the dialog sends and the page it lands on afterwards are
 * what the tests pin.
 */
type Page = import('@playwright/test').Page
type Api = import('../support/mocks').ApiMock

const base = {
  description: '', included_minutes: 100, included_calls: -1, max_agents: 1, max_phone_numbers: 1,
  max_knowledge_bases: 1, overage_rate_per_minute: 0.3, overage_rate_per_call: 0, features: {},
  trial_days: 14, is_trialable: false, is_active: true, is_public: true,
}

const STARTER = {
  ...base, id: 'p-starter', slug: 'starter', name: 'Starter', tier: 1, price_monthly: 49, price_yearly: 468,
  entitlements: { features: { inbound_calls: true }, limits: { agents: 1, minutes_per_month: 200 }, overage: { allowed: true, per_minute: 0.3 } },
}
const GROWTH = {
  ...base, id: 'p-growth', slug: 'growth', name: 'Growth', tier: 2, price_monthly: 149, price_yearly: 1428,
  entitlements: { features: { inbound_calls: true, outbound_calls: true }, limits: { agents: 3, minutes_per_month: 750 }, overage: { allowed: true, per_minute: 0.25 } },
}
const PAYG = {
  ...base, id: 'p-payg', slug: 'payg', name: 'Pay As You Go', tier: 0, price_monthly: 0, price_yearly: null,
  description: 'No monthly fee. Add credit and pay only for the minutes you use.',
  overage_rate_per_minute: 0.35,
  entitlements: {
    features: { inbound_calls: true, workflows: true },
    limits: { agents: 1, phone_numbers: 1, workflows: 3, minutes_per_month: -1, concurrent_calls: 2 },
    overage: { allowed: false },
    billing: { mode: 'prepaid', per_minute: 0.35, number_monthly_fee: 2, topup_presets: [10, 25, 50, 100], topup_min: 10, topup_max: 1000, low_balance: 5 },
  },
}
const PLANS = [STARTER, GROWTH, PAYG]

const wallet = (overrides: Record<string, unknown> = {}) => ({
  available: true, plan_id: 'p-payg', plan_name: 'Pay As You Go', on_plan: false, switching_at: null,
  balance: 0, held: 0, currency: 'usd', per_minute: 0.35, minutes_left: 0, number_monthly_fee: 2,
  low_balance: 5, is_low: false, is_empty: false,
  topup: { presets: [10, 25, 50, 100], minimum: 10, maximum: 1000 },
  provider: 'polar', checkout_mode: 'hosted', can_topup: true, publishable_key: null,
  auto_recharge: { supported: false, enabled: false, threshold: null, amount: null, card_brand: null, card_last4: null },
  ...overrides,
})

const subscription = (plan: { id: string; name: string }, extra: Record<string, unknown> = {}) => ({
  id: 'sub-1', plan_id: plan.id, plan_name: plan.name, status: 'active', billing_period: 'monthly',
  current_period_start: '2026-09-29T00:00:00Z', current_period_end: '2026-10-29T00:00:00Z',
  trial_end: null, scheduled_plan_id: null, scheduled_plan_name: null, canceled_at: null,
  current_period_minutes: 0, current_period_calls: 0, ...extra,
})

const HISTORY = {
  items: [
    { id: 't3', type: 'usage', amount: -1.05, balance_after: 23.95, description: 'Call from +14155550100, 3 min', created_at: '2026-10-02T10:05:00+00:00', receipt_url: null },
    { id: 't2', type: 'number_fee', amount: -2, balance_after: 25, description: 'Phone number +14155550123, 30 days', created_at: '2026-10-02T09:30:00+00:00', receipt_url: null },
    { id: 't1', type: 'topup', amount: 27, balance_after: 27, description: 'Credit added', created_at: '2026-10-02T09:00:00+00:00', receipt_url: 'https://pay.example/receipt/1' },
  ],
  total: 3, page: 1, page_size: 10, pages: 1,
}

async function openBilling(
  page: Page,
  api: Api,
  opts: {
    entitlements: Record<string, unknown>
    subscription: unknown
    wallet?: Record<string, unknown>
    usage?: Record<string, unknown>
    workspace?: Record<string, unknown>
    path?: string
  },
) {
  await api.on('**/api/v1/billing/plans', { body: PLANS })
  await api.on('**/api/v1/billing/invoices', { body: [] })
  await api.on('**/api/v1/billing/usage', {
    body: {
      minutes_used: 0, minutes_included: 30, minutes_overage: 0, calls_used: 0, calls_included: -1,
      calls_overage: 0, estimated_overage_cost: 0, overage_allowed: false, ...opts.usage,
    },
  })
  await api.on('**/api/v1/billing/subscription', { body: opts.subscription })
  await api.on('**/api/v1/billing/config', {
    body: { provider: 'polar', checkout_mode: 'hosted', configured: true, publishable_key: null },
  })
  await api.on('**/api/v1/billing/coupon**', { body: { valid: false } })
  await api.on('**/api/v1/billing/wallet/transactions**', { body: HISTORY })
  await api.on(/\/api\/v1\/billing\/wallet(\?.*)?$/, { body: wallet(opts.wallet) })

  await enterDashboard(page, api, opts.path ?? '/dashboard/settings/billing', {
    entitlements: opts.entitlements,
    workspace: opts.workspace,
  })
  await expect(page.getByRole('heading', { name: 'Available Plans' })).toBeVisible({ timeout: 30_000 })
}

const TRIAL = {
  status: 'trialing', is_trial: true, source: 'trial', plan_id: 'p-growth', plan_slug: 'growth',
  plan_name: 'Growth', plan_tier: 2, days_remaining: 10, is_live: true,
}
const ON_PAYG = {
  status: 'active', is_trial: false, source: 'wallet', plan_id: 'p-payg', plan_slug: 'payg',
  plan_name: 'Pay As You Go', plan_tier: 0, is_live: true, prepaid: true, wallet_balance: 23.95,
}
const ON_STARTER = {
  status: 'active', is_trial: false, source: 'polar', plan_id: 'p-starter', plan_slug: 'starter',
  plan_name: 'Starter', plan_tier: 1, is_live: true,
}

test('Pay As You Go is a card of its own, priced per minute, beside the subscriptions', async ({ page, api }) => {
  await openBilling(page, api, { entitlements: TRIAL, subscription: subscription(GROWTH, { status: 'trialing' }) })

  const card = page.getByTestId('payg-plan-card')
  await expect(card.getByRole('heading', { name: 'Pay As You Go' })).toBeVisible()
  await expect(card).toContainText('$0.35')
  await expect(card).toContainText('/ minute')
  await expect(card).toContainText('No monthly fee')
  await expect(card).toContainText('$0.35 per call minute, paid from your balance')
  await expect(card).toContainText('Phone number $2 a month')
  // It never shows up as a "$0/month" subscription card.
  await expect(page.locator('#available-plans')).not.toContainText('$0/month')
  await expect(page.locator('#available-plans h3').filter({ hasText: /^(Starter|Growth)$/ })).toHaveCount(2)

  // No balance card for a trial that has never held credit.
  await expect(page.getByRole('heading', { name: 'Balance', exact: true })).toHaveCount(0)
})

test('a trial starts Pay As You Go with a first top-up, sent as the amount chosen', async ({ page, api }) => {
  await api.on('**/api/v1/billing/wallet/topup-session', {
    body: { url: '/billing/return?checkout_id=chk_1&kind=topup&next=%2Fdashboard%2Fsettings%2Fbilling', checkout_id: 'chk_1' },
  }, { method: 'POST' })
  await api.on('**/api/v1/billing/wallet/topup-session/chk_1', { body: { status: 'active' } })
  await openBilling(page, api, { entitlements: TRIAL, subscription: subscription(GROWTH, { status: 'trialing' }) })

  await page.getByTestId('payg-plan-card').getByRole('button', { name: 'Get Started' }).click()
  const dialog = page.getByRole('dialog', { name: 'Start Pay As You Go' })
  await expect(dialog).toBeVisible()
  await expect(dialog).toContainText('No monthly fee. Calls cost $0.35 a minute')

  // The second preset is chosen by default; picking another updates what it buys.
  await expect(dialog.getByRole('button', { name: '$25', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(dialog).toContainText('About 71 minutes of calls')
  await dialog.getByRole('button', { name: '$50', exact: true }).click()
  await expect(dialog).toContainText('About 142 minutes of calls')

  await dialog.getByRole('button', { name: /Continue to payment · \$50\.00/ }).click()

  // The hosted checkout "returns", the page waits for the credit to land, and
  // only then goes back to billing.
  await expect(page.getByRole('heading', { name: "You're all set" })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('Your credit has been added.')).toBeVisible()
  await expect(page).toHaveURL(/\/dashboard\/settings\/billing/, { timeout: 30_000 })

  const sent = api.callsOf('POST', '/billing/wallet/topup-session')
  expect(sent).toHaveLength(1)
  expect(sent[0].body).toMatchObject({ amount: 50, activate: true, return_path: '/dashboard/settings/billing' })
  expect(api.callsTo('/billing/wallet/topup-session/chk_1').length).toBeGreaterThan(0)
  // Never the subscription checkout: there is nothing to subscribe to.
  expect(api.callsOf('POST', '/billing/checkout')).toHaveLength(0)
})

test('a custom amount outside the bounds is refused before anything is sent', async ({ page, api }) => {
  await openBilling(page, api, { entitlements: TRIAL, subscription: subscription(GROWTH, { status: 'trialing' }) })
  await page.getByTestId('payg-plan-card').getByRole('button', { name: 'Get Started' }).click()
  const dialog = page.getByRole('dialog', { name: 'Start Pay As You Go' })

  await dialog.getByRole('button', { name: 'Other' }).click()
  await dialog.getByLabel('Amount to add').fill('5')
  await expect(dialog).toContainText('The smallest top-up is $10.00.')
  await dialog.getByRole('button', { name: /Continue to payment/ }).click()
  await expect(dialog.getByRole('alert')).toContainText('The smallest top-up is $10.00.')

  await dialog.getByLabel('Amount to add').fill('5000')
  await dialog.getByRole('button', { name: /Continue to payment/ }).click()
  await expect(dialog.getByRole('alert')).toContainText('The largest single top-up is $1,000.00.')
  expect(api.callsOf('POST', '/billing/wallet/topup-session')).toHaveLength(0)
})

test('on Pay As You Go: the balance, what it buys, the history, and every subscription as an upgrade', async ({ page, api }) => {
  await openBilling(page, api, {
    entitlements: ON_PAYG,
    subscription: subscription(PAYG),
    wallet: { on_plan: true, balance: 23.95, minutes_left: 68 },
    usage: { minutes_used: 3, minutes_included: -1, prepaid: true, rate_per_minute: 0.35, period_spend: 1.05 },
  })

  const balance = page.locator('#wallet')
  await expect(balance.getByRole('heading', { name: 'Balance', exact: true })).toBeVisible()
  await expect(balance.getByTestId('wallet-balance')).toHaveText('$23.95')
  await expect(balance).toContainText('About 68 minutes of calls')
  await expect(balance).toContainText('Each phone number costs $2.00 a month from this balance')

  // Every movement, newest first, with a receipt link on the top-up.
  const rows = balance.locator('tbody tr')
  await expect(rows).toHaveCount(3)
  await expect(rows.nth(0)).toContainText('Call from +14155550100, 3 min')
  await expect(rows.nth(0)).toContainText('-$1.05')
  await expect(rows.nth(1)).toContainText('-$2.00')
  await expect(rows.nth(2)).toContainText('+$27.00')
  await expect(rows.nth(2).getByRole('link', { name: 'Receipt' })).toHaveAttribute('href', 'https://pay.example/receipt/1')

  // The current-plan block talks about a rate and a balance, not a renewal.
  await expect(page.getByText('$0.35 a minute, no monthly fee')).toBeVisible()
  await expect(page.getByText('Nothing renews: you only pay for what you use')).toBeVisible()
  await expect(page.getByText('Every call minute costs $0.35 from your balance')).toBeVisible()
  await expect(page.getByText('$1.05 spent on calls this period')).toBeVisible()
  // Nothing recurring to cancel.
  await expect(page.getByRole('button', { name: 'Cancel Subscription' })).toHaveCount(0)

  const card = page.getByTestId('payg-plan-card')
  await expect(card.getByRole('button', { name: 'Current Plan' })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Upgrade to Starter' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Upgrade to Growth' })).toBeVisible()

  // Add credit from the plan card opens the plain top-up, not a plan start.
  await card.getByRole('button', { name: 'Add credit' }).click()
  await expect(page.getByRole('dialog', { name: 'Add credit' })).toBeVisible()
})

test('an empty balance says calls have stopped, on the page and in the banner', async ({ page, api }) => {
  await openBilling(page, api, {
    entitlements: { ...ON_PAYG, wallet_balance: 0, wallet_empty: true },
    subscription: subscription(PAYG),
    wallet: { on_plan: true, balance: 0, minutes_left: 0, is_empty: true },
    usage: { minutes_included: -1, prepaid: true, rate_per_minute: 0.35 },
  })

  // The dashboard banner: cannot be dismissed, and asks for credit, not a plan.
  const banner = page.getByText('Your balance has run out').first()
  await expect(banner).toBeVisible()
  await expect(page.getByRole('button', { name: 'Dismiss' })).toHaveCount(0)

  const balance = page.locator('#wallet')
  await expect(balance.getByTestId('wallet-balance')).toHaveText('$0.00')
  await expect(balance.getByRole('status')).toContainText('Your agents have stopped making and answering calls')
  await expect(balance).toContainText('Not enough for a call')
})

test('a low balance is a warning that can be dismissed', async ({ page, api }) => {
  await openBilling(page, api, {
    entitlements: { ...ON_PAYG, wallet_balance: 3.2, wallet_low: true },
    subscription: subscription(PAYG),
    wallet: { on_plan: true, balance: 3.2, minutes_left: 9, is_low: true },
    usage: { minutes_included: -1, prepaid: true, rate_per_minute: 0.35 },
  })
  await expect(page.getByText('You have $3.20 of credit left.')).toBeVisible()
  await page.getByRole('button', { name: 'Dismiss' }).click()
  await expect(page.getByText('You have $3.20 of credit left.')).toHaveCount(0)
  // Still said on the balance card itself.
  await expect(page.locator('#wallet').getByRole('status')).toContainText('Your balance is running low')
})

test('a paid subscription switches at the end of its period, after a confirmation', async ({ page, api }) => {
  await api.on('**/api/v1/billing/subscription/change-plan', {
    body: subscription(STARTER, { scheduled_plan_id: 'p-payg', scheduled_plan_name: 'Pay As You Go', canceled_at: '2026-10-02T00:00:00Z' }),
  }, { method: 'POST' })
  await openBilling(page, api, { entitlements: ON_STARTER, subscription: subscription(STARTER) })

  const card = page.getByTestId('payg-plan-card')
  await expect(card).toContainText('Takes effect when your paid period ends')
  await card.getByRole('button', { name: 'Switch to Pay As You Go' }).click()

  // Nothing is sent until the customer has read what happens and agreed.
  expect(api.callsOf('POST', '/billing/subscription/change-plan')).toHaveLength(0)
  const confirm = page.getByRole('dialog')
  await expect(confirm).toContainText('will not renew')
  await expect(confirm).toContainText('$0.35 a minute')
  await confirm.getByRole('button', { name: 'Switch to Pay As You Go' }).click()

  await expect.poll(() => api.callsOf('POST', '/billing/subscription/change-plan').length).toBe(1)
  expect(api.callsOf('POST', '/billing/subscription/change-plan')[0].body).toEqual({ plan_id: 'p-payg' })
  // A switch is not a purchase: no top-up and no checkout were started.
  expect(api.callsOf('POST', '/billing/wallet/')).toHaveLength(0)
})

test('a queued move says when it starts and lets the customer stay', async ({ page, api }) => {
  await api.on('**/api/v1/billing/subscription/reactivate', { body: subscription(STARTER) }, { method: 'POST' })
  await openBilling(page, api, {
    entitlements: {
      ...ON_STARTER, cancel_at_period_end: true, current_period_end: '2026-10-29T00:00:00Z',
      switching_to_prepaid: true, wallet_balance: 0,
    },
    subscription: subscription(STARTER, { scheduled_plan_id: 'p-payg', scheduled_plan_name: 'Pay As You Go', canceled_at: '2026-10-02T00:00:00Z' }),
    wallet: { switching_at: '2026-10-29T00:00:00+00:00' },
  })

  // Announced as a move, never as "your subscription has been cancelled".
  await expect(page.getByText(/You move to Pay As You Go on/).first()).toBeVisible()
  await expect(page.getByText(/^Cancels /)).toHaveCount(0)

  // The balance card appears ahead of the switch so credit can be added.
  await expect(page.locator('#wallet')).toContainText('You move to Pay As You Go on')

  const card = page.getByTestId('payg-plan-card')
  await expect(card).toContainText('Starts on')
  await expect(card.getByRole('button', { name: 'Switch to Pay As You Go' })).toHaveCount(0)
  await card.getByRole('button', { name: 'Stay on Starter' }).click()
  await expect.poll(() => api.callsOf('POST', '/billing/subscription/reactivate').length).toBe(1)
})

test('an admin can see the balance but is offered nothing that spends money', async ({ page, api }) => {
  await openBilling(page, api, {
    entitlements: ON_PAYG,
    subscription: subscription(PAYG),
    wallet: { on_plan: true, balance: 23.95, minutes_left: 68 },
    usage: { minutes_included: -1, prepaid: true, rate_per_minute: 0.35 },
    workspace: {
      role: 'admin', is_owner: false, owner_email: 'owner@example.com',
      permissions: ALL_PERMISSIONS.filter((p) => !['billing:manage', 'team:manage_admins', 'workspace:delete'].includes(p)),
    },
  })
  await expect(page.locator('#wallet').getByTestId('wallet-balance')).toHaveText('$23.95')
  await expect(page.getByRole('button', { name: 'Add credit' })).toHaveCount(0)
  await expect(page.getByRole('note').first()).toContainText('Only the workspace owner can change the plan')
  expect(api.callsOf('POST', '/billing/')).toHaveLength(0)
})

test('when Pay As You Go is not on sale, no card and no balance are shown', async ({ page, api }) => {
  await api.on('**/api/v1/billing/plans', { body: [STARTER, GROWTH] })
  await api.on('**/api/v1/billing/invoices', { body: [] })
  await api.on('**/api/v1/billing/usage', { body: { minutes_used: 0, minutes_included: 200, minutes_overage: 0, calls_used: 0, calls_included: -1, calls_overage: 0, estimated_overage_cost: 0 } })
  await api.on('**/api/v1/billing/subscription', { body: subscription(STARTER) })
  await api.on(/\/api\/v1\/billing\/wallet(\?.*)?$/, { body: wallet({ available: false, plan_id: null, plan_name: null, can_topup: false }) })
  await enterDashboard(page, api, '/dashboard/settings/billing', { entitlements: ON_STARTER })
  await expect(page.getByRole('heading', { name: 'Available Plans' })).toBeVisible({ timeout: 30_000 })

  await expect(page.getByTestId('payg-plan-card')).toHaveCount(0)
  await expect(page.locator('#wallet')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Current Plan' })).toBeVisible()
})
