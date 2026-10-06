'use client'

import { useEffect, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { FileText, LayoutGrid, X } from 'lucide-react'
import { ArticleView, type ArticleData } from '@/components/blog/ArticleView'
import { BlogCard } from '@/components/blog/BlogCard'
import type { BlogCard as BlogCardData } from '@/lib/blog'
import { cn } from '@/lib/utils'

/**
 * The post as the website will show it, rendered with the website's own
 * components (ArticleView, BlogCard) on the site's background. Links inside
 * are inert: the post may not be live.
 */
export function PreviewSurface({ article, toolbar }: { article: ArticleData & { slug?: string }; toolbar?: ReactNode }) {
  const [view, setView] = useState<'article' | 'card'>('article')
  const card: BlogCardData = {
    slug: article.slug || 'preview',
    title: article.title || 'Untitled post',
    excerpt: article.excerpt,
    featured_image_url: article.featured_image_url,
    featured_image_alt: article.featured_image_alt,
    category: article.category,
    tags: article.tags,
    author: { id: null, ...article.author },
    published_at: article.published_at,
    updated_at: article.updated_at ?? null,
    reading_minutes: article.reading_minutes,
    is_featured: false,
  }

  const tab = (active: boolean) =>
    cn(
      'inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-xs font-medium transition-colors',
      active ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-300 hover:text-white'
    )

  return (
    <div className="min-h-full bg-[#10302f] bg-[radial-gradient(120%_90%_at_50%_-10%,#1c5453_0%,#16403f_45%,#10302f_100%)] text-white antialiased">
      <div className="sticky top-0 z-20 flex flex-wrap items-center gap-3 border-b border-white/10 bg-slate-950/90 px-4 py-2.5 backdrop-blur">
        <span className="rounded-full bg-amber-400/15 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider text-amber-300">
          Preview
        </span>
        <div className="flex rounded-lg bg-white/10 p-0.5" role="tablist" aria-label="Preview type">
          <button type="button" role="tab" aria-selected={view === 'article'} className={tab(view === 'article')} onClick={() => setView('article')}>
            <FileText className="h-3.5 w-3.5" />
            Article page
          </button>
          <button type="button" role="tab" aria-selected={view === 'card'} className={tab(view === 'card')} onClick={() => setView('card')}>
            <LayoutGrid className="h-3.5 w-3.5" />
            Blog card
          </button>
        </div>
        <div className="ml-auto flex items-center gap-2">{toolbar}</div>
      </div>

      {view === 'article' ? (
        // The article's own top padding assumes the site's fixed navbar.
        <div className="-mt-16">
          <ArticleView article={{ ...article, title: article.title || 'Untitled post' }} preview />
        </div>
      ) : (
        <div className="px-4 py-16 sm:px-6">
          <p className="mx-auto mb-6 max-w-6xl text-sm text-white/60">
            How the post appears on the home page, the blog page and in &ldquo;Keep reading&rdquo;.
          </p>
          <div className="mx-auto grid max-w-6xl gap-6 sm:grid-cols-2 lg:grid-cols-3">
            <BlogCard post={card} />
            <div className="hidden rounded-3xl border border-dashed border-white/10 sm:block" aria-hidden="true" />
            <div className="hidden rounded-3xl border border-dashed border-white/10 lg:block" aria-hidden="true" />
          </div>
        </div>
      )}
    </div>
  )
}

/** Full-screen preview over the editor, for unsaved changes. */
export function PreviewDialog({ open, onClose, article }: { open: boolean; onClose: () => void; article: ArticleData & { slug?: string } }) {
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = overflow
    }
  }, [open, onClose])
  if (!open || !mounted) return null
  return createPortal(
    <div role="dialog" aria-modal="true" aria-label="Post preview" className="fixed inset-0 z-[9600] overflow-y-auto">
      <PreviewSurface
        article={article}
        toolbar={
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-8 items-center gap-1.5 rounded-md bg-white/10 px-3 text-xs font-medium text-white hover:bg-white/20"
          >
            <X className="h-3.5 w-3.5" />
            Close preview
          </button>
        }
      />
    </div>,
    document.body
  )
}
