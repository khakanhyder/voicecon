import type { Metadata } from 'next'
import { MarketingShell } from '@/components/landing/MarketingShell'
import { Hero, LogoStrip } from '@/components/landing/Hero'
import { Features, Pillars } from '@/components/landing/Features'
import { ProductTour } from '@/components/landing/ProductTour'
import { HowItWorks, Workflows } from '@/components/landing/HowItWorks'
import { Integrations, UseCases } from '@/components/landing/Integrations'
import { Pricing } from '@/components/landing/Pricing'
import { Faq, FinalCta } from '@/components/landing/Closing'
import { SECTION_META } from '@/components/landing/sections'
import { getPricing } from '@/lib/pricing'

/**
 * The marketing site. It is one page: '/' renders it, and so does each section
 * URL (/pricing, /faq, ...; see app/[section]), which differ only in their
 * metadata and in where SmoothScroll lands.
 */

const SITE = 'https://voicecon.ai'
const HOME_TITLE = 'Voicecon: AI voice agents with no-code workflows'
const describeHome = (trialDays: number) =>
  `Build AI voice agents that answer calls in real time, respond from your own documents, and update your CRM, calendar and team chat through 35 integrations. Start your ${trialDays}-day free trial.`

/** Metadata for '/' or for one section path, each with its own canonical. */
export async function homeMetadata(path: string = '/'): Promise<Metadata> {
  const { trial } = await getPricing()
  const section = SECTION_META[path]
  const title = section?.title ?? HOME_TITLE
  const description = section?.description ?? describeHome(trial.days)
  return {
    metadataBase: new URL(SITE),
    title,
    description,
    alternates: { canonical: path },
    openGraph: {
      type: 'website',
      url: `${SITE}${path}`,
      siteName: 'Voicecon',
      title,
      description,
      images: [{ url: `${SITE}/landing/og-image.png`, width: 1200, height: 630, alt: 'Voicecon AI voice agents' }],
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
      images: [`${SITE}/landing/og-image.png`],
    },
  }
}

const structuredData = (description: string, plans: { name: string; price_monthly: number }[]) => ({
  '@context': 'https://schema.org',
  '@type': 'SoftwareApplication',
  name: 'Voicecon',
  applicationCategory: 'BusinessApplication',
  operatingSystem: 'Web',
  url: `${SITE}/`,
  description,
  offers: plans.map((p) => ({ '@type': 'Offer', name: p.name, price: String(p.price_monthly), priceCurrency: 'USD' })),
})

export async function HomePage() {
  const pricing = await getPricing()
  const days = pricing.trial.days
  return (
    <MarketingShell>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData(describeHome(days), pricing.plans)) }}
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
