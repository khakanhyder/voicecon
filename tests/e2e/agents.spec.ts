/**
 * The agent lifecycle driven through the real UI against the real backend.
 *
 * This is the test the mocks cannot do: it fails if the create payload stops
 * matching the API schema, if workspace scoping breaks, or if a plan limit
 * starts firing on the wrong request. It writes real rows, so each test brings
 * its own account and cleans up after itself.
 */
import { test, expect } from '@playwright/test'
import { auth, API_URL, createTrialSession, type Session } from '../support/api'

// These sign in as accounts they create, so they must not inherit the
// storageState session that auth.setup.ts left behind.
test.use({ storageState: { cookies: [], origins: [] } })

/** Drive the real login form and land inside the app. */
async function signIn(page: import('@playwright/test').Page, session: Session) {
  await page.goto('/login')
  await page.getByLabel('Email Id :').fill(session.account.email)
  await page.getByLabel('Password:', { exact: true }).fill(session.account.password)
  await page.getByRole('button', { name: 'Login Now' }).click()
  await expect(page).toHaveURL(/\/(dashboard|onboarding)/)
}

test('creates an agent through the form and persists it server-side', async ({ page, request }) => {
  const session = await createTrialSession(request)
  await signIn(page, session)

  await page.goto('/dashboard/agents/new')
  await page.getByPlaceholder('e.g. Riley').fill('E2E Receptionist')
  await page
    .getByPlaceholder('You are a helpful voice assistant.')
    .fill('You are a friendly clinic receptionist.')
  await page.getByRole('button', { name: 'Create Assistant' }).click()

  // The app routes to the new agent's page, which means the API returned an id.
  await expect(page).toHaveURL(/\/dashboard\/agents\/[0-9a-f-]{36}/)

  // Confirm it against the database, not the screen — a UI that renders what it
  // just typed proves nothing about what was stored.
  const listed = await (
    await request.get(`${API_URL}/api/v1/agents`, { headers: auth(session) })
  ).json()
  expect(listed.agents.map((a: { name: string }) => a.name)).toContain('E2E Receptionist')
})

test('shows the created agent on the list page', async ({ page, request }) => {
  const session = await createTrialSession(request)
  await request.post(`${API_URL}/api/v1/agents`, {
    headers: auth(session),
    data: { name: 'Seeded Agent', system_prompt: 'Seeded by the QA suite.' },
  })
  await signIn(page, session)

  await page.goto('/dashboard/agents')

  await expect(page.getByRole('heading', { name: 'Seeded Agent' })).toBeVisible()
})

test('edits an agent and the change survives a reload', async ({ page, request }) => {
  const session = await createTrialSession(request)
  const created = await (
    await request.post(`${API_URL}/api/v1/agents`, {
      headers: auth(session),
      data: { name: 'Before Rename', system_prompt: 'Original prompt.' },
    })
  ).json()
  await signIn(page, session)

  await page.goto(`/dashboard/agents/${created.id}/edit`)
  await expect(page.getByPlaceholder('e.g. Riley')).toHaveValue('Before Rename')

  await page.getByPlaceholder('e.g. Riley').fill('After Rename')
  await page.getByRole('button', { name: 'Save Changes' }).click()
  await expect(page).toHaveURL(new RegExp(`/dashboard/agents/${created.id}$`))

  const fetched = await (
    await request.get(`${API_URL}/api/v1/agents/${created.id}`, { headers: auth(session) })
  ).json()
  expect(fetched.name).toBe('After Rename')
  // The rename must not have blanked the prompt.
  expect(fetched.system_prompt).toBe('Original prompt.')
})

test('deletes an agent and the backend forgets it', async ({ page, request }) => {
  const session = await createTrialSession(request)
  const created = await (
    await request.post(`${API_URL}/api/v1/agents`, {
      headers: auth(session),
      data: { name: 'Doomed Agent', system_prompt: 'Short-lived.' },
    })
  ).json()
  await signIn(page, session)

  await page.goto('/dashboard/agents')
  await page.getByRole('button', { name: 'List view' }).click()
  await page.getByRole('button', { name: 'Delete Doomed Agent' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Delete Agent' }).click()

  await expect(page.getByRole('heading', { name: 'Doomed Agent' })).toBeHidden()

  const after = await request.get(`${API_URL}/api/v1/agents/${created.id}`, {
    headers: auth(session),
  })
  expect(after.status()).toBe(404)
})

test('a plan-capped workspace is offered an upgrade, not a broken form', async ({
  page,
  request,
}) => {
  // The trial allows exactly one agent, so the second create is a real 402 from
  // the real entitlement guard — no mocking involved.
  const session = await createTrialSession(request)
  await request.post(`${API_URL}/api/v1/agents`, {
    headers: auth(session),
    data: { name: 'The Only One', system_prompt: 'Uses up the trial limit.' },
  })
  await signIn(page, session)

  await page.goto('/dashboard/agents/new')
  await page.getByPlaceholder('e.g. Riley').fill('One Too Many')
  await page.getByPlaceholder('You are a helpful voice assistant.').fill('Prompt')
  await page.getByRole('button', { name: 'Create Assistant' }).click()

  await expect(page.getByText(/upgrade/i).first()).toBeVisible()
})

test('a signed-in user only ever sees their own workspace’s agents', async ({ page, request }) => {
  const mine = await createTrialSession(request)
  const theirs = await createTrialSession(request)
  await request.post(`${API_URL}/api/v1/agents`, {
    headers: auth(mine),
    data: { name: 'My Own Agent', system_prompt: 'Mine.' },
  })
  await request.post(`${API_URL}/api/v1/agents`, {
    headers: auth(theirs),
    data: { name: 'Somebody Elses Agent', system_prompt: 'Theirs.' },
  })

  await signIn(page, mine)
  await page.goto('/dashboard/agents')

  await expect(page.getByRole('heading', { name: 'My Own Agent' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Somebody Elses Agent' })).toBeHidden()
})
