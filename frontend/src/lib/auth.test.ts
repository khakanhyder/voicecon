/**
 * Unit tests for the auth service.
 *
 * The security-relevant behaviour here is what happens to `localStorage` around
 * a session change. Two rules matter most:
 *
 * - Signing in must clear `active_organization_id`. A workspace pinned by the
 *   previous session belongs to a *different user*, and it is sent as a header
 *   on every request — leaving it behind points the new session at someone
 *   else's workspace.
 * - Signing out must remove every key, and must do so even when the network
 *   call fails, or a user on a flaky connection stays signed in locally.
 *
 * `apiClient` is mocked, so nothing reaches the network.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('./api', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

const { apiClient } = await import('./api')
const { authService } = await import('./auth')

const TOKENS = {
  access_token: 'access-1',
  refresh_token: 'refresh-1',
  user: { id: 'u1', email: 'user@example.com' },
}

beforeEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
})

describe('login', () => {
  it('stores the tokens and the user', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: TOKENS } as never)

    await authService.login({ email: 'user@example.com', password: 'pw' })

    expect(localStorage.getItem('access_token')).toBe('access-1')
    expect(localStorage.getItem('refresh_token')).toBe('refresh-1')
    expect(JSON.parse(localStorage.getItem('user')!)).toMatchObject({ id: 'u1' })
  })

  it('clears the previous session workspace', async () => {
    // The pinned workspace belongs to whoever was signed in before and is sent
    // as a header on every request. Carrying it into a new session would point
    // this user at another user's workspace.
    localStorage.setItem('active_organization_id', 'previous-users-workspace')
    vi.mocked(apiClient.post).mockResolvedValue({ data: TOKENS } as never)

    await authService.login({ email: 'user@example.com', password: 'pw' })

    expect(localStorage.getItem('active_organization_id')).toBeNull()
  })

  it('stores nothing when the response carries no token', async () => {
    // A 200 with no token is a failed login, not a session.
    vi.mocked(apiClient.post).mockResolvedValue({ data: { message: 'mfa required' } } as never)

    await authService.login({ email: 'user@example.com', password: 'pw' })

    expect(localStorage.getItem('access_token')).toBeNull()
  })

  it('tolerates a session with no refresh token', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      data: { access_token: 'access-1' },
    } as never)

    await authService.login({ email: 'user@example.com', password: 'pw' })

    expect(localStorage.getItem('access_token')).toBe('access-1')
    expect(localStorage.getItem('refresh_token')).toBeNull()
  })
})

describe('persistSession', () => {
  it('is used by the social sign-in paths too', async () => {
    // Google and Apple return the same session shape; they must clear the
    // stale workspace exactly as password login does.
    localStorage.setItem('active_organization_id', 'stale')
    vi.mocked(apiClient.post).mockResolvedValue({ data: TOKENS } as never)

    await authService.googleAuth('auth-code')

    expect(localStorage.getItem('access_token')).toBe('access-1')
    expect(localStorage.getItem('active_organization_id')).toBeNull()
  })

  it('returns the response unchanged so callers can read it', () => {
    expect(authService.persistSession(TOKENS)).toBe(TOKENS)
  })

  it('ignores a response with no token', () => {
    authService.persistSession({ error: 'nope' })

    expect(localStorage.getItem('access_token')).toBeNull()
  })

  it('ignores a null response rather than throwing', () => {
    expect(() => authService.persistSession(null)).not.toThrow()
  })
})

describe('password reset', () => {
  it('signs the user in with the returned session', async () => {
    // Resetting a password is a proof of ownership, so it ends signed in —
    // otherwise the user is bounced to a login form seconds after choosing it.
    vi.mocked(apiClient.post).mockResolvedValue({ data: TOKENS } as never)

    await authService.resetPassword({
      email: 'user@example.com',
      code: '123456',
      new_password: 'new-password',
    })

    expect(localStorage.getItem('access_token')).toBe('access-1')
  })
})

describe('getCurrentUser', () => {
  it('reads the cached user', () => {
    localStorage.setItem('user', JSON.stringify({ id: 'u1', email: 'a@b.c' }))

    expect(authService.getCurrentUser()).toMatchObject({ id: 'u1' })
  })

  it('returns null when nothing is cached', () => {
    expect(authService.getCurrentUser()).toBeNull()
  })

  it('returns null rather than throwing on corrupt JSON', () => {
    // A half-written localStorage value would otherwise throw during the very
    // first render and white-screen the app with no way back.
    localStorage.setItem('user', '{not valid json')

    expect(authService.getCurrentUser()).toBeNull()
  })
})

describe('isAuthenticated', () => {
  it('is true with an access token', () => {
    localStorage.setItem('access_token', 'access-1')

    expect(authService.isAuthenticated()).toBe(true)
  })

  it('is false with no token', () => {
    expect(authService.isAuthenticated()).toBe(false)
  })

  it('is false for an empty token', () => {
    // An empty string is not a session; a truthiness bug here would let a
    // signed-out user through the route guard.
    localStorage.setItem('access_token', '')

    expect(authService.isAuthenticated()).toBe(false)
  })
})

describe('clearSession', () => {
  it('removes every trace of the session', () => {
    localStorage.setItem('access_token', 'a')
    localStorage.setItem('refresh_token', 'r')
    localStorage.setItem('user', '{}')
    localStorage.setItem('active_organization_id', 'ws-1')

    authService.clearSession()

    expect(localStorage.length).toBe(0)
  })

  it('is safe to call twice', () => {
    // Deliberately re-run after cancelling in-flight queries: `fetchMe` writes
    // `user` back whenever it resolves, so a request already on the wire can
    // repopulate the profile just after sign-out.
    authService.clearSession()

    expect(() => authService.clearSession()).not.toThrow()
  })
})

describe('logout', () => {
  it('clears the session after telling the server', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: {} } as never)
    localStorage.setItem('access_token', 'a')

    await authService.logout()

    expect(apiClient.post).toHaveBeenCalledWith('/api/v1/auth/logout')
    expect(localStorage.getItem('access_token')).toBeNull()
  })

  it('clears the session even when the server call fails', async () => {
    // Otherwise a user on a flaky connection stays signed in on a shared
    // machine because the sign-out request happened to fail.
    vi.mocked(apiClient.post).mockRejectedValue(new Error('offline'))
    localStorage.setItem('access_token', 'a')

    await expect(authService.logout()).resolves.not.toThrow()
    expect(localStorage.getItem('access_token')).toBeNull()
  })
})

describe('profile', () => {
  it('caches the fetched profile', async () => {
    const user = { id: 'u1', email: 'a@b.c', full_name: 'A' }
    vi.mocked(apiClient.get).mockResolvedValue({ data: user } as never)

    await authService.fetchMe()

    expect(JSON.parse(localStorage.getItem('user')!)).toMatchObject({ full_name: 'A' })
  })

  it('updates the cache after an edit, so the header does not go stale', async () => {
    localStorage.setItem('user', JSON.stringify({ id: 'u1', full_name: 'Old' }))
    vi.mocked(apiClient.patch).mockResolvedValue({
      data: { id: 'u1', full_name: 'New' },
    } as never)

    await authService.updateProfile({ full_name: 'New' })

    expect(JSON.parse(localStorage.getItem('user')!).full_name).toBe('New')
  })
})

describe('deleteAccount', () => {
  it('clears local state so the deleted account cannot appear signed in', async () => {
    vi.mocked(apiClient.delete).mockResolvedValue({ data: {} } as never)
    localStorage.setItem('access_token', 'a')
    localStorage.setItem('user', '{}')
    localStorage.setItem('active_organization_id', 'ws-1')

    await authService.deleteAccount()

    expect(localStorage.length).toBe(0)
  })
})

describe('email verification', () => {
  it('asks for a signup code for the given address', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      data: { message: 'sent', expires_in_minutes: 10 },
    } as never)

    await authService.sendEmailCode('user@example.com')

    expect(apiClient.post).toHaveBeenCalledWith('/api/v1/auth/email/send-code', {
      email: 'user@example.com',
      purpose: 'signup',
    })
  })

  it('exchanges a code for the token register requires', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      data: { verified: true, email_verification_token: 'proof' },
    } as never)

    const result = await authService.verifyEmailCode('user@example.com', '123456')

    expect(result.email_verification_token).toBe('proof')
  })

  it('does not create a session from verifying an address', async () => {
    // Confirming an email proves ownership of the address, not of an account.
    vi.mocked(apiClient.post).mockResolvedValue({
      data: { verified: true, email_verification_token: 'proof' },
    } as never)

    await authService.verifyEmailCode('user@example.com', '123456')

    expect(localStorage.getItem('access_token')).toBeNull()
  })
})
