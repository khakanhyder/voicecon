import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import { MarketingShell } from '@/components/landing/MarketingShell'
import { ArticleView } from '@/components/blog/ArticleView'
import { fetchBlogArticle, parsePostDate } from '@/lib/blog'

/**
 * One article at voicecon.ai/blog/<slug>. Drafts, scheduled posts and
 * unpublished posts are a 404 from the API, so they are a 404 here too.
 */

export const revalidate = 60

const SITE = 'https://voicecon.ai'

interface Props {
  params: { slug: string }
}

const iso = (value: string | null | undefined) => parsePostDate(value)?.toISOString()

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const article = await fetchBlogArticle(params.slug)
  if (!article) return { title: 'Article not found | Voicecon', robots: { index: false } }
  const title = article.seo_title || `${article.title} | Voicecon Blog`
  const description = article.seo_description || article.excerpt
  const image = article.social_image_url || article.featured_image_url
  const path = `/blog/${article.slug}`
  return {
    metadataBase: new URL(SITE),
    title,
    description,
    alternates: { canonical: path },
    authors: [{ name: article.author.name }],
    keywords: article.tags,
    openGraph: {
      type: 'article',
      url: `${SITE}${path}`,
      siteName: 'Voicecon',
      title: article.seo_title || article.title,
      description,
      publishedTime: iso(article.published_at),
      modifiedTime: iso(article.updated_at),
      authors: [article.author.name],
      section: article.category?.name,
      tags: article.tags,
      images: image ? [{ url: image, width: 1200, height: 675, alt: article.featured_image_alt }] : [`${SITE}/landing/og-image.png`],
    },
    twitter: {
      card: 'summary_large_image',
      title: article.seo_title || article.title,
      description,
      images: [image || `${SITE}/landing/og-image.png`],
    },
  }
}

export default async function BlogArticlePage({ params }: Props) {
  const article = await fetchBlogArticle(params.slug)
  if (!article) notFound()
  const url = `${SITE}/blog/${article.slug}`

  const structuredData = {
    '@context': 'https://schema.org',
    '@type': 'BlogPosting',
    headline: article.title,
    description: article.seo_description || article.excerpt,
    image: article.featured_image_url ? [article.featured_image_url] : undefined,
    datePublished: iso(article.published_at),
    dateModified: iso(article.updated_at),
    author: { '@type': 'Person', name: article.author.name },
    publisher: { '@type': 'Organization', name: 'Voicecon', logo: { '@type': 'ImageObject', url: `${SITE}/icon.svg` } },
    mainEntityOfPage: { '@type': 'WebPage', '@id': url },
    keywords: article.tags.join(', ') || undefined,
    articleSection: article.category?.name,
  }

  return (
    <MarketingShell>
      <script
        type="application/ld+json"
        // "<" escaped so a title containing "</script>" cannot end the tag.
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData).replace(/</g, '\\u003c') }}
      />
      <ArticleView article={article} related={article.related ?? []} shareUrl={url} />
    </MarketingShell>
  )
}
