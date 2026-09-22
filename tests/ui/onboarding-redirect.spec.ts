import { test, expect } from '../support/mocks'
import { loginResponse, TEST_PASSWORD, TEST_USER } from '../support/data'
import { signIn } from '../support/session'

/**
 * Where a session lands, in a real browser.
 *
 * One rule, shared by password login and the Google/Apple buttons: the
 * server's onboarding status decides. Unfinished onboarding continues;
 * finished onboarding goes to the dashboard and is never pulled back in.
 *
 * (The social buttons themselves cannot be driven here — they open Google's
 * and Apple's own popups — so the provider-specific coverage lives in
 * frontend/src/hooks/useSocialAuth.test.tsx, which mocks at the SDK boundary.
 * What this file proves is the shared routing those buttons feed into.)
 */

const STATUS = '**/api/v1/onboarding/status'

/**
 * These assertions wait on a client-side redirect, which cannot happen before
 * the page hydrates. Against `next dev` with several workers compiling at
 * once, first hydration routinely runs past the 15s default and the run turns
 * flaky — so navigation gets a longer leash than the rest of the suite.
 */
const NAV = { timeout: 30_000 }

function status(completed: boolean, step = completed ? 'done' : 'company') {
  return {
    body: {
      onboarding_completed: completed,
      step,
      has_company_profile: step !== 'company',
      has_subscription: completed,
      company: null,
    },
  }
}

async function logIn(page: import('@playwright/test').Page) {
  await page.getByLabel('Email address').fill(TEST_USER.email)
  await page.getByLabel('Password:', { exact: true }).fill(TEST_PASSWORD)
  await page.getByRole('button', { name: 'Login Now' }).click()
}

test.describe('Post-login routing', () => {
  test.beforeEach(async ({ api }) => {
    await api.on('**/api/v1/auth/login', { body: loginResponse() })
    await api.on('**/api/v1/users/me', { body: TEST_USER })
  })

  test('an account that finished onboarding goes to the dashboard', async ({
    page,
    api,
  }) => {
    await api.on(STATUS, status(true))

    await page.goto('/login')
    await logIn(page)

    await expect(page).toHaveURL(/\/dashboard/, NAV)
  })

  test('an account that never finished onboarding is sent back into it', async ({
    page,
    api,
  }) => {
    await api.on(STATUS, status(false))

    await page.goto('/login')
    await logIn(page)

    await expect(page).toHaveURL(/\/onboarding\/company/, NAV)
  })

  test('an account stopped at the plan step resumes at pricing', async ({ page, api }) => {
    await api.on(STATUS, status(false, 'pricing'))

    await page.goto('/login')
    await logIn(page)

    await expect(page).toHaveURL(/\/onboarding\/pricing/, NAV)
  })
})

test.describe('Revisiting /login with a session', () => {
  test('carries a set-up account on to the dashboard', async ({ page, api }) => {
    await api.on('**/api/v1/users/me', { body: TEST_USER })
    await api.on(STATUS, status(true))

    await signIn(page)
    await page.goto('/login')

    await expect(page).toHaveURL(/\/dashboard/, NAV)
  })

  test('carries an unfinished account back into onboarding', async ({ page, api }) => {
    await api.on('**/api/v1/users/me', { body: TEST_USER })
    await api.on(STATUS, status(false))

    await signIn(page)
    await page.goto('/login')

    await expect(page).toHaveURL(/\/onboarding\/company/, NAV)
  })
})

test.describe('The onboarding flow itself', () => {
  test('a finished account cannot re-enter it', async ({ page, api }) => {
    await api.on('**/api/v1/users/me', { body: TEST_USER })
    await api.on(STATUS, status(true))

    await signIn(page)
    await page.goto('/onboarding/company')

    await expect(page).toHaveURL(/\/dashboard/, NAV)
  })

  test('an unfinished account stays on the form', async ({ page, api }) => {
    await api.on('**/api/v1/users/me', { body: TEST_USER })
    await api.on(STATUS, status(false))

    await signIn(page)
    await page.goto('/onboarding/company')

    await expect(page.getByText('Company Information')).toBeVisible()
    await expect(page).toHaveURL(/\/onboarding\/company/, NAV)
  })
})
