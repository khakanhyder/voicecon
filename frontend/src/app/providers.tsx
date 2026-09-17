'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { GoogleOAuthProvider } from '@react-oauth/google'
import { ReactNode, useEffect, useState } from 'react'
import { usePathname } from 'next/navigation'
import { useAuthStore } from '@/store/authStore'

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || ''
const PUBLIC_PAGES = new Set(['/', '/coming-soon', '/landing-page', '/privacy', '/terms'])

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60 * 1000, // 1 minute
      refetchOnWindowFocus: false,
    },
  },
})

export function Providers({ children }: { children: ReactNode }) {
  const [mounted, setMounted] = useState(false)
  const initialize = useAuthStore((state) => state.initialize)
  const pathname = usePathname()

  useEffect(() => {
    setMounted(true)
    initialize()
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

  // Only mount GoogleOAuthProvider when a client id is configured. Google's GIS
  // script throws "Missing required parameter client_id" if initialized empty,
  // so the Google button component is likewise only rendered when configured.
  return (
    <QueryClientProvider client={queryClient}>
      {GOOGLE_CLIENT_ID ? (
        <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>{children}</GoogleOAuthProvider>
      ) : (
        children
      )}
    </QueryClientProvider>
  )
}
