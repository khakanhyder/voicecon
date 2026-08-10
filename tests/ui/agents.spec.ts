import { test, expect } from '../support/mocks'
import { enterDashboard } from '../support/session'
import { ROUTES } from '../support/routes'
import {
  agent,
  agentDetail,
  agentListResponse,
  agentStatsResponse,
  AGENT_ID,
  apiError,
  entitlementError,
  SECOND_AGENT_ID,
  VIEWER_PERMISSIONS,
} from '../support/data'

/**
 * Voice agents are the product. This covers the whole lifecycle — list, create,
 * edit, delete — plus the authorisation that decides who is offered each
 * control.
 *
 * Note on view modes: the list page renders cards as a grid by default, and the
 * Edit/Delete controls only exist in list view (dashboard/agents/page.tsx:146).
 * Tests that act on a row switch views first.
 */
test.describe('Agents', () => {
  test.describe('List', () => {
    test('shows each agent with the model it runs on', async ({ page, api }) => {
      await api.on(ROUTES.agents, {
        body: agentListResponse([
          agent(),
          agent({ id: SECOND_AGENT_ID, name: 'Sam', description: 'Qualifies inbound leads' }),
        ]),
      })
      await api.on(ROUTES.agentStats, { body: agentStatsResponse() })

      await enterDashboard(page, api, '/dashboard/agents')

      await expect(page.getByRole('heading', { name: 'Riley' })).toBeVisible()
      await expect(page.getByText('Books appointments for the clinic')).toBeVisible()
      await expect(page.getByRole('heading', { name: 'Sam' })).toBeVisible()
      await expect(page.getByText('gpt-4o-mini').first()).toBeVisible()
    })

    test('invites a first agent when the workspace has none', async ({ page, api }) => {
      await api.on(ROUTES.agents, { body: agentListResponse([]) })

      await enterDashboard(page, api, '/dashboard/agents')

      await expect(page.getByText(/Create your first AI voice agent/i)).toBeVisible()
    })

    test('still lists agents when the stats endpoint is down', async ({ page, api }) => {
      await api.on(ROUTES.agents, { body: agentListResponse([agent()]) })
      // Stats are supplementary — the page swallows this and renders zeroes
      // (dashboard/agents/page.tsx:283). Losing the whole list here would be
      // a real outage caused by a cosmetic endpoint.
      await api.on(ROUTES.agentStats, { status: 500, body: apiError('stats exploded') })

      await enterDashboard(page, api, '/dashboard/agents')

      await expect(page.getByRole('heading', { name: 'Riley' })).toBeVisible()
    })

    /**
     * There is deliberately no search test here.
     *
     * The page carries a full `search` filter — matching on name and
     * description, a "Found N agents matching…" banner and a "No agents match"
     * empty state (dashboard/agents/page.tsx:308-411) — but **no search input is
     * ever rendered**, and the header's "Search… ⌘K" button has no handler
     * (components/layout/Header.tsx:107). The feature is unreachable, so there
     * is nothing a user could drive.
     *
     * Wire up an input and this becomes testable; until then a passing test
     * here would only be testing React state, not the product.
     */
    test('shows every agent, since the list has no reachable filter', async ({ page, api }) => {
      await api.on(ROUTES.agents, {
        body: agentListResponse([agent(), agent({ id: SECOND_AGENT_ID, name: 'Sam' })]),
      })

      await enterDashboard(page, api, '/dashboard/agents')

      await expect(page.getByRole('heading', { name: 'Riley' })).toBeVisible()
      await expect(page.getByRole('heading', { name: 'Sam' })).toBeVisible()
    })
  })

  test.describe('Create', () => {
    test('posts the full agent config and opens the new agent', async ({ page, api }) => {
      await api.on(ROUTES.agents, { body: { id: AGENT_ID } })
      await api.on(ROUTES.agent, { body: agentDetail() })

      await enterDashboard(page, api, '/dashboard/agents/new')

      await page.getByPlaceholder('e.g. Riley').fill('Riley')
      await page.getByPlaceholder('You are a helpful voice assistant.').fill(
        'You are Riley, a friendly clinic receptionist.',
      )
      await page.getByRole('button', { name: 'Create Assistant' }).click()

      await expect(page).toHaveURL(new RegExp(`/dashboard/agents/${AGENT_ID}`))

      // The nested llm/voice/stt objects are the contract the backend validates
      // (backend/app/schemas/agent.py). A flattened body would 422 in production
      // while a shallow assertion here still passed.
      const [created] = api.callsOf('POST', '/api/v1/agents')
      expect(created.body).toMatchObject({
        name: 'Riley',
        system_prompt: 'You are Riley, a friendly clinic receptionist.',
        llm: { provider: expect.any(String), model: expect.any(String) },
        voice: { provider: expect.any(String) },
        stt: { provider: expect.any(String) },
      })
    })

    /**
     * Both required fields carry the native `required` attribute, so the browser
     * blocks submission before React's handler runs — which means the guard in
     * handleSubmit never fires and no toast appears. What matters is the
     * outcome: nothing is sent, and the offending field is the one flagged.
     */
    test('refuses to submit without a name', async ({ page, api }) => {
      await enterDashboard(page, api, '/dashboard/agents/new')

      await page.getByPlaceholder('You are a helpful voice assistant.').fill('Some prompt')
      await page.getByRole('button', { name: 'Create Assistant' }).click()

      await expect(page).toHaveURL(/\/dashboard\/agents\/new/)
      expect(api.callsOf('POST', '/api/v1/agents')).toHaveLength(0)
      await expect(page.getByPlaceholder('e.g. Riley')).not.toHaveJSProperty(
        'validity.valid',
        true,
      )
    })

    test('refuses to submit without a system prompt', async ({ page, api }) => {
      await enterDashboard(page, api, '/dashboard/agents/new')

      await page.getByPlaceholder('e.g. Riley').fill('Riley')
      await page.getByRole('button', { name: 'Create Assistant' }).click()

      await expect(page).toHaveURL(/\/dashboard\/agents\/new/)
      expect(api.callsOf('POST', '/api/v1/agents')).toHaveLength(0)
      await expect(
        page.getByPlaceholder('You are a helpful voice assistant.'),
      ).not.toHaveJSProperty('validity.valid', true)
    })

    test('surfaces a server rejection and keeps the typed config', async ({ page, api }) => {
      await api.on(ROUTES.agents, {
        status: 400,
        body: apiError('An agent with that name already exists'),
      })

      await enterDashboard(page, api, '/dashboard/agents/new')
      await page.getByPlaceholder('e.g. Riley').fill('Riley')
      await page.getByPlaceholder('You are a helpful voice assistant.').fill('Prompt')
      await page.getByRole('button', { name: 'Create Assistant' }).click()

      await expect(page.getByText('An agent with that name already exists')).toBeVisible()
      // Losing the form on a server error makes the user retype everything.
      await expect(page.getByPlaceholder('e.g. Riley')).toHaveValue('Riley')
      await expect(page).toHaveURL(/\/dashboard\/agents\/new/)
    })

    test('blocks a plan-capped workspace with the upgrade path, not an error', async ({
      page,
      api,
    }) => {
      // 402 is a distinct contract from 4xx: the API client turns it into an
      // upgrade dialog rather than a toast (frontend/src/lib/api.ts:66).
      //
      // Scoped to POST. This page also GETs /agents to fill its assistants
      // rail, and 402-ing that opened the dialog on page load — the test then
      // "passed" for the wrong reason, or blocked its own click.
      await api.on(ROUTES.agents, { body: agentListResponse([]) })
      await api.on(ROUTES.agents, { status: 402, body: entitlementError() }, { method: 'POST' })

      await enterDashboard(page, api, '/dashboard/agents/new')
      await page.getByPlaceholder('e.g. Riley').fill('Riley')
      await page.getByPlaceholder('You are a helpful voice assistant.').fill('Prompt')
      await page.getByRole('button', { name: 'Create Assistant' }).click()

      const dialog = page.getByRole('dialog')
      await expect(dialog).toBeVisible()
      await expect(dialog).toContainText('Your plan allows 1 agent')
      // A dead end would be the bug; the user must be offered the way out.
      await expect(dialog.getByRole('button', { name: /Upgrade to|View plans/ })).toBeVisible()
      await expect(dialog.getByRole('button', { name: 'Not now' })).toBeVisible()
    })
  })

  test.describe('Edit', () => {
    test('loads the saved config and PATCHes only what changed', async ({ page, api }) => {
      await api.on(ROUTES.agent, { body: agentDetail() })
      await api.on(ROUTES.agentKnowledgeBases, { body: [] })

      await enterDashboard(page, api, `/dashboard/agents/${AGENT_ID}/edit`)

      // The form must be populated from the server, not left blank — saving a
      // blank form would wipe the agent.
      await expect(page.getByPlaceholder('e.g. Riley')).toHaveValue('Riley')

      await page.getByPlaceholder('e.g. Riley').fill('Riley v2')
      await page.getByRole('button', { name: 'Save Changes' }).click()

      await expect(page).toHaveURL(new RegExp(`/dashboard/agents/${AGENT_ID}$`))
      const [patched] = api.callsOf('PATCH', `/api/v1/agents/${AGENT_ID}`)
      expect(patched.body).toMatchObject({ name: 'Riley v2' })
    })

    test('refuses to save a name that has been cleared', async ({ page, api }) => {
      await api.on(ROUTES.agent, { body: agentDetail() })
      await api.on(ROUTES.agentKnowledgeBases, { body: [] })

      await enterDashboard(page, api, `/dashboard/agents/${AGENT_ID}/edit`)
      await expect(page.getByPlaceholder('e.g. Riley')).toHaveValue('Riley')

      await page.getByPlaceholder('e.g. Riley').fill('')
      await page.getByRole('button', { name: 'Save Changes' }).click()

      // Native `required` stops the submit, so nothing reaches the server and
      // the agent keeps the name it had.
      await expect(page).toHaveURL(/\/edit$/)
      expect(api.callsOf('PATCH', `/api/v1/agents/${AGENT_ID}`)).toHaveLength(0)
    })

    test('returns to the list when the agent no longer exists', async ({ page, api }) => {
      await api.on(ROUTES.agent, { status: 404, body: apiError('Agent not found') })

      await enterDashboard(page, api, `/dashboard/agents/${AGENT_ID}/edit`)

      // Stranding the user on a dead edit form is worse than sending them back.
      await expect(page).toHaveURL(/\/dashboard\/agents$/)
    })

    test('reports a failed save without pretending it worked', async ({ page, api }) => {
      await api.on(ROUTES.agent, { body: agentDetail() })
      // Only the save fails — the initial GET must still succeed, or the page
      // bounces to the list before the test can even edit anything.
      await api.on(
        ROUTES.agent,
        { status: 500, body: apiError('Could not save agent') },
        { method: 'PATCH' },
      )
      await api.on(ROUTES.agentKnowledgeBases, { body: [] })

      await enterDashboard(page, api, `/dashboard/agents/${AGENT_ID}/edit`)
      await expect(page.getByPlaceholder('e.g. Riley')).toHaveValue('Riley')

      await page.getByPlaceholder('e.g. Riley').fill('Riley v2')
      await page.getByRole('button', { name: 'Save Changes' }).click()

      await expect(page.getByText('Could not save agent')).toBeVisible()
      // Navigating away on failure would tell the user the edit was saved.
      await expect(page).toHaveURL(/\/edit$/)
    })
  })

  test.describe('Delete', () => {
    /** Delete lives in list view only, so switch before acting. */
    async function openListView(page: import('@playwright/test').Page) {
      await page.getByRole('button', { name: 'List view' }).click()
    }

    test('asks for confirmation naming the agent, then removes the row', async ({ page, api }) => {
      await api.on(ROUTES.agents, {
        body: agentListResponse([agent(), agent({ id: SECOND_AGENT_ID, name: 'Sam' })]),
      })
      await api.on(ROUTES.agent, { status: 204, body: null })

      await enterDashboard(page, api, '/dashboard/agents')
      await openListView(page)
      await page.getByRole('button', { name: 'Delete Riley' }).click()

      const dialog = page.getByRole('dialog')
      // Naming the target is what stops the wrong agent being destroyed.
      await expect(dialog).toContainText('Are you sure you want to delete Riley?')

      await dialog.getByRole('button', { name: 'Delete Agent' }).click()

      await expect(page.getByRole('heading', { name: 'Riley' })).toBeHidden()
      await expect(page.getByRole('heading', { name: 'Sam' })).toBeVisible()
      expect(api.callsOf('DELETE', `/api/v1/agents/${AGENT_ID}`)).toHaveLength(1)
    })

    test('cancelling deletes nothing', async ({ page, api }) => {
      await api.on(ROUTES.agents, { body: agentListResponse([agent()]) })

      await enterDashboard(page, api, '/dashboard/agents')
      await openListView(page)
      await page.getByRole('button', { name: 'Delete Riley' }).click()
      await page.getByRole('dialog').getByRole('button', { name: 'Cancel' }).click()

      await expect(page.getByRole('dialog')).toBeHidden()
      await expect(page.getByRole('heading', { name: 'Riley' })).toBeVisible()
      expect(api.callsOf('DELETE', '/api/v1/agents/')).toHaveLength(0)
    })

    test('keeps the agent on screen when the delete fails', async ({ page, api }) => {
      await api.on(ROUTES.agents, { body: agentListResponse([agent()]) })
      await api.on(ROUTES.agent, { status: 409, body: apiError('Agent is handling a live call') })

      await enterDashboard(page, api, '/dashboard/agents')
      await openListView(page)
      await page.getByRole('button', { name: 'Delete Riley' }).click()
      await page.getByRole('dialog').getByRole('button', { name: 'Delete Agent' }).click()

      await expect(page.getByText('Agent is handling a live call')).toBeVisible()
      // Optimistically dropping the row here would show a deletion that never happened.
      await expect(page.getByRole('heading', { name: 'Riley' })).toBeVisible()
    })
  })

  test.describe('Permissions', () => {
    test('a viewer gets the list but no edit or delete controls', async ({ page, api }) => {
      await api.on(ROUTES.agents, { body: agentListResponse([agent()]) })

      await enterDashboard(page, api, '/dashboard/agents', {
        workspace: { permissions: VIEWER_PERMISSIONS, role: 'viewer', is_owner: false },
      })
      await page.getByRole('button', { name: 'List view' }).click()

      await expect(page.getByRole('heading', { name: 'Riley' })).toBeVisible()
      // The server enforces this too; hiding the control just stops the user
      // walking into a 403 (frontend/src/lib/workspace.ts:33).
      await expect(page.getByRole('button', { name: 'Delete Riley' })).toBeHidden()
      await expect(page.getByRole('link', { name: /Edit/ })).toBeHidden()
    })

    test('an owner gets both', async ({ page, api }) => {
      await api.on(ROUTES.agents, { body: agentListResponse([agent()]) })

      await enterDashboard(page, api, '/dashboard/agents')
      await page.getByRole('button', { name: 'List view' }).click()

      await expect(page.getByRole('button', { name: 'Delete Riley' })).toBeVisible()
      await expect(page.getByRole('link', { name: /Edit/ }).first()).toBeVisible()
    })
  })
})
