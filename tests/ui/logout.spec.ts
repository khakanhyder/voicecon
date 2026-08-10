import { test, expect } from '../support/mocks'
import { enterDashboard } from '../support/session'
import { ROUTES } from '../support/routes'
import { agentListResponse } from '../support/data'

/**
 * Logout is a security boundary, not a navigation. The bar it has to clear is
 * that the session is genuinely gone — not merely that the user was sent to
 * /login, which the Back button would undo.
 */
test.describe('Logout', () => {
  /** The sign-out control lives behind the sidebar account menu. */
  async function openAccountMenu(page: import('@playwright/test').Page) {
    await page.getByRole('button', { name: /Welcome back/ }).click()
  }

  test.beforeEach(async ({ api }) => {
    await api.on(ROUTES.agents, { body: agentListResponse([]) })
    await api.on(ROUTES.logout, { body: { message: 'ok' } })
  })

  test('signs the user out and returns them to the login form', async ({ page, api }) => {
    await enterDashboard(page, api)
    await openAccountMenu(page)

    await page.getByRole('button', { name: 'Sign out' }).click()

    await expect(page).toHaveURL(/\/login/)
  })

  test('clears every credential from the browser', async ({ page, api }) => {
    await enterDashboard(page, api)
    await openAccountMenu(page)
    await page.getByRole('button', { name: 'Sign out' }).click()
    await expect(page).toHaveURL(/\/login/)

    // A leftover refresh token on a shared machine is a full account takeover:
    // the axios interceptor would silently mint a new access token
    // (frontend/src/lib/api.ts:40).
    const stored = await page.evaluate(() => ({
      access: localStorage.getItem('access_token'),
      refresh: localStorage.getItem('refresh_token'),
      user: localStorage.getItem('user'),
      workspace: localStorage.getItem('active_organization_id'),
    }))
    expect(stored).toEqual({ access: null, refresh: null, user: null, workspace: null })
  })

  test('tells the server to revoke the session', async ({ page, api }) => {
    await enterDashboard(page, api)
    await openAccountMenu(page)
    await page.getByRole('button', { name: 'Sign out' }).click()
    await expect(page).toHaveURL(/\/login/)

    // Clearing localStorage alone leaves the refresh token valid server-side.
    expect(api.callsOf('POST', '/auth/logout')).toHaveLength(1)
  })

  test('the dashboard cannot be reached again by navigating back', async ({ page, api }) => {
    await enterDashboard(page, api)
    await openAccountMenu(page)
    await page.getByRole('button', { name: 'Sign out' }).click()
    await expect(page).toHaveURL(/\/login/)

    await page.goto('/dashboard')

    await expect(page).toHaveURL(/\/login/)
  })
})
