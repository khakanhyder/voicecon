import type { Metadata } from 'next'
import { MarketingShell } from '@/components/landing/MarketingShell'
import { Hero, LogoStrip } from '@/components/landing/Hero'
import { Features, Pillars } from '@/components/landing/Features'
import { ProductTour } from '@/components/landing/ProductTour'
import { HowItWorks, Workflows } from '@/components/landing/HowItWorks'
import { Integrations, UseCases } from '@/components/landing/Integrations'
import { Pricing } from '@/components/landing/Pricing'
import { Faq, FinalCta } from '@/components/landing/Closing'

/**
 * The full marketing site, same sections as src/app/page.tsx. The root serves
 * it again (the coming-soon rewrite in middleware is commented out), so the
 * canonical URL points at '/' to avoid duplicate-content indexing.
 */

const TITLE = 'Voicecon: AI voice agents with no-code workflows'
const DESCRIPTION =
  'Build AI voice agents that answer calls in real time, respond from your own documents, and update your CRM, calendar and team chat through 35 integrations. Start your 30-day free trial.'

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
    images: [{ url: 'https://voicecon.ai/landing/og-image.png', width: 1200, height: 630, alt: 'Voicecon AI voice agents' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: TITLE,
    description: DESCRIPTION,
    images: ['https://voicecon.ai/landing/og-image.png'],
  },
}

const structuredData = {
  '@context': 'https://schema.org',
  '@type': 'SoftwareApplication',
  name: 'Voicecon',
  applicationCategory: 'BusinessApplication',
  operatingSystem: 'Web',
  url: 'https://voicecon.ai/',
  description: DESCRIPTION,
  offers: [
    { '@type': 'Offer', name: 'Sales Chatbot', price: '119', priceCurrency: 'USD' },
    { '@type': 'Offer', name: 'Voice AI', price: '359', priceCurrency: 'USD' },
  ],
}

export default function LandingPage() {
  return (
    <MarketingShell>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
      />
      <Hero />
      <LogoStrip />
      <Pillars />
      <ProductTour />
      <Features />
      <HowItWorks />
      <Workflows />
      <Integrations />
      <UseCases />
      <Pricing />
      <Faq />
      <FinalCta />
    </MarketingShell>
  )
}
