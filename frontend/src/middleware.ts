import { NextRequest, NextResponse } from 'next/server'
import { SECTION_PATHS } from '@/components/landing/sections'

// One frontend deployment answers on two kinds of host:
//   - landing hosts (voicecon.ai, www.voicecon.ai) serve only the marketing page
//   - the app host (app.voicecon.ai) serves the product
// Auth tokens live in localStorage, which is per-origin, so everything except
// the landing page must be sent to the app host or sessions would split.
//
// These are deliberately not derived from NEXT_PUBLIC_APP_URL: NEXT_PUBLIC_*
// values are frozen at build time, and a stale value in the deploy settings
// once sent landing visitors to the old nip.io host.
const APP_HOST = (process.env.NEXT_PUBLIC_APP_HOST || 'app.voicecon.ai').toLowerCase()
const LANDING_HOSTS = (process.env.NEXT_PUBLIC_LANDING_HOSTS || 'voicecon.ai,www.voicecon.ai')
  .split(',')
  .map((h) => h.trim().toLowerCase())
  .filter(Boolean)
// The first landing host is the canonical one. The others (www) serve the same
// pages, so they redirect to it rather than answering 200 on two origins.
const CANONICAL_LANDING_HOST = LANDING_HOSTS[0]

// Public pages the landing hosts serve themselves; they need no session.
// '/' is the full marketing site and each of its sections has a clean URL
// (/pricing, /faq, ...; see SECTION_PATHS) served by app/[section].
// '/affiliate-program' is the public request form; the partner portal itself
// ('/affiliate/...') is an app-host page.
const MARKETING_PATHS = new Set([
  '/',
  '/privacy',
  '/terms',
  '/affiliate-program',
  ...Object.keys(SECTION_PATHS),
])

// Retired hosts that still route to this deployment (the old nip.io domains).
// They serve the production bundle, whose API rejects their origin, so login
// there always fails with a CORS "Network Error". Send them to the app host.
const LEGACY_HOST_SUFFIXES = ['.nip.io']

function requestHost(request: NextRequest): string {
  // Behind Traefik the forwarded host is the one the visitor typed.
  const raw = request.headers.get('x-forwarded-host') || request.headers.get('host') || ''
  return raw.split(',')[0].trim().split(':')[0].toLowerCase()
}

export function middleware(request: NextRequest) {
  const host = requestHost(request)
  const { pathname, search } = request.nextUrl

  if (host === APP_HOST) {
    // The bare root goes straight to login; the login page sends visitors who
    // are already signed in on to /dashboard.
    if (pathname === '/') {
      // An affiliate link pointed at the app host goes to sign-up with its
      // code; a plain redirect to /login would drop the ?ref=.
      const ref = request.nextUrl.searchParams.get('ref')
      if (ref) {
        return NextResponse.redirect(`https://${APP_HOST}/register?ref=${encodeURIComponent(ref)}`, 307)
      }
      return NextResponse.redirect(`https://${APP_HOST}/login`, 307)
    }
    // Section URLs (/pricing, /faq, ...) are marketing pages; the app host
    // never served them, so send them to the site that does.
    if (SECTION_PATHS[pathname]) {
      return NextResponse.redirect(`https://${CANONICAL_LANDING_HOST}${pathname}${search}`, 308)
    }
    return NextResponse.next()
  }

  if (LEGACY_HOST_SUFFIXES.some((suffix) => host.endsWith(suffix))) {
    return NextResponse.redirect(`https://${APP_HOST}${pathname}${search}`, 308)
  }

  if (LANDING_HOSTS.includes(host) && host !== CANONICAL_LANDING_HOST && MARKETING_PATHS.has(pathname)) {
    return NextResponse.redirect(`https://${CANONICAL_LANDING_HOST}${pathname}${search}`, 308)
  }

  // The marketing site lives at the root now; send the old URL there.
  if (pathname === '/landing-page') {
    const url = request.nextUrl.clone()
    url.pathname = '/'
    return NextResponse.redirect(url, 308)
  }

  if (LANDING_HOSTS.includes(host) && !MARKETING_PATHS.has(pathname)) {
    return NextResponse.redirect(`https://${APP_HOST}${pathname}${search}`, 307)
  }

  return NextResponse.next()
}

export const config = {
  // Skip Next internals and static files so the landing page's assets load.
  matcher: ['/((?!_next/|api/|brand/|favicon|icon\\.svg|robots\\.txt|.*\\.[a-zA-Z0-9]+$).*)'],
}
