'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import {
  Activity,
  Building2,
  CreditCard,
  FileClock,
  Gauge,
  Hash,
  KeyRound,
  Layers,
  LogOut,
  Menu,
  Phone,
  Plug,
  ShieldAlert,
  ShieldCheck,
  Users,
  X,
  type LucideIcon,
} from 'lucide-react'
import { useAdminSession } from '@/hooks/useAdminSession'
import { adminApi } from '@/lib/admin'
import { authService } from '@/lib/auth'
import { cn } from '@/lib/utils'

const NAV: { section: string; items: { name: string; href: string; icon: LucideIcon; exact?: boolean }[] }[] = [
  { section: '', items: [{ name: 'Overview', href: '/admin', icon: Gauge, exact: true }] },
  {
    section: 'Configuration',
    items: [
      { name: 'API Keys & Providers', href: '/admin/api-keys', icon: KeyRound },
      { name: 'Plans & Pricing', href: '/admin/plans', icon: Layers },
    ],
  },
  {
    section: 'Customers',
    items: [
      { name: 'Organizations', href: '/admin/organizations', icon: Building2 },
      { name: 'Users', href: '/admin/users', icon: Users },
      { name: 'Billing', href: '/admin/billing', icon: CreditCard },
    ],
  },
  {
    section: 'Operations',
    items: [
      { name: 'Calls', href: '/admin/calls', icon: Phone },
      { name: 'Phone Numbers', href: '/admin/phone-numbers', icon: Hash },
      { name: 'Integrations & Workflows', href: '/admin/integrations', icon: Plug },
    ],
  },
  {
    section: 'System',
    items: [
      { name: 'System Health', href: '/admin/system', icon: Activity },
      { name: 'Audit Log', href: '/admin/audit-log', icon: FileClock },
    ],
  },
]

/**
 * Ends the console session and returns to the admin sign-in page.
 *
 * Only the admin scope's credentials are dropped; a customer session in the
 * same browser is a different sign-in and is left alone. (The server's
 * `/auth/logout` is still "sign out everywhere" for the *account* — so an
 * admin signed into both with the same email is signed out of both.)
 */
function useAdminSignOut() {
  const router = useRouter()
  const queryClient = useQueryClient()
  return async () => {
    await authService.logout()
    // Cancel first: an in-flight admin query would repopulate the cache.
    await queryClient.cancelQueries()
    queryClient.clear()
    authService.clearSession('admin')
    router.replace('/admin/login')
  }
}

function Sidebar({ email, onNavigate }: { email?: string; onNavigate?: () => void }) {
  const signOut = useAdminSignOut()
  const pathname = usePathname()
  const isActive = (href: string, exact?: boolean) =>
    exact ? pathname === href : pathname === href || pathname?.startsWith(href + '/')

  return (
    <div className="flex h-full flex-col bg-slate-950 text-slate-300">
      <div className="flex h-16 flex-shrink-0 items-center gap-2.5 px-5">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
          <ShieldCheck className="h-4 w-4" />
        </span>
        <div className="leading-tight">
          <p className="text-sm font-semibold text-white">Voicecon</p>
          <p className="text-[11px] uppercase tracking-wider text-slate-400">Admin Console</p>
        </div>
      </div>

      <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
        {NAV.map((group) => (
          <div key={group.section || 'root'}>
            {group.section && (
              <p className="mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                {group.section}
              </p>
            )}
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const active = isActive(item.href, item.exact)
                const Icon = item.icon
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onNavigate}
                    className={cn(
                      'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
                      active ? 'bg-white/10 font-medium text-white' : 'text-slate-400 hover:bg-white/5 hover:text-white'
                    )}
                  >
                    <Icon className={cn('h-4 w-4 flex-shrink-0', active ? 'text-brand-300' : '')} />
                    <span className="truncate">{item.name}</span>
                  </Link>
                )
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="flex-shrink-0 border-t border-white/10 p-3">
        <p className="truncate px-3 pb-2 text-xs text-slate-500">{email}</p>
        <button
          type="button"
          onClick={signOut}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-400 transition-colors hover:bg-white/5 hover:text-white"
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </button>
      </div>
    </div>
  )
}

function FullScreen({ children }: { children: React.ReactNode }) {
  return <div className="flex h-screen items-center justify-center bg-slate-50 p-6">{children}</div>
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  // The sign-in page sits under /admin but must render without the console
  // around it (and without the admin check, which needs a session).
  if (pathname === '/admin/login') return <>{children}</>
  return <AdminShell>{children}</AdminShell>
}

function AdminShell({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const signOut = useAdminSignOut()
  const pathname = usePathname()
  const { isAuthenticated, isLoading } = useAdminSession()
  const [mobileOpen, setMobileOpen] = useState(false)

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace(`/admin/login?redirect=${encodeURIComponent(pathname || '/admin')}`)
    }
  }, [isAuthenticated, isLoading, router, pathname])

  // The server decides who is an admin; the cached user object only hides the link.
  const me = useQuery({
    queryKey: ['admin', 'me'],
    queryFn: adminApi.me,
    enabled: isAuthenticated,
    retry: false,
    staleTime: 5 * 60 * 1000,
  })

  if (isLoading || (isAuthenticated && me.isLoading)) {
    return (
      <FullScreen>
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-brand-100 border-t-brand" />
      </FullScreen>
    )
  }
  if (!isAuthenticated) return null

  if (me.isError) {
    const forbidden = axios.isAxiosError(me.error) && me.error.response?.status === 403
    return (
      <FullScreen>
        <div className="max-w-sm text-center">
          <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-rose-50 text-rose-600">
            <ShieldAlert className="h-6 w-6" />
          </span>
          <h1 className="mt-4 text-lg font-semibold text-slate-900">
            {forbidden ? 'Admin access required' : 'Could not open the admin console'}
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            {forbidden
              ? 'This area is for Voicecon platform administrators. Ask an existing admin to grant you access.'
              : 'The server did not respond. Check that the backend is running and try again.'}
          </p>
          <button
            type="button"
            onClick={signOut}
            className="mt-6 inline-flex h-9 items-center rounded-lg bg-brand-600 px-4 text-sm font-medium text-white hover:bg-brand-700"
          >
            Sign in with another account
          </button>
        </div>
      </FullScreen>
    )
  }

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      <aside className="hidden w-64 flex-shrink-0 lg:block">
        <Sidebar email={me.data?.email} />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMobileOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 shadow-2xl">
            <button
              type="button"
              aria-label="Close menu"
              onClick={() => setMobileOpen(false)}
              className="absolute right-3 top-4 z-10 rounded-md p-1.5 text-slate-400 hover:bg-white/10 hover:text-white"
            >
              <X className="h-5 w-5" />
            </button>
            <Sidebar email={me.data?.email} onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 flex-shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-4 lg:hidden">
          <button
            type="button"
            aria-label="Open menu"
            onClick={() => setMobileOpen(true)}
            className="rounded-md p-1.5 text-slate-600 hover:bg-slate-100"
          >
            <Menu className="h-5 w-5" />
          </button>
          <span className="text-sm font-semibold text-slate-900">Admin Console</span>
        </header>
        <main className="flex-1 overflow-y-auto">
          <div className="w-full px-4 py-6 md:px-8 md:py-8">{children}</div>
        </main>
      </div>
    </div>
  )
}
