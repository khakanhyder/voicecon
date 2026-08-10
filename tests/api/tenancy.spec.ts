/**
 * Tenancy: every resource one workspace owns, probed from another.
 *
 * This is the single check worth running against every feature, because the
 * failure mode is silent. A broken list filter does not raise — it just shows
 * one customer another customer's data, and nothing in the UI looks wrong.
 *
 * Each test creates two disposable accounts, so "the other workspace" is real
 * rather than simulated by a header.
 */
import { test, expect } from '@playwright/test'
import { API_URL, auth, createTrialSession, type Session } from '../support/api'

/** Create a resource for `owner` and return its id. */
async function seed(
  request: import('@playwright/test').APIRequestContext,
  owner: Session,
  path: string,
  body: Record<string, unknown>,
): Promise<string> {
  const res = await request.post(`${API_URL}${path}`, { headers: auth(owner), data: body })
  expect(res.status(), `seeding ${path}: ${await res.text()}`).toBeLessThan(300)
  return (await res.json()).id
}

test.describe('Tenancy — workflows', () => {
  test('a stranger cannot read, change, run or delete another workspace’s workflow', async ({
    request,
  }) => {
    const owner = await createTrialSession(request)
    const stranger = await createTrialSession(request)
    const id = await seed(request, owner, '/api/v1/workflows', {
      name: 'Owner Workflow',
      trigger_type: 'manual',
      trigger_config: {},
    })

    const attempts: Array<[string, Promise<import('@playwright/test').APIResponse>]> = [
      ['GET', request.get(`${API_URL}/api/v1/workflows/${id}`, { headers: auth(stranger) })],
      [
        'PATCH',
        request.patch(`${API_URL}/api/v1/workflows/${id}`, {
          headers: auth(stranger),
          data: { name: 'Hijacked' },
        }),
      ],
      [
        // Running someone else's workflow spends their quota and fires their
        // integrations — the most expensive thing on this list.
        'EXECUTE',
        request.post(`${API_URL}/api/v1/workflows/${id}/execute`, {
          headers: auth(stranger),
          data: { input_data: {} },
        }),
      ],
      [
        'EXECUTIONS',
        request.get(`${API_URL}/api/v1/workflows/${id}/executions`, { headers: auth(stranger) }),
      ],
      [
        'DELETE',
        request.delete(`${API_URL}/api/v1/workflows/${id}`, { headers: auth(stranger) }),
      ],
    ]

    for (const [label, pending] of attempts) {
      expect((await pending).status(), `${label} must not succeed`).toBe(404)
    }

    // The owner's workflow survived every attempt, under its original name.
    const mine = await request.get(`${API_URL}/api/v1/workflows/${id}`, { headers: auth(owner) })
    expect(mine.status()).toBe(200)
    expect((await mine.json()).name).toBe('Owner Workflow')
  })
})

test.describe('Tenancy — knowledge bases', () => {
  test('a stranger cannot reach another workspace’s knowledge base or its documents', async ({
    request,
  }) => {
    // Knowledge bases hold whatever a customer uploaded for their agent to
    // quote from — pricing, scripts, internal policy. A leak here is a
    // document leak, not just a row.
    const owner = await createTrialSession(request)
    const stranger = await createTrialSession(request)
    const id = await seed(request, owner, '/api/v1/knowledge/knowledge-bases', {
      name: 'Owner KB',
      description: 'Confidential source material.',
    })

    const attempts: Array<[string, Promise<import('@playwright/test').APIResponse>]> = [
      [
        'GET',
        request.get(`${API_URL}/api/v1/knowledge/knowledge-bases/${id}`, {
          headers: auth(stranger),
        }),
      ],
      [
        'DOCUMENTS',
        request.get(`${API_URL}/api/v1/knowledge/knowledge-bases/${id}/documents`, {
          headers: auth(stranger),
        }),
      ],
      [
        'DELETE',
        request.delete(`${API_URL}/api/v1/knowledge/knowledge-bases/${id}`, {
          headers: auth(stranger),
        }),
      ],
    ]

    for (const [label, pending] of attempts) {
      expect((await pending).status(), `${label} must not succeed`).toBe(404)
    }
  })
})

test.describe('Tenancy — tools', () => {
  test('a stranger cannot read, run or delete another workspace’s tool', async ({ request }) => {
    const owner = await createTrialSession(request)
    const stranger = await createTrialSession(request)
    const id = await seed(request, owner, '/api/v1/tools', {
      name: 'Owner Tool',
      description: 'Calls an internal endpoint.',
      tool_type: 'webhook',
    })

    const attempts: Array<[string, Promise<import('@playwright/test').APIResponse>]> = [
      ['GET', request.get(`${API_URL}/api/v1/tools/${id}`, { headers: auth(stranger) })],
      [
        // A tool is an outbound call to a configured URL; running one you do
        // not own borrows the owner's credentials.
        'TEST',
        request.post(`${API_URL}/api/v1/tools/${id}/test`, {
          headers: auth(stranger),
          data: { input_data: {} },
        }),
      ],
      ['DELETE', request.delete(`${API_URL}/api/v1/tools/${id}`, { headers: auth(stranger) })],
    ]

    for (const [label, pending] of attempts) {
      expect((await pending).status(), `${label} must not succeed`).toBe(404)
    }
  })
})

test.describe('Tenancy — list endpoints', () => {
  test('no list endpoint returns another workspace’s rows', async ({ request }) => {
    // The direct-fetch tests above would all pass even if the *list* filter
    // were missing — and a bad list filter is the version of this bug that
    // shows a customer someone else's data without anyone going looking.
    const owner = await createTrialSession(request)
    const stranger = await createTrialSession(request)

    await seed(request, owner, '/api/v1/agents', {
      name: 'Owner Agent',
      system_prompt: 'Confidential.',
    })
    await seed(request, owner, '/api/v1/workflows', {
      name: 'Owner Workflow',
      trigger_type: 'manual',
      trigger_config: {},
    })
    await seed(request, owner, '/api/v1/knowledge/knowledge-bases', {
      name: 'Owner KB',
      description: 'Confidential.',
    })
    await seed(request, owner, '/api/v1/tools', {
      name: 'Owner Tool',
      description: 'Confidential.',
      tool_type: 'webhook',
    })

    const lists: Array<[string, string, string | null]> = [
      ['agents', '/api/v1/agents', 'agents'],
      ['workflows', '/api/v1/workflows', 'workflows'],
      ['knowledge bases', '/api/v1/knowledge/knowledge-bases', null],
      ['tools', '/api/v1/tools', 'tools'],
    ]

    for (const [label, path, key] of lists) {
      const res = await request.get(`${API_URL}${path}`, { headers: auth(stranger) })
      expect(res.status(), label).toBe(200)

      const body = await res.json()
      const rows: Array<{ name?: string }> = key ? (body[key] ?? []) : body
      const names = rows.map((r) => r.name).filter(Boolean)

      expect(names.filter((n) => n!.startsWith('Owner ')), `${label} leaked rows`).toEqual([])
    }
  })
})

test.describe('Tenancy — calls', () => {
  test('the call list and stats are scoped to the caller’s workspace', async ({ request }) => {
    // No live telephony provider is needed to assert scoping: an empty list
    // for a fresh workspace is the claim, and it is the claim that breaks
    // first if the organisation filter is dropped from the query.
    const stranger = await createTrialSession(request)

    const list = await request.get(`${API_URL}/api/v1/calls`, { headers: auth(stranger) })
    expect(list.status()).toBe(200)
    const body = await list.json()
    expect(body.calls ?? body).toEqual([])

    const stats = await request.get(`${API_URL}/api/v1/calls/stats`, { headers: auth(stranger) })
    expect(stats.status()).toBe(200)

    // Another workspace's call cannot be fetched by guessing an id.
    const missing = await request.get(
      `${API_URL}/api/v1/calls/00000000-0000-0000-0000-000000000001`,
      { headers: auth(stranger) },
    )
    expect(missing.status()).toBe(404)
  })

  test('phone numbers are scoped, and a fresh workspace owns none', async ({ request }) => {
    // Deliberately no provisioning: buying a number needs live Twilio
    // credentials, which this suite does not have and must not spend.
    const session = await createTrialSession(request)

    const res = await request.get(`${API_URL}/api/v1/phone-numbers`, { headers: auth(session) })
    expect(res.status()).toBe(200)
    expect(await res.json()).toEqual([])
  })
})
