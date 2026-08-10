/**
 * Billing contract.
 *
 * The free trial is the default state of every new account, so anything that
 * only recognises a *paid* subscription is broken for the majority of users at
 * any given moment. Both defects below were exactly that shape.
 */
import { test, expect } from '@playwright/test'
import { API_URL, auth, createSession, createTrialSession } from '../support/api'

test.describe('Billing API — usage', () => {
  test('a trial user can read their usage without Stripe configured', async ({ request }) => {
    // `GET /billing/usage` injected the Stripe service as a dependency, and
    // that dependency raises 503 when no API key is set — so the request was
    // rejected before the handler ran. The handler only reads local rows and
    // does arithmetic; it never calls Stripe. The effect was that the billing
    // settings page (settings/billing/page.tsx fetches this) failed outright
    // on any deployment where card payments were not set up yet — which is
    // precisely the deployment the free trial exists to serve.
    const session = await createTrialSession(request)

    const res = await request.get(`${API_URL}/api/v1/billing/usage`, {
      headers: auth(session),
    })

    expect(res.status(), await res.text()).toBe(200)
    expect(await res.json()).toMatchObject({
      minutes_used: expect.any(Number),
      minutes_included: expect.any(Number),
      calls_used: expect.any(Number),
      calls_included: expect.any(Number),
    })
  })

  test('a live trial counts as having a subscription', async ({ request }) => {
    // The limits check filtered on status == "active" alone, while every other
    // query in the codebase uses LIVE_STATUSES — which includes "trialing".
    // So a user on the trial was told they had no subscription and were
    // outside their limits, on the one plan the product hands out by default.
    const session = await createTrialSession(request)

    const res = await request.get(`${API_URL}/api/v1/billing/usage/limits`, {
      headers: auth(session),
    })

    expect(res.status()).toBe(200)
    expect(await res.json()).toMatchObject({
      has_active_subscription: true,
      within_limits: true,
    })
  })

  test('an account with no subscription is reported as having none', async ({ request }) => {
    // The other half of the same fix: broadening the status filter must not
    // start claiming a subscription for an account that never took one.
    const session = await createSession(request)

    const res = await request.get(`${API_URL}/api/v1/billing/usage/limits`, {
      headers: auth(session),
    })

    expect(res.status()).toBe(200)
    expect((await res.json()).has_active_subscription).toBe(false)
  })

  test('paths that genuinely need Stripe still refuse when it is unconfigured', async ({
    request,
  }) => {
    // The fix must not have made card payments silently "work" with no keys.
    const session = await createTrialSession(request)

    const res = await request.post(`${API_URL}/api/v1/billing/checkout`, {
      headers: auth(session),
      data: { plan_id: 'some-plan' },
    })

    // 503 when Stripe is unconfigured (the local/CI case); a 4xx if it is
    // configured and simply rejects this plan id. Never a 2xx.
    expect(res.status()).toBeGreaterThanOrEqual(400)
  })

  test('usage is refused without a token', async ({ request }) => {
    const res = await request.get(`${API_URL}/api/v1/billing/usage`)
    expect(res.status()).toBe(401)
  })

  test('the plan catalogue is public', async ({ request }) => {
    // The pricing step of onboarding renders before the user has a workspace.
    const res = await request.get(`${API_URL}/api/v1/billing/plans`)
    expect(res.status()).toBe(200)
    expect(Array.isArray(await res.json())).toBe(true)
  })
})
