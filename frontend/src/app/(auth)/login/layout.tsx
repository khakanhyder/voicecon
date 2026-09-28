import type { Metadata } from 'next'

// The page itself is a client component and cannot export metadata.
export const metadata: Metadata = {
  title: 'Log in · Voicecon',
  description: 'Log in to your Voicecon workspace.',
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
