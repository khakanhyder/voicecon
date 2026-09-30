import type { Metadata } from 'next'
import { AffiliateLayoutSwitch } from '@/components/affiliate/AffiliateShell'

// The partner portal is a per-user area, not content for search results.
export const metadata: Metadata = {
  title: 'Partner portal · VoiceCon',
  robots: { index: false, follow: false },
}

/**
 * `/affiliate` — the partner portal, a separate front door with its own session
 * (lib/session.ts scope `affiliate`). Sign-in and invitation pages render bare;
 * everything else gets the portal shell, which requires a session.
 */
export default function AffiliateLayout({ children }: { children: React.ReactNode }) {
  return <AffiliateLayoutSwitch>{children}</AffiliateLayoutSwitch>
}
