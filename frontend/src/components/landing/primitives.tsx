import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { Reveal } from './Reveal'

/**
 * Shared building blocks for the marketing page. The visual language (deep
 * teal night sky, glass cards, brand-green pill buttons, gradient accent text)
 * follows the voicecon.ai coming-soon page.
 */

// App routes. On the landing hosts the middleware forwards these to the app
// host, so relative links stay correct in every environment.
export const ROUTES = {
  register: '/register',
  login: '/login',
  docs: '/docs',
  quickstart: '/docs/quickstart',
  api: '/docs/api',
} as const

const BUTTON_BASE =
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full font-semibold transition-[background,border-color,color,box-shadow,transform] duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-200 focus-visible:ring-offset-2 focus-visible:ring-offset-[#10302f] active:scale-[0.98]'

const BUTTON_SIZES = {
  md: 'h-11 px-5 text-[15px]',
  lg: 'h-[52px] px-7 text-base',
} as const

const BUTTON_VARIANTS = {
  primary:
    'bg-gradient-to-r from-brand-400 to-brand-600 text-white shadow-[0_10px_30px_-6px_rgba(47,155,126,0.6)] hover:from-brand-300 hover:to-brand-500 hover:shadow-[0_14px_36px_-6px_rgba(47,155,126,0.75)]',
  ghost:
    'border border-white/15 bg-white/[0.06] text-white backdrop-blur hover:border-brand-300/50 hover:bg-white/10',
} as const

export function buttonClass(
  variant: keyof typeof BUTTON_VARIANTS = 'primary',
  size: keyof typeof BUTTON_SIZES = 'md',
  className?: string
) {
  return cn(BUTTON_BASE, BUTTON_SIZES[size], BUTTON_VARIANTS[variant], className)
}

/** Mic mark + wordmark, matching the coming-soon page. */
export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn('flex items-center gap-2.5 text-white', className)}>
      <svg
        width="30"
        height="30"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#63b9a0"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
        <line x1="12" x2="12" y1="19" y2="22" />
      </svg>
      <span className="text-xl font-bold tracking-[-0.01em]">Voicecon</span>
    </span>
  )
}

/** Small uppercase pill that sits above section headings. */
export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 rounded-full border border-brand-300/30 bg-brand-500/10 px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-brand-200 backdrop-blur',
        className
      )}
    >
      {children}
    </span>
  )
}

/** Animated brand gradient used for the emphasised words in headings. */
export function Accent({ children }: { children: ReactNode }) {
  return (
    <span className="animate-gradient-pan bg-gradient-to-r from-brand-300 via-brand-200 to-brand-300 bg-[length:200%_auto] bg-clip-text text-transparent motion-reduce:animate-none">
      {children}
    </span>
  )
}

export function Section({
  id,
  children,
  className,
  labelledBy,
}: {
  id?: string
  children: ReactNode
  className?: string
  labelledBy?: string
}) {
  return (
    <section
      id={id}
      aria-labelledby={labelledBy}
      className={cn('relative scroll-mt-20 px-4 py-20 focus:outline-none sm:px-6 md:py-28', className)}
    >
      <div className="mx-auto w-full max-w-6xl">{children}</div>
    </section>
  )
}

export function SectionHeading({
  id,
  eyebrow,
  title,
  description,
  align = 'center',
}: {
  id: string
  eyebrow: string
  title: ReactNode
  description?: ReactNode
  align?: 'center' | 'left'
}) {
  return (
    <Reveal
      className={cn(
        'max-w-2xl',
        align === 'center' ? 'mx-auto text-center' : 'text-left'
      )}
    >
      <Eyebrow>{eyebrow}</Eyebrow>
      <h2
        id={id}
        className="mt-5 text-balance text-[clamp(1.875rem,4.2vw,2.75rem)] font-bold leading-[1.12] tracking-[-0.02em] text-white"
      >
        {title}
      </h2>
      {description && (
        <p className="mt-4 text-base leading-relaxed text-white/65 sm:text-lg">{description}</p>
      )}
    </Reveal>
  )
}

/** Glass card with the soft green hover glow from the coming-soon features. */
export function GlassCard({
  children,
  className,
  interactive = true,
}: {
  children: ReactNode
  className?: string
  interactive?: boolean
}) {
  return (
    <div
      className={cn(
        'relative overflow-hidden rounded-3xl border border-white/[0.08] bg-gradient-to-b from-white/[0.06] to-white/[0.02] shadow-[inset_0_1px_0_rgba(255,255,255,0.05),0_18px_40px_-24px_rgba(0,0,0,0.6)]',
        interactive &&
          'group transition-[transform,border-color,box-shadow] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] hover:-translate-y-1 hover:border-brand-300/35 hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.08),0_30px_60px_-28px_rgba(0,0,0,0.75)] motion-reduce:hover:translate-y-0',
        className
      )}
    >
      {interactive && (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute -top-24 left-1/2 h-56 w-56 -translate-x-1/2 rounded-full bg-[radial-gradient(circle,rgba(47,224,138,0.16)_0%,transparent_70%)] opacity-0 transition-opacity duration-500 group-hover:opacity-100"
        />
      )}
      {children}
    </div>
  )
}

/** Rounded icon well used on feature cards. */
export function IconWell({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        'flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-brand-300/25 bg-brand-500/15 text-brand-200',
        className
      )}
    >
      {children}
    </span>
  )
}
