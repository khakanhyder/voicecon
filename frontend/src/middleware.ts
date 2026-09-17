import { NextRequest, NextResponse } from 'next/server'

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

// Public pages the landing hosts serve themselves; they need no session.
// '/' is the coming-soon page (rewritten below), '/landing-page' is the full
// marketing site that used to live at the root.
const MARKETING_PATHS = new Set(['/', '/coming-soon', '/landing-page', '/privacy', '/terms'])

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
      return NextResponse.redirect(`https://${APP_HOST}/login`, 307)
    }
    return NextResponse.next()
  }

  // Every other host (the landing hosts, and localhost in development) serves
  // the coming-soon page at the root. A rewrite rather than a redirect keeps
  // the bare domain in the address bar; the full marketing site is at
  // /landing-page and src/app/page.tsx is left untouched behind it.
  if (pathname === '/') {
    const url = request.nextUrl.clone()
    url.pathname = '/coming-soon'
    return NextResponse.rewrite(url)
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
