/**
 * Workspace, profile, knowledge base and team settings.
 *
 * The recurring theme across this suite is a name that is technically present
 * but visually empty. `Field(..., min_length=1)` counts characters, so a single
 * space passes it — and these fields are the workspace switcher, the account
 * menu and the knowledge-base list. Each was found by posting a space.
 */
import { test, expect } from '@playwright/test'
import { API_URL, auth, createTrialSession, uniqueEmail } from '../support/api'

test.describe('Workspace settings', () => {
  test('a workspace cannot be renamed to whitespace', async ({ request }) => {
    // The handler `.strip()`s before saving, so a blank name was stored as ""
    // and the switcher rendered nothing — leaving the user unable to tell one
    // workspace from another.
    const session = await createTrialSession(request)

    const res = await request.patch(`${API_URL}/api/v1/workspaces/current`, {
      headers: auth(session),
      data: { name: '   ' },
    })

    expect(res.status()).toBe(422)
  })

  test('a rename is stored trimmed', async ({ request }) => {
    const session = await createTrialSession(request)

    const res = await request.patch(`${API_URL}/api/v1/workspaces/current`, {
      headers: auth(session),
      data: { name: '  Renamed Workspace  ' },
    })

    expect(res.status()).toBe(200)
    expect((await res.json()).name).toBe('Renamed Workspace')
  })

  test('a new workspace cannot be created blank', async ({ request }) => {
    const session = await createTrialSession(request)

    const res = await request.post(`${API_URL}/api/v1/workspaces`, {
      headers: auth(session),
      data: { name: '   ' },
    })

    expect(res.status()).toBe(422)
  })

  test('two workspaces may share a name', async ({ request }) => {
    // Slugs are unique, and deriving one from the name without a suffix is
    // what broke sign-up for duplicate email local parts. Workspace creation
    // appends a random suffix; this pins that it stays that way.
    const session = await createTrialSession(request)

    const first = await request.post(`${API_URL}/api/v1/workspaces`, {
      headers: auth(session),
      data: { name: 'Shared Name' },
    })
    const second = await request.post(`${API_URL}/api/v1/workspaces`, {
      headers: auth(session),
      data: { name: 'Shared Name' },
    })

    expect(first.status()).toBe(201)
    expect(second.status(), await second.text()).toBe(201)
  })
})

test.describe('Profile settings', () => {
  test('a profile name cannot be blanked', async ({ request }) => {
    const session = await createTrialSession(request)

    const res = await request.patch(`${API_URL}/api/v1/users/me`, {
      headers: auth(session),
      data: { full_name: '   ' },
    })

    expect(res.status()).toBe(422)
  })

  test('a real name still saves, trimmed', async ({ request }) => {
    const session = await createTrialSession(request)

    const res = await request.patch(`${API_URL}/api/v1/users/me`, {
      headers: auth(session),
      data: { full_name: '  Ada Lovelace  ' },
    })

    expect(res.status()).toBe(200)
    expect((await res.json()).full_name).toBe('Ada Lovelace')
  })

  test('omitting a field leaves it alone', async ({ request }) => {
    // The name is Optional, so a PATCH that does not mention it must not be
    // treated as an attempt to clear it.
    const session = await createTrialSession(request)
    await request.patch(`${API_URL}/api/v1/users/me`, {
      headers: auth(session),
      data: { full_name: 'Grace Hopper' },
    })

    const res = await request.patch(`${API_URL}/api/v1/users/me`, {
      headers: auth(session),
      data: { timezone: 'UTC' },
    })

    expect(res.status()).toBe(200)
    expect((await res.json()).full_name).toBe('Grace Hopper')
  })
})

test.describe('Knowledge bases', () => {
  test('a knowledge base cannot be named with whitespace', async ({ request }) => {
    const session = await createTrialSession(request)

    const res = await request.post(`${API_URL}/api/v1/knowledge/knowledge-bases`, {
      headers: auth(session),
      data: { name: '   ', description: 'Should never be created.' },
    })

    expect(res.status()).toBe(422)
  })

  test('a knowledge base is created and listed', async ({ request }) => {
    const session = await createTrialSession(request)

    const created = await request.post(`${API_URL}/api/v1/knowledge/knowledge-bases`, {
      headers: auth(session),
      data: { name: '  Support Docs  ', description: 'Answers for the agent.' },
    })
    expect(created.status()).toBe(201)
    expect((await created.json()).name).toBe('Support Docs')

    const list = await request.get(`${API_URL}/api/v1/knowledge/knowledge-bases`, {
      headers: auth(session),
    })
    const names = (await list.json()).map((k: { name: string }) => k.name)
    expect(names).toContain('Support Docs')
  })
})

test.describe('Team invitations', () => {
  test('an owner can invite someone and see the pending invitation', async ({ request }) => {
    const session = await createTrialSession(request)
    const invitee = uniqueEmail('invitee')

    const invited = await request.post(`${API_URL}/api/v1/team/invite`, {
      headers: auth(session),
      data: { email: invitee, role: 'member' },
    })

    expect(invited.status(), await invited.text()).toBe(201)
    expect(await invited.json()).toMatchObject({
      email: invitee,
      role: 'member',
      status: 'pending',
    })

    const list = await request.get(`${API_URL}/api/v1/team/invitations`, {
      headers: auth(session),
    })
    expect(list.status()).toBe(200)
    expect((await list.json()).map((i: { email: string }) => i.email)).toContain(invitee)
  })

  test('an unknown role is refused', async ({ request }) => {
    // Roles decide what the invitee may do once they accept, so an unchecked
    // value here is a privilege question, not a typo.
    const session = await createTrialSession(request)

    const res = await request.post(`${API_URL}/api/v1/team/invite`, {
      headers: auth(session),
      data: { email: uniqueEmail('badrole'), role: 'superuser' },
    })

    expect(res.status()).toBeGreaterThanOrEqual(400)
    expect(res.status()).toBeLessThan(500)
  })

  test('an invitation token that does not exist is a 404, not a crash', async ({ request }) => {
    // This endpoint is public — it renders the "you have been invited" page
    // before sign-in — so it is reachable by anyone with a guess.
    const res = await request.get(`${API_URL}/api/v1/invitations/not-a-real-token`)

    expect(res.status()).toBe(404)
  })

  test('a stranger cannot list another workspace’s invitations', async ({ request }) => {
    const owner = await createTrialSession(request)
    const stranger = await createTrialSession(request)
    const invitee = uniqueEmail('private')

    await request.post(`${API_URL}/api/v1/team/invite`, {
      headers: auth(owner),
      data: { email: invitee, role: 'member' },
    })

    const res = await request.get(`${API_URL}/api/v1/team/invitations`, {
      headers: auth(stranger),
    })

    expect(res.status()).toBe(200)
    // Pending invitations name real people's addresses.
    expect((await res.json()).map((i: { email: string }) => i.email)).not.toContain(invitee)
  })
})
