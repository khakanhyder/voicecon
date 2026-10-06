import { ChevronRight, Clock } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatPostDate, type BlogCard as BlogCardData, type BlogCategoryRef } from '@/lib/blog'
import { AuthorChip, BlogCard } from './BlogCard'
import { ShareLinks } from './ShareLinks'

export interface ArticleData {
  title: string
  excerpt: string
  content_html: string
  featured_image_url: string | null
  featured_image_alt: string
  category: BlogCategoryRef | null
  tags: string[]
  author: { name: string; avatar_url: string | null }
  published_at: string | null
  updated_at?: string | null
  reading_minutes: number
}

/**
 * Typography for the post body. The HTML comes from the console's editor and
 * is sanitised by the API (services/blog/content.py) before it is stored.
 */
export const ARTICLE_BODY_CLASS = cn(
  'prose prose-invert prose-lg max-w-none',
  'prose-headings:scroll-mt-24 prose-headings:font-semibold prose-headings:tracking-[-0.015em] prose-headings:text-white',
  'prose-h2:mt-12 prose-h2:text-[1.75rem] prose-h3:text-[1.35rem]',
  'prose-p:leading-[1.8] prose-p:text-white/75 prose-li:text-white/75 prose-li:marker:text-brand-300',
  'prose-strong:text-white prose-a:font-medium prose-a:text-brand-200 prose-a:decoration-brand-300/40 prose-a:underline-offset-4 hover:prose-a:decoration-brand-200',
  'prose-blockquote:border-l-brand-400 prose-blockquote:font-normal prose-blockquote:not-italic prose-blockquote:text-white/80',
  'prose-img:mx-auto prose-img:rounded-2xl prose-img:border prose-img:border-white/10',
  'prose-hr:border-white/10 prose-code:rounded prose-code:bg-white/10 prose-code:px-1.5 prose-code:py-0.5 prose-code:font-normal prose-code:text-brand-100 prose-code:before:content-none prose-code:after:content-none',
  'prose-pre:border prose-pre:border-white/10 prose-pre:bg-black/30',
  'prose-figcaption:text-center prose-figcaption:text-white/50'
)

/**
 * A full article: header, featured image, body, tags, sharing and related
 * posts. Server-renderable; the console's preview renders the same component,
 * so what an editor previews is what readers get.
 */
export function ArticleView({
  article,
  related = [],
  shareUrl,
  preview = false,
}: {
  article: ArticleData
  related?: BlogCardData[]
  /** The article's public URL; omit to hide sharing (previews). */
  shareUrl?: string
  /** Links go nowhere in a preview: the post may not be live yet. */
  preview?: boolean
}) {
  const date = formatPostDate(article.published_at)
  const link = (href: string) => (preview ? undefined : href)

  return (
    <article className="px-4 pb-20 pt-28 sm:px-6 md:pt-36">
      <header className="mx-auto max-w-3xl text-center">
        <nav aria-label="Breadcrumb" className="flex items-center justify-center gap-1.5 text-sm text-white/55">
          <a href={link('/blog')} className="transition-colors hover:text-white">
            Blog
          </a>
          {article.category && (
            <>
              <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
              <a href={link(`/blog?category=${article.category.slug}`)} className="text-brand-200 transition-colors hover:text-brand-100">
                {article.category.name}
              </a>
            </>
          )}
        </nav>

        <h1 className="mt-6 text-balance text-[clamp(2rem,5vw,3.25rem)] font-bold leading-[1.1] tracking-[-0.025em] text-white">
          {article.title}
        </h1>
        {article.excerpt && (
          <p className="mx-auto mt-5 max-w-2xl text-pretty text-lg leading-relaxed text-white/65">{article.excerpt}</p>
        )}

        <div className="mt-8 flex flex-wrap items-center justify-center gap-x-5 gap-y-3 text-sm text-white/55">
          <AuthorChip name={article.author.name} avatarUrl={article.author.avatar_url} size="md" />
          {date && (
            <>
              <span aria-hidden="true" className="hidden h-4 w-px bg-white/15 sm:block" />
              <time dateTime={article.published_at ?? undefined}>{date}</time>
            </>
          )}
          <span aria-hidden="true" className="hidden h-4 w-px bg-white/15 sm:block" />
          <span className="inline-flex items-center gap-1.5">
            <Clock className="h-4 w-4" aria-hidden="true" />
            {article.reading_minutes} min read
          </span>
        </div>
      </header>

      {article.featured_image_url && (
        <figure className="mx-auto mt-12 max-w-5xl">
          <div className="aspect-video overflow-hidden rounded-[28px] border border-white/10 bg-[#0c2423] shadow-[0_30px_80px_-40px_rgba(0,0,0,0.8)]">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={article.featured_image_url}
              alt={article.featured_image_alt || article.title}
              className="h-full w-full object-cover"
              fetchPriority="high"
            />
          </div>
        </figure>
      )}

      <div className="mx-auto mt-12 max-w-3xl">
        <div className={ARTICLE_BODY_CLASS} dangerouslySetInnerHTML={{ __html: article.content_html }} />

        {(article.tags.length > 0 || shareUrl) && (
          <footer className="mt-14 flex flex-col gap-6 border-t border-white/10 pt-8 sm:flex-row sm:items-center sm:justify-between">
            {article.tags.length > 0 ? (
              <ul className="flex flex-wrap gap-2" aria-label="Tags">
                {article.tags.map((tag) => (
                  <li key={tag}>
                    <a
                      href={link(`/blog?tag=${encodeURIComponent(tag)}`)}
                      className="inline-flex rounded-full border border-white/15 bg-white/[0.04] px-3.5 py-1.5 text-sm text-white/75 transition-colors hover:border-brand-300/50 hover:text-white"
                    >
                      #{tag}
                    </a>
                  </li>
                ))}
              </ul>
            ) : (
              <span />
            )}
            {shareUrl && <ShareLinks url={shareUrl} title={article.title} />}
          </footer>
        )}
      </div>

      {related.length > 0 && (
        <section aria-labelledby="related-title" className="mx-auto mt-24 max-w-6xl">
          <div className="flex items-end justify-between gap-4">
            <h2 id="related-title" className="text-2xl font-bold tracking-[-0.02em] text-white sm:text-3xl">
              Keep reading
            </h2>
            <a href={link('/blog')} className="text-sm font-semibold text-brand-200 hover:text-brand-100">
              All articles →
            </a>
          </div>
          <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {related.map((post) => (
              <BlogCard key={post.slug} post={post} href={link(`/blog/${post.slug}`)} />
            ))}
          </div>
        </section>
      )}
    </article>
  )
}
