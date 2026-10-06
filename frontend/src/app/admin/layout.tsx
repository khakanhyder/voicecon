'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import {
  Activity,
  Building2,
  Coins,
  CreditCard,
  FileClock,
  FileText,
  FolderTree,
  Gauge,
  Hash,
  HeartHandshake,
  Inbox,
  KeyRound,
  Layers,
  LogOut,
  Menu,
  Newspaper,
  PenSquare,
  Phone,
  Plug,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  UserCog,
  Users,
  X,
  type LucideIcon,
} from 'lucide-react'
import { useAdminSession } from '@/hooks/useAdminSession'
import { adminApi, type ConsoleMe } from '@/lib/admin'
import { AdminNotificationBell } from '@/components/admin/AdminNotificationBell'
import { authService } from '@/lib/auth'
import { cn } from '@/lib/utils'

type NavItem = {
  name: string
  href: string
  icon: LucideIcon
  exact?: boolean
  /** Who sees it (see GET /admin/me). Defaults to platform admins only. */
  perm?: string
}

const NAV: { section: string; items: NavItem[] }[] = [
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
    section: 'Growth',
    items: [
      // exact: the sub-pages below have their own entries.
      { name: 'Affiliates', href: '/admin/affiliates', icon: HeartHandshake, exact: true },
      { name: 'Affiliate Requests', href: '/admin/affiliates/requests', icon: Inbox },
      { name: 'Commissions & Payouts', href: '/admin/affiliates/commissions', icon: Coins },
      { name: 'Affiliate Program', href: '/admin/affiliates/program', icon: SlidersHorizontal },
    ],
  },
  {
    section: 'Content',
    items: [
      { name: 'Blog Dashboard', href: '/admin/blog', icon: Newspaper, exact: true, perm: 'blog:read' },
      { name: 'All Posts', href: '/admin/blog/posts', icon: FileText, perm: 'blog:read' },
      { name: 'New Post', href: '/admin/blog/new', icon: PenSquare, exact: true, perm: 'blog:write' },
      { name: 'Categories', href: '/admin/blog/categories', icon: FolderTree, perm: 'blog:read' },
      { name: 'Blog Team', href: '/admin/blog/team', icon: UserCog, perm: 'blog:team' },
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

const BLOG_HOME = '/admin/blog'

/**
 * Pages a console user may open. Platform admins: all of them. Blog editors
 * and viewers: the blog section only, and within it what their role allows.
 * This only decides what the browser shows — the API refuses the same
 * requests on its own (app/core/admin.py).
 */
function canOpen(pathname: string, permissions: string[]): boolean {
  if (permissions.includes('admin')) return true
  if (pathname !== BLOG_HOME && !pathname.startsWith(BLOG_HOME + '/')) return false
  if (pathname.startsWith('/admin/blog/team')) return permissions.includes('blog:team')
  if (pathname === '/admin/blog/new') return permissions.includes('blog:write')
  return permissions.includes('blog:read')
}

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

/** Sidebar entries that show a count of things waiting for staff. */
const REQUESTS_HREF = '/admin/affiliates/requests'

const ROLE_LABEL: Record<ConsoleMe['role'], string> = {
  admin: 'Platform admin',
  blog_editor: 'Blog Editor',
  blog_viewer: 'Blog Viewer',
}

function Sidebar({
  me,
  onNavigate,
  showBell = false,
}: {
  me: ConsoleMe
  onNavigate?: () => void
  /** The desktop sidebar carries the bell; on phones it sits in the top bar instead. */
  showBell?: boolean
}) {
  const signOut = useAdminSignOut()
  const pathname = usePathname()
  const isAdmin = me.permissions.includes('admin')
  const requests = useQuery({
    queryKey: ['admin', 'affiliate-applications', 'count'],
    queryFn: adminApi.affiliateApplicationCount,
    refetchInterval: 60_000,
    retry: false,
    enabled: isAdmin,
  })
  const nav = NAV.map((group) => ({
    ...group,
    items: group.items.filter((item) => me.permissions.includes(item.perm ?? 'admin')),
  })).filter((group) => group.items.length > 0)
  const badges: Record<string, number> = { [REQUESTS_HREF]: requests.data?.pending ?? 0 }
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
          <p className="text-[11px] uppercase tracking-wider text-slate-400">
            {isAdmin ? 'Admin Console' : 'Content Console'}
          </p>
        </div>
        {showBell && isAdmin && (
          <div className="ml-auto">
            <AdminNotificationBell />
          </div>
        )}
      </div>

      <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
        {nav.map((group) => (
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
                    {badges[item.href] > 0 && (
                      <span
                        aria-label={`${badges[item.href]} waiting`}
                        className="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-brand-600 px-1.5 text-[11px] font-semibold text-white"
                      >
                        {badges[item.href] > 99 ? '99+' : badges[item.href]}
                      </span>
                    )}
                  </Link>
                )
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="flex-shrink-0 border-t border-white/10 p-3">
        <p className="truncate px-3 text-xs text-slate-500">{me.email}</p>
        <p className="px-3 pb-2 text-[11px] text-slate-600">{ROLE_LABEL[me.role]}</p>
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

  const allowed = !me.data || canOpen(pathname || '/admin', me.data.permissions)
  useEffect(() => {
    // A blog user who lands on an admin page (the default after sign-in is
    // /admin) goes to the blog dashboard instead of a wall of 403s.
    if (me.data && !allowed) router.replace(BLOG_HOME)
  }, [me.data, allowed, router])

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
            {forbidden ? 'Console access required' : 'Could not open the admin console'}
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            {forbidden
              ? 'This area is for Voicecon administrators and the blog team. Ask an admin to grant you access.'
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

  if (!me.data || !allowed) {
    return (
      <FullScreen>
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-brand-100 border-t-brand" />
      </FullScreen>
    )
  }
  const isAdmin = me.data.permissions.includes('admin')

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      <aside className="hidden w-64 flex-shrink-0 lg:block">
        <Sidebar me={me.data} showBell />
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
            <Sidebar me={me.data} onNavigate={() => setMobileOpen(false)} />
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
          <span className="text-sm font-semibold text-slate-900">{isAdmin ? 'Admin Console' : 'Content Console'}</span>
          {isAdmin && (
            <div className="ml-auto">
              <AdminNotificationBell align="right" tone="light" />
            </div>
          )}
        </header>
        {/* relative: keeps hidden, absolutely positioned form controls (Radix
            Select) inside this scroller. See dashboard/layout.tsx. */}
        <main className="relative flex-1 overflow-y-auto">
          <div className="w-full px-4 py-6 md:px-8 md:py-8">{children}</div>
        </main>
      </div>
    </div>
  )
}
