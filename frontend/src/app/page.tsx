import type { Metadata } from 'next'
import { HomePage, homeMetadata } from '@/components/landing/HomePage'

// Prices, plans and the trial length are edited in the admin console; re-read
// them from the API at most once a minute (see lib/pricing.ts).
export const revalidate = 60

export function generateMetadata(): Promise<Metadata> {
  return homeMetadata('/')
}

export default function LandingPage() {
  return <HomePage />
}
