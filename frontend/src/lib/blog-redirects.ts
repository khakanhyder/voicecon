import { API_BASE } from '@/lib/constants'

/**
 * Old article URLs → current slugs, for the middleware's 301s.
 *
 * Done in middleware rather than the article page because the page is cached
 * (revalidate = 60) and Next kept serving the old URL's cached copy after a
 * rename. Middleware runs before that cache.
 *
 * The whole map is small (one row per renamed post), so it is fetched in one
 * call and kept in memory for a minute. If the API is down, the last map is
 * used, or none: the article page then renders or 404s as before.
 */

const TTL_MS = 60_000
const TIMEOUT_MS = 1_500

let cache: { map: Map<string, string>; at: number } | null = null
let inflight: Promise<Map<string, string>> | null = null

async function load(): Promise<Map<string, string>> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)
  try {
    const res = await fetch(`${API_BASE}/api/v1/blog/redirects`, { signal: controller.signal, cache: 'no-store' })
    if (!res.ok) throw new Error(`redirects ${res.status}`)
    const rows = (await res.json()) as { from: string; to: string }[]
    const map = new Map(rows.map((r) => [r.from, r.to]))
    cache = { map, at: Date.now() }
    return map
  } catch {
    // Retry after the TTL, not on every request, while the API is unreachable.
    const map = cache?.map ?? new Map<string, string>()
    cache = { map, at: Date.now() }
    return map
  } finally {
    clearTimeout(timer)
    inflight = null
  }
}

/** The current slug for an old one, or null when ``slug`` was never renamed. */
export async function blogRedirectFor(slug: string): Promise<string | null> {
  let map = cache?.map
  if (!cache || Date.now() - cache.at > TTL_MS) {
    map = await (inflight ??= load())
  }
  const to = map?.get(slug)
  return to && to !== slug ? to : null
}
