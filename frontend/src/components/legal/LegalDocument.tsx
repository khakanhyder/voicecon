import type { ReactNode } from 'react'
import { ArrowRight, Mail } from 'lucide-react'
import { MarketingShell } from '@/components/landing/MarketingShell'
import { Eyebrow } from '@/components/landing/primitives'
import { cn } from '@/lib/utils'
import { LEGAL } from '@/lib/legal'
import { LegalToc } from './LegalToc'

export interface LegalSection {
  id: string
  title: string
  body: ReactNode
}

/**
 * Layout for a long-form legal document: title block, plain-language summary,
 * sticky table of contents and numbered sections, inside the marketing chrome.
 */
export function LegalDocument({
  title,
  description,
  summary,
  sections,
  related,
}: {
  title: string
  description: string
  summary: ReactNode
  sections: LegalSection[]
  related: { label: string; href: string }
}) {
  return (
    <MarketingShell>
      <header className="px-4 pb-10 pt-32 sm:px-6 md:pb-14 md:pt-40">
        <div className="mx-auto max-w-6xl">
          <Eyebrow>Legal</Eyebrow>
          <h1 className="mt-5 text-balance text-[clamp(2.25rem,5.5vw,3.75rem)] font-bold leading-[1.08] tracking-[-0.025em] text-white">
            {title}
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-relaxed text-white/65 sm:text-lg">{description}</p>
          <dl className="mt-7 flex flex-wrap gap-x-8 gap-y-2 text-sm">
            <div className="flex gap-2">
              <dt className="text-white/45">Effective</dt>
              <dd className="font-medium text-white/85">
                <time dateTime={LEGAL.effectiveDateIso}>{LEGAL.effectiveDate}</time>
              </dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-white/45">Last updated</dt>
              <dd className="font-medium text-white/85">
                <time dateTime={LEGAL.lastUpdatedIso}>{LEGAL.lastUpdated}</time>
              </dd>
            </div>
          </dl>
        </div>
      </header>

      <div className="px-4 pb-20 sm:px-6 md:pb-28">
        <div className="mx-auto grid max-w-6xl grid-cols-1 gap-10 lg:grid-cols-[250px_minmax(0,1fr)] lg:gap-14">
          <aside className="min-w-0 lg:sticky lg:top-24 lg:max-h-[calc(100vh-7rem)] lg:self-start lg:overflow-y-auto lg:pb-6">
            <LegalToc items={sections.map(({ id, title }) => ({ id, title }))} />
          </aside>

          <article className="min-w-0 max-w-3xl">
            <section
              aria-labelledby="summary-title"
              className="rounded-3xl border border-brand-300/25 bg-brand-500/10 p-6 sm:p-8"
            >
              <h2 id="summary-title" className="text-lg font-semibold text-white">
                The short version
              </h2>
              <div className="mt-3 text-[15px] leading-relaxed text-white/75 [&_li]:mt-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:marker:text-brand-300">
                {summary}
              </div>
              <p className="mt-4 text-xs leading-relaxed text-white/50">
                This summary is for convenience. The full text below is what applies.
              </p>
            </section>

            <div className="mt-12 space-y-12">
              {sections.map((section, i) => (
                <section key={section.id} id={section.id} aria-labelledby={`${section.id}-title`} className="scroll-mt-24">
                  <h2
                    id={`${section.id}-title`}
                    className="flex gap-3 text-[1.45rem] font-bold leading-tight tracking-[-0.01em] text-white sm:text-[1.6rem]"
                  >
                    <span className="tabular-nums text-brand-300">{i + 1}.</span>
                    {section.title}
                  </h2>
                  <div className="mt-4">{section.body}</div>
                </section>
              ))}
            </div>

            <div className="mt-14 grid gap-4 sm:grid-cols-2">
              <a
                href={`mailto:${LEGAL.contactEmail}`}
                className="group flex items-start gap-4 rounded-2xl border border-white/10 bg-white/[0.04] p-5 transition-colors hover:border-brand-300/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-200"
              >
                <Mail className="mt-0.5 h-5 w-5 shrink-0 text-brand-300" aria-hidden="true" />
                <span>
                  <span className="block font-semibold text-white">Questions?</span>
                  <span className="mt-0.5 block text-sm text-white/60">{LEGAL.contactEmail}</span>
                </span>
              </a>
              <a
                href={related.href}
                className="group flex items-start gap-4 rounded-2xl border border-white/10 bg-white/[0.04] p-5 transition-colors hover:border-brand-300/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-200"
              >
                <ArrowRight className="mt-0.5 h-5 w-5 shrink-0 text-brand-300 transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
                <span>
                  <span className="block font-semibold text-white">Read next</span>
                  <span className="mt-0.5 block text-sm text-white/60">{related.label}</span>
                </span>
              </a>
            </div>

            <section
              aria-label="Company details"
              className="mt-4 rounded-2xl border border-white/10 bg-white/[0.04] p-5 text-sm leading-relaxed text-white/60"
            >
              <p className="font-semibold text-white">{LEGAL.product} is a product of {LEGAL.company}.</p>
              <address className="mt-2 not-italic">
                <span className="block">Registered office: {LEGAL.registeredAddress}</span>
                <span className="block">Operations office: {LEGAL.officeAddress}</span>
                <span className="mt-1 block">
                  <A href={`tel:${LEGAL.phoneHref}`}>{LEGAL.phone}</A> &middot;{' '}
                  <A href={`mailto:${LEGAL.contactEmail}`}>{LEGAL.contactEmail}</A>
                </span>
              </address>
            </section>
          </article>
        </div>
      </div>
    </MarketingShell>
  )
}

/* ───────────────────────────── Prose primitives ───────────────────────────── */

export function P({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cn('mt-4 text-[15.5px] leading-[1.75] text-white/70 first:mt-0', className)}>{children}</p>
}

export function H3({ children }: { children: ReactNode }) {
  return <h3 className="mt-7 text-[1.05rem] font-semibold text-white">{children}</h3>
}

export function UL({ children }: { children: ReactNode }) {
  return (
    <ul className="mt-4 space-y-2.5 pl-5 text-[15.5px] leading-[1.7] text-white/70 marker:text-brand-300 [list-style:disc]">
      {children}
    </ul>
  )
}

export function B({ children }: { children: ReactNode }) {
  return <strong className="font-semibold text-white">{children}</strong>
}

export function A({ href, children }: { href: string; children: ReactNode }) {
  const external = href.startsWith('http')
  return (
    <a
      href={href}
      {...(external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
      className="font-medium text-brand-200 underline decoration-brand-300/40 underline-offset-4 hover:decoration-brand-200"
    >
      {children}
    </a>
  )
}

export function Callout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mt-5 rounded-2xl border-l-4 border-brand-300 bg-white/[0.05] px-5 py-4">
      <p className="text-sm font-semibold text-white">{title}</p>
      <div className="mt-1.5 text-[15px] leading-relaxed text-white/70">{children}</div>
    </div>
  )
}

/** Responsive table: a real table on wider screens, stacked cards on phones. */
export function Table({ headers, rows }: { headers: string[]; rows: ReactNode[][] }) {
  return (
    <div className="mt-5">
      <div className="hidden overflow-hidden rounded-2xl border border-white/10 sm:block">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-white/[0.06]">
            <tr>
              {headers.map((h) => (
                <th key={h} scope="col" className="px-4 py-3 font-semibold text-white">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.07]">
            {rows.map((row, i) => (
              <tr key={i} className="align-top">
                {row.map((cell, j) => (
                  <td key={j} className={cn('px-4 py-3 leading-relaxed', j === 0 ? 'font-medium text-white' : 'text-white/70')}>
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="space-y-3 sm:hidden">
        {rows.map((row, i) => (
          <li key={i} className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 text-sm">
            <p className="font-semibold text-white">{row[0]}</p>
            <dl className="mt-2 space-y-1.5">
              {row.slice(1).map((cell, j) => (
                <div key={j}>
                  <dt className="text-xs uppercase tracking-wide text-white/45">{headers[j + 1]}</dt>
                  <dd className="leading-relaxed text-white/70">{cell}</dd>
                </div>
              ))}
            </dl>
          </li>
        ))}
      </ul>
    </div>
  )
}
