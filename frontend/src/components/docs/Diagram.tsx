import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/**
 * A left-to-right chain of labelled stages.
 *
 * Stacks vertically below `sm` with the connector rotated, so the same markup
 * reads correctly on a phone instead of overflowing off the side.
 *
 * Above `sm` the stages share the width equally and are allowed to shrink
 * (`flex-1` with `min-w-0`). A fixed minimum width was the obvious way to write
 * this and the wrong one: five stages at 124px need more room than the reading
 * column has once a sidebar and a contents rail are on screen, and the last
 * stage spilled out of the figure. Labels wrapping to two lines is the cheaper
 * compromise.
 */
export function Chain({
  stages,
}: {
  stages: { label: string; caption?: string; tone?: keyof typeof TONES }[]
}) {
  return (
    <div className="flex flex-col items-stretch gap-0 sm:flex-row sm:items-stretch">
      {stages.map((stage, index) => (
        <div
          key={stage.label}
          className="flex flex-col items-center sm:min-w-0 sm:flex-1 sm:flex-row sm:items-stretch"
        >
          <div
            className={cn(
              'flex w-full min-w-0 flex-1 flex-col justify-center rounded-xl border px-2.5 py-3 text-center',
              TONES[stage.tone ?? 'slate']
            )}
          >
            <span className="font-poppins text-[13px] font-bold leading-[1.25]">
              {stage.label}
            </span>
            {stage.caption && (
              <span className="mt-0.5 text-[11px] leading-[1.25] opacity-80">
                {stage.caption}
              </span>
            )}
          </div>
          {index < stages.length - 1 && (
            <span
              aria-hidden
              className="flex flex-shrink-0 items-center justify-center py-1.5 text-slate-300 sm:px-1.5 sm:py-0"
            >
              <span className="rotate-90 text-[14px] sm:rotate-0">→</span>
            </span>
          )}
        </div>
      ))}
    </div>
  )
}

const TONES = {
  slate: 'border-slate-200 bg-slate-50 text-slate-700',
  brand: 'border-brand-200 bg-brand-50 text-brand-800',
  blue: 'border-blue-200 bg-blue-50 text-blue-800',
  violet: 'border-violet-200 bg-violet-50 text-violet-800',
  amber: 'border-amber-200 bg-amber-50 text-amber-800',
  emerald: 'border-emerald-200 bg-emerald-50 text-emerald-800',
} as const

/**
 * A boxed illustration with a caption, for diagrams built from markup rather
 * than an image.
 */
export function Figure({
  caption,
  children,
}: {
  caption?: string
  children: ReactNode
}) {
  return (
    <figure className="rounded-xl border border-slate-200 bg-slate-50/60 px-4 py-5 sm:px-5">
      {children}
      {caption && (
        <figcaption className="mt-4 text-center text-[13px] leading-snug text-slate-500">
          {caption}
        </figcaption>
      )}
    </figure>
  )
}
