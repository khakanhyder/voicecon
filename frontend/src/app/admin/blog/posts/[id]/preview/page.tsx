'use client'

import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, ExternalLink, Pencil } from 'lucide-react'
import { blogApi } from '@/lib/blog-admin'
import { Callout, errorText } from '@/components/admin/ui'
import { PreviewSurface } from '@/components/admin/blog/PostPreview'
import { PostStatusBadge, publicUrl, useCanWriteBlog } from '@/components/admin/blog/shared'

/**
 * The saved post as the website shows it, for any console user, before or
 * after it goes live. Unsaved edits are previewed from the editor instead.
 */
export default function BlogPostPreviewPage({ params }: { params: { id: string } }) {
  const canWrite = useCanWriteBlog()
  const { data: post, isLoading, error } = useQuery({ queryKey: ['blog', 'post', params.id], queryFn: () => blogApi.post(params.id) })

  if (isLoading) return <div className="h-[70vh] animate-pulse rounded-xl bg-slate-100" />
  if (error || !post) {
    return (
      <Callout tone="danger" title="This post could not be loaded">
        {errorText(error)}
      </Callout>
    )
  }

  const link = 'inline-flex h-8 items-center gap-1.5 rounded-md bg-white/10 px-3 text-xs font-medium text-white hover:bg-white/20'
  return (
    // Bleed past the console's page padding so the preview fills the pane.
    <div className="-mx-4 -my-6 md:-mx-8 md:-my-8">
      <PreviewSurface
        article={post}
        toolbar={
          <>
            <PostStatusBadge status={post.status} />
            <Link href="/admin/blog/posts" className={link}>
              <ArrowLeft className="h-3.5 w-3.5" />
              All posts
            </Link>
            <Link href={`/admin/blog/posts/${post.id}`} className={link}>
              <Pencil className="h-3.5 w-3.5" />
              {canWrite ? 'Edit' : 'Details'}
            </Link>
            {post.status === 'published' && (
              <a href={publicUrl(post.slug)} target="_blank" rel="noopener noreferrer" className={link}>
                <ExternalLink className="h-3.5 w-3.5" />
                View live
              </a>
            )}
          </>
        }
      />
    </div>
  )
}
