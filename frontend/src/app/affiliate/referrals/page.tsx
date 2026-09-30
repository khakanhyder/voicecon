'use client'

import { useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Users } from 'lucide-react'
import { affiliateApi, formatDate, money, REFERRAL_STATUS_LABELS } from '@/lib/affiliate'
import { getErrorMessage } from '@/lib/api'
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

const STATUS_TONES: Record<string, BadgeTone> = {
  signed_up: 'slate',
  trial: 'blue',
  paying_monthly: 'amber',
  paying_annual: 'green',
  canceled: 'red',
  lapsed: 'slate',
}

const SOURCE_LABELS: Record<string, string> = { link: 'Referral link', coupon: 'Coupon' }

export default function AffiliateReferralsPage() {
  const [page, setPage] = useState(1)
  const q = useQuery({
    queryKey: ['affiliate', 'referrals', page],
    queryFn: () => affiliateApi.referrals(page),
    placeholderData: keepPreviousData,
  })

  return (
    <div>
      <PageHeader
        title="Referrals"
        description="Everyone who signed up through your link or coupon. Emails are partly hidden to protect customers’ privacy."
      />
      <div className={cardClass}>
        {q.isLoading ? (
          <TableSkeleton cols={6} />
        ) : q.isError ? (
          <LoadError message={getErrorMessage(q.error, 'We couldn’t load your referrals.')} onRetry={() => q.refetch()} />
        ) : !q.data || q.data.items.length === 0 ? (
          <EmptyState icon={<Users className="h-6 w-6" />} title="No referrals yet">
            Share your referral link or coupon — people who sign up through them will show up here.
          </EmptyState>
        ) : (
          <>
            <Table head={['Customer', 'Source', 'Status', 'Signed up', 'Converted', 'Earned']}>
              {q.data.items.map((r) => (
                <tr key={r.id} className="hover:bg-slate-50/60">
                  <td className={`${tdClass} font-medium text-slate-900`}>{r.customer}</td>
                  <td className={tdClass}>{SOURCE_LABELS[r.source] ?? r.source}</td>
                  <td className={tdClass}>
                    <Badge tone={STATUS_TONES[r.status] ?? 'slate'}>
                      {REFERRAL_STATUS_LABELS[r.status] ?? r.status}
                    </Badge>
                  </td>
                  <td className={tdClass}>{formatDate(r.signed_up_at)}</td>
                  <td className={tdClass}>{formatDate(r.converted_at)}</td>
                  <td className={`${tdClass} font-semibold text-slate-900`}>{money(r.earned)}</td>
                </tr>
              ))}
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
      <p className="mt-4 text-xs text-slate-500">
        Only annual plan payments earn a commission. Customers on monthly plans still count as your referrals.
      </p>
    </div>
  )
}
