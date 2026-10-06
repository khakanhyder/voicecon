import type { Metadata } from 'next'
import { ChevronLeft, ChevronRight, Search } from 'lucide-react'
import { MarketingShell } from '@/components/landing/MarketingShell'
import { Accent, Eyebrow } from '@/components/landing/primitives'
import { BlogCard } from '@/components/blog/BlogCard'
import { cn } from '@/lib/utils'
import { fetchBlogCategories, fetchBlogPosts } from '@/lib/blog'

/**
 * voicecon.ai/blog: every live post as cards, newest first, with category and
 * tag filters, search and pagination. Filters are plain links and a GET form,
 * so the page works without JavaScript and each filtered view has a real URL.
 */

// Same cadence as the home page: a publish shows up within a minute.
export const revalidate = 60

const SITE = 'https://voicecon.ai'
const TITLE = 'Blog | Voicecon'
const DESCRIPTION =
  'Guides, playbooks and product news from Voicecon on AI voice agents, call automation and no-code workflows.'

export const metadata: Metadata = {
  metadataBase: new URL(SITE),
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: '/blog' },
  openGraph: {
    type: 'website',
    url: `${SITE}/blog`,
    siteName: 'Voicecon',
    title: TITLE,
    description: DESCRIPTION,
    images: [{ url: `${SITE}/landing/og-image.png`, width: 1200, height: 630, alt: 'Voicecon blog' }],
  },
  twitter: { card: 'summary_large_image', title: TITLE, description: DESCRIPTION, images: [`${SITE}/landing/og-image.png`] },
}

const PAGE_SIZE = 9

interface Props {
  searchParams: { page?: string; category?: string; tag?: string; q?: string }
}

function hrefWith(current: Props['searchParams'], changes: Record<string, string | undefined>) {
  const params = new URLSearchParams()
  const merged = { ...current, ...changes }
  for (const key of ['category', 'tag', 'q', 'page'] as const) {
    const value = merged[key]
    if (value && !(key === 'page' && value === '1')) params.set(key, value)
  }
  const qs = params.toString()
  return qs ? `/blog?${qs}` : '/blog'
}

export default async function BlogIndexPage({ searchParams }: Props) {
  const page = Math.max(1, Number.parseInt(searchParams.page ?? '1', 10) || 1)
  const category = searchParams.category || undefined
  const tag = searchParams.tag || undefined
  const q = searchParams.q?.trim() || undefined

  const [result, categories] = await Promise.all([
    fetchBlogPosts({ page, page_size: PAGE_SIZE, category, tag, q }),
    fetchBlogCategories(),
  ])
  const posts = result?.items ?? []
  const pages = result?.pages ?? 1
  const activeCategory = categories?.find((c) => c.slug === category)
  const filtered = Boolean(category || tag || q)

  const pill = (active: boolean) =>
    cn(
      'inline-flex h-10 items-center whitespace-nowrap rounded-full border px-4 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-200',
      active
        ? 'border-brand-300/60 bg-brand-500/20 text-white'
        : 'border-white/12 bg-white/[0.04] text-white/70 hover:border-white/25 hover:text-white'
    )

  return (
    <MarketingShell>
      <div className="px-4 pb-24 pt-32 sm:px-6 md:pt-40">
        <div className="mx-auto max-w-6xl">
          <header className="max-w-3xl">
            <Eyebrow>Voicecon blog</Eyebrow>
            <h1 className="mt-5 text-balance text-[clamp(2.25rem,5.5vw,3.5rem)] font-bold leading-[1.08] tracking-[-0.025em] text-white">
              Insights on <Accent>AI voice agents</Accent> and the work around every call
            </h1>
            <p className="mt-5 max-w-2xl text-lg leading-relaxed text-white/65">
              Practical guides, customer playbooks and product updates from the team building Voicecon.
            </p>
          </header>

          <div className="mt-12 flex flex-col gap-5 border-b border-white/10 pb-8 lg:flex-row lg:items-center lg:justify-between">
            <nav aria-label="Categories" className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
              <ul className="flex gap-2 pb-1">
                <li>
                  <a href={hrefWith({ q, tag }, { category: undefined, page: undefined })} className={pill(!category)}>
                    All articles
                  </a>
                </li>
                {(categories ?? []).map((c) => (
                  <li key={c.slug}>
                    <a
                      href={hrefWith({ q, tag }, { category: c.slug, page: undefined })}
                      aria-current={c.slug === category ? 'page' : undefined}
                      className={pill(c.slug === category)}
                    >
                      {c.name}
                      <span className="ml-2 text-xs text-white/40">{c.posts}</span>
                    </a>
                  </li>
                ))}
              </ul>
            </nav>

            <form action="/blog" method="get" role="search" className="relative w-full lg:w-80">
              {category && <input type="hidden" name="category" value={category} />}
              {tag && <input type="hidden" name="tag" value={tag} />}
              <label htmlFor="blog-search" className="sr-only">
                Search articles
              </label>
              <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40" aria-hidden="true" />
              <input
                id="blog-search"
                name="q"
                type="search"
                defaultValue={q}
                placeholder="Search articles"
                className="h-11 w-full rounded-full border border-white/12 bg-white/[0.05] pl-11 pr-4 text-[15px] text-white placeholder:text-white/40 focus:border-brand-300/60 focus:outline-none focus:ring-2 focus:ring-brand-300/30"
              />
            </form>
          </div>

          {filtered && (
            <p className="mt-6 text-sm text-white/60">
              {result?.total ?? 0} article{result?.total === 1 ? '' : 's'}
              {activeCategory && <> in <span className="text-white">{activeCategory.name}</span></>}
              {tag && <> tagged <span className="text-white">#{tag}</span></>}
              {q && <> matching <span className="text-white">&ldquo;{q}&rdquo;</span></>}
              {' · '}
              <a href="/blog" className="font-medium text-brand-200 hover:text-brand-100">
                Clear filters
              </a>
            </p>
          )}

          {posts.length > 0 ? (
            <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {posts.map((post) => (
                <BlogCard key={post.slug} post={post} href={`/blog/${post.slug}`} headingLevel="h2" />
              ))}
            </div>
          ) : (
            <div className="mt-16 rounded-3xl border border-white/10 bg-white/[0.03] px-6 py-20 text-center">
              <p className="text-lg font-semibold text-white">{filtered ? 'No articles match that.' : 'Articles are on the way.'}</p>
              <p className="mt-2 text-white/60">
                {filtered ? 'Try another category or search term.' : 'Check back soon for guides and product news.'}
              </p>
            </div>
          )}

          {pages > 1 && (
            <nav aria-label="Pagination" className="mt-14 flex items-center justify-center gap-2">
              <PageLink href={page > 1 ? hrefWith(searchParams, { page: String(page - 1) }) : undefined} label="Previous page">
                <ChevronLeft className="h-4 w-4" />
              </PageLink>
              {Array.from({ length: pages }, (_, i) => i + 1).map((n) => (
                <PageLink key={n} href={hrefWith(searchParams, { page: String(n) })} current={n === page} label={`Page ${n}`}>
                  {n}
                </PageLink>
              ))}
              <PageLink href={page < pages ? hrefWith(searchParams, { page: String(page + 1) }) : undefined} label="Next page">
                <ChevronRight className="h-4 w-4" />
              </PageLink>
            </nav>
          )}
        </div>
      </div>
    </MarketingShell>
  )
}

function PageLink({
  href,
  current,
  label,
  children,
}: {
  href?: string
  current?: boolean
  label: string
  children: React.ReactNode
}) {
  const cls = cn(
    'inline-flex h-10 min-w-10 items-center justify-center rounded-full border px-3 text-sm font-medium transition-colors',
    current ? 'border-brand-300/60 bg-brand-500/25 text-white' : 'border-white/12 text-white/70 hover:border-white/25 hover:text-white',
    !href && 'pointer-events-none opacity-40'
  )
  if (!href) return <span className={cls} aria-hidden="true">{children}</span>
  return (
    <a href={href} aria-label={label} aria-current={current ? 'page' : undefined} className={cls}>
      {children}
    </a>
  )
}
