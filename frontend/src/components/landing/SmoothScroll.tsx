'use client'

import { useEffect } from 'react'
import Lenis from 'lenis'
import 'lenis/dist/lenis.css'
import { sectionForPath } from './sections'

/**
 * Eased, inertial scrolling for the marketing pages, plus smooth scrolling to
 * in-page anchors (navbar, footer and hero links), up or down the page.
 *
 * Sections have clean URLs (/pricing, /faq; see sections.ts) that all render
 * the home page. A click on one while the home page is showing glides to the
 * section and updates the address bar without a reload; opening one directly,
 * or going back/forward between them, lands on the section too.
 *
 * Targets land at their scroll-margin-top, so headings sit below the fixed
 * navbar. If Lenis is off (reduced motion, or it failed to start) anchor clicks
 * still glide there with the browser's own smooth scroll, and visitors who
 * prefer reduced motion get an instant jump to the same spot.
 */

let lenis: Lenis | null = null

/** The active Lenis instance, if smooth scrolling is on (e.g. to pause it behind a menu). */
export function getLenis() {
  return lenis
}

const DURATION = 1.2

function scrollToY(y: number, reduced: boolean) {
  if (lenis) lenis.scrollTo(y, { duration: DURATION, force: true })
  else window.scrollTo({ top: y, behavior: reduced ? 'auto' : 'smooth' })
}

/** Document Y a section should scroll to, honouring its scroll-margin-top. */
function targetY(el: HTMLElement) {
  const margin = Number.parseFloat(getComputedStyle(el).scrollMarginTop) || 0
  return Math.max(0, el.getBoundingClientRect().top + window.scrollY - margin)
}

/** The page a path renders: every section URL is the home page. */
const pageOf = (pathname: string) => (sectionForPath(pathname) ? '/' : pathname)

/** The element a URL points at: its section path, else its #hash. */
function targetFor(url: URL) {
  const id = sectionForPath(url.pathname) ?? (url.hash ? decodeURIComponent(url.hash.slice(1)) : '')
  return id ? document.getElementById(id) : null
}

export function SmoothScroll() {
  useEffect(() => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    let instance: Lenis | null = null
    if (!reduced) {
      try {
        instance = new Lenis({ autoRaf: true, lerp: 0.1 })
        lenis = instance
      } catch {
        // Native scrolling still works; anchor clicks fall back to it below.
      }
    }

    const onClick = (e: MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return
      const link = (e.target as Element | null)?.closest?.('a[href]') as HTMLAnchorElement | null
      if (!link || (link.target && link.target !== '_self') || link.hasAttribute('download')) return

      const url = new URL(link.href, window.location.href)
      if (url.origin !== window.location.origin || pageOf(url.pathname) !== pageOf(window.location.pathname)) return

      const href = url.pathname + url.search + url.hash
      const current = window.location.pathname + window.location.search + window.location.hash

      // A link to this page with no section or hash (the logo) glides back to the top.
      if (!sectionForPath(url.pathname) && !url.hash) {
        if (url.search !== window.location.search) return
        e.preventDefault()
        scrollToY(0, reduced)
        if (href !== current) history.pushState(null, '', href)
        return
      }

      const target = targetFor(url)
      if (!target) return
      e.preventDefault()
      scrollToY(targetY(target), reduced)
      if (href !== current) history.pushState(null, '', href)
      // Move focus too, as a native jump would, so keyboard and screen reader
      // users continue from the section they asked for.
      if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1')
      target.focus({ preventScroll: true })
    }

    // Opened directly on a section URL (voicecon.ai/pricing): jump there once
    // the page has laid out.
    const initial = sectionForPath(window.location.pathname) ? targetFor(new URL(window.location.href)) : null
    let frame = 0
    if (initial) {
      frame = requestAnimationFrame(() => {
        const y = targetY(initial)
        if (lenis) lenis.scrollTo(y, { immediate: true, force: true })
        else window.scrollTo({ top: y })
      })
    }

    // Back/forward between section URLs we pushed: follow along.
    const onPopState = () => {
      const url = new URL(window.location.href)
      if (pageOf(url.pathname) !== '/') return
      const target = targetFor(url)
      scrollToY(target ? targetY(target) : 0, reduced)
    }

    document.addEventListener('click', onClick)
    window.addEventListener('popstate', onPopState)
    return () => {
      cancelAnimationFrame(frame)
      document.removeEventListener('click', onClick)
      window.removeEventListener('popstate', onPopState)
      instance?.destroy()
      if (lenis === instance) lenis = null
    }
  }, [])

  return null
}
