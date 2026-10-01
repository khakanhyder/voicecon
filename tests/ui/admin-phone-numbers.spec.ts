import { test, expect } from '../support/mocks'
import { loginResponse, TEST_PASSWORD } from '../support/data'

/**
 * The console's Phone Numbers page is where an operator sees what the platform
 * phone account is costing with nobody paying for it: numbers on hold for a
 * workspace without a plan, when each will be released, and how close number
 * buying is to the daily limit.
 */

const ADMIN_USER = {
  id: '00000000-0000-4000-8000-0000000000ad',
  email: 'staff@voicecon.test',
  full_name: 'Staff Member',
}

const NAV = { timeout: 30_000 }

const HELD = {
  id: 'num-held',
  phone_number: '+14155550101',
  organization_id: 'org-1',
  organization_name: 'Lapsed Co',
  organization_active: true,
  agent_name: 'Aria',
  provider: 'twilio',
  provider_sid: 'PN1',
  bring_your_own: false,
  voicecon: true,
  status: 'suspended',
  monthly_cost: 1.15,
  created_at: '2026-09-01T10:00:00+00:00',
  suspended_at: '2026-10-01T12:00:00+00:00',
  release_after: '2026-10-15T12:00:00+00:00',
  release_error: null,
}

const OWN = {
  ...HELD,
  id: 'num-own',
  phone_number: '+13125550102',
  organization_name: 'Own Carrier Co',
  bring_your_own: true,
  voicecon: false,
  status: 'active',
  suspended_at: null,
  release_after: null,
}

function listing(items: unknown[], summary: Record<string, number> = {}) {
  return {
    body: {
      items,
      total: items.length,
      page: 1,
      page_size: 25,
      pages: 1,
      summary: { on_hold: 1, release_grace_days: 14, purchases_24h: 3, daily_purchase_cap: 25, ...summary },
    },
  }
}

async function openPhoneNumbers(page: import('@playwright/test').Page) {
  await page.goto('/admin/login')
  await page.getByRole('textbox', { name: 'Email' }).fill(ADMIN_USER.email)
  await page.getByRole('textbox', { name: 'Password' }).fill(TEST_PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/admin$/, NAV)
  await page.goto('/admin/phone-numbers')
  await expect(page.getByRole('heading', { name: 'Phone Numbers' })).toBeVisible(NAV)
}

test.describe('Admin console: phone numbers', () => {
  test.beforeEach(async ({ api }) => {
    await api.on('**/api/v1/auth/admin/login', { body: loginResponse({ user: ADMIN_USER }) })
    await api.on('**/api/v1/admin/me', { body: ADMIN_USER })
  })

  test('shows what is on hold, when it is released and how close buying is to the limit', async ({ page, api }) => {
    await api.on(/\/api\/v1\/admin\/phone-numbers(\?.*)?$/, listing([HELD, OWN]))
    await openPhoneNumbers(page)

    await expect(page.getByText(/1 number is on hold/)).toBeVisible()
    await expect(page.getByText(/released automatically 14 days after/)).toBeVisible()
    await expect(page.getByText(/3 of 25 Voicecon number purchases used/)).toBeVisible()

    const held = page.getByRole('row').filter({ hasText: '+14155550101' })
    await expect(held.getByText('On hold')).toBeVisible()
    await expect(held.getByText(/Releases Oct 15, 2026/)).toBeVisible()
    await expect(held.getByRole('button', { name: 'Keep' })).toBeVisible()
    await expect(held.getByRole('button', { name: 'Release' })).toBeVisible()

    // A number on the customer's own carrier account is theirs: no actions.
    const own = page.getByRole('row').filter({ hasText: '+13125550102' })
    await expect(own.getByRole('button')).toHaveCount(0)

    if (process.env.SCREENSHOT_DIR) {
      await page.screenshot({ path: `${process.env.SCREENSHOT_DIR}/admin-phone-numbers.png`, fullPage: true })
    }
  })

  test('says so when the daily purchase limit is reached', async ({ page, api }) => {
    await api.on(
      /\/api\/v1\/admin\/phone-numbers(\?.*)?$/,
      listing([], { on_hold: 0, purchases_24h: 25 }),
    )
    await openPhoneNumbers(page)

    await expect(page.getByText(/customers cannot buy a Voicecon number right now/)).toBeVisible()
    await expect(page.getByText(/on hold for/)).toHaveCount(0)
  })

  test('releasing a number asks first, then releases it', async ({ page, api }) => {
    await api.on(/\/api\/v1\/admin\/phone-numbers(\?.*)?$/, listing([HELD]))
    await api.on(
      '**/api/v1/admin/phone-numbers/num-held/release',
      { body: { released: true, phone_number: HELD.phone_number } },
      { method: 'POST' },
    )
    await openPhoneNumbers(page)

    await page.getByRole('row').filter({ hasText: '+14155550101' }).getByRole('button', { name: 'Release' }).click()
    await expect(page.getByRole('heading', { name: 'Release this number?' })).toBeVisible()
    await expect(page.getByText(/cannot get this number back/)).toBeVisible()
    // Nothing has been released yet.
    expect(api.callsOf('POST', '/phone-numbers/num-held/release')).toHaveLength(0)

    await page.getByRole('button', { name: 'Release number' }).click()
    await expect.poll(() => api.callsOf('POST', '/phone-numbers/num-held/release').length).toBe(1)
    await expect(page.getByText('+14155550101 was released.')).toBeVisible()
  })

  test('keeping a number pushes its release date back', async ({ page, api }) => {
    await api.on(/\/api\/v1\/admin\/phone-numbers(\?.*)?$/, listing([HELD]))
    await api.on(
      '**/api/v1/admin/phone-numbers/num-held/hold',
      { body: { phone_number: HELD.phone_number, release_after: '2026-10-29T12:00:00+00:00' } },
      { method: 'POST' },
    )
    await openPhoneNumbers(page)

    await page.getByRole('row').filter({ hasText: '+14155550101' }).getByRole('button', { name: 'Keep' }).click()
    await expect.poll(() => api.callsOf('POST', '/phone-numbers/num-held/hold').length).toBe(1)
    expect(api.callsOf('POST', '/phone-numbers/num-held/hold')[0].body).toEqual({ days: 14 })
    await expect(page.getByText(/will be kept until Oct 29, 2026/)).toBeVisible()
  })
})
