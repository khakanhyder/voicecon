/**
 * Route matchers for `ApiMock.on()`.
 *
 * These are RegExp, not globs, on purpose. Playwright's glob syntax treats `?`
 * as "exactly one character", so `**​/api/v1/agents` silently fails to match
 * `/api/v1/agents?limit=500` — the app's real request. A glob that never
 * matches falls through to the catch-all `{}`, and the test passes while
 * asserting nothing. Anchoring on the path avoids that whole class of bug.
 *
 * They also match regardless of host, so they keep working whether the app is
 * built against NEXT_PUBLIC_API_URL or a relative base (frontend/src/lib/constants.ts:1).
 */

/** A v1 path, ending at a query string or the end of the URL. */
const v1 = (path: string) => new RegExp(`/api/v1/${path}(?:\\?.*)?$`)

/** Matches a UUID path segment — the shape every id in this API uses. */
const UUID = '[0-9a-fA-F-]{36}'

export const ROUTES = {
  // ── Auth ────────────────────────────────────────────────────────────────
  login: v1('auth/login'),
  logout: v1('auth/logout'),
  register: v1('auth/register'),
  refresh: v1('auth/refresh'),
  sendCode: v1('auth/email/send-code'),
  verifyCode: v1('auth/email/verify-code'),

  // ── App shell (loaded by dashboard/layout.tsx on every page) ────────────
  me: v1('users/me'),
  workspaces: v1('workspaces'),
  workspaceCurrent: v1('workspaces/current'),
  entitlements: v1('billing/entitlements'),

  // ── Agents ──────────────────────────────────────────────────────────────
  /** Collection only: list (GET) and create (POST). Not /agents/stats. */
  agents: v1('agents'),
  agentStats: v1('agents/stats'),
  /** A single agent: GET, PATCH, DELETE. */
  agent: new RegExp(`/api/v1/agents/${UUID}(?:\\?.*)?$`),
  /**
   * Agent sub-resources are NOT nested under /agents — they live under the
   * owning feature's prefix (frontend/src/lib/constants.ts:60,124). Guessing
   * `/agents/{id}/knowledge-bases` here produced a matcher that never fired,
   * so the call fell through to the catch-all's `{}` and crashed the page.
   */
  agentKnowledgeBases: new RegExp(`/api/v1/knowledge/agents/${UUID}/knowledge-bases(?:\\?.*)?$`),
  agentTools: new RegExp(`/api/v1/tools/agents/${UUID}/tools(?:\\?.*)?$`),

  // ── Dashboard widgets ───────────────────────────────────────────────────
  callStats: v1('calls/stats'),
  calls: v1('calls'),
  workflows: v1('workflows'),
  phoneNumbers: v1('phone-numbers'),
  integrationConnections: v1('integrations/connections'),
  knowledgeBases: v1('knowledge/knowledge-bases'),
  tools: v1('tools'),
} as const
