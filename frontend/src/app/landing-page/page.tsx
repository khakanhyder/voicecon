import type { Metadata } from 'next'
import { MarketingShell } from '@/components/landing/MarketingShell'
import { Hero, LogoStrip } from '@/components/landing/Hero'
import { Features, Pillars } from '@/components/landing/Features'
import { ProductTour } from '@/components/landing/ProductTour'
import { HowItWorks, Workflows } from '@/components/landing/HowItWorks'
import { Integrations, UseCases } from '@/components/landing/Integrations'
import { Pricing } from '@/components/landing/Pricing'
import { Faq, FinalCta } from '@/components/landing/Closing'
import { getPricing } from '@/lib/pricing'

// Prices, plans and the trial length are edited in the admin console; re-read
// them from the API at most once a minute (see lib/pricing.ts).
export const revalidate = 60

/**
 * The full marketing site, same sections as src/app/page.tsx. The root serves
 * it again (the coming-soon rewrite in middleware is commented out), so the
 * canonical URL points at '/' to avoid duplicate-content indexing.
 */

const TITLE = 'Voicecon: AI voice agents with no-code workflows'
const describe = (trialDays: number) =>
  `Build AI voice agents that answer calls in real time, respond from your own documents, and update your CRM, calendar and team chat through 35 integrations. Start your ${trialDays}-day free trial.`

export async function generateMetadata(): Promise<Metadata> {
  const { trial } = await getPricing()
  const DESCRIPTION = describe(trial.days)
  return {
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
}

const structuredData = (description: string, plans: { name: string; price_monthly: number }[]) => ({
  '@context': 'https://schema.org',
  '@type': 'SoftwareApplication',
  name: 'Voicecon',
  applicationCategory: 'BusinessApplication',
  operatingSystem: 'Web',
  url: 'https://voicecon.ai/',
  description,
  offers: plans.map((p) => ({ '@type': 'Offer', name: p.name, price: String(p.price_monthly), priceCurrency: 'USD' })),
})

export default async function LandingPage() {
  const pricing = await getPricing()
  const days = pricing.trial.days
  return (
    <MarketingShell>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData(describe(days), pricing.plans)) }}
      />
      <Hero trialDays={days} />
      <LogoStrip />
      <Pillars />
      <ProductTour />
      <Features />
      <HowItWorks />
      <Workflows />
      <Integrations />
      <UseCases trialDays={days} />
      <Pricing pricing={pricing} />
      <Faq trial={pricing.trial} />
      <FinalCta trialDays={days} />
    </MarketingShell>
  )
}
