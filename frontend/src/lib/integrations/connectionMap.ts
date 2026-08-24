/**
 * Deciding which connection speaks for an integration on the Integrations page.
 *
 * Lives outside the page component because a Next.js App Router `page.tsx` may
 * only export a default — anything else fails the build's type check.
 */

export interface ApiConnection {
  id: string
  status: string
  connector: { slug: string }
  created_at: string
}

export type ConnectionHealth = 'connected' | 'error' | 'pending'

/** Better health wins, so one broken row cannot speak for a working app. */
const HEALTH_RANK: Record<ConnectionHealth, number> = {
  connected: 2,
  pending: 1,
  error: 0,
}

function healthOf(status: string): ConnectionHealth {
  if (status === 'active') return 'connected'
  if (status === 'error' || status === 'expired') return 'error'
  return 'pending'
}

/**
 * Reduce the connection list to one entry per app.
 *
 * An app can legitimately have more than one connection row — reconnecting
 * used to add one rather than replace it, so older workspaces carry the
 * leftovers. Keying on slug alone meant whichever row happened to come *last*
 * decided the card, so a stale expired connection made a perfectly working
 * integration read "Error" and offer a Connect button.
 */
export function buildConnectionMap(
  connections: ApiConnection[]
): Record<string, { connectionId: string; status: ConnectionHealth }> {
  const map: Record<string, { connectionId: string; status: ConnectionHealth }> = {}

  for (const conn of connections) {
    if (conn.status === 'disconnected') continue
    const slug = conn.connector?.slug
    if (!slug) continue

    const status = healthOf(conn.status)
    const current = map[slug]
    if (!current || HEALTH_RANK[status] > HEALTH_RANK[current.status]) {
      map[slug] = { connectionId: conn.id, status }
    }
  }

  return map
}
