/**
 * An account switched off mid-session: the API client must end the session,
 * remember why, and send the person to the sign-in page — not sit on a page
 * full of failed requests, and not waste a token refresh that cannot succeed.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from 'axios'
import { ACCOUNT_INACTIVE_MESSAGE, apiClient, isAccountInactive } from './api'
import { takeSignedOutNotice } from './session'

function respondWith(status: number, data: unknown) {
  apiClient.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    throw new AxiosError('failed', 'ERR_BAD_REQUEST', config, null, {
      status,
      statusText: '',
      headers: {},
      config,
      data,
    })
  }
}

function stubLocation(pathname: string) {
  const location = { pathname, href: `http://localhost${pathname}`, search: '' }
  Object.defineProperty(window, 'location', { value: location, writable: true, configurable: true })
  return location
}

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  vi.restoreAllMocks()
})

describe('isAccountInactive', () => {
  it('recognises the server code and nothing else', () => {
    expect(isAccountInactive({ response: { data: { code: 'account_inactive' } } })).toBe(true)
    expect(isAccountInactive({ response: { data: { detail: 'Could not validate credentials' } } })).toBe(false)
    expect(isAccountInactive(new Error('offline'))).toBe(false)
    expect(isAccountInactive(null)).toBe(false)
  })
})

describe('a request refused because the account is inactive', () => {
  it('clears the session, keeps the reason, and goes to sign-in without refreshing', async () => {
    const location = stubLocation('/dashboard/agents')
    localStorage.setItem('access_token', 'a')
    localStorage.setItem('refresh_token', 'r')
    localStorage.setItem('user', '{}')
    respondWith(401, { detail: ACCOUNT_INACTIVE_MESSAGE, code: 'account_inactive' })

    await expect(apiClient.get('/api/v1/agents')).rejects.toBeTruthy()

    expect(localStorage.getItem('access_token')).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBeNull()
    expect(location.href).toBe('/login')
    expect(takeSignedOutNotice('app')).toBe(ACCOUNT_INACTIVE_MESSAGE)
    expect(takeSignedOutNotice('app')).toBeNull() // shown once
  })

  it('leaves an ordinary 403 alone', async () => {
    const location = stubLocation('/dashboard/agents')
    localStorage.setItem('access_token', 'a')
    respondWith(403, { detail: 'You do not have permission to do that.' })

    await expect(apiClient.get('/api/v1/agents')).rejects.toBeTruthy()

    expect(localStorage.getItem('access_token')).toBe('a')
    expect(location.href).toBe('http://localhost/dashboard/agents')
    expect(takeSignedOutNotice('app')).toBeNull()
  })
})
