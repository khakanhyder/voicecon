import { ArrowRight } from 'lucide-react'
import { BlogCard } from '@/components/blog/BlogCard'
import type { BlogCard as BlogCardData } from '@/lib/blog'
import { Accent, Section, SectionHeading, buttonClass } from './primitives'
import { Reveal } from './Reveal'

/**
 * The home page's blog section: posts marked "Show on home page" in the
 * console first, then the newest (GET /blog/highlights). Not rendered at all
 * until something is published.
 */
export function BlogHighlights({ posts }: { posts: BlogCardData[] }) {
  if (posts.length === 0) return null
  return (
    <Section id="blog" labelledBy="blog-title" className="border-t border-white/[0.06]">
      <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
        <SectionHeading
          id="blog-title"
          align="left"
          eyebrow="From the blog"
          title={
            <>
              Ideas for teams that <Accent>run on calls</Accent>
            </>
          }
          description="Guides, playbooks and product news on AI voice agents and the workflows around them."
        />
        <Reveal className="flex-shrink-0">
          <a href="/blog" className={buttonClass('ghost', 'md')}>
            View all articles
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </a>
        </Reveal>
      </div>
      <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {posts.map((post, i) => (
          <Reveal key={post.slug} delay={i * 80} className="h-full">
            <BlogCard post={post} href={`/blog/${post.slug}`} />
          </Reveal>
        ))}
      </div>
    </Section>
  )
}
