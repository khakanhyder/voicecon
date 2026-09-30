'use client'

import { useState, type ReactNode } from 'react'
import { Check, ChevronLeft, ChevronRight, Copy } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

/** Pieces shared by the affiliate portal pages. */

export const cardClass =
  'rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_4px_20px_-4px_rgba(16,105,89,0.1)] sm:p-6'

export function PageHeader({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="font-poppins text-2xl font-bold text-slate-900">{title}</h1>
        {description && <p className="mt-1 text-sm text-slate-600">{description}</p>}
      </div>
      {action}
    </div>
  )
}

export function SectionTitle({ title, description }: { title: string; description?: ReactNode }) {
  return (
    <div className="mb-4">
      <h2 className="font-poppins text-lg font-bold text-slate-900">{title}</h2>
      {description && <p className="mt-1 text-sm text-slate-600">{description}</p>}
    </div>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-md bg-slate-200/70', className)} />
}

export function Spinner({ className }: { className?: string }) {
  return (
    <div
      className={cn('h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-[#243275]', className)}
      role="status"
      aria-label="Loading"
    />
  )
}

export function StatCard({
  label,
  value,
  sub,
  icon,
  tone = 'default',
}: {
  label: string
  value: ReactNode
  sub?: ReactNode
  icon?: ReactNode
  tone?: 'default' | 'accent'
}) {
  return (
    <div
      className={cn(
        'rounded-xl border p-4',
        tone === 'accent' ? 'border-[#106959]/30 bg-[#0F6A590F]' : 'border-slate-200 bg-white'
      )}
    >
      <div className="flex items-center gap-2 text-sm font-medium text-slate-600">
        {icon}
        <span>{label}</span>
      </div>
      <p className="mt-2 font-poppins text-2xl font-bold leading-none text-slate-900">{value}</p>
      {sub && <p className="mt-1.5 text-xs text-slate-500">{sub}</p>}
    </div>
  )
}

/** Copy `text` and confirm it, falling back to a message when the browser refuses. */
export async function copyText(text: string, what = 'Copied') {
  try {
    await navigator.clipboard.writeText(text)
    toast.success(`${what} to clipboard`)
    return true
  } catch {
    toast.error('Could not copy automatically — select the text and copy it instead.')
    return false
  }
}

export function CopyField({ label, value, hint }: { label: string; value: string; hint?: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    if (await copyText(value, `${label} copied`)) {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }
  }
  return (
    <div className="space-y-1.5">
      <p className="text-sm font-semibold text-slate-800">{label}</p>
      <div className="flex items-stretch gap-2">
        <input
          readOnly
          value={value}
          onFocus={(e) => e.currentTarget.select()}
          aria-label={label}
          className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 font-mono text-sm text-slate-800 outline-none focus:border-[#243275] focus:ring-3 focus:ring-[#243275]/15"
        />
        <button
          type="button"
          onClick={copy}
          className="inline-flex flex-shrink-0 items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
        >
          {copied ? <Check className="h-4 w-4 text-[#106959]" /> : <Copy className="h-4 w-4" />}
          <span className="hidden sm:inline">{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      {hint && <p className="text-xs text-slate-500">{hint}</p>}
    </div>
  )
}

const BADGE_TONES = {
  green: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  amber: 'bg-amber-50 text-amber-800 ring-amber-600/20',
  blue: 'bg-blue-50 text-blue-700 ring-blue-600/20',
  slate: 'bg-slate-100 text-slate-700 ring-slate-500/20',
  red: 'bg-rose-50 text-rose-700 ring-rose-600/20',
} as const

export type BadgeTone = keyof typeof BADGE_TONES

export function Badge({ tone = 'slate', children, title }: { tone?: BadgeTone; children: ReactNode; title?: string }) {
  return (
    <span
      title={title}
      className={cn(
        'inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset',
        BADGE_TONES[tone]
      )}
    >
      {children}
    </span>
  )
}

export function Notice({
  tone = 'info',
  icon,
  title,
  children,
  action,
}: {
  tone?: 'info' | 'warning' | 'danger'
  icon?: ReactNode
  title: string
  children?: ReactNode
  action?: ReactNode
}) {
  const tones = {
    info: 'border-blue-200 bg-blue-50 text-blue-900',
    warning: 'border-amber-200 bg-amber-50 text-amber-900',
    danger: 'border-rose-200 bg-rose-50 text-rose-900',
  }
  return (
    <div className={cn('flex flex-col gap-3 rounded-xl border p-4 sm:flex-row sm:items-center', tones[tone])}>
      <div className="flex flex-1 items-start gap-3">
        {icon && <span className="mt-0.5 flex-shrink-0">{icon}</span>}
        <div className="text-sm">
          <p className="font-semibold">{title}</p>
          {children && <div className="mt-0.5 opacity-90">{children}</div>}
        </div>
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </div>
  )
}

export function EmptyState({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-12 text-center">
      {icon && (
        <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-500">
          {icon}
        </span>
      )}
      <p className="font-semibold text-slate-900">{title}</p>
      {children && <p className="mt-1 max-w-sm text-sm text-slate-500">{children}</p>}
    </div>
  )
}

export function TableSkeleton({ rows = 5, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="space-y-3 py-2">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4">
          {Array.from({ length: cols }).map((__, j) => (
            <Skeleton key={j} className="h-5 flex-1" />
          ))}
        </div>
      ))}
    </div>
  )
}

/** A horizontally scrollable table frame, so wide tables never push the page sideways. */
export function Table({ head, children }: { head: ReactNode[]; children: ReactNode }) {
  return (
    <div className="-mx-5 overflow-x-auto sm:-mx-6">
      <table className="min-w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
            {head.map((h, i) => (
              <th key={i} scope="col" className="whitespace-nowrap px-5 py-3 font-semibold first:pl-5 sm:px-6">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">{children}</tbody>
      </table>
    </div>
  )
}

export const tdClass = 'whitespace-nowrap px-5 py-3 align-top text-slate-700 sm:px-6'

export function Pagination({
  page,
  pages,
  total,
  onChange,
  disabled,
}: {
  page: number
  pages: number
  total: number
  onChange: (page: number) => void
  disabled?: boolean
}) {
  if (pages <= 1) return null
  const btn =
    'inline-flex h-9 items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50'
  return (
    <div className="mt-4 flex items-center justify-between gap-3 border-t border-slate-100 pt-4">
      <p className="text-sm text-slate-500">
        Page {page} of {pages} · {total.toLocaleString('en-US')} total
      </p>
      <div className="flex gap-2">
        <button type="button" className={btn} disabled={disabled || page <= 1} onClick={() => onChange(page - 1)}>
          <ChevronLeft className="h-4 w-4" />
          <span className="hidden sm:inline">Previous</span>
        </button>
        <button type="button" className={btn} disabled={disabled || page >= pages} onClick={() => onChange(page + 1)}>
          <span className="hidden sm:inline">Next</span>
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}

export const primaryButtonClass =
  'inline-flex items-center justify-center gap-2 rounded-lg bg-[#243275] px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-[#1c2960] focus:outline-none focus:ring-3 focus:ring-[#243275]/30 disabled:cursor-not-allowed disabled:opacity-60'

export const secondaryButtonClass =
  'inline-flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60'

export const inputClass =
  'w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-base text-slate-900 outline-none transition-all placeholder:text-slate-400 focus:border-[#243275] focus:ring-3 focus:ring-[#243275]/15 disabled:cursor-not-allowed disabled:opacity-50'

/** Shown when a list failed to load; the message is already customer-safe. */
export function LoadError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 py-10 text-center">
      <p className="text-sm text-slate-600">{message}</p>
      <button type="button" onClick={onRetry} className={secondaryButtonClass}>
        Try again
      </button>
    </div>
  )
}
