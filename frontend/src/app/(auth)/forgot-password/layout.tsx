import type { Metadata } from 'next'

// The page itself is a client component and cannot export metadata.
export const metadata: Metadata = {
  title: 'Reset your password · Voicecon',
  description: 'Reset the password for your Voicecon account.',
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
