import type { MetadataRoute } from 'next'
import { SECTION_PATHS } from '@/components/landing/sections'
import { fetchBlogSitemap, parsePostDate } from '@/lib/blog'

// The public marketing site only; the app host's pages are all private.
const SITE = 'https://voicecon.ai'

// Re-read the list of live posts at most once a minute, like the blog pages.
export const revalidate = 60

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const paths = ['/', ...Object.keys(SECTION_PATHS), '/blog', '/affiliate-program', '/privacy', '/terms']
  const pages: MetadataRoute.Sitemap = paths.map((path) => ({
    url: `${SITE}${path === '/' ? '' : path}`,
    changeFrequency: path === '/privacy' || path === '/terms' ? 'yearly' : path === '/blog' ? 'weekly' : 'monthly',
    priority: path === '/' ? 1 : 0.6,
  }))
  const posts = (await fetchBlogSitemap()) ?? []
  return [
    ...pages,
    ...posts.map((post) => ({
      url: `${SITE}/blog/${post.slug}`,
      lastModified: parsePostDate(post.updated_at) ?? undefined,
      changeFrequency: 'monthly' as const,
      priority: 0.7,
    })),
  ]
}
