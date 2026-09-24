'use client'

import { useEffect, useState } from 'react'
import { Menu, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Logo, ROUTES, buttonClass } from './primitives'
import { getLenis } from './SmoothScroll'

const LINKS = [
  { label: 'Product', href: '/product' },
  { label: 'How it works', href: '/how-it-works' },
  { label: 'Workflows', href: '/workflows' },
  { label: 'Integrations', href: '/integrations' },
  { label: 'Pricing', href: '/pricing' },
  { label: 'FAQ', href: '/faq' },
]

export function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // Close the mobile menu on Escape or when the viewport grows past it.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    const mq = window.matchMedia('(min-width: 1024px)')
    const onResize = () => mq.matches && setOpen(false)
    window.addEventListener('keydown', onKey)
    mq.addEventListener('change', onResize)
    document.body.style.overflow = 'hidden'
    getLenis()?.stop()
    return () => {
      getLenis()?.start()
      window.removeEventListener('keydown', onKey)
      mq.removeEventListener('change', onResize)
      document.body.style.overflow = ''
    }
  }, [open])

  return (
    <header
      className={cn(
        'fixed inset-x-0 top-0 z-50 transition-[background,border-color,backdrop-filter] duration-300',
        scrolled || open
          ? 'border-b border-white/10 bg-[#0f2c2b]/80 backdrop-blur-xl'
          : 'border-b border-transparent'
      )}
    >
      {/* Padding sits outside the max-width, as in Section, so the nav aligns with page content. */}
      <div className="px-4 sm:px-6">
        <nav
          aria-label="Main"
          className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-4"
        >
          <a
            href="/"
            aria-label="Voicecon home"
            className="rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-200"
            onClick={() => setOpen(false)}
          >
            <Logo />
          </a>

          <ul className="hidden items-center gap-1 lg:flex">
            {LINKS.map((link) => (
              <li key={link.href}>
                <a
                  href={link.href}
                  className="rounded-full px-3.5 py-2 text-[15px] font-medium text-white/70 transition-colors hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-200"
                >
                  {link.label}
                </a>
              </li>
            ))}
          </ul>

          <div className="flex items-center gap-2">
            <a
              href={ROUTES.login}
              className="hidden rounded-full px-4 py-2 text-[15px] font-medium text-white/80 transition-colors hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-200 sm:inline-flex"
            >
              Log in
            </a>
            <a
              href={ROUTES.register}
              className={buttonClass('primary', 'md', 'hidden h-10 px-5 sm:inline-flex')}
            >
              Start free trial
            </a>
            <button
              type="button"
              className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/15 bg-white/[0.06] text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-200 lg:hidden"
              aria-expanded={open}
              aria-controls="mobile-menu"
              aria-label={open ? 'Close menu' : 'Open menu'}
              onClick={() => setOpen((v) => !v)}
            >
              {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </nav>
      </div>

      <div
        id="mobile-menu"
        hidden={!open}
        data-lenis-prevent
        className="h-[calc(100dvh-4rem)] overflow-y-auto border-t border-white/10 bg-[#0f2c2b] px-4 pb-8 pt-4 sm:px-6 lg:hidden"
      >
        <ul className="mx-auto flex max-w-6xl flex-col">
          {LINKS.map((link) => (
            <li key={link.href}>
              <a
                href={link.href}
                onClick={() => setOpen(false)}
                className="block border-b border-white/[0.07] py-4 text-lg font-medium text-white/85 hover:text-white"
              >
                {link.label}
              </a>
            </li>
          ))}
          <li>
            <a
              href={ROUTES.docs}
              className="block border-b border-white/[0.07] py-4 text-lg font-medium text-white/85 hover:text-white"
            >
              Docs
            </a>
          </li>
        </ul>
        <div className="mx-auto mt-6 flex max-w-6xl flex-col gap-3">
          <a href={ROUTES.register} className={buttonClass('primary', 'lg', 'w-full')}>
            Start free trial
          </a>
          <a href={ROUTES.login} className={buttonClass('ghost', 'lg', 'w-full')}>
            Log in
          </a>
        </div>
      </div>
    </header>
  )
}
