/**
 * Unit tests for the public waitlist sign-up.
 *
 * This runs on the anonymous "Launching Soon" page with a bare `fetch` and no
 * auth interceptor, which means it owns its own error handling. Every failure
 * mode has to end as a readable sentence — an unhandled rejection here shows a
 * visitor a blank form that appears to do nothing.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'

import { joinWaitlist } from './waitlist'

function mockFetch(response: Partial<Response> & { json?: () => Promise<unknown> }) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({}),
    ...response,
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('joinWaitlist', () => {
  it('posts the email as JSON', async () => {
    const fetchMock = mockFetch({ json: async () => ({ success: true, message: 'Added' }) })

    await joinWaitlist('user@example.com')

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toContain('/api/v1/waitlist/subscribe')
    expect(init.method).toBe('POST')
    expect(init.headers['Content-Type']).toBe('application/json')
    expect(JSON.parse(init.body)).toEqual({ email: 'user@example.com' })
  })

  it('returns the server message on success', async () => {
    mockFetch({ json: async () => ({ success: true, message: "You're in!" }) })

    await expect(joinWaitlist('user@example.com')).resolves.toEqual({
      success: true,
      message: "You're in!",
    })
  })

  it('falls back to a friendly message when the server sends none', async () => {
    // A bare `{}` must still produce something to show the visitor.
    mockFetch({ json: async () => ({}) })

    const result = await joinWaitlist('user@example.com')

    expect(result.success).toBe(true)
    expect(result.message).toBeTruthy()
  })

  it('surfaces the server error detail', async () => {
    mockFetch({
      ok: false,
      status: 400,
      json: async () => ({ detail: 'That address is already on the list.' }),
    })

    await expect(joinWaitlist('user@example.com')).rejects.toThrow(
      'That address is already on the list.'
    )
  })

  it('explains a failure with no detail in the body', async () => {
    mockFetch({ ok: false, status: 500, json: async () => ({}) })

    await expect(joinWaitlist('user@example.com')).rejects.toThrow(/something went wrong/i)
  })

  it('handles an error page that is not JSON at all', async () => {
    // A proxy returning an HTML 502 would otherwise throw a raw SyntaxError.
    mockFetch({
      ok: false,
      status: 502,
      json: async () => {
        throw new SyntaxError('Unexpected token <')
      },
    })

    await expect(joinWaitlist('user@example.com')).rejects.toThrow(/something went wrong/i)
  })

  it('reports a connection failure in plain language', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(joinWaitlist('user@example.com')).rejects.toThrow(/network error/i)
  })

  it('succeeds even when a 200 body fails to parse', async () => {
    // An empty 200 is still a success; the fallback message covers it.
    mockFetch({
      ok: true,
      json: async () => {
        throw new SyntaxError('Unexpected end of JSON input')
      },
    })

    await expect(joinWaitlist('user@example.com')).resolves.toMatchObject({ success: true })
  })
})
