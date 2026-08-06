'use client'

import { useState, useEffect } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { useAuthStore } from '@/store/authStore'
import { useWorkspaceStore } from '@/store/workspaceStore'
import { useEntitlementStore } from '@/store/entitlementStore'
import { Header } from '@/components/layout/Header'
import { Sidebar } from '@/components/layout/Sidebar'
import { BillingBanner } from '@/components/billing/BillingBanner'
import { UpgradeDialog } from '@/components/billing/UpgradeDialog'

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const router = useRouter()
  const pathname = usePathname()
  const { isAuthenticated, isLoading } = useAuthStore()
  const loadWorkspace = useWorkspaceStore((s) => s.load)
  const resetWorkspace = useWorkspaceStore((s) => s.reset)
  const currentWorkspaceId = useWorkspaceStore((s) => s.current?.id)
  const loadEntitlements = useEntitlementStore((s) => s.load)
  const refreshEntitlements = useEntitlementStore((s) => s.refresh)
  const resetEntitlements = useEntitlementStore((s) => s.reset)
  const [mobileOpen, setMobileOpen] = useState(false)

  // The workflow canvas manages its own scrolling and needs the full width;
  // the centered, padded container would letterbox it.
  const isFullBleed = pathname?.endsWith('/builder') ?? false

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/login')
    }
  }, [isAuthenticated, isLoading, router])

  // Resolve which workspace this session is working inside, and with what role.
  // Everything under /dashboard is workspace-scoped, so this loads once here
  // rather than in each page.
  useEffect(() => {
    if (isAuthenticated) {
      loadWorkspace()
      loadEntitlements()
    } else {
      resetWorkspace()
      resetEntitlements()
    }
  }, [
    isAuthenticated,
    loadWorkspace,
    resetWorkspace,
    loadEntitlements,
    resetEntitlements,
  ])

  // Plans are per-workspace, so switching workspaces has to re-resolve them —
  // otherwise the user carries their old workspace's plan into the new one and
  // sees features unlocked that this workspace has not paid for.
  useEffect(() => {
    if (isAuthenticated && currentWorkspaceId) {
      refreshEntitlements()
    }
  }, [isAuthenticated, currentWorkspaceId, refreshEntitlements])

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50">
        <div className="flex flex-col items-center gap-4">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-brand-100 border-t-brand" />
          <p className="text-sm text-slate-500 font-medium">Loading your workspace…</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return null
  }

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      <Sidebar mobileOpen={mobileOpen} onMobileClose={() => setMobileOpen(false)} />
      <div className="flex flex-1 flex-col overflow-hidden min-w-0">
        <Header onMenuClick={() => setMobileOpen(true)} />
        {/* One banner, chosen by severity — trial countdown, payment failure,
            or "your access has ended". Renders nothing when all is well. */}
        <BillingBanner />
        {/* Every 402 anywhere in the product opens this, so no page has to
            handle billing errors itself. */}
        <UpgradeDialog />
        <main
          className={
            isFullBleed ? 'flex-1 overflow-hidden' : 'flex-1 overflow-y-auto'
          }
        >
          {isFullBleed ? (
            children
          ) : (
            <div className="p-4 md:p-5">
              {children}
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
