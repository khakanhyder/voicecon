'use client'

import { useEffect, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface TocItem {
  id: string
  title: string
}

/**
 * "On this page" navigation for a legal document. On large screens it sits in
 * a sticky rail and highlights the section being read; on smaller screens it
 * collapses into a disclosure above the text.
 */
export function LegalToc({ items }: { items: TocItem[] }) {
  const [active, setActive] = useState(items[0]?.id)

  useEffect(() => {
    const sections = items
      .map((item) => document.getElementById(item.id))
      .filter((el): el is HTMLElement => Boolean(el))
    if (!sections.length) return

    // The active section is the last one whose heading has passed the band
    // just below the fixed navbar.
    const update = () => {
      const line = 120
      let current = sections[0].id
      for (const section of sections) {
        if (section.getBoundingClientRect().top - line <= 0) current = section.id
      }
      setActive(current)
    }
    update()
    window.addEventListener('scroll', update, { passive: true })
    window.addEventListener('resize', update)
    return () => {
      window.removeEventListener('scroll', update)
      window.removeEventListener('resize', update)
    }
  }, [items])

  const list = (onNavigate?: () => void) => (
    <ol className="space-y-0.5">
      {items.map((item, i) => (
        <li key={item.id}>
          <a
            href={`#${item.id}`}
            onClick={onNavigate}
            aria-current={active === item.id ? 'location' : undefined}
            className={cn(
              'flex gap-2.5 rounded-lg border-l-2 py-1.5 pl-3 pr-2 text-sm leading-snug transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-200',
              active === item.id
                ? 'border-brand-300 bg-white/[0.05] font-medium text-white'
                : 'border-transparent text-white/55 hover:text-white'
            )}
          >
            <span className="w-5 shrink-0 tabular-nums text-white/35">{i + 1}.</span>
            {item.title}
          </a>
        </li>
      ))}
    </ol>
  )

  return (
    <>
      <details className="group rounded-2xl border border-white/10 bg-white/[0.04] lg:hidden [&_summary::-webkit-details-marker]:hidden">
        <summary className="flex cursor-pointer list-none items-center justify-between px-5 py-4 text-sm font-semibold text-white">
          On this page
          <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" aria-hidden="true" />
        </summary>
        <nav aria-label="On this page" className="border-t border-white/10 px-3 py-3">
          {list()}
        </nav>
      </details>

      <nav aria-label="On this page" className="hidden lg:block">
        <p className="mb-3 pl-3 text-xs font-semibold uppercase tracking-[0.12em] text-white/45">On this page</p>
        {list()}
      </nav>
    </>
  )
}
