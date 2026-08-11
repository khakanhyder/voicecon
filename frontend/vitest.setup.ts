/**
 * Global test setup.
 *
 * Everything here exists because jsdom is not a browser: it has no layout
 * engine, no network, and no Next.js router. Each stub below replaces a browser
 * or framework API that components legitimately use and jsdom does not provide,
 * so a missing one shows up as a crash rather than a meaningful failure.
 */
import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// React Testing Library mounts into a container per test; without this the
// previous test's DOM stays mounted and queries match two copies of everything.
afterEach(() => {
  cleanup()
})

// jsdom implements neither of these, and any component that measures itself or
// watches for viewport entry throws on mount without them.
class MockObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return []
  }
}

vi.stubGlobal('ResizeObserver', MockObserver)
vi.stubGlobal('IntersectionObserver', MockObserver)

// Used by Radix and by anything responsive. jsdom has no media query engine.
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
})

// Radix uses these for focus management inside portals.
if (!window.HTMLElement.prototype.scrollIntoView) {
  window.HTMLElement.prototype.scrollIntoView = () => {}
}
if (!window.HTMLElement.prototype.hasPointerCapture) {
  window.HTMLElement.prototype.hasPointerCapture = () => false
}
if (!window.HTMLElement.prototype.releasePointerCapture) {
  window.HTMLElement.prototype.releasePointerCapture = () => {}
}
