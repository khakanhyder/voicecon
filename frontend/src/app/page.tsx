import type { Metadata } from 'next'
import { HomePage, homeMetadata } from '@/components/landing/HomePage'

// Prices, plans and the trial length are edited in the admin console; re-read
// them from the API at most once a minute (see lib/pricing.ts).
export const revalidate = 60

export async function generateMetadata(): Promise<Metadata> {
  // Search Console ownership check — the SEO team wants it on the homepage only.
  return {
    ...(await homeMetadata('/')),
    verification: { google: 'IRfPeiEqfP2qJ8RLXGOeMHSgVG3srGifZRR_anba3y8' },
  }
}

export default function LandingPage() {
  return <HomePage />
}
