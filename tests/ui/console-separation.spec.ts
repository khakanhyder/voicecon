import { test, expect } from '../support/mocks'
import { loginResponse, TEST_PASSWORD, TEST_USER } from '../support/data'
import { signIn } from '../support/session'

/**
 * Two front doors, in a real browser.
 *
 * Signing in at `/admin/login` must not leave you signed into the product, and
 * signing in at `/login` must not leave you inside the admin console — which
 * is exactly what one shared set of localStorage keys used to do.
 */

const ADMIN_USER = {
  id: '00000000-0000-4000-8000-0000000000ad',
  email: 'staff@voicecon.test',
  full_name: 'Staff Member',
}

const NAV = { timeout: 30_000 }

async function signInToConsole(page: import('@playwright/test').Page) {
  await page.goto('/admin/login')
  await page.getByRole('textbox', { name: 'Email' }).fill(ADMIN_USER.email)
  // By role, not label: the field shares its label with the show/hide button.
  await page.getByRole('textbox', { name: 'Password' }).fill(TEST_PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
}

test.describe('Signing into the admin console', () => {
  test.beforeEach(async ({ api }) => {
    await api.on('**/api/v1/auth/admin/login', {
      body: loginResponse({ user: ADMIN_USER }),
    })
    await api.on('**/api/v1/admin/me', { body: ADMIN_USER })
  })

  test('opens the console', async ({ page }) => {
    await signInToConsole(page)

    await expect(page).toHaveURL(/\/admin$/, NAV)
  })

  test('does not sign you into the product', async ({ page }) => {
    await signInToConsole(page)
    await expect(page).toHaveURL(/\/admin$/, NAV)

    await page.goto('/dashboard')

    await expect(page).toHaveURL(/\/login/, NAV)
  })

  test('goes to its own sign-in endpoint, not the app one', async ({ page, api }) => {
    await signInToConsole(page)
    await expect(page).toHaveURL(/\/admin$/, NAV)

    expect(api.callsTo('/auth/admin/login')).toHaveLength(1)
    expect(api.callsTo('/auth/login')).toHaveLength(0)
  })

  test('leaves the app session alone when it signs out', async ({ page, api }) => {
    await api.on('**/api/v1/users/me', { body: TEST_USER })
    await api.on('**/api/v1/onboarding/status', {
      body: {
        onboarding_completed: true,
        step: 'done',
        has_company_profile: true,
        has_subscription: true,
        company: null,
      },
    })
    // The console's landing page reads this; the catch-all's `{}` is not the
    // shape it expects.
    await api.on('**/api/v1/admin/overview', {
      body: {
        kpis: {},
        subscriptions: {},
        providers: [],
        calls_daily: [],
        signups_daily: [],
        recent_organizations: [],
      },
    })

    // A customer session already in this browser…
    await signIn(page)
    // …then a console session on top of it.
    await signInToConsole(page)
    await expect(page).toHaveURL(/\/admin$/, NAV)

    await page.getByRole('button', { name: 'Sign out' }).first().click()
    await expect(page).toHaveURL(/\/admin\/login/, NAV)

    // The customer session is a separate sign-in and is untouched.
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/dashboard/, NAV)
  })
})

test.describe('Signing into the product', () => {
  test('does not let you into the admin console', async ({ page, api }) => {
    await api.on('**/api/v1/users/me', { body: TEST_USER })

    await signIn(page)
    await page.goto('/admin')

    await expect(page).toHaveURL(/\/admin\/login/, NAV)
  })

  test('does not count as being signed in on the admin sign-in page', async ({
    page,
    api,
  }) => {
    await api.on('**/api/v1/users/me', { body: TEST_USER })

    await signIn(page)
    await page.goto('/admin/login')

    // The form, not a pass straight through to the console.
    await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible()
  })
})

test.describe('The admin sign-in form', () => {
  test('tells a refused account nothing about which half was wrong', async ({
    page,
    api,
  }) => {
    await api.on('**/api/v1/auth/admin/login', {
      status: 401,
      body: { detail: 'Could not validate credentials' },
    })

    await signInToConsole(page)

    // .first(): Next's route announcer is also role="alert".
    await expect(page.getByRole('alert').first()).toContainText(
      /incorrect email or password, or this account does not have admin access/i,
    )
    await expect(page).toHaveURL(/\/admin\/login/, NAV)
  })
})
