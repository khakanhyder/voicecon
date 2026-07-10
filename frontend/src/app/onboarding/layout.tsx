'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/store/authStore'
import { onboardingService } from '@/lib/onboarding'
import { QUERY_KEYS } from '@/lib/constants'
import { MobileAccentBar } from '@/components/auth/MobileAccentBar'

/**
 * Shared shell for the onboarding flow (Company Information → Pricing → Billing).
 * Guards the routes (must be authenticated) and provides the soft gradient
 * background used across the auth/onboarding screens. Each page renders its own
 * columns so it can choose a 2-column (with BrandPanel) or single-column layout.
 */
export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const { isAuthenticated, isLoading } = useAuthStore()

  // If onboarding is already complete, don't let the user back into the flow.
  const { data: status } = useQuery({
    queryKey: QUERY_KEYS.ONBOARDING_STATUS,
    queryFn: onboardingService.getStatus,
    enabled: isAuthenticated,
    retry: false,
    staleTime: 30 * 1000,
  })

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace('/login')
    }
  }, [isAuthenticated, isLoading, router])

  useEffect(() => {
    if (status?.onboarding_completed) {
      router.replace('/dashboard')
    }
  }, [status, router])

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-brand-100 border-t-brand-600" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return null
  }

  return (
    <div
      className="min-h-screen w-full px-4 py-6 lg:px-8 lg:py-8"
      style={{
        background: 'linear-gradient(135deg, #fdf3ec 0%, #ffffff 45%, #eef4ff 100%)',
      }}
    >
      {children}

      {/* Brand accent line — small screens only */}
      <MobileAccentBar />
    </div>
  )
}
