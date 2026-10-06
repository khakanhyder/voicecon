import { ArrowUpRight, Clock } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatPostDate, type BlogCard as BlogCardData } from '@/lib/blog'

/**
 * One post as a card, used on the home page's blog section, /blog and the
 * "related articles" row. No hooks, so it renders on the server as well as in
 * the console's preview.
 *
 * The image frame is fixed at 16:9 (the recommended 1200 × 675 upload) and
 * crops anything else from the centre, so a row of cards always lines up.
 */
export function BlogCard({
  post,
  href,
  className,
  headingLevel = 'h3',
}: {
  post: BlogCardData
  /** Omit to render without a link (console preview). */
  href?: string
  className?: string
  headingLevel?: 'h2' | 'h3'
}) {
  const Heading = headingLevel
  const date = formatPostDate(post.published_at)
  const body = (
    <>
      <div className="relative aspect-video overflow-hidden rounded-2xl bg-[#0c2423]">
        {post.featured_image_url ? (
          // eslint-disable-next-line @next/next/no-img-element -- uploads live on the API/S3 host
          <img
            src={post.featured_image_url}
            alt={post.featured_image_alt || post.title}
            loading="lazy"
            decoding="async"
            className="h-full w-full object-cover transition-transform duration-500 ease-out group-hover:scale-[1.03] motion-reduce:transition-none"
          />
        ) : (
          <ImagePlaceholder title={post.title} />
        )}
        {post.category && (
          <span className="absolute left-3 top-3 rounded-full border border-white/15 bg-[#0f2c2b]/80 px-3 py-1 text-xs font-semibold text-brand-100 backdrop-blur">
            {post.category.name}
          </span>
        )}
      </div>

      <div className="flex flex-1 flex-col px-1 pt-5">
        <p className="flex flex-wrap items-center gap-x-2 text-[13px] text-white/50">
          {date && <time dateTime={post.published_at ?? undefined}>{date}</time>}
          {date && <span aria-hidden="true">·</span>}
          <span className="inline-flex items-center gap-1">
            <Clock className="h-3.5 w-3.5" aria-hidden="true" />
            {post.reading_minutes} min read
          </span>
        </p>
        <Heading className="mt-2.5 line-clamp-2 text-xl font-semibold leading-snug tracking-[-0.01em] text-brand-200 transition-colors group-hover:text-brand-100">
          {post.title}
        </Heading>
        {post.excerpt && <p className="mt-3 line-clamp-3 text-[15px] leading-relaxed text-white/65">{post.excerpt}</p>}

        <div className="mt-auto flex items-center justify-between gap-3 pt-6">
          <AuthorChip name={post.author.name} avatarUrl={post.author.avatar_url} />
          <span
            aria-hidden="true"
            className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full border border-white/25 text-white transition-colors group-hover:border-brand-300 group-hover:bg-brand-500 group-hover:text-white"
          >
            <ArrowUpRight className="h-5 w-5" />
          </span>
        </div>
      </div>
    </>
  )

  const shell = cn(
    'group relative flex h-full flex-col overflow-hidden rounded-3xl border border-white/[0.1] bg-gradient-to-b from-white/[0.06] to-white/[0.02] p-3 pb-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.05),0_18px_40px_-24px_rgba(0,0,0,0.6)] transition-[transform,border-color] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] hover:-translate-y-1 hover:border-brand-300/35 motion-reduce:hover:translate-y-0',
    className
  )

  if (!href) return <article className={shell}>{body}</article>
  return (
    <article className={shell}>
      <a
        href={href}
        className="flex flex-1 flex-col rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-200 focus-visible:ring-offset-4 focus-visible:ring-offset-[#10302f]"
      >
        <span className="sr-only">Read article: </span>
        {body}
      </a>
    </article>
  )
}

export function AuthorChip({ name, avatarUrl, size = 'sm' }: { name: string; avatarUrl: string | null; size?: 'sm' | 'md' }) {
  const box = size === 'md' ? 'h-10 w-10 text-sm' : 'h-8 w-8 text-xs'
  return (
    <span className="flex min-w-0 items-center gap-2.5">
      {avatarUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={avatarUrl} alt="" className={cn('flex-shrink-0 rounded-full object-cover', box)} />
      ) : (
        <span
          aria-hidden="true"
          className={cn('flex flex-shrink-0 items-center justify-center rounded-full bg-brand-500/25 font-semibold text-brand-100', box)}
        >
          {initials(name)}
        </span>
      )}
      <span className={cn('truncate font-medium text-white/80', size === 'md' ? 'text-[15px]' : 'text-sm')}>{name}</span>
    </span>
  )
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  return ((parts[0]?.[0] ?? 'V') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
}

/** Shown when a post has no featured image: a branded panel, not a broken frame. */
export function ImagePlaceholder({ title }: { title: string }) {
  return (
    <div className="flex h-full w-full items-end bg-[radial-gradient(120%_120%_at_0%_0%,#1f6a5c_0%,#143f3c_45%,#0c2423_100%)] p-5">
      <span className="line-clamp-2 text-lg font-semibold leading-snug text-white/85">{title}</span>
    </div>
  )
}
