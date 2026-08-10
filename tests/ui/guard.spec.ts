import { test, expect } from '../support/mocks'
import { TEST_USER } from '../support/data'
import { signIn, signOut } from '../support/session'

/**
 * The dashboard is guarded client-side in frontend/src/app/dashboard/layout.tsx:34.
 * These lock in that an unauthenticated visitor can never see it.
 */
test.describe('Dashboard access', () => {
  const GUARDED = ['/dashboard', '/dashboard/agents', '/dashboard/calls', '/dashboard/settings']

  for (const path of GUARDED) {
    test(`redirects an anonymous visitor away from ${path}`, async ({ page }) => {
      await page.goto(path)
      await expect(page).toHaveURL(/\/login/)
    })
  }

  test('lets a visitor through once a session exists', async ({ page, api }) => {
    await api.on('**/api/v1/users/me', { body: TEST_USER })

    await signIn(page)
    await page.goto('/dashboard')

    await expect(page).toHaveURL(/\/dashboard/)
  })

  test('locks the dashboard again once the session is dropped', async ({ page, api }) => {
    await api.on('**/api/v1/users/me', { body: TEST_USER })

    await signIn(page)
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/dashboard/)

    await signOut(page)
    await page.reload()

    await expect(page).toHaveURL(/\/login/)
  })
})
