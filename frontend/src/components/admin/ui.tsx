'use client'

/**
 * Building blocks for the platform admin console.
 *
 * Kept deliberately small and local: the admin area is a dense, table-heavy
 * surface with different needs from the customer dashboard, so these do not
 * try to be general-purpose.
 */
import { ReactNode, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Inbox,
  Loader2,
  Search,
  X,
  XCircle,
  type LucideIcon,
} from 'lucide-react'
import { cn } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

/** The API sends naive UTC timestamps; without a zone JS would read them as local. */
export function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null
  const hasZone = /[zZ]|[+-]\d{2}:?\d{2}$/.test(value)
  const d = new Date(hasZone ? value : `${value}Z`)
  return Number.isNaN(d.getTime()) ? null : d
}

export function formatDate(value: string | null | undefined, withTime = false): string {
  const d = parseDate(value)
  if (!d) return '—'
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    ...(withTime ? { hour: '2-digit', minute: '2-digit' } : {}),
  })
}

export function timeAgo(value: string | null | undefined): string {
  const d = parseDate(value)
  if (!d) return '—'
  const seconds = Math.round((Date.now() - d.getTime()) / 1000)
  const future = seconds < 0
  const s = Math.abs(seconds)
  const units: [number, string][] = [
    [60 * 60 * 24 * 365, 'y'],
    [60 * 60 * 24 * 30, 'mo'],
    [60 * 60 * 24, 'd'],
    [60 * 60, 'h'],
    [60, 'm'],
  ]
  for (const [size, label] of units) {
    if (s >= size) {
      const n = Math.floor(s / size)
      return future ? `in ${n}${label}` : `${n}${label} ago`
    }
  }
  return future ? 'in a moment' : 'just now'
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return '—'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m ? `${m}m ${s.toString().padStart(2, '0')}s` : `${s}s`
}

export function formatNumber(n: number | null | undefined): string {
  if (n == null) return '—'
  return n.toLocaleString()
}

export function formatMoney(n: number | null | undefined, currency = 'usd'): string {
  if (n == null) return '—'
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: currency.toUpperCase(),
    maximumFractionDigits: n % 1 === 0 ? 0 : 2,
  }).format(n)
}

export function formatLimit(n: number | null | undefined): string {
  if (n == null) return '—'
  return n === -1 ? 'Unlimited' : n.toLocaleString()
}

export function humanize(value: string | null | undefined): string {
  if (!value) return '—'
  return value.replace(/[_-]+/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
}

/**
 * A query-string value from the live URL. Read directly rather than through
 * `useSearchParams`, which needs a Suspense boundary to build; admin pages only
 * render client-side behind the Providers mount gate anyway.
 */
export function initialParam(name: string): string {
  if (typeof window === 'undefined') return ''
  return new URLSearchParams(window.location.search).get(name) ?? ''
}

// ---------------------------------------------------------------------------
// Layout
// ---------------------------------------------------------------------------

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string
  description?: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-sm text-slate-500">{description}</p>}
      </div>
      {actions && <div className="flex flex-shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function Panel({
  title,
  description,
  actions,
  children,
  className,
  bodyClassName,
}: {
  title?: ReactNode
  description?: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
}) {
  return (
    <section className={cn('rounded-xl border border-slate-200 bg-white shadow-sm', className)}>
      {(title || actions) && (
        <header className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
          <div className="min-w-0">
            {title && <h2 className="text-sm font-semibold text-slate-900">{title}</h2>}
            {description && <p className="mt-0.5 text-xs text-slate-500">{description}</p>}
          </div>
          {actions && <div className="flex flex-shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cn('p-5', bodyClassName)}>{children}</div>
    </section>
  )
}

export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = 'default',
}: {
  label: string
  value: ReactNode
  hint?: ReactNode
  icon?: LucideIcon
  tone?: 'default' | 'warning' | 'danger' | 'success'
}) {
  const toneRing = {
    default: 'bg-slate-100 text-slate-600',
    success: 'bg-emerald-50 text-emerald-700',
    warning: 'bg-amber-50 text-amber-700',
    danger: 'bg-rose-50 text-rose-700',
  }[tone]
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
        {Icon && (
          <span className={cn('flex h-8 w-8 items-center justify-center rounded-lg', toneRing)}>
            <Icon className="h-4 w-4" />
          </span>
        )}
      </div>
      <p className="mt-2 text-2xl font-semibold tabular-nums text-slate-900">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Badges
// ---------------------------------------------------------------------------

export type Tone = 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'brand'

const TONES: Record<Tone, string> = {
  neutral: 'bg-slate-100 text-slate-700 ring-slate-200',
  success: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  warning: 'bg-amber-50 text-amber-800 ring-amber-200',
  danger: 'bg-rose-50 text-rose-700 ring-rose-200',
  info: 'bg-sky-50 text-sky-700 ring-sky-200',
  brand: 'bg-brand-50 text-brand-700 ring-brand-200',
}

const DOTS: Record<Tone, string> = {
  neutral: 'bg-slate-400',
  success: 'bg-emerald-500',
  warning: 'bg-amber-500',
  danger: 'bg-rose-500',
  info: 'bg-sky-500',
  brand: 'bg-brand-500',
}

export function Badge({ tone = 'neutral', children, dot = false }: { tone?: Tone; children: ReactNode; dot?: boolean }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset',
        TONES[tone]
      )}
    >
      {dot && <span className={cn('h-1.5 w-1.5 rounded-full', DOTS[tone])} />}
      {children}
    </span>
  )
}

const STATUS_TONES: Record<string, Tone> = {
  // subscriptions
  active: 'success',
  trialing: 'info',
  past_due: 'warning',
  grace: 'warning',
  expired: 'danger',
  canceled: 'neutral',
  incomplete: 'neutral',
  none: 'neutral',
  // calls
  completed: 'success',
  'in-progress': 'info',
  in_progress: 'info',
  ringing: 'info',
  initiated: 'neutral',
  queued: 'neutral',
  failed: 'danger',
  busy: 'warning',
  'no-answer': 'warning',
  no_answer: 'warning',
  error: 'danger',
  // connections / runs
  connected: 'success',
  success: 'success',
  running: 'info',
  pending: 'neutral',
  released: 'neutral',
  inactive: 'neutral',
}

export function StatusBadge({ status, label }: { status: string | null | undefined; label?: string }) {
  const key = (status || 'none').toLowerCase()
  return (
    <Badge tone={STATUS_TONES[key] ?? 'neutral'} dot>
      {label ?? humanize(key === 'none' ? 'No plan' : key)}
    </Badge>
  )
}

// ---------------------------------------------------------------------------
// Tables
// ---------------------------------------------------------------------------

export function Table({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('overflow-x-auto', className)}>
      <table className="min-w-full divide-y divide-slate-100 text-sm">{children}</table>
    </div>
  )
}

export function Th({ children, className }: { children?: ReactNode; className?: string }) {
  return (
    <th
      scope="col"
      className={cn(
        'whitespace-nowrap bg-slate-50/70 px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-500',
        className
      )}
    >
      {children}
    </th>
  )
}

export function Td({ children, className, colSpan }: { children?: ReactNode; className?: string; colSpan?: number }) {
  return (
    <td colSpan={colSpan} className={cn('whitespace-nowrap px-4 py-3 align-middle text-slate-700', className)}>
      {children}
    </td>
  )
}

export function Tr({ children, onClick, className }: { children: ReactNode; onClick?: () => void; className?: string }) {
  return (
    <tr
      onClick={onClick}
      className={cn('transition-colors', onClick && 'cursor-pointer hover:bg-slate-50', className)}
    >
      {children}
    </tr>
  )
}

export function TableState({
  colSpan,
  loading,
  error,
  empty,
  emptyText = 'Nothing here yet.',
}: {
  colSpan: number
  loading?: boolean
  error?: unknown
  empty?: boolean
  emptyText?: string
}) {
  if (loading) {
    return (
      <>
        {Array.from({ length: 5 }).map((_, i) => (
          <tr key={i}>
            <td colSpan={colSpan} className="px-4 py-3">
              <div className="h-4 w-full animate-pulse rounded bg-slate-100" />
            </td>
          </tr>
        ))}
      </>
    )
  }
  if (error) {
    return (
      <tr>
        <td colSpan={colSpan} className="px-4 py-10 text-center text-sm text-rose-600">
          Could not load this list. {errorText(error)}
        </td>
      </tr>
    )
  }
  if (empty) {
    return (
      <tr>
        <td colSpan={colSpan} className="px-4 py-12 text-center">
          <Inbox className="mx-auto h-8 w-8 text-slate-300" />
          <p className="mt-2 text-sm text-slate-500">{emptyText}</p>
        </td>
      </tr>
    )
  }
  return null
}

export function Pagination({
  page,
  pages,
  total,
  onPage,
}: {
  page: number
  pages: number
  total: number
  onPage: (page: number) => void
}) {
  return (
    <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-xs text-slate-500">
      <span>
        {total.toLocaleString()} result{total === 1 ? '' : 's'}
      </span>
      <div className="flex items-center gap-2">
        <span>
          Page {page} of {pages}
        </span>
        <button
          type="button"
          aria-label="Previous page"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
          className="rounded-md border border-slate-200 p-1 hover:bg-slate-50 disabled:opacity-40"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <button
          type="button"
          aria-label="Next page"
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
          className="rounded-md border border-slate-200 p-1 hover:bg-slate-50 disabled:opacity-40"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Inputs
// ---------------------------------------------------------------------------

/** Search box that reports its value after the user pauses typing. */
export function SearchInput({
  value,
  onChange,
  placeholder = 'Search…',
  className,
}: {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
}) {
  const [draft, setDraft] = useState(value)
  const first = useRef(true)
  useEffect(() => {
    if (first.current) {
      first.current = false
      return
    }
    const t = setTimeout(() => onChange(draft), 300)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft])
  return (
    <div className={cn('relative', className)}>
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder={placeholder}
        className="h-9 w-full rounded-lg border border-slate-200 bg-white pl-9 pr-3 text-sm text-slate-800 placeholder:text-slate-400 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
      />
    </div>
  )
}

export function FilterSelect({
  value,
  onChange,
  options,
  label,
}: {
  value: string
  onChange: (value: string) => void
  options: { value: string; label: string }[]
  label: string
}) {
  return (
    <select
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-9 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-700 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  )
}

export const inputClass =
  'h-9 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-800 placeholder:text-slate-400 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100 disabled:bg-slate-50 disabled:text-slate-500'

export function Field({ label, hint, children }: { label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-700">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
    </label>
  )
}

export function Toggle({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
  label: string
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative inline-flex h-5 w-9 flex-shrink-0 items-center rounded-full transition-colors disabled:opacity-50',
        checked ? 'bg-brand-600' : 'bg-slate-300'
      )}
    >
      <span
        className={cn(
          'inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform',
          checked ? 'translate-x-[18px]' : 'translate-x-0.5'
        )}
      />
    </button>
  )
}

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost'

export function AdminButton({
  variant = 'secondary',
  loading,
  icon: Icon,
  children,
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant
  loading?: boolean
  icon?: LucideIcon
}) {
  const styles: Record<ButtonVariant, string> = {
    primary: 'bg-brand-600 text-white hover:bg-brand-700 shadow-sm',
    secondary: 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 shadow-sm',
    danger: 'bg-rose-600 text-white hover:bg-rose-700 shadow-sm',
    ghost: 'text-slate-600 hover:bg-slate-100',
  }
  return (
    <button
      type="button"
      {...props}
      disabled={props.disabled || loading}
      className={cn(
        'inline-flex h-9 items-center justify-center gap-2 whitespace-nowrap rounded-lg px-3.5 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50',
        styles[variant],
        className
      )}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : Icon ? <Icon className="h-4 w-4" /> : null}
      {children}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Overlays
// ---------------------------------------------------------------------------

function usePortal() {
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  return mounted
}

function useEscape(open: boolean, onClose: () => void) {
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose])
}

export function Drawer({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
}: {
  open: boolean
  onClose: () => void
  title: ReactNode
  subtitle?: ReactNode
  children: ReactNode
  footer?: ReactNode
}) {
  const mounted = usePortal()
  useEscape(open, onClose)
  if (!open || !mounted) return null
  return createPortal(
    <div className="fixed inset-0 z-[9000] flex justify-end">
      <div className="absolute inset-0 bg-slate-900/30 backdrop-blur-[1px]" onClick={onClose} />
      <aside
        role="dialog"
        aria-modal="true"
        className="relative flex h-full w-full max-w-xl flex-col bg-white shadow-2xl animate-in slide-in-from-right duration-200"
      >
        <header className="flex items-start justify-between gap-4 border-b border-slate-100 px-6 py-4">
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold text-slate-900">{title}</h2>
            {subtitle && <p className="mt-0.5 truncate text-xs text-slate-500">{subtitle}</p>}
          </div>
          <button type="button" aria-label="Close" onClick={onClose} className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600">
            <X className="h-5 w-5" />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>
        {footer && <footer className="flex flex-wrap justify-end gap-2 border-t border-slate-100 px-6 py-3">{footer}</footer>}
      </aside>
    </div>,
    document.body
  )
}

export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  wide = false,
}: {
  open: boolean
  onClose: () => void
  title: ReactNode
  description?: ReactNode
  children?: ReactNode
  footer?: ReactNode
  wide?: boolean
}) {
  const mounted = usePortal()
  useEscape(open, onClose)
  if (!open || !mounted) return null
  return createPortal(
    <div className="fixed inset-0 z-[9500] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        className={cn(
          'relative max-h-[90vh] w-full overflow-y-auto rounded-2xl bg-white shadow-xl animate-in fade-in zoom-in-95 duration-150',
          wide ? 'max-w-2xl' : 'max-w-md'
        )}
      >
        <div className="px-6 pb-2 pt-5">
          <h2 className="text-base font-semibold text-slate-900">{title}</h2>
          {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
        </div>
        {children && <div className="px-6 py-3">{children}</div>}
        {footer && <div className="flex justify-end gap-2 border-t border-slate-100 px-6 py-3">{footer}</div>}
      </div>
    </div>,
    document.body
  )
}

/** A labelled value inside a detail view. */
export function Detail({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-0.5 break-words text-sm text-slate-800">{children ?? '—'}</dd>
    </div>
  )
}

export function Callout({
  tone = 'warning',
  title,
  children,
}: {
  tone?: 'warning' | 'danger' | 'success' | 'info'
  title?: ReactNode
  children?: ReactNode
}) {
  const styles = {
    warning: ['border-amber-200 bg-amber-50 text-amber-900', AlertTriangle, 'text-amber-500'],
    danger: ['border-rose-200 bg-rose-50 text-rose-900', XCircle, 'text-rose-500'],
    success: ['border-emerald-200 bg-emerald-50 text-emerald-900', CheckCircle2, 'text-emerald-500'],
    info: ['border-sky-200 bg-sky-50 text-sky-900', AlertTriangle, 'text-sky-500'],
  } as const
  const [box, Icon, iconColor] = styles[tone]
  return (
    <div className={cn('flex gap-3 rounded-xl border px-4 py-3 text-sm', box)}>
      <Icon className={cn('mt-0.5 h-4 w-4 flex-shrink-0', iconColor)} />
      <div className="min-w-0">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className={cn(title && 'mt-0.5', 'opacity-90')}>{children}</div>}
      </div>
    </div>
  )
}

export function errorText(error: unknown): string {
  const anyErr = error as { response?: { data?: { detail?: unknown; message?: string } }; message?: string }
  const detail = anyErr?.response?.data?.detail
  if (typeof detail === 'string') return detail
  return anyErr?.response?.data?.message || anyErr?.message || 'Unexpected error.'
}
