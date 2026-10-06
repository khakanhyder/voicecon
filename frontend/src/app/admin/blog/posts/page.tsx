'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { PenSquare, Star, X } from 'lucide-react'
import { blogApi } from '@/lib/blog-admin'
import type { BlogPostRow } from '@/lib/blog'
import {
  FilterSelect,
  PageHeader,
  Pagination,
  SearchInput,
  Table,
  TableState,
  Td,
  Th,
  Tr,
  formatDate,
  initialParam,
  inputClass,
} from '@/components/admin/ui'
import { DeletePostDialog, PostRowMenu, PostStatusBadge, PostThumb, useCanWriteBlog } from '@/components/admin/blog/shared'
import { cn } from '@/lib/utils'

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

interface Filters {
  q: string
  status: string
  author_id: string
  category_id: string
  date_field: string
  date_from: string
  date_to: string
  month: string
  year: string
  sort: string
}

const DEFAULTS: Filters = {
  q: '',
  status: '',
  author_id: '',
  category_id: '',
  date_field: 'created',
  date_from: '',
  date_to: '',
  month: '',
  year: '',
  sort: 'newest',
}

function readFilters(): Filters {
  const out = { ...DEFAULTS }
  for (const key of Object.keys(DEFAULTS) as (keyof Filters)[]) {
    const value = initialParam(key)
    if (value) out[key] = value
  }
  return out
}

export default function BlogPostsPage() {
  const router = useRouter()
  const canWrite = useCanWriteBlog()
  const [filters, setFilters] = useState<Filters>(readFilters)
  const [page, setPage] = useState(() => Number(initialParam('page')) || 1)
  const [deleting, setDeleting] = useState<BlogPostRow | null>(null)

  const set = (key: keyof Filters, value: string) => {
    setFilters((f) => ({ ...f, [key]: value }))
    setPage(1)
  }

  // Keep the URL in step, so a filtered view can be bookmarked or shared.
  useEffect(() => {
    const params = new URLSearchParams()
    for (const [k, v] of Object.entries(filters)) if (v && v !== DEFAULTS[k as keyof Filters]) params.set(k, v)
    if (page > 1) params.set('page', String(page))
    const qs = params.toString()
    window.history.replaceState(null, '', qs ? `?${qs}` : window.location.pathname)
  }, [filters, page])

  const { data, isLoading, error } = useQuery({
    queryKey: ['blog', 'posts', filters, page],
    queryFn: () => blogApi.posts({ ...filters, page, page_size: 20 }),
    placeholderData: keepPreviousData,
  })
  const authors = useQuery({ queryKey: ['blog', 'authors'], queryFn: blogApi.authors })
  const categories = useQuery({ queryKey: ['blog', 'categories'], queryFn: blogApi.categories })

  const years = useMemo(() => {
    const now = new Date().getFullYear()
    return Array.from({ length: 6 }, (_, i) => String(now + 1 - i))
  }, [])

  const active = (Object.keys(DEFAULTS) as (keyof Filters)[]).filter((k) => k !== 'sort' && k !== 'date_field' && filters[k]).length
  const dateLabel = { created: 'Created', updated: 'Updated', published: 'Published' }[filters.date_field] ?? 'Created'

  return (
    <div>
      <PageHeader
        title="All posts"
        description="Search, filter and manage every post. Click a row to open it."
        actions={
          canWrite && (
            <Link
              href="/admin/blog/new"
              className="inline-flex h-9 items-center gap-2 rounded-lg bg-brand-600 px-3.5 text-sm font-medium text-white shadow-sm hover:bg-brand-700"
            >
              <PenSquare className="h-4 w-4" />
              New post
            </Link>
          )
        }
      />

      {/* Status tabs */}
      <div className="mb-4 flex gap-1 overflow-x-auto border-b border-slate-200">
        {[
          ['', 'All'],
          ['published', 'Published'],
          ['scheduled', 'Scheduled'],
          ['draft', 'Drafts'],
        ].map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => set('status', value)}
            className={cn(
              '-mb-px whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-medium transition-colors',
              filters.status === value ? 'border-brand-600 text-brand-700' : 'border-transparent text-slate-500 hover:text-slate-800'
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="space-y-3 border-b border-slate-100 p-4">
          <div className="flex flex-col gap-3 lg:flex-row">
            <SearchInput value={filters.q} onChange={(v) => set('q', v)} placeholder="Search by title or URL…" className="lg:w-80" />
            <div className="flex flex-wrap gap-2">
              <FilterSelect
                label="Author"
                value={filters.author_id}
                onChange={(v) => set('author_id', v)}
                options={[{ value: '', label: 'All authors' }, ...(authors.data ?? []).map((a) => ({ value: a.id, label: a.name }))]}
              />
              <FilterSelect
                label="Category"
                value={filters.category_id}
                onChange={(v) => set('category_id', v)}
                options={[
                  { value: '', label: 'All categories' },
                  { value: 'none', label: 'Uncategorised' },
                  ...(categories.data ?? []).map((c) => ({ value: c.id, label: c.name })),
                ]}
              />
              <FilterSelect
                label="Sort"
                value={filters.sort}
                onChange={(v) => set('sort', v)}
                options={[
                  { value: 'newest', label: `Newest ${dateLabel.toLowerCase()} first` },
                  { value: 'oldest', label: `Oldest ${dateLabel.toLowerCase()} first` },
                  { value: 'updated', label: 'Recently updated' },
                  { value: 'title', label: 'Title A–Z' },
                ]}
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <FilterSelect
              label="Date filter applies to"
              value={filters.date_field}
              onChange={(v) => set('date_field', v)}
              options={[
                { value: 'created', label: 'Created date' },
                { value: 'updated', label: 'Updated date' },
                { value: 'published', label: 'Publish date' },
              ]}
            />
            <label className="flex items-center gap-1.5 text-xs text-slate-500">
              From
              <input type="date" value={filters.date_from} max={filters.date_to || undefined} onChange={(e) => set('date_from', e.target.value)} className={cn(inputClass, 'w-auto')} />
            </label>
            <label className="flex items-center gap-1.5 text-xs text-slate-500">
              To
              <input type="date" value={filters.date_to} min={filters.date_from || undefined} onChange={(e) => set('date_to', e.target.value)} className={cn(inputClass, 'w-auto')} />
            </label>
            <FilterSelect
              label="Month"
              value={filters.month}
              onChange={(v) => set('month', v)}
              options={[{ value: '', label: 'Any month' }, ...MONTHS.map((m, i) => ({ value: String(i + 1), label: m }))]}
            />
            <FilterSelect
              label="Year"
              value={filters.year}
              onChange={(v) => set('year', v)}
              options={[{ value: '', label: 'Any year' }, ...years.map((y) => ({ value: y, label: y }))]}
            />
            {active > 0 && (
              <button
                type="button"
                onClick={() => {
                  setFilters({ ...DEFAULTS, sort: filters.sort })
                  setPage(1)
                }}
                className="inline-flex h-9 items-center gap-1 rounded-lg px-2.5 text-sm font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-800"
              >
                <X className="h-4 w-4" />
                Clear {active} filter{active === 1 ? '' : 's'}
              </button>
            )}
          </div>
        </div>

        <Table>
          <thead>
            <tr>
              <Th>Post</Th>
              <Th>Status</Th>
              <Th>Category</Th>
              <Th>Author</Th>
              <Th>Created</Th>
              <Th>Updated</Th>
              <Th>Published</Th>
              <Th className="w-10" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            <TableState
              colSpan={8}
              loading={isLoading}
              error={error}
              empty={!data?.items.length}
              emptyText={active ? 'No posts match these filters.' : 'No posts yet.'}
            />
            {data?.items.map((post) => (
              <Tr key={post.id} onClick={() => router.push(`/admin/blog/posts/${post.id}`)}>
                <Td className="max-w-[26rem]">
                  <div className="flex items-center gap-3">
                    <PostThumb url={post.featured_image_url} />
                    <div className="min-w-0">
                      <p className="flex items-center gap-1.5 truncate font-medium text-slate-900">
                        {post.is_featured && <Star className="h-3.5 w-3.5 flex-shrink-0 fill-amber-400 text-amber-400" aria-label="On home page" />}
                        <span className="truncate">{post.title}</span>
                      </p>
                      <p className="truncate text-xs text-slate-500">/blog/{post.slug}</p>
                    </div>
                  </div>
                </Td>
                <Td>
                  <PostStatusBadge status={post.status} />
                </Td>
                <Td className="text-slate-600">{post.category?.name ?? <span className="text-slate-400">—</span>}</Td>
                <Td className="text-slate-600">{post.author.name}</Td>
                <Td className="text-xs text-slate-500">{formatDate(post.created_at)}</Td>
                <Td className="text-xs text-slate-500">{formatDate(post.updated_at)}</Td>
                <Td className="text-xs text-slate-500">
                  {post.status === 'draft' ? <span className="text-slate-400">—</span> : formatDate(post.published_at, post.status === 'scheduled')}
                </Td>
                <Td>
                  <PostRowMenu post={post} canWrite={canWrite} onDelete={() => setDeleting(post)} />
                </Td>
              </Tr>
            ))}
          </tbody>
        </Table>
        {data && data.total > 0 && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />}
      </section>

      <DeletePostDialog post={deleting} onClose={() => setDeleting(null)} />
    </div>
  )
}
