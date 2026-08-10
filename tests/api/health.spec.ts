/**
 * Backend liveness. Runs first and cheapest: when this fails, every other
 * `api` and `e2e` failure in the run is noise.
 *
 *   E2E=1 npx playwright test --project=api
 */
import { test, expect } from '@playwright/test'
import { API_URL } from '../support/api'

test.describe('Service health', () => {
  test('the API is up and reports its environment', async ({ request }) => {
    // Note: /health sits at the root, not under /api/v1 (backend/app/main.py:274).
    const res = await request.get(`${API_URL}/health`)

    expect(res.status()).toBe(200)
    expect(await res.json()).toMatchObject({ status: 'healthy' })
  })

  test('the v1 API is mounted', async ({ request }) => {
    // 401 is the right answer here — it proves the router is mounted and the
    // auth dependency is wired. A 404 would mean the app booted with no routes.
    const res = await request.get(`${API_URL}/api/v1/agents`)

    expect(res.status()).toBe(401)
  })

  test('the OpenAPI schema is served and describes the auth surface', async ({ request }) => {
    // Mounted under the v1 prefix, and only when DEBUG is on — production
    // serves no schema at all (backend/app/main.py:139).
    const res = await request.get(`${API_URL}/api/v1/openapi.json`)
    test.skip(res.status() === 404, 'Schema is disabled: this backend runs with DEBUG off.')
    expect(res.status()).toBe(200)

    const paths = Object.keys((await res.json()).paths)
    // These are the endpoints the frontend hard-codes in lib/constants.ts;
    // renaming one server-side breaks the app silently.
    expect(paths).toContain('/api/v1/auth/login')
    expect(paths).toContain('/api/v1/auth/register')
    expect(paths).toContain('/api/v1/agents')
  })
})
