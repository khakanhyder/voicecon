// Local development talks to the API over plain http (http://localhost:8001),
// which the https-only connect-src below would block, leaving every dashboard
// page empty. Allow exactly that origin, and only when it is http.
const devApiOrigins = (() => {
  try {
    const origin = new URL(process.env.NEXT_PUBLIC_API_URL || '').origin
    return origin.startsWith('http:') ? [origin, origin.replace(/^http:/, 'ws:')] : []
  } catch {
    return []
  }
})()

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  swcMinify: true,
  poweredByHeader: false, // M-05: hide X-Powered-By
  typescript: {
    // During Docker builds, ignore TypeScript errors to allow build to complete
    ignoreBuildErrors: true,
  },
  eslint: {
    // Warning: This allows production builds to successfully complete even if
    // your project has ESLint errors.
    ignoreDuringBuilds: true,
  },
  images: {
    domains: ['localhost'],
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**',
      },
    ],
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000',
  },
  transpilePackages: ['react-flow-renderer'],
  // Browsers ask for /favicon.ico on their own; the icon is app/icon.svg.
  async rewrites() {
    return [{ source: '/favicon.ico', destination: '/icon.svg' }]
  },
  // M-05: Security headers for the frontend origin
  async headers() {
    return [
      // Signed-in and per-user pages must stay out of search results. robots.txt
      // alone does not do that: a disallowed URL can still be listed from a
      // link to it, so these answer with noindex as well.
      {
        source: '/:area(dashboard|admin|onboarding|billing|invite|login|register|forgot-password)/:path*',
        headers: [{ key: 'X-Robots-Tag', value: 'noindex, nofollow' }],
      },
      {
        source: '/(.*)',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-XSS-Protection', value: '1; mode=block' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'Strict-Transport-Security', value: 'max-age=31536000; includeSubDomains' },
          // The browser test call needs the microphone on this origin, and
          // Stripe's card field may use the Payment Request API; nothing else.
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(self), geolocation=(), payment=(self "https://js.stripe.com"), usb=()',
          },
          {
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              // Social sign-in SDKs: Sign in with Apple JS and Google Identity Services.
              // Cloudflare Web Analytics is injected by the proxy in front of voicecon.ai.
              // Stripe.js must load from js.stripe.com and mounts its card field and
              // 3-D Secure challenge in iframes; without these checkout never opens
              // (its API calls to api.stripe.com are covered by connect-src https:).
              "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://appleid.cdn-apple.com https://accounts.google.com https://static.cloudflareinsights.com https://js.stripe.com",
              "frame-src https://appleid.apple.com https://accounts.google.com https://js.stripe.com https://hooks.stripe.com",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: https:",
              "font-src 'self' data: https:",
              // Without this, media falls back to default-src 'self': the test
              // call plays the agent's voice from blob: URLs and call recordings
              // come from the API host, so both were silently blocked.
              "media-src 'self' blob: data: https:",
              ["connect-src 'self' https: wss:", ...devApiOrigins].join(' '),
              "frame-ancestors 'none'",
            ].join('; '),
          },
        ],
      },
    ]
  },
}

module.exports = nextConfig
// Trigger dev server reload
