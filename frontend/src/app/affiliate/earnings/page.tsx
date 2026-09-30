'use client'

import { useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Receipt } from 'lucide-react'
import {
  affiliateApi,
  billingReasonLabel,
  COMMISSION_STATUS_LABELS,
  formatDate,
  KIND_LABELS,
  money,
  type Commission,
  type CommissionStatus,
} from '@/lib/affiliate'
import { getErrorMessage } from '@/lib/api'
import { cn } from '@/lib/utils'
import {
  Badge,
  EmptyState,
  LoadError,
  PageHeader,
  Pagination,
  Table,
  TableSkeleton,
  cardClass,
  tdClass,
  type BadgeTone,
} from '@/components/affiliate/ui'
import { useAffiliateMe } from '@/components/affiliate/useAffiliateMe'

const FILTERS: { value: CommissionStatus | undefined; label: string }[] = [
  { value: undefined, label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'approved', label: 'Approved' },
  { value: 'paid', label: 'Paid' },
  { value: 'reversed', label: 'Reversed' },
  { value: 'rejected', label: 'Rejected' },
]

const STATUS_TONES: Record<string, BadgeTone> = {
  pending: 'amber',
  approved: 'blue',
  paid: 'green',
  reversed: 'slate',
  rejected: 'red',
}

function statusHelp(c: Commission): string | null {
  switch (c.status) {
    case 'pending':
      return c.available_at ? `Payable on ${formatDate(c.available_at)}` : 'In the refund window'
    case 'approved':
      return 'Included in your next payout'
    case 'paid':
      return c.paid_at ? `Paid on ${formatDate(c.paid_at)}` : 'Paid to you'
    case 'reversed':
      return 'The payment was refunded'
    case 'rejected':
      return 'Not payable'
    default:
      return null
  }
}

function typeLabel(c: Commission): { kind: string; reason: string | null } {
  return {
    kind: KIND_LABELS[c.kind] ?? c.kind,
    reason: c.kind === 'commission' ? billingReasonLabel(c.billing_reason, c.billing_period) : null,
  }
}

export default function AffiliateEarningsPage() {
  const [status, setStatus] = useState<CommissionStatus | undefined>(undefined)
  const [page, setPage] = useState(1)
  const { data: me } = useAffiliateMe()
  const q = useQuery({
    queryKey: ['affiliate', 'commissions', status ?? 'all', page],
    queryFn: () => affiliateApi.commissions(page, status),
    placeholderData: keepPreviousData,
  })

  const choose = (value: CommissionStatus | undefined) => {
    setStatus(value)
    setPage(1)
  }

  return (
    <div>
      <PageHeader
        title="Earnings"
        description={
          me
            ? `Every commission you’ve earned. New commissions stay pending for ${me.rules.hold_days} day${
                me.rules.hold_days === 1 ? '' : 's'
              } (the refund window), then become payable.`
            : 'Every commission you’ve earned.'
        }
      />

      <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="Filter by status">
        {FILTERS.map((f) => {
          const active = status === f.value
          return (
            <button
              key={f.label}
              type="button"
              aria-pressed={active}
              onClick={() => choose(f.value)}
              className={cn(
                'rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors',
                active
                  ? 'border-[#243275] bg-[#243275] text-white'
                  : 'border-slate-300 bg-white text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              )}
            >
              {f.label}
            </button>
          )
        })}
      </div>

      <div className={cardClass}>
        {q.isLoading ? (
          <TableSkeleton cols={7} />
        ) : q.isError ? (
          <LoadError message={getErrorMessage(q.error, 'We couldn’t load your earnings.')} onRetry={() => q.refetch()} />
        ) : !q.data || q.data.items.length === 0 ? (
          <EmptyState icon={<Receipt className="h-6 w-6" />} title={status ? 'Nothing here' : 'No earnings yet'}>
            {status
              ? `You have no ${COMMISSION_STATUS_LABELS[status].toLowerCase()} commissions.`
              : 'When a customer you referred makes a payment that earns commission, it appears here.'}
          </EmptyState>
        ) : (
          <>
            <Table head={['Date', 'Customer', 'Type', 'Amount paid', 'Rate', 'Commission', 'Status', 'Note']}>
              {q.data.items.map((c) => {
                const t = typeLabel(c)
                const help = statusHelp(c)
                const negative = c.amount < 0
                return (
                  <tr key={c.id} className="hover:bg-slate-50/60">
                    <td className={tdClass}>{formatDate(c.earned_at)}</td>
                    <td className={`${tdClass} font-medium text-slate-900`}>{c.customer ?? '—'}</td>
                    <td className={tdClass}>
                      <p>{t.kind}</p>
                      {t.reason && <p className="text-xs text-slate-500">{t.reason}</p>}
                    </td>
                    <td className={tdClass}>{c.base_amount ? money(c.base_amount) : '—'}</td>
                    <td className={tdClass}>{c.rate_percent ? `${c.rate_percent}%` : '—'}</td>
                    <td className={cn(tdClass, 'font-semibold', negative ? 'text-rose-600' : 'text-slate-900')}>
                      {money(c.amount)}
                    </td>
                    <td className={tdClass}>
                      <Badge tone={STATUS_TONES[c.status] ?? 'slate'}>
                        {COMMISSION_STATUS_LABELS[c.status] ?? c.status}
                      </Badge>
                      {help && <p className="mt-1 text-xs text-slate-500">{help}</p>}
                    </td>
                    <td className={cn(tdClass, 'min-w-[12rem] whitespace-pre-line text-xs text-slate-500')}>
                      {c.note || '—'}
                    </td>
                  </tr>
                )
              })}
            </Table>
            <Pagination
              page={q.data.page}
              pages={q.data.pages}
              total={q.data.total}
              onChange={setPage}
              disabled={q.isFetching}
            />
          </>
        )}
      </div>
    </div>
  )
}
