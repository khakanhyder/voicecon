/**
 * Unit tests for the auth store.
 *
 * The store holds the in-memory session only. `logout` deliberately makes no
 * network call — the sign-out flow in `hooks/useAuth` already posts
 * `/auth/logout`, and having the store post it too sent the request twice on
 * every sign-out. That absence is asserted, since it is easy to "fix" back in.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/auth', () => ({
  authService: {
    getCurrentUser: vi.fn(),
    isAuthenticated: vi.fn(),
    logout: vi.fn(),
    clearSession: vi.fn(),
  },
}))

const { authService } = await import('@/lib/auth')
const { useAuthStore } = await import('./authStore')

const USER = { id: 'u1', email: 'user@example.com' } as never

const store = () => useAuthStore.getState()

beforeEach(() => {
  useAuthStore.setState({ user: null, isAuthenticated: false, isLoading: true })
  vi.clearAllMocks()
})

describe('setUser', () => {
  it('marks the session authenticated', () => {
    store().setUser(USER)

    expect(store().user).toBe(USER)
    expect(store().isAuthenticated).toBe(true)
    expect(store().isLoading).toBe(false)
  })

  it('clearing the user de-authenticates', () => {
    // `isAuthenticated` is derived, never set independently — otherwise the two
    // can disagree and a route guard reads the stale one.
    store().setUser(USER)

    store().setUser(null)

    expect(store().user).toBeNull()
    expect(store().isAuthenticated).toBe(false)
  })

  it('ends the loading state either way', () => {
    // The guard renders a spinner while loading; leaving it true after a
    // resolved "no user" would hang the login redirect forever.
    store().setUser(null)

    expect(store().isLoading).toBe(false)
  })
})

describe('initialize', () => {
  it('adopts a session already in storage', () => {
    // Runs on first paint after a reload, so a returning user is not bounced
    // to the login page.
    vi.mocked(authService.getCurrentUser).mockReturnValue(USER)
    vi.mocked(authService.isAuthenticated).mockReturnValue(true)

    store().initialize()

    expect(store().user).toBe(USER)
    expect(store().isAuthenticated).toBe(true)
    expect(store().isLoading).toBe(false)
  })

  it('settles as signed out when there is no session', () => {
    vi.mocked(authService.getCurrentUser).mockReturnValue(null)
    vi.mocked(authService.isAuthenticated).mockReturnValue(false)

    store().initialize()

    expect(store().isAuthenticated).toBe(false)
    expect(store().isLoading).toBe(false)
  })

  it('trusts the token, not the cached profile, for the authenticated flag', () => {
    // A cached user with no token is not a session; the token is the credential.
    vi.mocked(authService.getCurrentUser).mockReturnValue(USER)
    vi.mocked(authService.isAuthenticated).mockReturnValue(false)

    store().initialize()

    expect(store().isAuthenticated).toBe(false)
  })
})

describe('logout', () => {
  it('clears the in-memory session', async () => {
    store().setUser(USER)

    await store().logout()

    expect(store().user).toBeNull()
    expect(store().isAuthenticated).toBe(false)
  })

  it('makes no network call of its own', async () => {
    // The sign-out flow in hooks/useAuth owns the request. Posting here too
    // sent /auth/logout twice on every sign-out.
    await store().logout()

    expect(authService.logout).not.toHaveBeenCalled()
  })
})

describe('setLoading', () => {
  it('toggles the loading flag without touching the session', () => {
    store().setUser(USER)

    store().setLoading(true)

    expect(store().isLoading).toBe(true)
    expect(store().user).toBe(USER)
  })
})
