'use client'

import { useState, useEffect } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { useAuthStore } from '@/store/authStore'
import { useWorkspaceStore } from '@/store/workspaceStore'
import { Header } from '@/components/layout/Header'
import { Sidebar } from '@/components/layout/Sidebar'

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
    } else {
      resetWorkspace()
    }
  }, [isAuthenticated, loadWorkspace, resetWorkspace])

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
