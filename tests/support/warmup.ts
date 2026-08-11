/**
 * Compile every route the suite visits, once, before any test runs.
 *
 * The UI projects run against `next dev`, which compiles a route the first time
 * it is asked for. With three browsers and several workers that first request
 * lands in the middle of a test, races the other workers' compiles, and blows
 * past the expect timeout — producing failures that could not be reproduced
 * afterwards, because by then the route was compiled. The symptom was never the
 * same test twice: a `page.goto` timing out, or a guard's client-side redirect
 * to a route that was still being built.
 *
 * So the compiles are paid for here instead, serially, while nothing is
 * asserting. A failure to warm a route is not a failure of the run — the test
 * that needs it will report it far better than this can.
 */
import type { FullConfig } from '@playwright/test'

/** Same defaults as playwright.config.ts. */
const PORT = process.env.PORT ?? '3000'
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? `http://localhost:${PORT}`

/**
 * Every route reached by a test, whether by `goto` or by the app navigating
 * itself. Dynamic segments use a throwaway id: the compile is per route, not
 * per id, and the page's own data call is mocked away in the tests.
 */
const ROUTES = [
  '/',
  '/login',
  '/register',
  '/forgot-password',
  '/onboarding/company',
  '/dashboard',
  '/dashboard/agents',
  '/dashboard/agents/new',
  '/dashboard/agents/warmup/edit',
  '/dashboard/analytics',
  '/dashboard/calls',
  '/dashboard/settings',
  // The not-found page, which the 404 test relies on.
  '/this-route-does-not-exist',
]

export default async function warmup(_config: FullConfig) {
  const started = Date.now()
  let warmed = 0

  for (const route of ROUTES) {
    try {
      // Long, because this is the compile itself — the cost this exists to pay.
      const res = await fetch(`${BASE_URL}${route}`, {
        signal: AbortSignal.timeout(120_000),
      })
      // Drain the body: an unread response can leave the connection hanging.
      await res.arrayBuffer()
      warmed++
    } catch {
      // Leave it cold. Whatever is wrong will surface as a real assertion.
    }
  }

  const seconds = ((Date.now() - started) / 1000).toFixed(1)
  console.log(`Warmed ${warmed}/${ROUTES.length} routes in ${seconds}s`)
}
