import Link from 'next/link'
import { ArrowLeft, ArrowRight, ChevronDown, ChevronRight } from 'lucide-react'
import {
  getDocGroup,
  getDocNeighbours,
  getDocPage,
} from '@/lib/docs/navigation'
import { cn } from '@/lib/utils'
import { TableOfContents } from './TableOfContents'

/**
 * The frame every documentation page renders inside.
 *
 * Title, lead, table of contents, and prev/next all come from the navigation
 * registry keyed by `href` — a page supplies only its body. That keeps the
 * sidebar label, the browser title, and the paging links from ever disagreeing
 * about what a page is called.
 *
 * The body is wrapped in `.doc-prose`, which owns the spacing between blocks;
 * see globals.css.
 */
export function DocPage({
  href,
  children,
}: {
  href: string
  children: React.ReactNode
}) {
  const page = getDocPage(href)
  const group = getDocGroup(href)
  const { previous, next } = getDocNeighbours(href)

  if (!page) {
    // A page whose href is not registered would otherwise render headless, with
    // no title and no navigation. Failing loudly in development is cheaper than
    // discovering it in production.
    throw new Error(
      `DocPage: "${href}" is not in DOCS_NAV. Add it to lib/docs/navigation.ts.`
    )
  }

  return (
    // Below xl the contents rail is hidden, so the article centres itself in
    // the space rather than hugging the sidebar with dead room to its right.
    <div className="mx-auto flex w-full max-w-[720px] gap-14 xl:max-w-[1030px]">
      <article className="min-w-0 flex-1 pb-24 pt-9 lg:pt-12">
        <header>
          {group && (
            <nav
              aria-label="Breadcrumb"
              className="flex items-center gap-1.5 text-[12.5px] font-medium text-slate-400"
            >
              <Link href="/docs" className="transition-colors hover:text-slate-600">
                Docs
              </Link>
              <ChevronRight className="h-3 w-3 flex-shrink-0 text-slate-300" />
              <span className="text-slate-600">{group.title}</span>
            </nav>
          )}

          <h1 className="mt-3.5 font-poppins text-[31px] font-bold leading-[1.14] tracking-[-0.028em] text-slate-900 sm:text-[38px]">
            {page.title}
          </h1>
          <p className="mt-3.5 max-w-[62ch] text-[16.5px] leading-[1.62] text-slate-500 sm:text-[17.5px]">
            {page.description}
          </p>
        </header>

        {/* Compact contents for viewports where the rail is hidden. */}
        {page.sections.length > 2 && (
          <details className="group mt-8 rounded-lg border border-slate-200 xl:hidden">
            <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-2.5 font-poppins text-[11.5px] font-bold uppercase tracking-[0.07em] text-slate-500 [&::-webkit-details-marker]:hidden">
              On this page
              <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
            </summary>
            <ul className="space-y-1.5 border-t border-slate-200 px-4 py-3">
              {page.sections.map((section) => (
                <li key={section.id}>
                  <a
                    href={`#${section.id}`}
                    className="block text-[13.5px] leading-snug text-slate-600 transition-colors hover:text-brand-700"
                  >
                    {section.title}
                  </a>
                </li>
              ))}
            </ul>
          </details>
        )}

        <div className="doc-prose mt-10">{children}</div>

        <nav className="mt-20 grid gap-3 border-t border-slate-200 pt-8 sm:grid-cols-2">
          {previous ? (
            <PageLink page={previous} direction="previous" />
          ) : (
            <span className="hidden sm:block" />
          )}
          {next && <PageLink page={next} direction="next" />}
        </nav>
      </article>

      <aside className="sticky top-[60px] hidden h-[calc(100vh-60px)] w-[216px] flex-shrink-0 overflow-y-auto pb-12 pt-12 xl:block">
        <TableOfContents sections={page.sections} />
      </aside>
    </div>
  )
}

function PageLink({
  page,
  direction,
}: {
  page: { title: string; href: string }
  direction: 'previous' | 'next'
}) {
  const isNext = direction === 'next'
  return (
    <Link
      href={page.href}
      className={cn(
        'group flex flex-col rounded-lg border border-slate-200 px-4 py-3 transition-colors hover:border-brand-300 hover:bg-brand-50/40',
        isNext && 'sm:col-start-2 sm:text-right'
      )}
    >
      <span
        className={cn(
          'flex items-center gap-1.5 text-[11.5px] font-semibold uppercase tracking-[0.06em] text-slate-400',
          isNext && 'sm:justify-end'
        )}
      >
        {!isNext && <ArrowLeft className="h-3.5 w-3.5" />}
        {isNext ? 'Next' : 'Previous'}
        {isNext && <ArrowRight className="h-3.5 w-3.5" />}
      </span>
      <span className="mt-1 font-poppins text-[14.5px] font-bold leading-snug text-slate-900 transition-colors group-hover:text-brand-700">
        {page.title}
      </span>
    </Link>
  )
}

/** Page metadata derived from the registry, for each route's `metadata` export. */
export function docMetadata(href: string) {
  const page = getDocPage(href)
  if (!page) return {}
  return {
    title: `${page.title} — Voicecon Docs`,
    description: page.description,
  }
}
