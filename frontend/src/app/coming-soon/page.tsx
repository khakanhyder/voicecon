import type { Metadata } from 'next'
import { ComingSoon } from '@/components/landing/ComingSoon'

/**
 * The page voicecon.ai serves at its root. The middleware rewrites "/" here, so
 * visitors keep the bare domain in the address bar. The full marketing site is
 * still built and served from /landing-page.
 */

const TITLE = 'Voicecon AI - Native AI Voice Large Language Model'
const DESCRIPTION =
  'Voicecon AI powers human-like AI voice conversations with instant responses, voice-to-action automation, and advanced LLM intelligence.'

export const metadata: Metadata = {
  metadataBase: new URL('https://voicecon.ai'),
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: '/' },
  openGraph: {
    type: 'website',
    url: 'https://voicecon.ai/',
    siteName: 'Voicecon',
    title: TITLE,
    description: DESCRIPTION,
    images: [{ url: 'https://voicecon.ai/landing/og-image2.png', width: 1200, height: 630, alt: 'Voicecon AI' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: TITLE,
    description: DESCRIPTION,
    images: ['https://voicecon.ai/landing/og-image2.png'],
  },
}

export default function ComingSoonPage() {
  return <ComingSoon />
}
