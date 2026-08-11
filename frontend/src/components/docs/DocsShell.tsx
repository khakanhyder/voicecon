'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { ChevronRight, Menu, Search, X } from 'lucide-react'
import { DOCS_NAV } from '@/lib/docs/navigation'
import { cn } from '@/lib/utils'
import { DocsSearch } from './DocsSearch'

/**
 * The documentation chrome: header, sidebar, content.
 *
 * Deliberately the conventional documentation arrangement rather than anything
 * novel. A reader arriving at a reference site already knows where the nav,
 * the search, and the contents live; spending that familiarity on a bespoke
 * layout costs them time and buys nothing. What makes this Voicecon's is the
 * typography, the restraint of the palette, and the density — not the frame.
 *
 * Groups collapse. Thirty-five links expanded at once is a scroll rather than
 * a menu, so only the section being read is open.
 */
export function DocsShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const [navOpen, setNavOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)

  useEffect(() => {
    setNavOpen(false)
  }, [pathname])

  // Lock body scroll behind the drawer so a swipe moves the menu, not the page.
  useEffect(() => {
    if (!navOpen) return
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previous
    }
  }, [navOpen])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setSearchOpen(true)
      }
      if (event.key === '/' && !isTypingTarget(event.target)) {
        event.preventDefault()
        setSearchOpen(true)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  return (
    <div className="min-h-screen bg-white">
      <DocsSearch open={searchOpen} onOpenChange={setSearchOpen} />

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-[60px] max-w-[1600px] items-center gap-4 px-4 sm:px-6 lg:px-8">
          <button
            type="button"
            onClick={() => setNavOpen(true)}
            aria-label="Open navigation"
            className="-ml-1.5 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-slate-100 lg:hidden"
          >
            <Menu className="h-5 w-5" />
          </button>

          <Wordmark />

          <div className="flex-1" />

          {/* Search is the primary way people use reference docs, so it gets
              real estate rather than an icon. */}
          <button
            type="button"
            onClick={() => setSearchOpen(true)}
            className="hidden h-9 w-[260px] items-center gap-2.5 rounded-lg border border-slate-200 bg-slate-50 pl-3 pr-2 text-slate-400 transition-colors hover:border-slate-300 hover:bg-white sm:flex xl:w-[320px]"
          >
            <Search className="h-4 w-4 flex-shrink-0" />
            <span className="flex-1 text-left text-[13.5px]">Search documentation…</span>
            <kbd className="rounded border border-slate-200 bg-white px-1.5 py-0.5 font-sans text-[11px] text-slate-400">
              ⌘K
            </kbd>
          </button>
          <button
            type="button"
            onClick={() => setSearchOpen(true)}
            aria-label="Search documentation"
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition-colors hover:border-slate-300 sm:hidden"
          >
            <Search className="h-4 w-4" />
          </button>

          <nav className="hidden items-center gap-1 md:flex">
            <Link
              href="/docs/api"
              className="rounded-lg px-3 py-2 text-[13.5px] font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
            >
              API
            </Link>
            <Link
              href="/dashboard"
              className="ml-1 flex h-9 items-center rounded-lg bg-brand-600 px-4 font-poppins text-[13.5px] font-semibold text-white transition-colors hover:bg-brand-700"
            >
              Dashboard
            </Link>
          </nav>
        </div>
      </header>

      <div className="mx-auto flex max-w-[1600px] px-4 sm:px-6 lg:px-8">
        {/* ── Sidebar ───────────────────────────────────────────────────── */}
        <aside className="sticky top-[60px] hidden h-[calc(100vh-60px)] w-[262px] flex-shrink-0 overflow-y-auto py-8 pr-8 lg:block">
          <SidebarNav pathname={pathname} />
        </aside>

        <div className="min-w-0 flex-1 lg:border-l lg:border-slate-200 lg:pl-10 xl:pl-14">
          {children}
        </div>
      </div>

      {/* ── Mobile drawer ─────────────────────────────────────────────── */}
      {navOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-slate-900/40"
            onClick={() => setNavOpen(false)}
            aria-hidden
          />
          <div className="absolute inset-y-0 left-0 flex w-[300px] max-w-[86vw] flex-col bg-white shadow-2xl">
            <div className="flex h-[60px] flex-shrink-0 items-center justify-between border-b border-slate-200 px-5">
              <Wordmark />
              <button
                type="button"
                onClick={() => setNavOpen(false)}
                aria-label="Close navigation"
                className="-mr-1.5 flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-5 py-6">
              <SidebarNav pathname={pathname} />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Grouped, collapsible navigation.
 *
 * The group containing the current page is open; the rest are shut until
 * asked for. Opening one does not close another — a reader comparing two
 * sections should not have to keep reopening the one they just left.
 */
function SidebarNav({ pathname }: { pathname: string | null }) {
  const activeGroupTitle = useMemo(
    () => DOCS_NAV.find((group) => group.pages.some((page) => page.href === pathname))?.title,
    [pathname]
  )

  const [manuallyToggled, setManuallyToggled] = useState<Record<string, boolean>>({})

  const isOpen = (title: string) =>
    manuallyToggled[title] ?? title === activeGroupTitle

  return (
    <nav aria-label="Documentation">
      <ul className="space-y-0.5">
        {DOCS_NAV.map((group) => {
          const open = isOpen(group.title)
          const isActiveGroup = group.title === activeGroupTitle
          return (
            <li key={group.title}>
              <button
                type="button"
                aria-expanded={open}
                onClick={() =>
                  setManuallyToggled((current) => ({ ...current, [group.title]: !open }))
                }
                className={cn(
                  'flex w-full items-center gap-1.5 rounded-lg py-[7px] pl-2 pr-2 text-left font-poppins text-[13.5px] font-semibold transition-colors',
                  isActiveGroup
                    ? 'text-slate-900'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                )}
              >
                <ChevronRight
                  className={cn(
                    'h-3.5 w-3.5 flex-shrink-0 text-slate-400 transition-transform',
                    open && 'rotate-90'
                  )}
                />
                {group.title}
              </button>

              {open && (
                <ul className="mb-1 ml-[15px] space-y-px border-l border-slate-200 pl-3">
                  {group.pages.map((page) => {
                    const active = pathname === page.href
                    return (
                      <li key={page.href} className="relative">
                        {active && (
                          <span className="absolute -left-[13px] top-1/2 h-[18px] w-[2px] -translate-y-1/2 rounded-full bg-brand-600" />
                        )}
                        <Link
                          href={page.href}
                          aria-current={active ? 'page' : undefined}
                          className={cn(
                            'block rounded-md py-[6px] pl-2.5 pr-2 text-[13.5px] leading-[1.45] transition-colors',
                            active
                              ? 'font-semibold text-brand-700'
                              : 'text-slate-500 hover:text-slate-900'
                          )}
                        >
                          {page.title}
                        </Link>
                      </li>
                    )
                  })}
                </ul>
              )}
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

function Wordmark() {
  return (
    <Link href="/docs" className="flex flex-shrink-0 items-center gap-2.5">
      <span className="flex h-[26px] w-[26px] items-center justify-center rounded-lg bg-brand-600 font-poppins text-[13.5px] font-bold text-white">
        V
      </span>
      <span className="font-poppins text-[15.5px] font-bold tracking-[-0.015em] text-slate-900">
        Voicecon
      </span>
      <span className="hidden rounded-md bg-slate-100 px-1.5 py-0.5 font-poppins text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-500 sm:inline">
        Docs
      </span>
    </Link>
  )
}

/** True when the event target is a field the "/" shortcut must not hijack. */
function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  const tag = target.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable
}
