/**
 * The blog: types and the public reads the website does on the server
 * (`/api/v1/blog`, no session). The console's client is in lib/blog-admin.ts,
 * kept apart so server pages never bundle the browser API client.
 *
 * Featured images are shown in a 16:9 frame everywhere (home page, /blog,
 * article header, link previews), so the console recommends 1200 × 675 uploads.
 */
import { API_BASE } from '@/lib/constants'

// ---------- Types ----------

export type PostStatus = 'draft' | 'published' | 'scheduled'

export interface BlogCategoryRef {
  id: string
  name: string
  slug: string
}

export interface BlogAuthor {
  id: string | null
  name: string
  avatar_url: string | null
}

/** A post as a card: no body. */
export interface BlogCard {
  slug: string
  title: string
  excerpt: string
  featured_image_url: string | null
  featured_image_alt: string
  category: BlogCategoryRef | null
  tags: string[]
  author: BlogAuthor
  published_at: string | null
  updated_at: string | null
  reading_minutes: number
  is_featured: boolean
}

export interface BlogArticle extends BlogCard {
  content_html: string
  social_image_url: string | null
  seo_title: string | null
  seo_description: string | null
  related?: BlogCard[]
}

export interface BlogPostRow extends BlogCard {
  id: string
  status: PostStatus
  stored_status: 'draft' | 'published'
  created_at: string
}

export interface BlogPostDetail extends BlogPostRow {
  content_html: string
  social_image_url: string | null
  seo_title: string | null
  seo_description: string | null
  category_id: string | null
  author_id: string | null
}

export interface BlogPostInput {
  title?: string
  slug?: string
  excerpt?: string
  content_html?: string
  featured_image_url?: string | null
  featured_image_alt?: string
  social_image_url?: string | null
  category_id?: string | null
  tags?: string[]
  author_id?: string | null
  status?: 'draft' | 'published'
  published_at?: string | null
  is_featured?: boolean
  seo_title?: string
  seo_description?: string
}

export interface BlogCategory extends BlogCategoryRef {
  description: string | null
  posts: number
  created_at?: string
}

export interface BlogOverview {
  counts: {
    total: number
    published: number
    scheduled: number
    draft: number
    featured: number
    published_this_month: number
  }
  monthly: { year: number; month: number; posts: number }[]
  by_category: { name: string; posts: number }[]
  by_author: { name: string; posts: number }[]
  recent: BlogPostRow[]
  upcoming: BlogPostRow[]
  generated_at: string
}

export type ConsoleRole = 'admin' | 'blog_editor' | 'blog_viewer'

export interface ConsoleAuthor {
  id: string
  name: string
  email: string
  role: ConsoleRole
  is_active: boolean
}

export interface BlogTeamMember {
  id: string
  email: string
  full_name: string | null
  role: ConsoleRole
  is_active: boolean
  posts: number
  last_login_at: string | null
  created_at: string | null
}

export interface Paged<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export const ROLE_LABELS: Record<ConsoleRole, string> = {
  admin: 'Admin',
  blog_editor: 'Blog Editor',
  blog_viewer: 'Blog Viewer',
}

export const FEATURED_IMAGE = { width: 1200, height: 675, label: '1200 × 675 px, 16:9, JPG/WebP/PNG' } as const

// ---------- Public reads (server components) ----------

/** Seconds a fetched blog page is reused; a publish shows on the site within this. */
export const BLOG_REVALIDATE = 60

async function publicGet<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/blog${path}`, { next: { revalidate: BLOG_REVALIDATE } })
    if (!res.ok) return null
    return (await res.json()) as T
  } catch {
    // The API is unreachable (a build with no network, a deploy in progress):
    // the page renders without posts rather than failing.
    return null
  }
}

export function fetchBlogPosts(params: { page?: number; category?: string; tag?: string; q?: string; page_size?: number }) {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== '') qs.set(k, String(v))
  return publicGet<Paged<BlogCard>>(`/posts?${qs.toString()}`)
}

export const fetchBlogHighlights = (limit = 3) => publicGet<BlogCard[]>(`/highlights?limit=${limit}`)
export const fetchBlogCategories = () => publicGet<(BlogCategoryRef & { description: string | null; posts: number })[]>('/categories')
export const fetchBlogArticle = (slug: string) => publicGet<BlogArticle>(`/posts/${encodeURIComponent(slug)}`)
export const fetchBlogSitemap = () => publicGet<{ slug: string; updated_at: string | null }[]>('/sitemap')

// ---------- Formatting ----------

/**
 * An API timestamp as a Date. Same rule as lib/datetime's parseApiDate (a value
 * with no zone is UTC), repeated here because that module uses a React hook
 * and so cannot be imported by the website's server components.
 */
export function parsePostDate(value: string | null | undefined): Date | null {
  if (!value) return null
  const d = new Date(/(?:[zZ]|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`)
  return Number.isNaN(d.getTime()) ? null : d
}

/**
 * "September 25, 2026", the site's date style. Shown as the UTC calendar day so
 * the server render and the browser agree (and every reader sees the same date).
 */
export function formatPostDate(value: string | null | undefined): string {
  const d = parsePostDate(value)
  if (!d) return ''
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' })
}
