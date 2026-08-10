/**
 * Session helpers for mocked tests.
 *
 * Seeds localStorage the way a real login does. Deliberately not
 * `addInitScript` — that re-runs on every navigation, which would silently
 * re-authenticate a test that is trying to verify logout.
 */
import type { Page } from '@playwright/test'
import { loginResponse, TEST_USER, WORKSPACE_ID } from './data'

export async function signIn(page: Page) {
  // localStorage needs an origin, so land on a cheap public page first.
  await page.goto('/login')
  // Wait until the login screen has finished its own routing. Next fires
  // several navigations while hydrating, and on WebKit — the slowest of the
  // three engines here — one of them lands *after* this helper returns and
  // interrupts the caller's `goto` with "interrupted by another navigation".
  // Waiting for an interactive control is the cheapest proof it has settled.
  await page.getByRole('button', { name: 'Login Now' }).waitFor({ state: 'visible' })
  await page.evaluate(
    ([token, refresh, user, workspaceId]) => {
      localStorage.setItem('access_token', token)
      localStorage.setItem('refresh_token', refresh)
      localStorage.setItem('user', user)
      // The API client reads this synchronously to scope every request to a
      // workspace (frontend/src/lib/workspace.ts:57). A real login writes it,
      // so a seeded session that omits it is not the state the app ships.
      localStorage.setItem('active_organization_id', workspaceId)
    },
    [
      loginResponse().access_token,
      loginResponse().refresh_token,
      JSON.stringify(TEST_USER),
      WORKSPACE_ID,
    ] as const,
  )
}

export async function signOut(page: Page) {
  await page.evaluate(() => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
    localStorage.removeItem('active_organization_id')
  })
}

/**
 * Types into a 6-box OTP field the way a person does.
 *
 * OtpInput rebuilds the whole code from React state on every keystroke, so
 * digits sent faster than it re-renders get dropped — hence the per-key delay
 * rather than six back-to-back fill() calls. Filling the last box fires the
 * component's onComplete, which submits the code on its own.
 */
export async function fillOtp(page: Page, code: string) {
  await page.getByLabel('Digit 1').click()
  await page.keyboard.type(code, { delay: 100 })
}

/**
 * Put the browser inside the authenticated app and land on `path`.
 *
 * Order matters: the route stubs must exist before any navigation, because
 * dashboard/layout.tsx fires the workspace and entitlement requests during its
 * first render. Registering them afterwards races the page.
 */
export async function enterDashboard(
  page: Page,
  api: import('./mocks').ApiMock,
  path = '/dashboard',
  shell: Parameters<import('./mocks').ApiMock['installAppShell']>[0] = {},
) {
  await api.installAppShell(shell)
  await signIn(page)
  await gotoStable(page, path)
}

/**
 * `page.goto` that tolerates one lost race with the app's own client-side
 * routing. Only a navigation *interruption* is retried — a real failure (bad
 * URL, server down) still throws on the first attempt, so this cannot mask a
 * genuinely broken page.
 */
export async function gotoStable(page: Page, path: string) {
  try {
    await page.goto(path)
  } catch (error) {
    if (!/interrupted by another navigation/.test(String(error))) throw error
    await page.goto(path)
  }
}
