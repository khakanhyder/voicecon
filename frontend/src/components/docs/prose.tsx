/**
 * Documentation content primitives.
 *
 * Server components by design — a docs page is static text, so nothing here
 * ships JavaScript. The two pieces that genuinely need the client (code copy
 * buttons, the table of contents scroll-spy) live in their own files.
 *
 * These components carry no vertical margins. Spacing between blocks is owned
 * by the `.doc-prose` rules in globals.css so the whole page moves on one
 * scale; adding a `mt-*` here is how that scale starts drifting.
 *
 * Heading ids are supplied explicitly rather than slugified from the text: the
 * same ids appear in `lib/docs/navigation.ts`, and deriving them in two places
 * is how anchors quietly stop matching their table of contents.
 */
import Link from 'next/link'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Info,
  Lightbulb,
  XCircle,
} from 'lucide-react'

// ── Headings ──────────────────────────────────────────────────────────────────

/**
 * Section heading.
 *
 * A full-width hairline is the documentation convention and is kept, with a
 * short brand-green segment anchored at its left. The rule does the separating;
 * the green tick is the one place a Voicecon page signs its own name, and it
 * costs no layout — the text stays on the body's left margin.
 */
export function H2({ id, children }: { id: string; children: ReactNode }) {
  return (
    <h2
      id={id}
      className="group relative scroll-mt-[84px] border-b border-slate-200 pb-3 font-poppins text-[21px] font-bold leading-[1.3] tracking-[-0.022em] text-slate-900 sm:text-[24px]"
    >
      <a href={`#${id}`} className="no-underline">
        {children}
        <span
          aria-hidden
          className="ml-2 select-none text-brand-400 opacity-0 transition-opacity group-hover:opacity-100"
        >
          #
        </span>
      </a>
      <span
        aria-hidden
        className="absolute -bottom-px left-0 h-[2px] w-8 rounded-full bg-brand-500"
      />
    </h2>
  )
}

export function H3({ id, children }: { id?: string; children: ReactNode }) {
  return (
    <h3
      id={id}
      className="scroll-mt-[84px] font-poppins text-[17px] font-bold leading-[1.4] tracking-[-0.01em] text-slate-900 sm:text-[18.5px]"
    >
      {children}
    </h3>
  )
}

export function H4({ children }: { children: ReactNode }) {
  return (
    <h4 className="font-poppins text-[15px] font-bold leading-[1.45] text-slate-800 sm:text-[15.5px]">
      {children}
    </h4>
  )
}

// ── Text ──────────────────────────────────────────────────────────────────────

export function P({ children }: { children: ReactNode }) {
  return <p className="text-[15px] leading-[1.75] text-slate-700 sm:text-[15.5px]">{children}</p>
}

/** The standfirst under a page title. Slightly larger, slightly quieter. */
export function Lead({ children }: { children: ReactNode }) {
  return <p className="text-[16px] leading-[1.65] text-slate-600 sm:text-[17px]">{children}</p>
}

export function UL({ children }: { children: ReactNode }) {
  return (
    <ul className="space-y-2 text-[15px] leading-[1.7] text-slate-700 sm:text-[15.5px]">
      {children}
    </ul>
  )
}

export function LI({ children }: { children: ReactNode }) {
  return (
    <li className="relative pl-[22px] before:absolute before:left-[3px] before:top-[0.62em] before:h-[6px] before:w-[6px] before:rounded-full before:bg-brand-300">
      {children}
    </li>
  )
}

export function OL({ children }: { children: ReactNode }) {
  return (
    <ol className="list-decimal space-y-2 pl-[22px] text-[15px] leading-[1.7] text-slate-700 marker:font-semibold marker:text-brand-600 sm:text-[15.5px]">
      {children}
    </ol>
  )
}

/** Inline code. Named `C` because it appears several times per sentence. */
export function C({ children }: { children: ReactNode }) {
  return (
    <code className="whitespace-nowrap rounded-[5px] border border-slate-200 bg-slate-50 px-[5px] py-[1.5px] font-mono text-[0.855em] text-brand-700">
      {children}
    </code>
  )
}

export function A({ href, children }: { href: string; children: ReactNode }) {
  const external = href.startsWith('http')
  if (external) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium text-brand-600 underline decoration-brand-300 underline-offset-[3px] transition-colors hover:text-brand-700 hover:decoration-brand-500"
      >
        {children}
      </a>
    )
  }
  return (
    <Link
      href={href}
      className="font-medium text-brand-600 underline decoration-brand-300 underline-offset-[3px] transition-colors hover:text-brand-700 hover:decoration-brand-500"
    >
      {children}
    </Link>
  )
}

export function Strong({ children }: { children: ReactNode }) {
  return <strong className="font-semibold text-slate-900">{children}</strong>
}

export function Divider() {
  return <hr className="border-slate-200" />
}

// ── Callouts ──────────────────────────────────────────────────────────────────

/**
 * Callouts are marked by a solid left edge rather than a full border box.
 * Several boxed panels down a reference page start to read as a form; an edge
 * marker reads as an aside on the same page, which is what it is.
 */
const CALLOUT_STYLES = {
  note: {
    icon: Info,
    wrap: 'border-slate-300 bg-slate-50',
    mark: 'text-slate-500',
    label: 'text-slate-900',
  },
  tip: {
    icon: Lightbulb,
    wrap: 'border-brand-500 bg-brand-50/50',
    mark: 'text-brand-600',
    label: 'text-brand-800',
  },
  warning: {
    icon: AlertTriangle,
    wrap: 'border-amber-400 bg-amber-50/50',
    mark: 'text-amber-600',
    label: 'text-amber-900',
  },
  danger: {
    icon: XCircle,
    wrap: 'border-red-400 bg-red-50/50',
    mark: 'text-red-600',
    label: 'text-red-900',
  },
  success: {
    icon: CheckCircle2,
    wrap: 'border-emerald-400 bg-emerald-50/50',
    mark: 'text-emerald-600',
    label: 'text-emerald-900',
  },
} as const

export type CalloutKind = keyof typeof CALLOUT_STYLES

export function Callout({
  kind = 'note',
  title,
  children,
}: {
  kind?: CalloutKind
  title?: string
  children: ReactNode
}) {
  const style = CALLOUT_STYLES[kind]
  const Icon = style.icon
  return (
    <aside
      className={cn(
        'rounded-l-[3px] rounded-r-lg border-l-[3px] px-4 py-3.5 sm:px-[18px]',
        style.wrap
      )}
    >
      <div className="flex gap-3">
        <Icon className={cn('mt-[3px] h-[17px] w-[17px] flex-shrink-0', style.mark)} />
        <div className="min-w-0 flex-1">
          {title && (
            <p className={cn('font-poppins text-[13.5px] font-bold leading-snug', style.label)}>
              {title}
            </p>
          )}
          <div
            className={cn(
              'space-y-2 text-[14px] leading-[1.65] text-slate-700 sm:text-[14.5px]',
              title && 'mt-1.5'
            )}
          >
            {children}
          </div>
        </div>
      </div>
    </aside>
  )
}

// ── Parameter tables ──────────────────────────────────────────────────────────

export interface Param {
  name: string
  type: string
  /** Rendered as `—` when omitted, so the column never looks broken. */
  default?: string
  required?: boolean
  description: ReactNode
}

/**
 * The reference table used for every node, tool, and setting.
 *
 * Two renderings of the same rows: a real table from `md` up, and stacked
 * cards below it. A four-column table on a phone is unreadable, and horizontal
 * scroll hides the description column — the one people came for.
 */
export function ParamTable({ params }: { params: Param[] }) {
  return (
    <div>
      {/* Desktop */}
      <div className="hidden overflow-hidden rounded-xl border border-slate-200 md:block">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50/80">
              <th className="w-[23%] px-4 py-3 font-poppins text-[11px] font-bold uppercase tracking-[0.06em] text-slate-500">
                Parameter
              </th>
              <th className="w-[14%] px-4 py-3 font-poppins text-[11px] font-bold uppercase tracking-[0.06em] text-slate-500">
                Type
              </th>
              <th className="w-[14%] px-4 py-3 font-poppins text-[11px] font-bold uppercase tracking-[0.06em] text-slate-500">
                Default
              </th>
              <th className="px-4 py-3 font-poppins text-[11px] font-bold uppercase tracking-[0.06em] text-slate-500">
                Description
              </th>
            </tr>
          </thead>
          <tbody>
            {params.map((param) => (
              <tr
                key={param.name}
                className="border-b border-slate-100 align-top last:border-0"
              >
                <td className="px-4 py-3.5">
                  <span className="font-mono text-[12.5px] font-semibold text-slate-900">
                    {param.name}
                  </span>
                  {param.required && (
                    <span className="mt-0.5 block text-[10.5px] font-bold uppercase tracking-wide text-red-500">
                      required
                    </span>
                  )}
                </td>
                <td className="px-4 py-3.5 font-mono text-[12px] leading-[1.5] text-slate-500">
                  {param.type}
                </td>
                <td className="px-4 py-3.5 font-mono text-[12px] leading-[1.5] text-slate-500">
                  {param.default ?? '—'}
                </td>
                <td className="px-4 py-3.5 text-[13.5px] leading-[1.65] text-slate-700">
                  {param.description}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile */}
      <div className="space-y-2.5 md:hidden">
        {params.map((param) => (
          <div key={param.name} className="rounded-xl border border-slate-200 px-4 py-3.5">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="font-mono text-[12.5px] font-semibold text-slate-900">
                {param.name}
              </span>
              <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10.5px] text-slate-500">
                {param.type}
              </span>
              {param.required && (
                <span className="rounded bg-red-50 px-1.5 py-0.5 text-[10.5px] font-bold uppercase tracking-wide text-red-600">
                  required
                </span>
              )}
            </div>
            {param.default && (
              <p className="mt-1.5 font-mono text-[11.5px] text-slate-500">
                Default: {param.default}
              </p>
            )}
            <div className="mt-2 text-[13.5px] leading-[1.65] text-slate-700">
              {param.description}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Generic table ─────────────────────────────────────────────────────────────

/**
 * A comparison or reference table.
 *
 * Below `md` each row becomes a card: the first cell is the card's heading and
 * the rest are label/value pairs. Horizontal scrolling was the alternative, and
 * it hides exactly the columns a reader on a phone needs most.
 */
export function Table({
  headers,
  rows,
  /** Column widths as Tailwind classes, applied to the header cells. */
  widths,
  /**
   * Lays the mobile cards out as inline label/value pairs instead of stacked
   * rows. For matrices whose cells are a tick or a word, stacking turns four
   * columns into eight lines of mostly whitespace.
   */
  dense = false,
}: {
  headers: string[]
  rows: ReactNode[][]
  widths?: string[]
  dense?: boolean
}) {
  return (
    <div>
      {/* Desktop */}
      <div className="hidden overflow-hidden rounded-xl border border-slate-200 md:block">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50/80">
              {headers.map((header, index) => (
                <th
                  key={index}
                  className={cn(
                    'px-4 py-3 font-poppins text-[11px] font-bold uppercase tracking-[0.06em] text-slate-500',
                    widths?.[index]
                  )}
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="border-b border-slate-100 align-top last:border-0">
                {row.map((cell, cellIndex) => (
                  <td
                    key={cellIndex}
                    className="px-4 py-3.5 text-[13.5px] leading-[1.65] text-slate-700"
                  >
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile */}
      <div className="space-y-2.5 md:hidden">
        {rows.map((row, rowIndex) => (
          <div key={rowIndex} className="rounded-xl border border-slate-200 px-4 py-3.5">
            <div className="text-[14px] font-semibold leading-snug text-slate-900">{row[0]}</div>
            <dl
              className={cn(
                'mt-2.5',
                dense ? 'flex flex-wrap gap-x-5 gap-y-1.5' : 'space-y-2'
              )}
            >
              {row.slice(1).map((cell, cellIndex) => (
                <div
                  key={cellIndex}
                  className={dense ? 'flex items-center gap-1.5' : undefined}
                >
                  <dt className="font-poppins text-[10.5px] font-bold uppercase tracking-[0.06em] text-slate-400">
                    {headers[cellIndex + 1]}
                  </dt>
                  <dd
                    className={cn(
                      'text-[13.5px] leading-[1.6] text-slate-700',
                      !dense && 'mt-0.5'
                    )}
                  >
                    {cell}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Steps ─────────────────────────────────────────────────────────────────────

/** A numbered procedure. The connecting rail is drawn by each `Step`. */
export function Steps({ children }: { children: ReactNode }) {
  return <div>{children}</div>
}

export function Step({
  n,
  title,
  children,
}: {
  n: number
  title: string
  children: ReactNode
}) {
  return (
    <div className="group/step relative flex gap-4 pb-7 last:pb-0">
      {/* Absolutely positioned so the rail spans the padding between items and
          meets the next marker. As a flex child it stopped at the content box,
          leaving a stub floating short of the following step.
          Hidden on the final step — a rail past the last item points nowhere. */}
      <span
        aria-hidden
        className="absolute bottom-0 left-[13.5px] top-[34px] w-px bg-slate-200 group-last/step:hidden"
      />
      <div className="relative flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-brand-600 font-poppins text-[12.5px] font-bold text-white">
        {n}
      </div>
      <div className="min-w-0 flex-1 pb-0.5">
        <p className="font-poppins text-[15px] font-bold leading-[1.45] text-slate-900 sm:text-[15.5px]">
          {title}
        </p>
        <div className="mt-1.5 space-y-3">{children}</div>
      </div>
    </div>
  )
}

// ── Cards ─────────────────────────────────────────────────────────────────────

export function CardGrid({
  children,
  cols = 2,
}: {
  children: ReactNode
  cols?: 2 | 3
}) {
  return (
    <div
      className={cn(
        'grid gap-3',
        cols === 2 ? 'sm:grid-cols-2' : 'sm:grid-cols-2 lg:grid-cols-3'
      )}
    >
      {children}
    </div>
  )
}

export function DocCard({
  href,
  title,
  children,
}: {
  href: string
  title: string
  children: ReactNode
}) {
  return (
    <Link
      href={href}
      className="group flex flex-col rounded-xl border border-slate-200 bg-white px-4 py-3.5 transition-all hover:border-brand-300 hover:shadow-[0_2px_12px_rgba(15,106,89,0.08)]"
    >
      <span className="flex items-center gap-1.5 font-poppins text-[14.5px] font-bold leading-snug text-slate-900">
        {title}
        <ArrowRight className="h-3.5 w-3.5 flex-shrink-0 text-brand-500 opacity-0 transition-all group-hover:translate-x-0.5 group-hover:opacity-100" />
      </span>
      <span className="mt-1 text-[13.5px] leading-[1.6] text-slate-600">{children}</span>
    </Link>
  )
}

/** A non-navigating card, for concept summaries. */
export function InfoCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3.5">
      <p className="font-poppins text-[14.5px] font-bold leading-snug text-slate-900">{title}</p>
      <div className="mt-1 text-[13.5px] leading-[1.6] text-slate-600">{children}</div>
    </div>
  )
}

// ── Badges ────────────────────────────────────────────────────────────────────

const BADGE_TONES = {
  brand: 'bg-brand-50 text-brand-700 border-brand-200',
  slate: 'bg-slate-100 text-slate-600 border-slate-200',
  blue: 'bg-blue-50 text-blue-700 border-blue-200',
  amber: 'bg-amber-50 text-amber-700 border-amber-200',
  violet: 'bg-violet-50 text-violet-700 border-violet-200',
  emerald: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  rose: 'bg-rose-50 text-rose-700 border-rose-200',
} as const

export function Badge({
  tone = 'slate',
  children,
}: {
  tone?: keyof typeof BADGE_TONES
  children: ReactNode
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2 py-[1.5px] font-poppins text-[11px] font-semibold leading-[1.5]',
        BADGE_TONES[tone]
      )}
    >
      {children}
    </span>
  )
}

// ── Node / tool reference header ──────────────────────────────────────────────

/**
 * The heading block that opens each node or tool entry: name, category chip,
 * and a one-line purpose.
 *
 * The chip and summary are wrapped with the heading so `.doc-prose` treats the
 * whole block as one unit — otherwise the chip inherits the gap meant to
 * separate paragraphs and drifts away from the title it labels.
 */
export function RefHeader({
  id,
  name,
  chip,
  tone = 'slate',
  children,
}: {
  id: string
  name: string
  chip: string
  tone?: keyof typeof BADGE_TONES
  children: ReactNode
}) {
  return (
    <div className="doc-ref">
      <H2 id={id}>{name}</H2>
      <div className="mt-3.5 flex flex-wrap items-center gap-2">
        <Badge tone={tone}>{chip}</Badge>
      </div>
      <p className="mt-2.5 text-[15px] leading-[1.75] text-slate-700 sm:text-[15.5px]">
        {children}
      </p>
    </div>
  )
}

/** Small labelled block, e.g. "Outputs: true, false". */
export function Meta({ label, children }: { label: string; children: ReactNode }) {
  return (
    <p className="doc-meta text-[13.5px] leading-[1.6] text-slate-600">
      <span className="font-poppins font-bold text-slate-800">{label}: </span>
      {children}
    </p>
  )
}
