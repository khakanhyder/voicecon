'use client'

import { useEffect, useState } from 'react'
import type { DocSection } from '@/lib/docs/navigation'
import { cn } from '@/lib/utils'

/**
 * On-page table of contents with scroll-spy.
 *
 * Uses IntersectionObserver against a band near the top of the viewport rather
 * than scroll offsets, so the highlight tracks the heading a reader is
 * actually looking at instead of lagging behind by a viewport height. The
 * observer is rebuilt when `sections` changes because each docs page mounts
 * this with a different set.
 */
export function TableOfContents({ sections }: { sections: DocSection[] }) {
  const [activeId, setActiveId] = useState<string>('')

  useEffect(() => {
    if (sections.length === 0) return

    const headings = sections
      .map((section) => document.getElementById(section.id))
      .filter((element): element is HTMLElement => element !== null)

    if (headings.length === 0) return

    const observer = new IntersectionObserver(
      (entries) => {
        // Several headings can be inside the band at once; the topmost one is
        // the section being read.
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)

        if (visible.length > 0) {
          setActiveId(visible[0].target.id)
          return
        }

        // Nothing in the band — happens when a long section fills the screen.
        // Fall back to the last heading scrolled past so the rail never blanks.
        const scrolledPast = headings.filter(
          (heading) => heading.getBoundingClientRect().top < 120
        )
        if (scrolledPast.length > 0) {
          setActiveId(scrolledPast[scrolledPast.length - 1].id)
        }
      },
      { rootMargin: '-100px 0px -70% 0px', threshold: 0 }
    )

    headings.forEach((heading) => observer.observe(heading))
    return () => observer.disconnect()
  }, [sections])

  if (sections.length === 0) return null

  return (
    <nav aria-label="On this page">
      <p className="px-3.5 font-poppins text-[11px] font-bold uppercase tracking-[0.07em] text-slate-400">
        On this page
      </p>
      <ul className="mt-3 space-y-px border-l border-slate-200">
        {sections.map((section) => {
          const active = activeId === section.id
          return (
            <li key={section.id}>
              <a
                href={`#${section.id}`}
                className={cn(
                  '-ml-px block border-l-2 py-[5px] pl-3.5 pr-2 text-[13px] leading-[1.45] transition-colors',
                  active
                    ? 'border-brand-500 font-medium text-brand-700'
                    : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-900'
                )}
              >
                {section.title}
              </a>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
