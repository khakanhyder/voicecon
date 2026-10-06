'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { CalendarClock, CheckCircle2, FileEdit, Files, PenSquare, RefreshCw, Star } from 'lucide-react'
import { blogApi } from '@/lib/blog-admin'
import type { BlogPostRow } from '@/lib/blog'
import {
  AdminButton,
  Callout,
  PageHeader,
  Panel,
  StatCard,
  errorText,
  formatDate,
  formatNumber,
} from '@/components/admin/ui'
import { RelativeTime } from '@/components/ui/relative-time'
import { PostStatusBadge, PostThumb, useCanWriteBlog } from '@/components/admin/blog/shared'

const BRAND = '#0f7a63'
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ChartTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-md">
      <p className="font-medium text-slate-900">
        {MONTHS[p.month - 1]} {p.year}
      </p>
      <p className="mt-0.5 text-slate-600">
        <span className="font-semibold tabular-nums text-slate-900">{p.posts}</span> published
      </p>
    </div>
  )
}

function PostLine({ post, meta }: { post: BlogPostRow; meta: React.ReactNode }) {
  const router = useRouter()
  return (
    <li>
      <button
        type="button"
        onClick={() => router.push(`/admin/blog/posts/${post.id}`)}
        className="flex w-full items-center gap-3 rounded-lg px-2 py-2.5 text-left transition-colors hover:bg-slate-50"
      >
        <PostThumb url={post.featured_image_url} className="w-16" />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-slate-900">{post.title}</span>
          <span className="mt-0.5 block truncate text-xs text-slate-500">
            {post.author.name}
            {post.category && <> · {post.category.name}</>}
          </span>
        </span>
        <span className="hidden flex-shrink-0 text-right sm:block">
          <PostStatusBadge status={post.status} />
          <span className="mt-1 block text-[11px] text-slate-500">{meta}</span>
        </span>
      </button>
    </li>
  )
}

export default function BlogDashboardPage() {
  const canWrite = useCanWriteBlog()
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['blog', 'overview'],
    queryFn: blogApi.overview,
  })
  const c = data?.counts

  return (
    <div>
      <PageHeader
        title="Blog"
        description="Everything published on voicecon.ai/blog and the home page's blog section."
        actions={
          <>
            <AdminButton icon={RefreshCw} onClick={() => refetch()} loading={isFetching && !isLoading}>
              Refresh
            </AdminButton>
            {canWrite && (
              <Link
                href="/admin/blog/new"
                className="inline-flex h-9 items-center gap-2 rounded-lg bg-brand-600 px-3.5 text-sm font-medium text-white shadow-sm hover:bg-brand-700"
              >
                <PenSquare className="h-4 w-4" />
                New post
              </Link>
            )}
          </>
        }
      />

      {error ? (
        <Callout tone="danger" title="Could not load the blog dashboard">
          {errorText(error)}
        </Callout>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Link href="/admin/blog/posts" className="block">
              <StatCard label="Total posts" value={isLoading ? '—' : formatNumber(c?.total)} icon={Files} hint="All statuses" />
            </Link>
            <Link href="/admin/blog/posts?status=published" className="block">
              <StatCard
                label="Published"
                value={isLoading ? '—' : formatNumber(c?.published)}
                icon={CheckCircle2}
                tone="success"
                hint={c ? `${c.published_this_month} this month · ${c.featured} on home page` : undefined}
              />
            </Link>
            <Link href="/admin/blog/posts?status=draft" className="block">
              <StatCard label="Drafts" value={isLoading ? '—' : formatNumber(c?.draft)} icon={FileEdit} hint="Not on the website" />
            </Link>
            <Link href="/admin/blog/posts?status=scheduled" className="block">
              <StatCard
                label="Scheduled"
                value={isLoading ? '—' : formatNumber(c?.scheduled)}
                icon={CalendarClock}
                tone={c?.scheduled ? 'warning' : 'default'}
                hint="Go live on their publish date"
              />
            </Link>
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-3">
            <Panel title="Published per month" description="Last 12 months" className="xl:col-span-2">
              <div className="h-56">
                {data && (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data.monthly} margin={{ top: 8, right: 4, left: -16, bottom: 0 }} barCategoryGap="28%">
                      <CartesianGrid vertical={false} stroke="#eef2f6" />
                      <XAxis
                        dataKey={(m: { month: number }) => MONTHS[m.month - 1]}
                        tick={{ fontSize: 11, fill: '#64748b' }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                      <Tooltip cursor={{ fill: 'rgba(15,122,99,0.06)' }} content={<ChartTooltip />} />
                      <Bar dataKey="posts" fill={BRAND} radius={[4, 4, 0, 0]} maxBarSize={28} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </Panel>

            <Panel title="By category" description="All posts, any status">
              {data && data.by_category.length > 0 ? (
                <ul className="space-y-3">
                  {data.by_category.map((row) => (
                    <li key={row.name}>
                      <div className="flex items-center justify-between text-sm">
                        <span className="truncate text-slate-700">{row.name}</span>
                        <span className="tabular-nums text-slate-500">{row.posts}</span>
                      </div>
                      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className="h-full rounded-full bg-brand-500"
                          style={{ width: `${Math.max(4, (row.posts / Math.max(1, data.counts.total)) * 100)}%` }}
                        />
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="py-8 text-center text-sm text-slate-500">{isLoading ? 'Loading…' : 'No posts yet.'}</p>
              )}
            </Panel>
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-3">
            <Panel
              title="Recently updated"
              className="xl:col-span-2"
              bodyClassName="p-3"
              actions={
                <Link href="/admin/blog/posts?sort=updated" className="text-xs font-medium text-brand-700 hover:underline">
                  View all
                </Link>
              }
            >
              {data && data.recent.length > 0 ? (
                <ul className="divide-y divide-slate-100">
                  {data.recent.map((post) => (
                    <PostLine key={post.id} post={post} meta={<>Updated <RelativeTime value={post.updated_at} /></>} />
                  ))}
                </ul>
              ) : (
                <div className="py-10 text-center">
                  <p className="text-sm text-slate-500">{isLoading ? 'Loading…' : 'No posts yet.'}</p>
                  {!isLoading && canWrite && (
                    <Link href="/admin/blog/new" className="mt-3 inline-flex text-sm font-medium text-brand-700 hover:underline">
                      Write the first post
                    </Link>
                  )}
                </div>
              )}
            </Panel>

            <div className="space-y-6">
              <Panel title="Scheduled" description="Next to go live" bodyClassName="p-3">
                {data && data.upcoming.length > 0 ? (
                  <ul className="divide-y divide-slate-100">
                    {data.upcoming.map((post) => (
                      <PostLine key={post.id} post={post} meta={formatDate(post.published_at, true)} />
                    ))}
                  </ul>
                ) : (
                  <p className="px-2 py-6 text-center text-sm text-slate-500">Nothing scheduled.</p>
                )}
              </Panel>
              <Panel title="Top authors">
                {data && data.by_author.length > 0 ? (
                  <ul className="space-y-2.5">
                    {data.by_author.map((row) => (
                      <li key={row.name} className="flex items-center justify-between text-sm">
                        <span className="flex min-w-0 items-center gap-2">
                          <span className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-brand-50 text-[11px] font-semibold text-brand-700">
                            {row.name.slice(0, 1).toUpperCase()}
                          </span>
                          <span className="truncate text-slate-700">{row.name}</span>
                        </span>
                        <span className="tabular-nums text-slate-500">
                          {row.posts} post{row.posts === 1 ? '' : 's'}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="py-4 text-center text-sm text-slate-500">—</p>
                )}
                {c && c.featured > 0 && (
                  <p className="mt-4 flex items-center gap-1.5 border-t border-slate-100 pt-3 text-xs text-slate-500">
                    <Star className="h-3.5 w-3.5 text-amber-500" />
                    {c.featured} live post{c.featured === 1 ? '' : 's'} featured on the home page
                  </p>
                )}
              </Panel>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
