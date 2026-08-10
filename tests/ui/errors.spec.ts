import { test, expect } from '../support/mocks'
import { enterDashboard, signIn } from '../support/session'
import { ROUTES } from '../support/routes'
import {
  agentListResponse,
  apiError,
  entitlementError,
  loginResponse,
  TEST_PASSWORD,
  TEST_USER,
} from '../support/data'

/**
 * Failure paths, which is where products actually break for users. Each of
 * these is a distinct branch in frontend/src/lib/api.ts, and they behave
 * differently on purpose:
 *
 *   401 → refresh, retry once, and only then bounce to /login
 *   402 → open the upgrade dialog (the plan is the problem, not the request)
 *   403 → surface the message; the user needs their admin, not a retry
 *   5xx / transport failure → report it, keep the shell alive
 */
test.describe('Error handling', () => {
  test.describe('Expired sessions', () => {
    test('refreshes a stale access token and retries the request', async ({ page, api }) => {
      await api.installAppShell()
      // The first agents call 401s on a stale token; after the refresh the
      // retry must succeed and the user must never see the failure.
      await api.on(ROUTES.agents, [
        { status: 401, body: apiError('Token expired') },
        { body: agentListResponse([]) },
      ])
      await api.on(ROUTES.refresh, { body: loginResponse({ access_token: 'refreshed-token' }) })

      await signIn(page)
      await page.goto('/dashboard/agents')

      await expect(page).toHaveURL(/\/dashboard\/agents/)
      expect(api.callsOf('POST', '/auth/refresh')).toHaveLength(1)
      // The refreshed token has to be written back, or the next request 401s again.
      await expect
        .poll(() => page.evaluate(() => localStorage.getItem('access_token')))
        .toBe('refreshed-token')
    })

    test('sends the user to login when the refresh token is dead too', async ({ page, api }) => {
      await api.installAppShell()
      await api.on(ROUTES.agents, { status: 401, body: apiError('Token expired') })
      await api.on(ROUTES.refresh, { status: 401, body: apiError('Refresh token expired') })

      await signIn(page)
      await page.goto('/dashboard/agents')

      await expect(page).toHaveURL(/\/login/)
      // Keeping a token that the server rejects traps the user in a redirect loop.
      expect(await page.evaluate(() => localStorage.getItem('access_token'))).toBeNull()
    })

    test('treats a 2xx refresh with no token as a failed refresh', async ({ page, api }) => {
      await api.installAppShell()
      await api.on(ROUTES.agents, { status: 401, body: apiError('Token expired') })
      // 200, but no access_token — what a proxy or a half-deployed backend
      // returns. This used to store the literal string "undefined", after which
      // every request carried `Authorization: Bearer undefined` and the user
      // was wedged: apparently signed in, rejected by the API forever.
      await api.on(ROUTES.refresh, { body: { token_type: 'bearer' } })

      await signIn(page)
      await page.goto('/dashboard/agents')

      await expect(page).toHaveURL(/\/login/)
      const stored = await page.evaluate(() => localStorage.getItem('access_token'))
      expect(stored).toBeNull()
      expect(stored).not.toBe('undefined')
    })

    test('does not retry forever when every call 401s', async ({ page, api }) => {
      await api.installAppShell()
      await api.on(ROUTES.agents, { status: 401, body: apiError('Token expired') })
      await api.on(ROUTES.refresh, { status: 401, body: apiError('Refresh token expired') })

      await signIn(page)
      await page.goto('/dashboard/agents')
      await expect(page).toHaveURL(/\/login/)

      // `_retry` guards this (frontend/src/lib/api.ts:40). Without it a stale
      // token hammers the auth service in a tight loop.
      expect(api.callsOf('POST', '/auth/refresh').length).toBeLessThanOrEqual(2)
    })
  })

  test.describe('Server failures', () => {
    test('reports a 500 without blanking the app shell', async ({ page, api }) => {
      await api.on(ROUTES.agents, { status: 500, body: apiError('Internal server error') })

      await enterDashboard(page, api, '/dashboard/agents')

      await expect(page.getByText('Internal server error').first()).toBeVisible()
      // The navigation must survive, so the user can go somewhere else.
      await expect(page.getByRole('link', { name: 'Calls', exact: true })).toBeVisible()
    })

    test('survives a transport failure, which carries no status code', async ({ page, api }) => {
      // A dropped connection is not a 500: `error.response` is undefined, so any
      // handler reading `error.response.data.detail` throws instead of reporting.
      await api.on(ROUTES.agents, { abort: 'connectionrefused' })

      await enterDashboard(page, api, '/dashboard/agents')

      await expect(page.getByRole('link', { name: 'Calls', exact: true })).toBeVisible()
      await expect(page.locator('body')).not.toBeEmpty()
    })

    test('reports a malformed error body instead of crashing on it', async ({ page, api }) => {
      // FastAPI's envelope is `{detail}`; a proxy or gateway can return HTML or
      // an empty body on a bad day.
      await api.on(ROUTES.agents, { status: 502, body: '<html>Bad Gateway</html>' })

      await enterDashboard(page, api, '/dashboard/agents')

      await expect(page.getByRole('link', { name: 'Calls', exact: true })).toBeVisible()
    })

    test('a failed login leaves no half-authenticated state', async ({ page, api }) => {
      await api.on(ROUTES.login, { status: 500, body: apiError('Auth service unavailable') })

      await page.goto('/login')
      await page.getByLabel('Email Id :').fill(TEST_USER.email)
      await page.getByLabel('Password:', { exact: true }).fill(TEST_PASSWORD)
      await page.getByRole('button', { name: 'Login Now' }).click()

      await expect(page).toHaveURL(/\/login/)
      expect(await page.evaluate(() => localStorage.getItem('access_token'))).toBeNull()
    })
  })

  test.describe('Authorisation', () => {
    test('explains a 403 rather than bouncing the user to login', async ({ page, api }) => {
      // 403 means "you are signed in, but not allowed". Treating it as 401 and
      // logging the user out is a confusing and common bug.
      await api.on(ROUTES.agents, {
        status: 403,
        body: apiError('You do not have permission to view agents'),
      })

      await enterDashboard(page, api, '/dashboard/agents')

      await expect(page.getByText('You do not have permission to view agents').first()).toBeVisible()
      await expect(page).toHaveURL(/\/dashboard\/agents/)
      expect(await page.evaluate(() => localStorage.getItem('access_token'))).not.toBeNull()
    })

    test('a 402 opens the upgrade path, not an error toast', async ({ page, api }) => {
      // The `code` discriminator is what routes this to the dialog; a bare
      // `{detail}` 402 would surface as an ordinary error instead.
      await api.on(ROUTES.agents, { status: 402, body: entitlementError() })

      await enterDashboard(page, api, '/dashboard/agents')

      const dialog = page.getByRole('dialog')
      await expect(dialog).toBeVisible()
      await expect(dialog).toContainText('Your plan allows 1 agent')
    })
  })

  test.describe('Unknown routes', () => {
    test('a bad URL renders a 404 page, not a crash', async ({ page }) => {
      const response = await page.goto('/this-route-does-not-exist')

      expect(response?.status()).toBe(404)
      await expect(page.locator('body')).not.toBeEmpty()
    })
  })
})
