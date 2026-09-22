'use client'

import { useId, useState } from 'react'
import { Plus } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * FAQ accordion whose answers slide open and closed. Answers stay in the
 * server HTML (collapsed with a 0fr grid row, not removed), so crawlers still
 * read them; closed answers are aria-hidden (they hold no links or controls).
 */
export function FaqList({ items }: { items: { q: string; a: string }[] }) {
  const [open, setOpen] = useState<Set<number>>(() => new Set())
  const baseId = useId()

  const toggle = (i: number) =>
    setOpen((prev) => {
      const next = new Set(prev)
      if (next.has(i)) next.delete(i)
      else next.add(i)
      return next
    })

  return (
    <>
      {items.map((item, i) => {
        const isOpen = open.has(i)
        const buttonId = `${baseId}-q${i}`
        const panelId = `${baseId}-a${i}`
        return (
          <div key={item.q} className="px-5 sm:px-7">
            <h3>
              <button
                type="button"
                id={buttonId}
                aria-expanded={isOpen}
                aria-controls={panelId}
                onClick={() => toggle(i)}
                className="group flex w-full items-center justify-between gap-4 rounded-lg py-5 text-left text-base font-semibold text-white outline-none transition-colors hover:text-brand-100 focus-visible:ring-2 focus-visible:ring-brand-200 sm:text-[17px]"
              >
                {item.q}
                <span
                  className={cn(
                    'flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-white/70 transition-[transform,border-color,color] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none',
                    isOpen ? 'rotate-45 border-brand-300/50 text-brand-200' : 'border-white/15'
                  )}
                >
                  <Plus className="h-4 w-4" aria-hidden="true" />
                </span>
              </button>
            </h3>
            <div
              id={panelId}
              role="region"
              aria-labelledby={buttonId}
              aria-hidden={!isOpen}
              className={cn(
                'grid transition-[grid-template-rows,opacity] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none',
                isOpen ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'
              )}
            >
              <div className="overflow-hidden">
                <p
                  className={cn(
                    '-mt-1 pb-5 pr-10 text-[15px] leading-relaxed text-white/65 transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none',
                    isOpen ? 'translate-y-0' : '-translate-y-2'
                  )}
                >
                  {item.a}
                </p>
              </div>
            </div>
          </div>
        )
      })}
    </>
  )
}
