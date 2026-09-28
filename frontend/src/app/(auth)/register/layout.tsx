import type { Metadata } from 'next'

// The page itself is a client component and cannot export metadata.
export const metadata: Metadata = {
  title: 'Create your account · Voicecon',
  description: 'Create a Voicecon account and start your free trial.',
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
