/**
 * The customer app's session and the staff console's session share a browser
 * but not a credential. These pin the part of that which lives client-side:
 * which keys each scope reads, and that neither can see or clear the other.
 */
import { beforeEach, describe, expect, it } from 'vitest'
import {
  clearScope,
  currentScope,
  getAccessToken,
  getStoredUser,
  storeSession,
} from './session'

/** Put the jsdom window on a path, the way a navigation would. */
function at(path: string) {
  window.history.pushState({}, '', path)
}

const appSession = {
  access_token: 'app-token',
  refresh_token: 'app-refresh',
  user: { id: 'u-app', email: 'customer@example.com' },
}

const adminSession = {
  access_token: 'admin-token',
  refresh_token: 'admin-refresh',
  user: { id: 'u-admin', email: 'staff@example.com' },
}

beforeEach(() => {
  localStorage.clear()
  at('/')
})

describe('currentScope', () => {
  it.each([
    ['/dashboard', 'app'],
    ['/login', 'app'],
    ['/onboarding/company', 'app'],
    ['/admin', 'admin'],
    ['/admin/login', 'admin'],
    ['/admin/organizations/123', 'admin'],
  ])('reads %s as the %s session', (path, expected) => {
    at(path)
    expect(currentScope()).toBe(expected)
  })
})

describe('storing a session', () => {
  it('signing into the app does not sign you into the console', () => {
    storeSession(appSession, 'app')

    expect(getAccessToken('app')).toBe('app-token')
    expect(getAccessToken('admin')).toBeNull()
  })

  it('signing into the console does not sign you into the app', () => {
    storeSession(adminSession, 'admin')

    expect(getAccessToken('admin')).toBe('admin-token')
    expect(getAccessToken('app')).toBeNull()
  })

  it('keeps two live sessions apart, profile and all', () => {
    storeSession(appSession, 'app')
    storeSession(adminSession, 'admin')

    expect(getStoredUser<{ email: string }>('app')?.email).toBe('customer@example.com')
    expect(getStoredUser<{ email: string }>('admin')?.email).toBe('staff@example.com')
  })

  it('ignores a response with no token rather than half-storing it', () => {
    storeSession({ user: { id: 'nope' } } as never, 'app')

    expect(getAccessToken('app')).toBeNull()
    expect(getStoredUser('app')).toBeNull()
  })
})

describe('reading without naming a scope', () => {
  it('follows the path the browser is on', () => {
    storeSession(appSession, 'app')
    storeSession(adminSession, 'admin')

    at('/dashboard/agents')
    expect(getAccessToken()).toBe('app-token')

    at('/admin/users')
    expect(getAccessToken()).toBe('admin-token')
  })
})

describe('signing out', () => {
  it('ends only the console session', () => {
    storeSession(appSession, 'app')
    storeSession(adminSession, 'admin')

    clearScope('admin')

    expect(getAccessToken('admin')).toBeNull()
    expect(getAccessToken('app')).toBe('app-token')
  })

  it('ends only the app session', () => {
    storeSession(appSession, 'app')
    storeSession(adminSession, 'admin')

    clearScope('app')

    expect(getAccessToken('app')).toBeNull()
    expect(getAccessToken('admin')).toBe('admin-token')
  })

  it('takes the pinned workspace with the app session', () => {
    storeSession(appSession, 'app')
    localStorage.setItem('active_organization_id', 'org-1')

    clearScope('app')

    expect(localStorage.getItem('active_organization_id')).toBeNull()
  })
})
