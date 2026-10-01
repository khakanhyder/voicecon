'use client'

/** Requests to join the affiliate program, sent from the public form: review, then create the affiliate or reject. */
import { Suspense, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { ExternalLink, RotateCcw, UserPlus, XCircle } from 'lucide-react'
import { adminApi, type AffiliateApplication, type AffiliateApplicationStatus } from '@/lib/admin'
import {
  AdminButton,
  Badge,
  Callout,
  Detail,
  Dialog,
  Drawer,
  Field,
  FilterSelect,
  PageHeader,
  Pagination,
  SearchInput,
  Table,
  TableState,
  Td,
  Th,
  Tr,
  errorText,
  formatDate,
  humanize,
  inputClass,
  type Tone,
} from '@/components/admin/ui'
import { cn } from '@/lib/utils'
import { AffiliateFormDialog } from '@/components/admin/affiliates/AffiliateFormDialog'
import { InviteLinkDialog } from '@/components/admin/affiliates/shared'

const STATUS_TONES: Record<AffiliateApplicationStatus, Tone> = {
  pending: 'warning',
  approved: 'success',
  rejected: 'neutral',
}

function RequestStatusBadge({ status }: { status: AffiliateApplicationStatus }) {
  return (
    <Badge tone={STATUS_TONES[status] ?? 'neutral'} dot>
      {humanize(status)}
    </Badge>
  )
}

/** A typed-in website as a safe link: only http(s), with the scheme added when it is missing. */
function websiteHref(value: string): string | null {
  const raw = value.trim()
  const candidate = /^https?:\/\//i.test(raw) ? raw : /^[\w-]+(\.[\w-]+)+(\/\S*)?$/.test(raw) ? `https://${raw}` : null
  if (!candidate) return null
  try {
    const url = new URL(candidate)
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.toString() : null
  } catch {
    return null
  }
}

function invalidate(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ['admin', 'affiliate-applications'] })
  qc.invalidateQueries({ queryKey: ['admin', 'notifications'] })
}

function RequestDrawer({
  applicationId,
  onClose,
  onCreate,
}: {
  applicationId: string
  onClose: () => void
  onCreate: (application: AffiliateApplication) => void
}) {
  const qc = useQueryClient()
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')

  const { data: a, isLoading, error } = useQuery({
    queryKey: ['admin', 'affiliate-applications', 'one', applicationId],
    queryFn: () => adminApi.affiliateApplication(applicationId),
  })

  const reject = useMutation({
    mutationFn: () => adminApi.rejectAffiliateApplication(applicationId, reason.trim() || undefined),
    onSuccess: () => {
      toast.success('Request rejected.')
      setRejecting(false)
      setReason('')
      invalidate(qc)
    },
    onError: (e) => toast.error(errorText(e)),
  })
  const reopen = useMutation({
    mutationFn: () => adminApi.reopenAffiliateApplication(applicationId),
    onSuccess: () => {
      toast.success('Request reopened.')
      invalidate(qc)
    },
    onError: (e) => toast.error(errorText(e)),
  })

  const href = a?.website ? websiteHref(a.website) : null
  // The address already belongs to an affiliate, so creating another would be refused.
  const duplicate = !!a && a.status === 'pending' && !!a.existing_affiliate

  const footer = a && (
    <>
      {a.status === 'pending' && (
        <>
          <AdminButton variant="ghost" icon={XCircle} className="text-rose-600 hover:bg-rose-50" onClick={() => setRejecting(true)}>
            Reject
          </AdminButton>
          <AdminButton
            variant="primary"
            icon={UserPlus}
            disabled={duplicate}
            title={duplicate ? 'This person is already an affiliate.' : undefined}
            onClick={() => onCreate(a)}
          >
            Create affiliate
          </AdminButton>
        </>
      )}
      {a.status === 'rejected' && (
        <AdminButton icon={RotateCcw} loading={reopen.isPending} onClick={() => reopen.mutate()}>
          Reopen request
        </AdminButton>
      )}
      {a.status === 'approved' && a.affiliate_id && (
        <Link
          href={`/admin/affiliates?focus=${a.affiliate_id}`}
          className="inline-flex h-9 items-center gap-2 rounded-lg bg-brand-600 px-3.5 text-sm font-medium text-white shadow-sm hover:bg-brand-700"
        >
          Open affiliate
        </Link>
      )}
    </>
  )

  return (
    <Drawer open onClose={onClose} title={a?.name || 'Affiliate request'} subtitle={a ? [a.email, a.company].filter(Boolean).join(' · ') : undefined} footer={footer || undefined}>
      {error ? (
        <Callout tone="danger" title="Could not load this request">{errorText(error)}</Callout>
      ) : isLoading || !a ? (
        <div className="h-40 animate-pulse rounded-lg bg-slate-50" />
      ) : (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-2">
            <RequestStatusBadge status={a.status} />
            <span className="text-xs text-slate-400">Received {formatDate(a.created_at, true)}</span>
          </div>

          {a.existing_affiliate && a.existing_affiliate.id !== a.affiliate_id && (
            <Callout tone="warning" title="This person is already an affiliate">
              {a.email} is the login of{' '}
              <Link href={`/admin/affiliates?focus=${a.existing_affiliate.id}`} className="font-medium underline">
                {a.existing_affiliate.name}
              </Link>
              . Edit that affiliate instead, and reject this request.
            </Callout>
          )}

          <dl className="grid gap-4 sm:grid-cols-2">
            <Detail label="Name">{a.name}</Detail>
            <Detail label="Email">
              <a href={`mailto:${a.email}`} className="text-brand-700 hover:underline">{a.email}</a>
            </Detail>
            <Detail label="Company">{a.company || '—'}</Detail>
            <Detail label="Website or channel">
              {!a.website ? (
                '—'
              ) : href ? (
                <a href={href} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-1 text-brand-700 hover:underline">
                  {a.website}
                  <ExternalLink className="h-3.5 w-3.5 flex-shrink-0" />
                </a>
              ) : (
                a.website
              )}
            </Detail>
          </dl>

          <section>
            <h3 className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-slate-500">
              Audience and how they would promote
            </h3>
            <p className="whitespace-pre-wrap break-words rounded-lg border border-slate-200 bg-slate-50/60 px-4 py-3 text-sm leading-relaxed text-slate-800">
              {a.message || '—'}
            </p>
          </section>

          {a.status !== 'pending' && (
            <dl className="grid gap-4 border-t border-slate-100 pt-5 sm:grid-cols-2">
              <Detail label={a.status === 'approved' ? 'Approved by' : 'Rejected by'}>{a.reviewed_by || '—'}</Detail>
              <Detail label="On">{formatDate(a.reviewed_at, true)}</Detail>
              {a.status === 'rejected' && (
                <div className="sm:col-span-2">
                  <Detail label="Reason">{a.review_note || '—'}</Detail>
                </div>
              )}
            </dl>
          )}

          {a.status === 'pending' && !duplicate && (
            <p className="text-xs text-slate-500">
              “Create affiliate” opens the normal affiliate form with this person filled in. You set the commission,
              coupon and limits there, and creating the account approves this request.
            </p>
          )}
        </div>
      )}

      <Dialog
        open={rejecting}
        onClose={() => !reject.isPending && setRejecting(false)}
        title="Reject this request?"
        description={`${a?.name ?? 'The applicant'} is not told. You can reopen the request later.`}
        footer={
          <>
            <AdminButton variant="ghost" onClick={() => setRejecting(false)} disabled={reject.isPending}>Cancel</AdminButton>
            <AdminButton variant="danger" loading={reject.isPending} onClick={() => reject.mutate()}>Reject request</AdminButton>
          </>
        }
      >
        <Field label="Reason" hint="Optional. Only visible to admins.">
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            maxLength={2000}
            className={cn(inputClass, 'h-auto py-2')}
            placeholder="e.g. No relevant audience"
          />
        </Field>
      </Dialog>
    </Drawer>
  )
}

const PATH = '/admin/affiliates/requests'

// useSearchParams needs a Suspense boundary to build.
export default function AffiliateRequestsPage() {
  return (
    <Suspense fallback={null}>
      <AffiliateRequests />
    </Suspense>
  )
}

function AffiliateRequests() {
  const router = useRouter()
  // `?focus=<id>` comes from a bell notification or the email link. It is read
  // through the router, not once from `window.location`, so a notification
  // clicked while this page is already open still opens its request.
  const focus = useSearchParams().get('focus') ?? ''
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('pending')
  const [page, setPage] = useState(1)
  const [open, setOpen] = useState('')
  const [creating, setCreating] = useState<AffiliateApplication | null>(null)
  const [invite, setInvite] = useState<{ url: string; sent: boolean; name?: string } | null>(null)

  useEffect(() => {
    if (!focus) return
    setOpen(focus)
    // The request may be in any state, so don't hide it behind the filter.
    setStatus('')
    setPage(1)
  }, [focus])

  const close = () => {
    setOpen('')
    // Drop `?focus=` so the same notification can open the request again.
    if (focus) router.replace(PATH)
  }

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin', 'affiliate-applications', 'list', { search, status, page }],
    queryFn: () => adminApi.affiliateApplications({ search, status, page, page_size: 25 }),
    placeholderData: keepPreviousData,
  })

  return (
    <>
      <PageHeader
        title="Affiliate requests"
        description="People who applied through the Affiliate Program form on the website. Open a request to review it, then create their affiliate account or reject it."
      />

      <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row">
          <SearchInput
            value={search}
            onChange={(v) => { setSearch(v); setPage(1) }}
            placeholder="Search by name, email, company or website"
            className="flex-1"
          />
          <FilterSelect
            label="Status"
            value={status}
            onChange={(v) => { setStatus(v); setPage(1) }}
            options={[
              { value: '', label: 'All statuses' },
              { value: 'pending', label: 'Pending' },
              { value: 'approved', label: 'Approved' },
              { value: 'rejected', label: 'Rejected' },
            ]}
          />
        </div>
        <Table>
          <thead>
            <tr>
              <Th>Applicant</Th>
              <Th>Status</Th>
              <Th>Website or channel</Th>
              <Th>About</Th>
              <Th>Received</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            <TableState
              colSpan={5}
              loading={isLoading}
              error={error}
              empty={data?.items.length === 0}
              emptyText={
                search || status !== 'pending'
                  ? 'No requests match.'
                  : 'No requests are waiting. New ones from the website form appear here.'
              }
            />
            {data?.items.map((a) => (
              <Tr key={a.id} onClick={() => setOpen(a.id)}>
                <Td>
                  <p className="font-medium text-slate-900">{a.name}</p>
                  <p className="text-xs text-slate-400">{a.email}{a.company ? ` · ${a.company}` : ''}</p>
                </Td>
                <Td>
                  <RequestStatusBadge status={a.status} />
                  {a.status === 'pending' && a.existing_affiliate && (
                    <p className="mt-1 text-xs text-amber-700">Already an affiliate</p>
                  )}
                </Td>
                <Td className="max-w-[14rem] truncate text-slate-600">{a.website || <span className="text-slate-400">—</span>}</Td>
                <Td className="max-w-[22rem] truncate text-slate-600">{a.message || <span className="text-slate-400">—</span>}</Td>
                <Td className="whitespace-nowrap text-slate-600">{formatDate(a.created_at, true)}</Td>
              </Tr>
            ))}
          </tbody>
        </Table>
        {data && data.total > 0 && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />}
      </div>

      {open && <RequestDrawer applicationId={open} onClose={close} onCreate={setCreating} />}
      <AffiliateFormDialog
        open={!!creating}
        application={creating}
        onClose={() => setCreating(null)}
        onCreated={(created) => {
          if (created.invite_url) setInvite({ url: created.invite_url, sent: !!created.invite_sent, name: created.email ?? undefined })
        }}
      />
      <InviteLinkDialog invite={invite} onClose={() => setInvite(null)} />
    </>
  )
}
