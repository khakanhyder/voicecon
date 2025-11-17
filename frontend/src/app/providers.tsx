'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactNode, useEffect, useState } from 'react'
import { useAuthStore } from '@/store/authStore'

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

  useEffect(() => {
    setMounted(true)
    initialize()
  }, [initialize])

  if (!mounted) {
    return null
  }

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
}
