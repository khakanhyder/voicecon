import { NextRequest, NextResponse } from 'next/server'

// One frontend deployment answers on two kinds of host:
//   - landing hosts (voicecon.ai, www.voicecon.ai) serve only the marketing page
//   - the app host (NEXT_PUBLIC_APP_URL, e.g. app.voicecon.ai) serves the product
// Auth tokens live in localStorage, which is per-origin, so everything except
// the landing page must be sent to the app host or sessions would split.
const LANDING_HOSTS = (process.env.NEXT_PUBLIC_LANDING_HOSTS || 'voicecon.ai,www.voicecon.ai')
  .split(',')
  .map((h) => h.trim().toLowerCase())
  .filter(Boolean)

function appOrigin(): URL | null {
  try {
    return process.env.NEXT_PUBLIC_APP_URL ? new URL(process.env.NEXT_PUBLIC_APP_URL) : null
  } catch {
    return null
  }
}

function requestHost(request: NextRequest): string {
  // Behind Traefik the forwarded host is the one the visitor typed.
  const raw = request.headers.get('x-forwarded-host') || request.headers.get('host') || ''
  return raw.split(',')[0].trim().split(':')[0].toLowerCase()
}

export function middleware(request: NextRequest) {
  const host = requestHost(request)
  const app = appOrigin()
  const { pathname, search } = request.nextUrl

  if (!app || host === app.hostname) {
    // App host: the bare root goes straight to login (the login page sends
    // visitors who are already signed in on to /dashboard).
    const isLocal = host === 'localhost' || host === '127.0.0.1'
    if (app && pathname === '/' && !isLocal) {
      return NextResponse.redirect(new URL('/login', app), 307)
    }
    return NextResponse.next()
  }

  if (LANDING_HOSTS.includes(host) && pathname !== '/') {
    return NextResponse.redirect(new URL(`${pathname}${search}`, app), 307)
  }

  return NextResponse.next()
}

export const config = {
  // Skip Next internals and static files so the landing page's assets load.
  matcher: ['/((?!_next/|api/|brand/|favicon|icon\\.svg|robots\\.txt|.*\\.[a-zA-Z0-9]+$).*)'],
}
