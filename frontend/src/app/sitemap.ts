import type { MetadataRoute } from 'next'
import { SECTION_PATHS } from '@/components/landing/sections'

// The public marketing site only; the app host's pages are all private.
const SITE = 'https://voicecon.ai'

export default function sitemap(): MetadataRoute.Sitemap {
  const paths = ['/', ...Object.keys(SECTION_PATHS), '/affiliate-program', '/privacy', '/terms']
  return paths.map((path) => ({
    url: `${SITE}${path === '/' ? '' : path}`,
    changeFrequency: path === '/privacy' || path === '/terms' ? 'yearly' : 'monthly',
    priority: path === '/' ? 1 : 0.6,
  }))
}
