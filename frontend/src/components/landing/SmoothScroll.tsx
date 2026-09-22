'use client'

import { useEffect } from 'react'
import Lenis from 'lenis'
import 'lenis/dist/lenis.css'

/**
 * Eased, inertial scrolling for the marketing pages, plus smooth scrolling to
 * in-page anchors (navbar, footer and hero links), up or down the page.
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
      if (url.origin !== window.location.origin || url.pathname !== window.location.pathname) return

      // A link to this page without a hash (the logo) glides back to the top.
      if (!url.hash) {
        if (url.search !== window.location.search) return
        e.preventDefault()
        scrollToY(0, reduced)
        history.pushState(null, '', url.pathname + url.search)
        return
      }

      const target = document.getElementById(decodeURIComponent(url.hash.slice(1)))
      if (!target) return
      e.preventDefault()
      scrollToY(targetY(target), reduced)
      if (url.hash !== window.location.hash) history.pushState(null, '', url.hash)
      // Move focus too, as a native jump would, so keyboard and screen reader
      // users continue from the section they asked for.
      if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1')
      target.focus({ preventScroll: true })
    }

    document.addEventListener('click', onClick)
    return () => {
      document.removeEventListener('click', onClick)
      instance?.destroy()
      if (lenis === instance) lenis = null
    }
  }, [])

  return null
}
