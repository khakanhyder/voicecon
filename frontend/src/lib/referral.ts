/**
 * Affiliate referral links (`?ref=CODE`).
 *
 * A visitor usually lands on the marketing site (voicecon.ai) and signs up on
 * the app host (app.voicecon.ai). localStorage is per-origin, so the code is
 * kept in a cookie on the shared parent domain instead, where both hosts can
 * read it. The server decides what the code is worth; this only carries it to
 * sign-up (see `authService.register` / `googleAuth` / `appleAuth`).
 *
 * First touch wins: a second link does not replace a code already stored.
 */
import { API_BASE } from '@/lib/constants'

const COOKIE = 'vc_ref'
const DEFAULT_DAYS = 60
const CODE_RE = /^[A-Za-z0-9_-]{3,60}$/

/** `.voicecon.ai` on voicecon.ai / app.voicecon.ai; host-only on localhost and IPs. */
function cookieDomain(): string {
  const host = window.location.hostname
  if (host === 'localhost' || /^[\d.]+$/.test(host) || !host.includes('.')) return ''
  const parts = host.split('.')
  return `; domain=.${parts.slice(-2).join('.')}`
}

function writeCookie(code: string, days: number) {
  const secure = window.location.protocol === 'https:' ? '; secure' : ''
  document.cookie =
    `${COOKIE}=${encodeURIComponent(code)}; max-age=${Math.round(days * 86400)}; path=/; samesite=lax` +
    cookieDomain() +
    secure
}

export function getReferralCode(): string | undefined {
  if (typeof document === 'undefined') return undefined
  const match = document.cookie.split('; ').find((c) => c.startsWith(`${COOKIE}=`))
  if (!match) return undefined
  const value = decodeURIComponent(match.slice(COOKIE.length + 1))
  return CODE_RE.test(value) ? value : undefined
}

/** Forget the code once an account has been created with it. */
export function clearReferralCode() {
  if (typeof document === 'undefined') return
  document.cookie = `${COOKIE}=; max-age=0; path=/; samesite=lax${cookieDomain()}`
}

/**
 * Store `?ref=` from the current URL and count the visit. Called on every page
 * load; a no-op without `?ref=`. An unknown or paused code is dropped.
 */
export function captureReferral() {
  if (typeof window === 'undefined') return
  const code = new URLSearchParams(window.location.search).get('ref')?.trim()
  if (!code || !CODE_RE.test(code) || getReferralCode()) return

  writeCookie(code, DEFAULT_DAYS)
  fetch(`${API_BASE}/api/v1/affiliate-public/click`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      code,
      landing_path: window.location.pathname,
      referrer: document.referrer || undefined,
    }),
    keepalive: true,
  })
    .then((res) => (res.ok ? res.json() : null))
    .then((data) => {
      if (!data) return
      if (data.valid) writeCookie(code, data.cookie_days || DEFAULT_DAYS)
      else clearReferralCode()
    })
    .catch(() => {
      // Counting the visit is best effort; the stored code still reaches sign-up.
    })
}
