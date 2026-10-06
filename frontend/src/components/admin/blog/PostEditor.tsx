'use client'

/**
 * Add / edit a blog post. One form for both: `postId` undefined is a new post.
 *
 * Status works like most CMSs: choose Draft or Published, and the main button
 * says what saving will do ("Save draft", "Publish", "Schedule", "Update").
 * A publish date in the future schedules the post; it goes live on its own at
 * that time (the public API only lists posts whose date has passed).
 *
 * Blog viewers get the same page read-only. The API refuses their writes
 * regardless (app/core/admin.py).
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { ArrowLeft, CalendarClock, Check, ExternalLink, Eye, EyeOff, Plus, Save, Send, Star, Trash2, X } from 'lucide-react'
import { blogApi } from '@/lib/blog-admin'
import type { BlogPostDetail, BlogPostInput } from '@/lib/blog'
import { parseApiDate } from '@/lib/datetime'
import {
  AdminButton,
  Callout,
  Field,
  Panel,
  Toggle,
  errorText,
  formatDate,
  inputClass,
} from '@/components/admin/ui'
import { cn } from '@/lib/utils'
import { RichTextEditor } from './RichTextEditor'
import { ImageUploadField } from './ImageUploadField'
import { PreviewDialog } from './PostPreview'
import { DeletePostDialog, PostStatusBadge, publicUrl, useConsoleMe, usePostActions } from './shared'

interface FormState {
  title: string
  slug: string
  excerpt: string
  content_html: string
  featured_image_url: string | null
  featured_image_alt: string
  social_image_url: string | null
  category_id: string
  tags: string[]
  author_id: string
  status: 'draft' | 'published'
  /** `YYYY-MM-DDTHH:mm` in the editor's local time, or '' for "when published". */
  published_at: string
  is_featured: boolean
  seo_title: string
  seo_description: string
}

const EMPTY: FormState = {
  title: '',
  slug: '',
  excerpt: '',
  content_html: '',
  featured_image_url: null,
  featured_image_alt: '',
  social_image_url: null,
  category_id: '',
  tags: [],
  author_id: '',
  status: 'draft',
  published_at: '',
  is_featured: false,
  seo_title: '',
  seo_description: '',
}

const EXCERPT_MAX = 300
const SEO_TITLE_MAX = 60
const SEO_DESC_MAX = 160

function slugify(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 120)
    .replace(/-+$/, '')
}

/** API timestamp → `<input type="datetime-local">` value, in the browser's zone. */
function toLocalInput(value: string | null | undefined): string {
  const d = parseApiDate(value)
  if (!d) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function fromPost(post: BlogPostDetail): FormState {
  return {
    title: post.title,
    slug: post.slug,
    excerpt: post.excerpt ?? '',
    content_html: post.content_html ?? '',
    featured_image_url: post.featured_image_url,
    featured_image_alt: post.featured_image_alt === post.title ? '' : post.featured_image_alt ?? '',
    social_image_url: post.social_image_url,
    category_id: post.category_id ?? '',
    tags: post.tags ?? [],
    author_id: post.author_id ?? '',
    status: post.stored_status,
    published_at: toLocalInput(post.published_at),
    is_featured: post.is_featured,
    seo_title: post.seo_title ?? '',
    seo_description: post.seo_description ?? '',
  }
}

function toBody(form: FormState): BlogPostInput {
  return {
    ...form,
    category_id: form.category_id || null,
    author_id: form.author_id || null,
    published_at: form.published_at ? new Date(form.published_at).toISOString() : null,
    featured_image_alt: form.featured_image_alt.trim(),
  }
}

export function PostEditor({ postId }: { postId?: string }) {
  const router = useRouter()
  const qc = useQueryClient()
  const me = useConsoleMe()
  const canWrite = me.data?.permissions.includes('blog:write') ?? false
  const readOnly = !canWrite

  const post = useQuery({ queryKey: ['blog', 'post', postId], queryFn: () => blogApi.post(postId!), enabled: !!postId })
  const categories = useQuery({ queryKey: ['blog', 'categories'], queryFn: blogApi.categories })
  const authors = useQuery({ queryKey: ['blog', 'authors'], queryFn: blogApi.authors })

  const [form, setForm] = useState<FormState>(EMPTY)
  const [saved, setSaved] = useState<FormState>(EMPTY)
  const [slugTouched, setSlugTouched] = useState(false)
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({})
  const [previewing, setPreviewing] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const initialised = useRef(false)

  // Seed the form once: from the saved post, or with the signed-in user as author.
  useEffect(() => {
    if (initialised.current) return
    if (postId && post.data) {
      const state = fromPost(post.data)
      setForm(state)
      setSaved(state)
      setSlugTouched(true)
      initialised.current = true
    } else if (!postId && me.data) {
      const state = { ...EMPTY, author_id: me.data.id }
      setForm(state)
      setSaved(state)
      initialised.current = true
    }
  }, [postId, post.data, me.data])

  const dirty = useMemo(() => JSON.stringify(form) !== JSON.stringify(saved), [form, saved])
  useEffect(() => {
    if (!dirty || readOnly) return
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty, readOnly])

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((f) => ({ ...f, [key]: value }))
    setErrors((e) => ({ ...e, [key]: undefined }))
  }

  // The slug follows the title until someone edits it by hand.
  const onTitle = (title: string) => {
    setForm((f) => ({ ...f, title, slug: slugTouched ? f.slug : slugify(title) }))
    setErrors((e) => ({ ...e, title: undefined }))
  }

  const [slugState, setSlugState] = useState<{ slug: string; available: boolean; suggestion: string | null } | null>(null)
  useEffect(() => {
    if (readOnly || !form.slug) return setSlugState(null)
    if (post.data && form.slug === post.data.slug) return setSlugState(null)
    const t = setTimeout(() => {
      blogApi
        .slugCheck(form.slug, postId)
        .then(setSlugState)
        .catch(() => setSlugState(null))
    }, 400)
    return () => clearTimeout(t)
  }, [form.slug, postId, post.data, readOnly])

  const scheduledFor = form.published_at ? new Date(form.published_at) : null
  const isFuture = !!scheduledFor && scheduledFor.getTime() > Date.now()
  const wasLive = post.data?.stored_status === 'published'

  const primaryLabel =
    form.status === 'draft'
      ? wasLive
        ? 'Unpublish & save'
        : 'Save draft'
      : isFuture
        ? 'Schedule'
        : wasLive
          ? 'Update'
          : 'Publish'

  const validate = (): boolean => {
    const next: typeof errors = {}
    if (!form.title.trim()) next.title = 'Add a title.'
    if (form.status === 'published' && !form.content_html.trim()) next.content_html = 'Write the article before publishing it.'
    if (form.excerpt.length > 400) next.excerpt = 'Keep the excerpt under 400 characters.'
    if (slugState && !slugState.available) next.slug = 'Another post already uses this URL.'
    setErrors(next)
    if (Object.keys(next).length) {
      toast.error(Object.values(next)[0] as string)
      return false
    }
    return true
  }

  const save = useMutation({
    mutationFn: (body: BlogPostInput) => (postId ? blogApi.updatePost(postId, body) : blogApi.createPost(body)),
    onSuccess: (result) => {
      const state = fromPost(result)
      setForm(state)
      setSaved(state)
      qc.invalidateQueries({ queryKey: ['blog'] })
      qc.setQueryData(['blog', 'post', result.id], result)
      toast.success(
        result.status === 'scheduled'
          ? `Scheduled for ${formatDate(result.published_at, true)}.`
          : result.status === 'published'
            ? wasLive
              ? 'Changes are live on the website.'
              : 'Published. It is live on the website.'
            : 'Draft saved.'
      )
      if (!postId) router.replace(`/admin/blog/posts/${result.id}`)
    },
    onError: (e) => toast.error(errorText(e)),
  })

  const { unpublish } = usePostActions()
  const submit = () => validate() && save.mutate(toBody(form))

  if ((postId && post.isLoading) || me.isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-64 animate-pulse rounded bg-slate-200" />
        <div className="h-[520px] animate-pulse rounded-xl bg-slate-100" />
      </div>
    )
  }
  if (postId && post.isError) {
    return (
      <Callout tone="danger" title="This post could not be loaded">
        {errorText(post.error)} <Link href="/admin/blog/posts" className="font-medium underline">Back to all posts</Link>
      </Callout>
    )
  }

  const category = categories.data?.find((c) => c.id === form.category_id) ?? null
  const author = authors.data?.find((a) => a.id === form.author_id)
  const previewArticle = {
    slug: form.slug,
    title: form.title,
    excerpt: form.excerpt,
    content_html: form.content_html,
    featured_image_url: form.featured_image_url,
    featured_image_alt: form.featured_image_alt || form.title,
    category: category ? { id: category.id, name: category.name, slug: category.slug } : null,
    tags: form.tags,
    author: { name: author?.name ?? post.data?.author.name ?? me.data?.full_name ?? 'Voicecon Team', avatar_url: post.data?.author.avatar_url ?? null },
    published_at: scheduledFor ? scheduledFor.toISOString() : post.data?.published_at ?? new Date().toISOString(),
    reading_minutes: Math.max(1, Math.ceil(form.content_html.replace(/<[^>]+>/g, ' ').split(/\s+/).filter(Boolean).length / 220)),
  }

  return (
    <div className="pb-24">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <Link href="/admin/blog/posts" className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-800">
            <ArrowLeft className="h-3.5 w-3.5" />
            All posts
          </Link>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <h1 className="truncate text-2xl font-semibold tracking-tight text-slate-900">
              {postId ? (readOnly ? 'View post' : 'Edit post') : 'New post'}
            </h1>
            {post.data && <PostStatusBadge status={post.data.status} />}
            {dirty && !readOnly && <span className="text-xs font-medium text-amber-600">Unsaved changes</span>}
          </div>
          {post.data && (
            <p className="mt-1 text-xs text-slate-500">
              Created {formatDate(post.data.created_at, true)} · Last updated {formatDate(post.data.updated_at, true)}
              {post.data.published_at && post.data.status !== 'draft' && <> · {post.data.status === 'scheduled' ? 'Goes live' : 'Published'} {formatDate(post.data.published_at, true)}</>}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {post.data?.status === 'published' && (
            <a
              href={publicUrl(post.data.slug)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-9 items-center gap-2 rounded-lg px-3 text-sm font-medium text-slate-600 hover:bg-slate-100"
            >
              <ExternalLink className="h-4 w-4" />
              View live
            </a>
          )}
          <AdminButton icon={Eye} onClick={() => setPreviewing(true)}>
            Preview
          </AdminButton>
          {!readOnly && wasLive && postId && (
            <AdminButton
              icon={EyeOff}
              loading={unpublish.isPending}
              onClick={() => {
                if (dirty) return toast.error('Save or discard your changes first.')
                unpublish.mutate(postId, {
                  onSuccess: (result) => {
                    const state = fromPost(result)
                    setForm(state)
                    setSaved(state)
                    qc.setQueryData(['blog', 'post', result.id], result)
                  },
                })
              }}
            >
              Unpublish
            </AdminButton>
          )}
          {!readOnly && (
            <AdminButton
              variant="primary"
              icon={form.status === 'draft' ? Save : isFuture ? CalendarClock : Send}
              loading={save.isPending}
              disabled={!!postId && !dirty}
              onClick={submit}
            >
              {primaryLabel}
            </AdminButton>
          )}
        </div>
      </div>

      {readOnly && (
        <div className="mb-6">
          <Callout tone="info" title="View only">
            Your role is Blog Viewer, so you can read posts but not change them. Ask an admin for editor access.
          </Callout>
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        {/* Main column */}
        <div className="min-w-0 space-y-6">
          <Panel title="Article">
            <div className="space-y-5">
              <div>
                <label htmlFor="post-title" className="mb-1 block text-xs font-medium text-slate-700">
                  Title <span className="text-rose-500">*</span>
                </label>
                <input
                  id="post-title"
                  value={form.title}
                  onChange={(e) => onTitle(e.target.value)}
                  disabled={readOnly}
                  maxLength={200}
                  placeholder="e.g. How AI voice agents cut missed calls for dental clinics"
                  className={cn(
                    inputClass,
                    'h-12 text-lg font-semibold',
                    errors.title && 'border-rose-300 focus:border-rose-400 focus:ring-rose-100'
                  )}
                />
                <FieldMessage error={errors.title} />
              </div>

              <div>
                <label htmlFor="post-slug" className="mb-1 block text-xs font-medium text-slate-700">
                  URL (slug)
                </label>
                <div className={cn('flex items-center overflow-hidden rounded-lg border bg-white focus-within:border-brand-400 focus-within:ring-2 focus-within:ring-brand-100', errors.slug || (slugState && !slugState.available) ? 'border-rose-300' : 'border-slate-200', readOnly && 'bg-slate-50')}>
                  <span className="hidden whitespace-nowrap border-r border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500 sm:block">voicecon.ai/blog/</span>
                  <input
                    id="post-slug"
                    value={form.slug}
                    disabled={readOnly}
                    onChange={(e) => {
                      setSlugTouched(true)
                      set('slug', e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-').replace(/-{2,}/g, '-'))
                    }}
                    onBlur={() => set('slug', slugify(form.slug))}
                    placeholder="generated-from-the-title"
                    className="h-9 min-w-0 flex-1 border-0 bg-transparent px-3 text-sm text-slate-800 focus:outline-none focus:ring-0 disabled:text-slate-500"
                  />
                  {!readOnly && slugState?.available && <Check className="mr-3 h-4 w-4 text-emerald-500" aria-label="Available" />}
                </div>
                {slugState && !slugState.available ? (
                  <p className="mt-1 text-xs text-rose-600">
                    Another post uses this URL.{' '}
                    {slugState.suggestion && (
                      <button type="button" className="font-medium underline" onClick={() => set('slug', slugState.suggestion!)}>
                        Use {slugState.suggestion}
                      </button>
                    )}
                  </p>
                ) : wasLive && post.data && form.slug !== post.data.slug ? (
                  <p className="mt-1 text-xs text-amber-700">Changing the URL of a live post breaks links already shared to the old one.</p>
                ) : (
                  <p className="mt-1 text-xs text-slate-500">Lowercase letters, numbers and dashes. Left empty, it is made from the title.</p>
                )}
              </div>

              <div>
                <div className="mb-1 flex items-baseline justify-between">
                  <label htmlFor="post-excerpt" className="text-xs font-medium text-slate-700">
                    Excerpt / summary
                  </label>
                  <Counter value={form.excerpt.length} max={EXCERPT_MAX} />
                </div>
                <textarea
                  id="post-excerpt"
                  value={form.excerpt}
                  disabled={readOnly}
                  onChange={(e) => set('excerpt', e.target.value)}
                  rows={3}
                  maxLength={400}
                  placeholder="One or two sentences shown on blog cards and under the title. Left empty, the opening of the article is used."
                  className={cn(inputClass, 'h-auto py-2 leading-relaxed')}
                />
              </div>

              <div>
                <span className="mb-1 block text-xs font-medium text-slate-700">
                  Content {form.status === 'published' && <span className="text-rose-500">*</span>}
                </span>
                <RichTextEditor
                  value={form.content_html}
                  onChange={(html) => set('content_html', html)}
                  readOnly={readOnly}
                  invalid={!!errors.content_html}
                />
                <FieldMessage error={errors.content_html} />
              </div>
            </div>
          </Panel>

          <Panel title="Search & social" description="How the post appears in Google results and when the link is shared.">
            <div className="grid gap-5 lg:grid-cols-2">
              <div className="space-y-4">
                <div>
                  <div className="mb-1 flex items-baseline justify-between">
                    <label htmlFor="seo-title" className="text-xs font-medium text-slate-700">SEO title</label>
                    <Counter value={form.seo_title.length} max={SEO_TITLE_MAX} />
                  </div>
                  <input
                    id="seo-title"
                    value={form.seo_title}
                    disabled={readOnly}
                    maxLength={200}
                    onChange={(e) => set('seo_title', e.target.value)}
                    placeholder={form.title ? `${form.title} | Voicecon Blog` : 'Defaults to the post title'}
                    className={inputClass}
                  />
                </div>
                <div>
                  <div className="mb-1 flex items-baseline justify-between">
                    <label htmlFor="seo-desc" className="text-xs font-medium text-slate-700">SEO meta description</label>
                    <Counter value={form.seo_description.length} max={SEO_DESC_MAX} />
                  </div>
                  <textarea
                    id="seo-desc"
                    value={form.seo_description}
                    disabled={readOnly}
                    maxLength={320}
                    rows={3}
                    onChange={(e) => set('seo_description', e.target.value)}
                    placeholder="Defaults to the excerpt"
                    className={cn(inputClass, 'h-auto py-2 leading-relaxed')}
                  />
                </div>
                <SearchSnippet
                  title={form.seo_title || (form.title ? `${form.title} | Voicecon Blog` : 'Post title | Voicecon Blog')}
                  slug={form.slug || 'post-url'}
                  description={form.seo_description || form.excerpt || 'The excerpt is shown here when no meta description is set.'}
                />
              </div>
              <ImageUploadField
                label="Social share image (optional)"
                value={form.social_image_url}
                onChange={(url) => set('social_image_url', url)}
                disabled={readOnly}
                hint="Used for LinkedIn, X and Facebook link previews. Leave empty to use the featured image. 1200 × 675 px, 16:9."
              />
            </div>
          </Panel>
        </div>

        {/* Side column */}
        <div className="space-y-6">
          <Panel title="Publishing">
            <div className="space-y-4">
              <div>
                <span className="mb-1 block text-xs font-medium text-slate-700">Status</span>
                <div className="grid grid-cols-2 rounded-lg bg-slate-100 p-1" role="radiogroup" aria-label="Publish status">
                  {(['draft', 'published'] as const).map((value) => (
                    <button
                      key={value}
                      type="button"
                      role="radio"
                      aria-checked={form.status === value}
                      disabled={readOnly}
                      onClick={() => set('status', value)}
                      className={cn(
                        'h-8 rounded-md text-sm font-medium transition-colors disabled:cursor-not-allowed',
                        form.status === value ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-800'
                      )}
                    >
                      {value === 'draft' ? 'Draft' : 'Published'}
                    </button>
                  ))}
                </div>
              </div>

              <Field
                label="Publish date"
                hint={
                  form.status === 'published' && isFuture
                    ? `Scheduled: goes live ${scheduledFor!.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}.`
                    : 'Leave empty to publish immediately. A future date schedules the post. Your local time.'
                }
              >
                <div className="flex gap-2">
                  <input
                    type="datetime-local"
                    value={form.published_at}
                    disabled={readOnly}
                    onChange={(e) => set('published_at', e.target.value)}
                    className={inputClass}
                  />
                  {form.published_at && !readOnly && (
                    <button
                      type="button"
                      aria-label="Clear publish date"
                      onClick={() => set('published_at', '')}
                      className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg border border-slate-200 text-slate-400 hover:bg-slate-50 hover:text-slate-700"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </Field>

              <div className="flex items-start justify-between gap-3 rounded-lg border border-slate-200 px-3 py-2.5">
                <div>
                  <p className="flex items-center gap-1.5 text-sm font-medium text-slate-800">
                    <Star className="h-3.5 w-3.5 text-amber-500" />
                    Show on home page
                  </p>
                  <p className="mt-0.5 text-xs text-slate-500">Featured posts lead the home page&apos;s blog section.</p>
                </div>
                <Toggle checked={form.is_featured} onChange={(v) => set('is_featured', v)} disabled={readOnly} label="Show on home page" />
              </div>

              <Field label="Author">
                <select
                  value={form.author_id}
                  disabled={readOnly}
                  onChange={(e) => set('author_id', e.target.value)}
                  className={cn(inputClass, 'pr-8')}
                >
                  {!form.author_id && <option value="">{post.data?.author.name ?? 'Choose an author'}</option>}
                  {(authors.data ?? []).map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                      {a.id === me.data?.id ? ' (you)' : ''}
                    </option>
                  ))}
                </select>
              </Field>

              {postId && !readOnly && (
                <button
                  type="button"
                  onClick={() => setDeleting(true)}
                  className="inline-flex items-center gap-1.5 text-xs font-medium text-rose-600 hover:underline"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Delete this post
                </button>
              )}
            </div>
          </Panel>

          <Panel title="Featured image">
            <div className="space-y-4">
              <ImageUploadField
                label="Image"
                value={form.featured_image_url}
                onChange={(url) => set('featured_image_url', url)}
                disabled={readOnly}
              />
              <Field label="Alt text" hint="Describes the image for screen readers and search engines.">
                <input
                  value={form.featured_image_alt}
                  disabled={readOnly}
                  maxLength={255}
                  onChange={(e) => set('featured_image_alt', e.target.value)}
                  placeholder={form.title || 'e.g. Receptionist answering calls with an AI assistant'}
                  className={inputClass}
                />
              </Field>
            </div>
          </Panel>

          <Panel title="Category & tags">
            <div className="space-y-4">
              <CategoryPicker value={form.category_id} onChange={(id) => set('category_id', id)} disabled={readOnly} />
              <TagInput value={form.tags} onChange={(tags) => set('tags', tags)} disabled={readOnly} />
            </div>
          </Panel>
        </div>
      </div>

      <PreviewDialog open={previewing} onClose={() => setPreviewing(false)} article={previewArticle} />
      <DeletePostDialog
        post={deleting && post.data ? { id: post.data.id, title: post.data.title, status: post.data.status } : null}
        onClose={() => setDeleting(false)}
        onDeleted={() => {
          setSaved(form) // nothing left to warn about
          router.replace('/admin/blog/posts')
        }}
      />
    </div>
  )
}

function FieldMessage({ error }: { error?: string }) {
  if (!error) return null
  return <p className="mt-1 text-xs text-rose-600">{error}</p>
}

function Counter({ value, max }: { value: number; max: number }) {
  return <span className={cn('text-[11px] tabular-nums', value > max ? 'text-amber-600' : 'text-slate-400')}>{value}/{max}</span>
}

function SearchSnippet({ title, slug, description }: { title: string; slug: string; description: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50/60 p-3">
      <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">Search result preview</p>
      <p className="mt-2 truncate text-xs text-slate-500">voicecon.ai › blog › {slug}</p>
      <p className="mt-0.5 line-clamp-1 text-[15px] text-[#1a0dab]">{title}</p>
      <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-slate-600">{description}</p>
    </div>
  )
}

function CategoryPicker({ value, onChange, disabled }: { value: string; onChange: (id: string) => void; disabled?: boolean }) {
  const qc = useQueryClient()
  const categories = useQuery({ queryKey: ['blog', 'categories'], queryFn: blogApi.categories })
  const [adding, setAdding] = useState(false)
  const [name, setName] = useState('')
  const create = useMutation({
    mutationFn: () => blogApi.createCategory({ name: name.trim() }),
    onSuccess: (category) => {
      qc.invalidateQueries({ queryKey: ['blog', 'categories'] })
      onChange(category.id)
      setName('')
      setAdding(false)
      toast.success(`Category "${category.name}" created.`)
    },
    onError: (e) => toast.error(errorText(e)),
  })

  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <span className="text-xs font-medium text-slate-700">Category</span>
        {!disabled && (
          <button type="button" onClick={() => setAdding((v) => !v)} className="text-xs font-medium text-brand-700 hover:underline">
            {adding ? 'Cancel' : 'New category'}
          </button>
        )}
      </div>
      {adding ? (
        <div className="flex gap-2">
          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && name.trim()) {
                e.preventDefault()
                create.mutate()
              }
            }}
            maxLength={80}
            placeholder="Category name"
            aria-label="New category name"
            className={inputClass}
          />
          <AdminButton variant="primary" icon={Plus} loading={create.isPending} disabled={!name.trim()} onClick={() => create.mutate()}>
            Add
          </AdminButton>
        </div>
      ) : (
        <select value={value} onChange={(e) => onChange(e.target.value)} disabled={disabled} aria-label="Category" className={cn(inputClass, 'pr-8')}>
          <option value="">Uncategorised</option>
          {(categories.data ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      )}
    </div>
  )
}

function TagInput({ value, onChange, disabled }: { value: string[]; onChange: (tags: string[]) => void; disabled?: boolean }) {
  const [draft, setDraft] = useState('')
  const add = (raw: string) => {
    const tags = raw
      .split(',')
      .map((t) => t.trim().replace(/^#/, '').slice(0, 40))
      .filter(Boolean)
    const next = [...value]
    for (const tag of tags) if (!next.some((t) => t.toLowerCase() === tag.toLowerCase())) next.push(tag)
    onChange(next.slice(0, 10))
    setDraft('')
  }
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <span className="text-xs font-medium text-slate-700">Tags</span>
        <span className="text-[11px] text-slate-400">{value.length}/10</span>
      </div>
      <div className={cn('flex min-h-9 flex-wrap items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2 py-1.5 focus-within:border-brand-400 focus-within:ring-2 focus-within:ring-brand-100', disabled && 'bg-slate-50')}>
        {value.map((tag) => (
          <span key={tag} className="inline-flex items-center gap-1 rounded-md bg-slate-100 py-0.5 pl-2 pr-1 text-xs font-medium text-slate-700">
            {tag}
            {!disabled && (
              <button type="button" aria-label={`Remove ${tag}`} onClick={() => onChange(value.filter((t) => t !== tag))} className="rounded p-0.5 text-slate-400 hover:bg-slate-200 hover:text-slate-700">
                <X className="h-3 w-3" />
              </button>
            )}
          </span>
        ))}
        {!disabled && value.length < 10 && (
          <input
            value={draft}
            onChange={(e) => (e.target.value.includes(',') ? add(e.target.value) : setDraft(e.target.value))}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && draft.trim()) {
                e.preventDefault()
                add(draft)
              } else if (e.key === 'Backspace' && !draft && value.length) {
                onChange(value.slice(0, -1))
              }
            }}
            onBlur={() => draft.trim() && add(draft)}
            placeholder={value.length ? '' : 'Type a tag and press Enter'}
            aria-label="Add tag"
            className="h-6 min-w-[8rem] flex-1 border-0 bg-transparent p-0 text-sm focus:outline-none focus:ring-0"
          />
        )}
        {disabled && value.length === 0 && <span className="text-sm text-slate-400">No tags</span>}
      </div>
      <p className="mt-1 text-xs text-slate-500">Up to 10. Readers can browse all posts with a tag.</p>
    </div>
  )
}
