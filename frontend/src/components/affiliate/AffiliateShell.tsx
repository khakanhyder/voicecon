'use client'

import { useEffect, useState, type ReactNode } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { LayoutDashboard, LogOut, PauseCircle, Users, Wallet, Receipt, type LucideIcon } from 'lucide-react'
import { VoiceconLogo } from '@/lib/icons'
import { affiliateAuth } from '@/lib/affiliate'
import { cn } from '@/lib/utils'
import { FullScreenSpinner } from './AuthFrame'
import { useAffiliateMe } from './useAffiliateMe'
import { primaryButtonClass, secondaryButtonClass } from './ui'

const NAV: { name: string; href: string; icon: LucideIcon; exact?: boolean }[] = [
  { name: 'Overview', href: '/affiliate', icon: LayoutDashboard, exact: true },
  { name: 'Referrals', href: '/affiliate/referrals', icon: Users },
  { name: 'Earnings', href: '/affiliate/earnings', icon: Receipt },
  { name: 'Payouts', href: '/affiliate/payouts', icon: Wallet },
]

/** Pages under /affiliate that render without the portal around them. */
const PUBLIC_PATHS = new Set(['/affiliate/login', '/affiliate/accept-invite'])

export function useAffiliateSignOut() {
  const router = useRouter()
  const queryClient = useQueryClient()
  return async () => {
    await affiliateAuth.logout()
    // Cancel first: an in-flight portal query would repopulate the cache.
    await queryClient.cancelQueries()
    queryClient.clear()
    router.replace('/affiliate/login')
  }
}

export function AffiliateLayoutSwitch({ children }: { children: ReactNode }) {
  const pathname = usePathname()
  if (pathname && PUBLIC_PATHS.has(pathname.replace(/\/$/, ''))) return <>{children}</>
  return <AffiliateShell>{children}</AffiliateShell>
}

function AffiliateShell({ children }: { children: ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const signOut = useAffiliateSignOut()
  // localStorage is only readable after mount; until then we don't know.
  const [signedIn, setSignedIn] = useState<boolean | null>(null)

  useEffect(() => {
    const ok = affiliateAuth.isSignedIn()
    setSignedIn(ok)
    if (!ok) router.replace(`/affiliate/login?redirect=${encodeURIComponent(pathname || '/affiliate')}`)
  }, [router, pathname])

  const me = useAffiliateMe(signedIn === true)

  if (signedIn !== true || me.isLoading) return <FullScreenSpinner />

  if (me.isError) {
    const status = axios.isAxiosError(me.error) ? me.error.response?.status : undefined
    const paused = status === 403
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
        <div className="max-w-sm text-center">
          <span
            className={cn(
              'mx-auto flex h-12 w-12 items-center justify-center rounded-full',
              paused ? 'bg-amber-50 text-amber-600' : 'bg-slate-100 text-slate-500'
            )}
          >
            <PauseCircle className="h-6 w-6" />
          </span>
          <h1 className="mt-4 text-lg font-semibold text-slate-900">
            {paused ? 'Your affiliate account is paused' : 'We couldn’t open the partner portal'}
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            {paused
              ? 'Your referral links and coupon aren’t active right now. Contact us if you think this is a mistake.'
              : 'Something went wrong on our side. Please try again in a moment.'}
          </p>
          <div className="mt-6 flex justify-center gap-2">
            {!paused && (
              <button type="button" onClick={() => me.refetch()} className={primaryButtonClass}>
                Try again
              </button>
            )}
            <button type="button" onClick={signOut} className={paused ? primaryButtonClass : secondaryButtonClass}>
              Sign out
            </button>
          </div>
        </div>
      </div>
    )
  }

  const data = me.data
  const isActive = (href: string, exact?: boolean) =>
    exact ? pathname === href : pathname === href || !!pathname?.startsWith(href + '/')

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-4 sm:px-6">
          <Link href="/affiliate" className="flex flex-shrink-0 items-center gap-2">
            <VoiceconLogo className="h-7 w-7" />
            <span className="text-lg font-bold text-slate-900">VoiceCon</span>
            <span className="hidden rounded-full bg-[#243275]/10 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-[#243275] sm:inline">
              Partners
            </span>
          </Link>
          <div className="ml-auto flex min-w-0 items-center gap-3">
            <div className="hidden min-w-0 text-right leading-tight sm:block">
              <p className="truncate text-sm font-semibold text-slate-900">{data?.name}</p>
              {data?.email && <p className="truncate text-xs text-slate-500">{data.email}</p>}
            </div>
            <button
              type="button"
              onClick={signOut}
              className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
            >
              <LogOut className="h-4 w-4" />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </div>
        <nav className="mx-auto max-w-6xl overflow-x-auto px-4 sm:px-6" aria-label="Partner portal">
          <div className="flex gap-1">
            {NAV.map((item) => {
              const active = isActive(item.href, item.exact)
              const Icon = item.icon
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? 'page' : undefined}
                  className={cn(
                    '-mb-px flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-3 text-sm font-medium transition-colors',
                    active
                      ? 'border-[#243275] text-[#243275]'
                      : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-800'
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {item.name}
                </Link>
              )
            })}
          </div>
        </nav>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">{children}</main>
    </div>
  )
}
