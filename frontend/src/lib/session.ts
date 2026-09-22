/**
 * Two front doors, two sessions.
 *
 * The product has a customer app (`/login` → `/dashboard`) and a staff console
 * (`/admin/login` → `/admin`). They are separate sign-ins: signing into one
 * must not sign you into the other, even for a staff member who has both.
 *
 * Both used to share one set of localStorage keys, so a session opened at
 * either door was immediately a session at the other. Each scope now keeps its
 * own credentials under its own keys, and the backend stamps every token with
 * the scope it was issued for — the browser side is convenience, the token
 * claim is what actually enforces it (see app/core/dependencies.py).
 *
 * Which scope a call reads is decided by the path the browser is on, so a tab
 * inside `/admin` can only ever see the admin session and a tab in the product
 * can only ever see the customer one.
 */

export type SessionScope = 'app' | 'admin'

interface Keys {
  accessToken: string
  refreshToken: string
  user: string
  /** Only the customer app is workspace-scoped; the admin API is not. */
  organization?: string
}

const KEYS: Record<SessionScope, Keys> = {
  app: {
    accessToken: 'access_token',
    refreshToken: 'refresh_token',
    user: 'user',
    organization: 'active_organization_id',
  },
  admin: {
    accessToken: 'admin_access_token',
    refreshToken: 'admin_refresh_token',
    user: 'admin_user',
  },
}

/** The sign-in page a scope belongs to. */
export const LOGIN_PATH: Record<SessionScope, string> = {
  app: '/login',
  admin: '/admin/login',
}

/** Which session the current page belongs to. */
export function currentScope(): SessionScope {
  if (typeof window === 'undefined') return 'app'
  return window.location.pathname.startsWith('/admin') ? 'admin' : 'app'
}

function keys(scope: SessionScope = currentScope()): Keys {
  return KEYS[scope]
}

export function getAccessToken(scope?: SessionScope): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(keys(scope).accessToken)
}

export function getRefreshToken(scope?: SessionScope): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(keys(scope).refreshToken)
}

export function setAccessToken(token: string, scope?: SessionScope): void {
  if (typeof window === 'undefined') return
  localStorage.setItem(keys(scope).accessToken, token)
}

export function getStoredUser<T>(scope?: SessionScope): T | null {
  if (typeof window === 'undefined') return null
  const raw = localStorage.getItem(keys(scope).user)
  if (!raw) return null
  try {
    return JSON.parse(raw) as T
  } catch {
    return null
  }
}

export function setStoredUser(user: unknown, scope?: SessionScope): void {
  if (typeof window === 'undefined') return
  localStorage.setItem(keys(scope).user, JSON.stringify(user))
}

export function getOrganizationId(scope?: SessionScope): string | null {
  if (typeof window === 'undefined') return null
  const key = keys(scope).organization
  return key ? localStorage.getItem(key) : null
}

export function setOrganizationId(id: string, scope?: SessionScope): void {
  if (typeof window === 'undefined') return
  const key = keys(scope).organization
  if (key) localStorage.setItem(key, id)
}

export function clearOrganizationId(scope?: SessionScope): void {
  if (typeof window === 'undefined') return
  const key = keys(scope).organization
  if (key) localStorage.removeItem(key)
}

/** Store the tokens and profile a sign-in returned, in one scope only. */
export function storeSession(
  data: { access_token?: string; refresh_token?: string; user?: unknown },
  scope: SessionScope = currentScope(),
): void {
  if (typeof window === 'undefined' || !data?.access_token) return
  const k = keys(scope)
  // A workspace pinned by the previous session belongs to a different user;
  // let the server resolve this one's from scratch.
  clearOrganizationId(scope)
  localStorage.setItem(k.accessToken, data.access_token)
  if (data.refresh_token) localStorage.setItem(k.refreshToken, data.refresh_token)
  if (data.user) localStorage.setItem(k.user, JSON.stringify(data.user))
}

/** Drop one scope's credentials. The other scope's session is left alone. */
export function clearScope(scope: SessionScope = currentScope()): void {
  if (typeof window === 'undefined') return
  const k = keys(scope)
  localStorage.removeItem(k.accessToken)
  localStorage.removeItem(k.refreshToken)
  localStorage.removeItem(k.user)
  if (k.organization) localStorage.removeItem(k.organization)
}
