import type { Metadata } from 'next'
import './globals.css'
import { Providers } from './providers'
import { Toaster } from 'sonner'

// DM Sans is self-hosted through @font-face in globals.css (see the note there).
// Poppins (the sidebar/nav face in the brand spec) is resolved through a plain
// CSS stack in globals.css rather than next/font — fetching it from Google
// Fonts stalls every cold compile on machines without network access to them,
// and falls back to the same face anyway.

const SHARE_DESCRIPTION =
  'Build AI voice agents that answer calls in real time and update your CRM, calendar and team chat through 35 integrations.'

// Link-preview defaults (Slack, WhatsApp, LinkedIn, X) for every page that does
// not set its own — mainly app.voicecon.ai links like /login and invites. Without
// metadataBase, Next would emit the image URL against localhost.
export const metadata: Metadata = {
  metadataBase: new URL('https://app.voicecon.ai'),
  title: 'Voicecon - Voice AI Platform with Integration Management',
  description: 'Create, deploy, and manage AI voice agents with unlimited integrations',
  openGraph: {
    type: 'website',
    siteName: 'Voicecon',
    title: 'Voicecon: AI voice agents with no-code workflows',
    description: SHARE_DESCRIPTION,
    images: [{ url: 'https://voicecon.ai/landing/og-image.png', width: 1200, height: 630, alt: 'Voicecon AI voice agents' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Voicecon: AI voice agents with no-code workflows',
    description: SHARE_DESCRIPTION,
    images: ['https://voicecon.ai/landing/og-image.png'],
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Google tag (gtag.js) — the SEO team asked for it first in <head>.
            It loads on the marketing hosts only: the app host (login, dashboard,
            admin, ...) is signed-in product usage and must not show up in the
            site's Analytics. Same host list as middleware.ts LANDING_HOSTS. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `if (['voicecon.ai', 'www.voicecon.ai'].indexOf(location.hostname) !== -1) {
  var s = document.createElement('script');
  s.async = true;
  s.src = 'https://www.googletagmanager.com/gtag/js?id=G-ZC5PPBD3B6';
  document.head.appendChild(s);
  window.dataLayer = window.dataLayer || [];
  window.gtag = function(){dataLayer.push(arguments);};
  gtag('js', new Date());
  gtag('config', 'G-ZC5PPBD3B6');

  // DataFast analytics (lead's request) — same marketing-hosts-only rule.
  var d = document.createElement('script');
  d.defer = true;
  d.setAttribute('data-website-id', 'dfid_kbJtmTY2MRZC7hqrZX8Rd');
  d.setAttribute('data-domain', 'voicecon.ai');
  d.src = 'https://datafa.st/js/script.js';
  document.head.appendChild(d);
}`,
          }}
        />
        <link rel="preload" href="/fonts/dm-sans-latin.woff2" as="font" type="font/woff2" crossOrigin="anonymous" />
      </head>
      <body className="font-sans">
        <Providers>
          {children}
          <Toaster position="top-right" richColors />
        </Providers>
      </body>
    </html>
  )
}
