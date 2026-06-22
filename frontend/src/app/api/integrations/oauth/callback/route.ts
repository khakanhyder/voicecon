import { NextRequest, NextResponse } from 'next/server'

/**
 * OAuth2 callback handler.
 * Provider redirects to: /api/integrations/oauth/callback?code=...&state=...
 * We forward code+state to the backend, then redirect to the integration page.
 */
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const code = searchParams.get('code')
  const state = searchParams.get('state')
  const error = searchParams.get('error')
  const errorDescription = searchParams.get('error_description')

  const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

  if (error) {
    const msg = encodeURIComponent(errorDescription || error || 'OAuth authorization failed')
    return NextResponse.redirect(new URL(`/dashboard/integrations?oauth_error=${msg}`, request.url))
  }

  if (!code || !state) {
    return NextResponse.redirect(
      new URL('/dashboard/integrations?oauth_error=Missing+code+or+state', request.url)
    )
  }

  try {
    // Get the access token, which also creates the IntegrationConnection in the DB
    const redirectUri = `${request.nextUrl.origin}/api/integrations/oauth/callback`
    const res = await fetch(`${BASE}/api/v1/integrations/oauth/callback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, state, redirect_uri: redirectUri }),
    })

    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      const msg = encodeURIComponent((data as any).detail || 'OAuth callback failed')
      return NextResponse.redirect(new URL(`/dashboard/integrations?oauth_error=${msg}`, request.url))
    }

    const data = await res.json()
    const connectionId = (data as any).id || ''

    // Redirect back to connected integrations with success indicator
    const successUrl = new URL('/dashboard/integrations/connected', request.url)
    successUrl.searchParams.set('oauth_success', '1')
    if (connectionId) successUrl.searchParams.set('connection_id', connectionId)
    return NextResponse.redirect(successUrl)
  } catch {
    return NextResponse.redirect(
      new URL('/dashboard/integrations?oauth_error=Server+error', request.url)
    )
  }
}
