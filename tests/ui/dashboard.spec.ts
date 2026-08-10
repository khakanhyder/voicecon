import { test, expect } from '../support/mocks'
import { enterDashboard } from '../support/session'
import { ROUTES } from '../support/routes'
import {
  agent,
  agentListResponse,
  callStatsResponse,
  connectionListResponse,
  TEST_USER,
  workflowListResponse,
} from '../support/data'

/**
 * The dashboard is a fan-out page: it fires five independent requests with
 * `Promise.allSettled` and derives every tile from them
 * (dashboard/page.tsx:107). The interesting failures are not "does it render"
 * but "does it render the right number, and does one dead endpoint take the
 * whole page down".
 */
test.describe('Dashboard', () => {
  /** The five calls the overview page makes, with enough data to be countable. */
  async function stubOverview(api: import('../support/mocks').ApiMock) {
    await api.on(ROUTES.agents, {
      body: agentListResponse([
        agent({ is_active: true }),
        agent({ id: '00000000-0000-4000-8000-00000000a002', name: 'Sam', is_active: false }),
      ]),
    })
    await api.on(ROUTES.callStats, { body: callStatsResponse({ total_calls: 42 }) })
    await api.on(ROUTES.integrationConnections, {
      body: connectionListResponse([{ id: 'c1', status: 'active' }, { id: 'c2', status: 'error' }]),
    })
    await api.on(ROUTES.workflows, { body: workflowListResponse([{ id: 'w1' }]) })
    await api.on(ROUTES.phoneNumbers, { body: [{ id: 'p1', number: '+15550000000' }] })
  }

  test('greets the signed-in user by name', async ({ page, api }) => {
    await stubOverview(api)
    await enterDashboard(page, api)

    // `full_name` is "QA Bot", and the banner shows the first name only.
    await expect(page.getByRole('heading', { name: /Good day, QA/i })).toBeVisible()
  })

  test('derives each stat tile from its own endpoint', async ({ page, api }) => {
    await stubOverview(api)
    await enterDashboard(page, api)

    // Scoped to <main>: the sidebar links to /dashboard/integrations with the
    // very same label, and would otherwise satisfy the locator with no number
    // in it at all.
    const tile = (label: string) =>
      page.getByRole('main').locator('a', { has: page.getByText(label, { exact: true }) }).first()

    // Only the active agent counts, so a naive `agents.length` would read 2.
    await expect(tile('Active Agents')).toContainText('1')
    await expect(tile('Total Calls')).toContainText('42')
    // Likewise only the connected integration counts, not the errored one.
    await expect(tile('Integrations')).toContainText('1')
    await expect(tile('Workflows')).toContainText('1')
  })

  test('survives one dead endpoint instead of blanking the page', async ({ page, api }) => {
    await stubOverview(api)
    // `Promise.allSettled` is supposed to isolate this failure.
    await api.on(ROUTES.callStats, { status: 500, body: { detail: 'boom' } })

    await enterDashboard(page, api)

    await expect(page.getByRole('heading', { name: /Good day/i })).toBeVisible()
    // The agent tile still has its real number; only calls falls back to zero.
    const tile = (label: string) =>
      page.getByRole('main').locator('a', { has: page.getByText(label, { exact: true }) }).first()
    await expect(tile('Active Agents')).toContainText('1')
    await expect(tile('Total Calls')).toContainText('0')
  })

  test('ticks off onboarding steps the workspace has already done', async ({ page, api }) => {
    await stubOverview(api)
    await enterDashboard(page, api)

    await expect(page.getByRole('heading', { name: 'Getting started' })).toBeVisible()
    // Agents, phone numbers, integrations and workflows all have data above,
    // so every step is complete. The count is rendered as "4/4" or "4 of 4"
    // depending on the layout — assert on the step itself instead.
    const stepLabel = page.getByText('Create your first AI agent', { exact: true })
    await expect(stepLabel).toHaveClass(/line-through/)
  })

  test('shows a fresh workspace an empty, not a broken, dashboard', async ({ page, api }) => {
    await api.on(ROUTES.agents, { body: agentListResponse([]) })
    await api.on(ROUTES.callStats, { body: callStatsResponse({ total_calls: 0 }) })
    await api.on(ROUTES.integrationConnections, { body: connectionListResponse([]) })
    await api.on(ROUTES.workflows, { body: workflowListResponse([]) })
    await api.on(ROUTES.phoneNumbers, { body: [] })

    await enterDashboard(page, api)

    await expect(page.getByRole('heading', { name: /Good day/i })).toBeVisible()
    await expect(
      page.getByRole('main').locator('a', { has: page.getByText('Active Agents', { exact: true }) }).first(),
    ).toContainText('0')
    // Nothing done yet, so no step is struck through.
    await expect(page.getByText('Create your first AI agent', { exact: true })).not.toHaveClass(
      /line-through/,
    )
  })

  test('routes the primary action to agent creation', async ({ page, api }) => {
    await stubOverview(api)
    await enterDashboard(page, api)
    await expect(page.getByRole('heading', { name: /Good day/i })).toBeVisible()

    await page.getByRole('link', { name: 'Create Agent' }).first().click()

    await expect(page).toHaveURL(/\/dashboard\/agents\/new/)
  })

  test('renders the workspace navigation', async ({ page, api }) => {
    await stubOverview(api)
    await enterDashboard(page, api)

    const nav = page.getByRole('navigation').first()
    for (const item of ['Agents', 'Calls', 'Workflows', 'Integrations', 'Analytics']) {
      await expect(nav.getByRole('link', { name: item, exact: true })).toBeVisible()
    }
  })

  test('scopes every request to the active workspace', async ({ page, api }) => {
    await stubOverview(api)
    await enterDashboard(page, api)
    await expect(page.getByRole('heading', { name: /Good day/i })).toBeVisible()

    // The workspace has to be resolved before the page can show anything
    // workspace-scoped; skipping it is how one tenant sees another's data.
    expect(api.callsTo('/workspaces/current').length).toBeGreaterThan(0)
    expect(api.callsTo('/users/me').length).toBeGreaterThan(0)
  })

  test('does not leak the previous user after the profile changes', async ({ page, api }) => {
    await stubOverview(api)
    await enterDashboard(page, api, '/dashboard', {
      user: { ...TEST_USER, full_name: 'Renamed Person' },
    })

    // The banner name comes from the refetched profile, not the localStorage
    // copy the session seeded (frontend/src/hooks/useAuth.ts:19).
    await expect(page.getByRole('heading', { name: /Good day, Renamed/i })).toBeVisible()
  })
})
