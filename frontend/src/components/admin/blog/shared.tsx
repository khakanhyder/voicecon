'use client'

/**
 * Pieces shared by the console's blog pages.
 */
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useRouter } from 'next/navigation'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Eye, EyeOff, ExternalLink, ImageIcon, MoreHorizontal, Pencil, Send, Trash2 } from 'lucide-react'
import { adminApi } from '@/lib/admin'
import { blogApi } from '@/lib/blog-admin'
import type { BlogPostRow, PostStatus } from '@/lib/blog'
import { AdminButton, Badge, Dialog, errorText, formatDate } from '@/components/admin/ui'
import { cn } from '@/lib/utils'

/** The signed-in console user (cached by the layout, which loads it first). */
export function useConsoleMe() {
  return useQuery({ queryKey: ['admin', 'me'], queryFn: adminApi.me, staleTime: 5 * 60 * 1000 })
}

/** Whether this person may write: admins and blog editors. The API checks again. */
export function useCanWriteBlog(): boolean {
  return useConsoleMe().data?.permissions.includes('blog:write') ?? false
}

const STATUS: Record<PostStatus, { label: string; tone: 'success' | 'info' | 'neutral' }> = {
  published: { label: 'Published', tone: 'success' },
  scheduled: { label: 'Scheduled', tone: 'info' },
  draft: { label: 'Draft', tone: 'neutral' },
}

export function PostStatusBadge({ status }: { status: PostStatus }) {
  const s = STATUS[status] ?? STATUS.draft
  return (
    <Badge tone={s.tone} dot>
      {s.label}
    </Badge>
  )
}

export function PostThumb({ url, className }: { url: string | null; className?: string }) {
  return (
    <span className={cn('flex aspect-video w-20 flex-shrink-0 items-center justify-center overflow-hidden rounded-md bg-slate-100', className)}>
      {url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url} alt="" className="h-full w-full object-cover" />
      ) : (
        <ImageIcon className="h-4 w-4 text-slate-300" />
      )}
    </span>
  )
}

/** When the post went (or goes) live, or "Not published". */
export function publishedLabel(post: Pick<BlogPostRow, 'status' | 'published_at'>): string {
  if (post.status === 'draft') return 'Not published'
  return formatDate(post.published_at, true)
}

/** Where a live post can be seen on the website. */
export function publicUrl(slug: string): string {
  const site = process.env.NEXT_PUBLIC_SITE_URL || (typeof window !== 'undefined' && window.location.hostname === 'localhost' ? window.location.origin : 'https://voicecon.ai')
  return `${site.replace(/\/$/, '')}/blog/${slug}`
}

function invalidate(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ['blog'] })
}

/** Publish / unpublish / delete, with the confirmation and toasts. */
export function usePostActions() {
  const qc = useQueryClient()
  const publish = useMutation({
    mutationFn: (id: string) => blogApi.publish(id),
    onSuccess: (post) => {
      toast.success(post.status === 'scheduled' ? `Scheduled for ${formatDate(post.published_at, true)}` : 'Published. It is live on the website.')
      invalidate(qc)
    },
    onError: (e) => toast.error(errorText(e)),
  })
  const unpublish = useMutation({
    mutationFn: (id: string) => blogApi.unpublish(id),
    onSuccess: () => {
      toast.success('Unpublished. The post is a draft again.')
      invalidate(qc)
    },
    onError: (e) => toast.error(errorText(e)),
  })
  const remove = useMutation({
    mutationFn: (id: string) => blogApi.deletePost(id),
    onSuccess: () => {
      toast.success('Post deleted.')
      invalidate(qc)
    },
    onError: (e) => toast.error(errorText(e)),
  })
  return { publish, unpublish, remove }
}

export function DeletePostDialog({
  post,
  onClose,
  onDeleted,
}: {
  post: { id: string; title: string; status: PostStatus } | null
  onClose: () => void
  onDeleted?: () => void
}) {
  const { remove } = usePostActions()
  return (
    <Dialog
      open={!!post}
      onClose={() => !remove.isPending && onClose()}
      title="Delete this post?"
      description={
        <>
          <span className="font-medium text-slate-700">{post?.title}</span> will be deleted permanently
          {post?.status !== 'draft' ? ' and taken off the website' : ''}. This cannot be undone.
        </>
      }
      footer={
        <>
          <AdminButton variant="ghost" onClick={onClose} disabled={remove.isPending}>
            Cancel
          </AdminButton>
          <AdminButton
            variant="danger"
            icon={Trash2}
            loading={remove.isPending}
            onClick={() =>
              post &&
              remove.mutate(post.id, {
                onSuccess: () => {
                  onClose()
                  onDeleted?.()
                },
              })
            }
          >
            Delete post
          </AdminButton>
        </>
      }
    />
  )
}

/** The "…" menu on a post row. Viewers get only View/Preview. */
export function PostRowMenu({ post, canWrite, onDelete }: { post: BlogPostRow; canWrite: boolean; onDelete: () => void }) {
  const router = useRouter()
  const buttonRef = useRef<HTMLButtonElement>(null)
  // Fixed-position coordinates, or null when closed. Portalled to <body>
  // because the table scrolls sideways, which would clip an inline menu.
  const [at, setAt] = useState<{ top: number; left: number } | null>(null)
  const open = at !== null
  const setOpen = (value: boolean | ((v: boolean) => boolean)) => {
    const next = typeof value === 'function' ? value(open) : value
    if (!next) return setAt(null)
    const rect = buttonRef.current?.getBoundingClientRect()
    if (!rect) return
    const below = rect.bottom + 4 + 260 < window.innerHeight
    setAt({ top: below ? rect.bottom + 4 : Math.max(8, rect.top - 264), left: Math.max(8, rect.right - 192) })
  }
  useEffect(() => {
    if (!open) return
    const close = () => setAt(null)
    window.addEventListener('resize', close)
    window.addEventListener('scroll', close, true)
    return () => {
      window.removeEventListener('resize', close)
      window.removeEventListener('scroll', close, true)
    }
  }, [open])
  const { publish, unpublish } = usePostActions()
  const item = 'flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50'

  return (
    <div className="relative" onClick={(e) => e.stopPropagation()}>
      <button
        ref={buttonRef}
        type="button"
        aria-label={`Actions for ${post.title}`}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
      >
        <MoreHorizontal className="h-4 w-4" />
      </button>
      {at && createPortal(
        <div onClick={(e) => e.stopPropagation()}>
          <div className="fixed inset-0 z-[8000]" onClick={() => setOpen(false)} />
          <div
            role="menu"
            style={{ top: at.top, left: at.left }}
            className="fixed z-[8001] w-48 overflow-hidden rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
          >
            <button type="button" role="menuitem" className={item} onClick={() => router.push(`/admin/blog/posts/${post.id}`)}>
              <Pencil className="h-4 w-4 text-slate-400" />
              {canWrite ? 'Edit' : 'View details'}
            </button>
            <button type="button" role="menuitem" className={item} onClick={() => router.push(`/admin/blog/posts/${post.id}/preview`)}>
              <Eye className="h-4 w-4 text-slate-400" />
              Preview
            </button>
            {post.status === 'published' && (
              <a role="menuitem" className={item} href={publicUrl(post.slug)} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="h-4 w-4 text-slate-400" />
                View on website
              </a>
            )}
            {canWrite && (
              <>
                <div className="my-1 border-t border-slate-100" />
                {post.status === 'draft' ? (
                  <button
                    type="button"
                    role="menuitem"
                    className={item}
                    onClick={() => {
                      setOpen(false)
                      publish.mutate(post.id)
                    }}
                  >
                    <Send className="h-4 w-4 text-slate-400" />
                    Publish now
                  </button>
                ) : (
                  <button
                    type="button"
                    role="menuitem"
                    className={item}
                    onClick={() => {
                      setOpen(false)
                      unpublish.mutate(post.id)
                    }}
                  >
                    <EyeOff className="h-4 w-4 text-slate-400" />
                    Unpublish
                  </button>
                )}
                <button
                  type="button"
                  role="menuitem"
                  className={cn(item, 'text-rose-600')}
                  onClick={() => {
                    setOpen(false)
                    onDelete()
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                  Delete
                </button>
              </>
            )}
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}
