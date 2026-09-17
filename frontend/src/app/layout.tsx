import { DM_Sans } from 'next/font/google'
import type { Metadata } from 'next'
import './globals.css'
import { Providers } from './providers'
import { Toaster } from 'sonner'

const dmSans = DM_Sans({ 
  subsets: ['latin'],
  variable: '--font-dm-sans',
  display: 'swap',
})
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
      <body className={`${dmSans.variable} font-sans`}>
        <Providers>
          {children}
          <Toaster position="top-right" richColors />
        </Providers>
      </body>
    </html>
  )
}
