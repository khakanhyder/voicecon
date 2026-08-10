/**
 * Real backend + real Postgres. These are the tests mocks cannot do: they fail
 * if the API contract drifts, if password hashing breaks, or if the verification
 * token stops being enforced.
 *
 * Requires the backend on API_URL (default :8001). Run with:
 *   E2E=1 npx playwright test --project=e2e
 */
import { test, expect } from '@playwright/test'
import { createVerifiedAccount, uniqueEmail, API_URL } from '../support/api'

// This suite signs in as accounts it creates, so it must not inherit the
// storageState session that auth.setup.ts left behind.
test.use({ storageState: { cookies: [], origins: [] } })

test('a newly registered account can sign in through the UI', async ({ page, request }) => {
  const account = await createVerifiedAccount(request)

  await page.goto('/login')
  await page.getByLabel('Email Id :').fill(account.email)
  await page.getByLabel('Password:', { exact: true }).fill(account.password)
  await page.getByRole('button', { name: 'Login Now' }).click()

  await expect(page).toHaveURL(/\/(dashboard|onboarding)/)
  expect(await page.evaluate(() => localStorage.getItem('access_token'))).not.toBeNull()
})

test('the real API rejects a wrong password', async ({ page, request }) => {
  const account = await createVerifiedAccount(request)

  await page.goto('/login')
  await page.getByLabel('Email Id :').fill(account.email)
  await page.getByLabel('Password:', { exact: true }).fill('definitely-not-the-password')
  await page.getByRole('button', { name: 'Login Now' }).click()

  await expect(page).toHaveURL(/\/login/)
  expect(await page.evaluate(() => localStorage.getItem('access_token'))).toBeNull()
})

test('registration is refused without a verification token', async ({ request }) => {
  // The UI disables the button, but the endpoint must enforce it independently.
  const res = await request.post(`${API_URL}/api/v1/auth/register`, {
    data: { email: uniqueEmail('unverified'), password: 'qa-password-123', full_name: 'No Token' },
  })

  expect(res.status()).toBe(400)
  expect((await res.json()).detail).toContain('verify your email')
})
