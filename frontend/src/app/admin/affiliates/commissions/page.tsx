'use client'

import { useMemo, useState } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { RotateCw } from 'lucide-react'
import { adminApi, type AffiliatePayout } from '@/lib/admin'
import {
  AdminButton,
  FilterSelect,
  PageHeader,
  Pagination,
  Table,
  TableState,
  Td,
  Th,
  Tr,
  errorText,
  formatDate,
  formatMoney,
  humanize,
  initialParam,
  parseDate,
  timeAgo,
} from '@/components/admin/ui'
import { cn } from '@/lib/utils'
import { AffiliateDrawer } from '@/components/admin/affiliates/AffiliateDrawer'
import {
  CommissionActions,
  CommissionStatusBadge,
  PayoutStatusBadge,
  billingReasonLabel,
  invalidateAffiliateData,
  moneyClass,
  payableIn,
} from '@/components/admin/affiliates/shared'

type Tab = 'commissions' | 'payouts'

const STALE_PROCESSING_MS = 5 * 60 * 1000

function AffiliateLink({ id, name, onOpen }: { id?: string | null; name?: string | null; onOpen: (id: string) => void }) {
  if (!id) return <span className="text-slate-400">—</span>
  return (
    <button type="button" onClick={() => onOpen(id)} className="text-left font-medium text-slate-900 hover:underline">
      {name || 'Affiliate'}
    </button>
  )
}

function CommissionsTab({ onOpenAffiliate }: { onOpenAffiliate: (id: string) => void }) {
  const [status, setStatus] = useState(() => initialParam('status'))
  const [page, setPage] = useState(1)
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin', 'affiliate-commissions', { status, page }],
    queryFn: () => adminApi.affiliateCommissions({ status, page, page_size: 25 }),
    placeholderData: keepPreviousData,
  })
  const program = useQuery({ queryKey: ['admin', 'affiliate-program'], queryFn: adminApi.affiliateProgram })
  const planNames = useMemo(
    () => Object.fromEntries((program.data?.plans ?? []).map((p) => [p.slug, p.name])) as Record<string, string>,
    [program.data]
  )

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row sm:items-center">
        <FilterSelect
          label="Status"
          value={status}
          onChange={(v) => { setStatus(v); setPage(1) }}
          options={[
            { value: '', label: 'All statuses' },
            { value: 'pending', label: 'Pending (in hold)' },
            { value: 'approved', label: 'Approved (payable)' },
            { value: 'paid', label: 'Paid' },
            { value: 'reversed', label: 'Reversed' },
            { value: 'rejected', label: 'Rejected' },
          ]}
        />
        <p className="text-xs text-slate-500">
          Pending commissions become payable automatically when their hold ends. Approve early to skip the hold.
        </p>
      </div>
      <Table>
        <thead>
          <tr>
            <Th>Affiliate</Th>
            <Th>Customer</Th>
            <Th>Kind</Th>
            <Th>For</Th>
            <Th className="text-right">Base</Th>
            <Th className="text-right">Rate</Th>
            <Th className="text-right">Amount</Th>
            <Th>Status</Th>
            <Th>Earned</Th>
            <Th>Available</Th>
            <Th><span className="sr-only">Actions</span></Th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          <TableState colSpan={11} loading={isLoading} error={error} empty={data?.items.length === 0} emptyText="No commissions match." />
          {data?.items.map((c) => {
            const plan = c.plan_slug ? planNames[c.plan_slug] || c.plan_slug : null
            return (
              <Tr key={c.id}>
                <Td><AffiliateLink id={c.affiliate_id} name={c.affiliate_name} onOpen={onOpenAffiliate} /></Td>
                <Td>
                  <p className="text-slate-800">{c.customer || '—'}</p>
                  {c.organization_name && <p className="text-xs text-slate-400">{c.organization_name}</p>}
                </Td>
                <Td className="text-slate-500">{humanize(c.kind)}</Td>
                <Td>
                  {c.kind === 'adjustment' ? (
                    <p className="max-w-[16rem] truncate text-xs text-slate-500" title={c.note ?? undefined}>{c.note || 'Manual adjustment'}</p>
                  ) : (
                    <>
                      <p className="text-slate-700">{[plan, c.billing_period && humanize(c.billing_period)].filter(Boolean).join(' · ') || '—'}</p>
                      {c.billing_reason && <p className="text-xs text-slate-400">{billingReasonLabel(c.billing_reason)}</p>}
                      {c.status === 'rejected' && c.note && (
                        <p className="max-w-[16rem] truncate text-xs text-rose-500" title={c.note}>{c.note}</p>
                      )}
                    </>
                  )}
                </Td>
                <Td className="text-right tabular-nums text-slate-500">{c.kind === 'adjustment' ? '—' : formatMoney(c.base_amount, c.currency)}</Td>
                <Td className="text-right tabular-nums text-slate-500">{c.kind === 'adjustment' ? '—' : `${c.rate_percent}%`}</Td>
                <Td className={cn('text-right font-medium tabular-nums', moneyClass(c.amount))}>
                  {formatMoney(c.amount, c.currency)}
                  {c.refunded_fraction > 0 && c.amount !== c.original_amount && (
                    <p className="text-xs font-normal text-slate-400">was {formatMoney(c.original_amount, c.currency)}</p>
                  )}
                </Td>
                <Td><CommissionStatusBadge status={c.status} /></Td>
                <Td className="text-slate-500">{formatDate(c.earned_at)}</Td>
                <Td className="text-slate-500">
                  {c.status === 'pending' ? payableIn(c.available_at) : formatDate(c.available_at)}
                </Td>
                <Td className="text-right"><CommissionActions commission={c} /></Td>
              </Tr>
            )
          })}
        </tbody>
      </Table>
      {data && data.total > 0 && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />}
    </div>
  )
}

function ResumeButton({ payout }: { payout: AffiliatePayout }) {
  const qc = useQueryClient()
  const resume = useMutation({
    mutationFn: () => adminApi.resumeAffiliatePayout(payout.id),
    onSuccess: (res) => {
      invalidateAffiliateData(qc)
      qc.invalidateQueries({ queryKey: ['admin', 'affiliate-payouts'] })
      if (res.status === 'failed') toast.error(`Payout failed: ${res.failure_reason || 'the transfer was not completed.'}`)
      else if (res.status === 'paid') toast.success(`Payout of ${formatMoney(res.amount, res.currency)} completed.`)
      else toast.message('The payout is still processing.')
    },
    onError: (e) => toast.error(errorText(e)),
  })
  return (
    <AdminButton className="h-8 px-2.5 text-xs" icon={RotateCw} loading={resume.isPending} onClick={() => resume.mutate()}>
      Resume
    </AdminButton>
  )
}

function PayoutsTab({ onOpenAffiliate }: { onOpenAffiliate: (id: string) => void }) {
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin', 'affiliate-payouts', { status, page }],
    queryFn: () => adminApi.affiliatePayouts({ status, page, page_size: 25 }),
    placeholderData: keepPreviousData,
  })

  const isStale = (p: AffiliatePayout) => {
    const created = parseDate(p.created_at)
    return p.status === 'processing' && p.method === 'stripe' && !!created && Date.now() - created.getTime() > STALE_PROCESSING_MS
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row sm:items-center">
        <FilterSelect
          label="Status"
          value={status}
          onChange={(v) => { setStatus(v); setPage(1) }}
          options={[
            { value: '', label: 'All statuses' },
            { value: 'processing', label: 'Processing' },
            { value: 'paid', label: 'Paid' },
            { value: 'failed', label: 'Failed' },
          ]}
        />
        <p className="text-xs text-slate-500">
          Payouts are started from an affiliate’s page. A Stripe payout stuck in “processing” for more than a few minutes can be resumed safely.
        </p>
      </div>
      <Table>
        <thead>
          <tr>
            <Th>Affiliate</Th>
            <Th className="text-right">Amount</Th>
            <Th>Method</Th>
            <Th>Status</Th>
            <Th>Reference / transfer</Th>
            <Th>Created</Th>
            <Th>Paid</Th>
            <Th>Failure</Th>
            <Th><span className="sr-only">Actions</span></Th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          <TableState colSpan={9} loading={isLoading} error={error} empty={data?.items.length === 0} emptyText="No payouts match." />
          {data?.items.map((p) => (
            <Tr key={p.id}>
              <Td><AffiliateLink id={p.affiliate_id} name={p.affiliate_name} onOpen={onOpenAffiliate} /></Td>
              <Td className="text-right font-medium tabular-nums">
                {formatMoney(p.amount, p.currency)}
                <p className="text-xs font-normal text-slate-400">{p.commission_count} commission{p.commission_count === 1 ? '' : 's'}</p>
              </Td>
              <Td className="text-slate-500">{p.method === 'stripe' ? 'Stripe transfer' : 'Manual'}</Td>
              <Td><PayoutStatusBadge status={p.status} /></Td>
              <Td>
                {p.reference && <p className="text-slate-700">{p.reference}</p>}
                {p.stripe_transfer_id && <p className="font-mono text-xs text-slate-500">{p.stripe_transfer_id}</p>}
                {!p.reference && !p.stripe_transfer_id && <span className="text-slate-400">—</span>}
                {p.note && <p className="max-w-[14rem] truncate text-xs text-slate-400" title={p.note}>{p.note}</p>}
              </Td>
              <Td className="text-slate-500" >
                <span title={formatDate(p.created_at, true)}>{formatDate(p.created_at)}</span>
                {p.status === 'processing' && <p className="text-xs text-slate-400">{timeAgo(p.created_at)}</p>}
              </Td>
              <Td className="text-slate-500">{formatDate(p.paid_at)}</Td>
              <Td className="max-w-[18rem] whitespace-normal">
                {p.failure_reason ? <p className="text-xs text-rose-600">{p.failure_reason}</p> : <span className="text-slate-400">—</span>}
              </Td>
              <Td className="text-right">{isStale(p) && <ResumeButton payout={p} />}</Td>
            </Tr>
          ))}
        </tbody>
      </Table>
      {data && data.total > 0 && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />}
    </div>
  )
}

export default function AffiliateCommissionsPage() {
  const [tab, setTab] = useState<Tab>(() => (initialParam('tab') === 'payouts' ? 'payouts' : 'commissions'))
  const [open, setOpen] = useState('')

  return (
    <>
      <PageHeader
        title="Commissions & Payouts"
        description="Every commission affiliates have earned, and every payout sent to them. Commission is earned on annual plan payments only."
      />

      <div role="tablist" aria-label="View" className="mb-4 inline-flex rounded-lg border border-slate-200 bg-white p-1 shadow-sm">
        {(['commissions', 'payouts'] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={cn(
              'rounded-md px-4 py-1.5 text-sm font-medium transition-colors',
              tab === t ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-50'
            )}
          >
            {t === 'commissions' ? 'Commissions' : 'Payouts'}
          </button>
        ))}
      </div>

      {tab === 'commissions' ? <CommissionsTab onOpenAffiliate={setOpen} /> : <PayoutsTab onOpenAffiliate={setOpen} />}

      {open && <AffiliateDrawer affiliateId={open} onClose={() => setOpen('')} />}
    </>
  )
}
