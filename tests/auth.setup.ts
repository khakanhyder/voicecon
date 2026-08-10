/**
 * Runs once before the `e2e` project and leaves an authenticated browser state
 * on disk, so real-backend tests start logged in instead of driving the login
 * form every time.
 *
 * It also starts the workspace's free trial. Registration alone leaves
 * entitlements `expired`, and every guarded write endpoint answers 402 — so
 * without this every "create an agent" test fails on billing rather than on
 * anything it meant to check.
 */
import { test as setup, expect } from '@playwright/test'
import { createVerifiedAccount, login, startTrial } from './support/api'

export const STORAGE_STATE = 'playwright/.auth/user.json'

setup('authenticate', async ({ page, request }) => {
  const account = await createVerifiedAccount(request)
  const session = await login(request, account)
  await startTrial(request, session)

  await page.goto('/login')
  await page.getByLabel('Email Id :').fill(account.email)
  await page.getByLabel('Password:', { exact: true }).fill(account.password)
  await page.getByRole('button', { name: 'Login Now' }).click()

  // With a live trial the app routes to the dashboard, but onboarding is still
  // a valid landing spot — either destination means the session is live.
  await expect(page).toHaveURL(/\/(dashboard|onboarding)/)
  await expect
    .poll(() => page.evaluate(() => localStorage.getItem('access_token')))
    .not.toBeNull()

  await page.context().storageState({ path: STORAGE_STATE })
})
