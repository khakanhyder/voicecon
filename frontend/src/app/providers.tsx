'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { GoogleOAuthProvider } from '@react-oauth/google'
import { ReactNode, useEffect, useState } from 'react'
import { usePathname } from 'next/navigation'
import { useAuthStore } from '@/store/authStore'
import { SECTION_PATHS } from '@/components/landing/sections'
import { captureReferral } from '@/lib/referral'
import { useGoogleClientId } from '@/lib/googleClient'

const PUBLIC_PAGES = new Set(['/', '/coming-soon', '/privacy', '/terms', '/affiliate-program', ...Object.keys(SECTION_PATHS)])

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60 * 1000, // 1 minute
      refetchOnWindowFocus: false,
    },
  },
})

// Only mount GoogleOAuthProvider when a client id is configured. Google's GIS
// script throws "Missing required parameter client_id" if initialized empty,
// so the Google button component is likewise only rendered when configured.
function GoogleProvider({ children }: { children: ReactNode }) {
  const { clientId } = useGoogleClientId()
  if (!clientId) return <>{children}</>
  return <GoogleOAuthProvider clientId={clientId}>{children}</GoogleOAuthProvider>
}

export function Providers({ children }: { children: ReactNode }) {
  const [mounted, setMounted] = useState(false)
  const initialize = useAuthStore((state) => state.initialize)
  const pathname = usePathname()

  useEffect(() => {
    setMounted(true)
    initialize()
    // Affiliate links (?ref=) can land on any page, marketing ones included.
    captureReferral()
  }, [initialize])

  // Public marketing pages need no query client, session or Google script,
  // and must server-render in full for search engines and first paint, so
  // they skip the mount gate below.
  if (pathname && PUBLIC_PAGES.has(pathname)) {
    return <>{children}</>
  }

  if (!mounted) {
    return null
  }

  return (
    <QueryClientProvider client={queryClient}>
      <GoogleProvider>{children}</GoogleProvider>
    </QueryClientProvider>
  )
}
