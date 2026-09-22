import type { ReactNode } from 'react'
import { Navbar } from './Navbar'
import { Footer } from './Closing'
import { SmoothScroll } from './SmoothScroll'

/**
 * Page chrome shared by every public marketing page (landing, privacy, terms):
 * the coming-soon page's deep-teal sky with its grid and glow orbs, a skip
 * link, the navbar, the footer and smooth scrolling.
 */
export function MarketingShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-screen overflow-x-clip bg-[#10302f] bg-[radial-gradient(120%_90%_at_50%_-10%,#1c5453_0%,#16403f_45%,#10302f_100%)] text-white antialiased">
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 z-0">
        <div className="absolute inset-0 opacity-[0.15] [background-image:linear-gradient(rgba(255,255,255,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.08)_1px,transparent_1px)] [background-size:54px_54px] [mask-image:radial-gradient(circle_at_50%_30%,black,transparent_78%)]" />
        <div className="absolute -top-40 left-[calc(50%-280px)] h-[560px] w-[560px] animate-glow-pulse rounded-full bg-[radial-gradient(circle,rgba(47,155,126,0.55),transparent_65%)] blur-[70px] motion-reduce:animate-none" />
        <div className="absolute -left-32 top-1/3 h-[420px] w-[420px] animate-glow-pulse rounded-full bg-[radial-gradient(circle,rgba(36,50,117,0.45),transparent_65%)] blur-[70px] [animation-delay:2s] motion-reduce:animate-none" />
        <div className="absolute -right-32 bottom-0 h-[460px] w-[460px] animate-glow-pulse rounded-full bg-[radial-gradient(circle,rgba(19,128,102,0.5),transparent_65%)] blur-[70px] [animation-delay:4s] motion-reduce:animate-none" />
      </div>

      <a
        href="#main"
        className="sr-only z-[60] rounded-full bg-white px-4 py-2 text-sm font-semibold text-[#10302f] focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        Skip to content
      </a>

      <SmoothScroll />
      <Navbar />

      <main id="main" className="relative z-10 focus:outline-none">
        {children}
      </main>

      <div className="relative z-10">
        <Footer />
      </div>
    </div>
  )
}
