'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Plus, SlidersHorizontal } from 'lucide-react'
import { adminApi } from '@/lib/admin'
import {
  AdminButton,
  Callout,
  FilterSelect,
  PageHeader,
  Pagination,
  SearchInput,
  Table,
  TableState,
  Td,
  Th,
  Tr,
  formatMoney,
  initialParam,
} from '@/components/admin/ui'
import { AffiliateDrawer } from '@/components/admin/affiliates/AffiliateDrawer'
import { AffiliateFormDialog } from '@/components/admin/affiliates/AffiliateFormDialog'
import { AffiliateStatusBadge, InviteLinkDialog, StripeStateBadge } from '@/components/admin/affiliates/shared'

export default function AffiliatesPage() {
  const router = useRouter()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [open, setOpen] = useState<string>(() => initialParam('focus'))
  const [creating, setCreating] = useState(false)
  const [invite, setInvite] = useState<{ url: string; sent: boolean; name?: string } | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin', 'affiliates', { search, status, page }],
    queryFn: () => adminApi.affiliates({ search, status, page, page_size: 25 }),
    placeholderData: keepPreviousData,
  })
  const program = useQuery({ queryKey: ['admin', 'affiliate-program'], queryFn: adminApi.affiliateProgram })

  return (
    <>
      <PageHeader
        title="Affiliates"
        description="Partners who earn a commission on the plans their referrals buy (monthly, annual or both — set per affiliate). Open one to see their links, balance, referrals and to pay them."
        actions={
          <>
            <AdminButton icon={SlidersHorizontal} onClick={() => router.push('/admin/affiliates/program')}>Program rules</AdminButton>
            <AdminButton variant="primary" icon={Plus} onClick={() => setCreating(true)}>New affiliate</AdminButton>
          </>
        }
      />

      {program.data && !program.data.enabled && (
        <div className="mb-4">
          <Callout tone="warning" title="The affiliate program is turned off">
            Referral links and coupons are not tracked and no commissions are earned.{' '}
            <Link href="/admin/affiliates/program" className="font-medium underline">Turn it on in Program rules</Link>.
          </Callout>
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row">
          <SearchInput
            value={search}
            onChange={(v) => { setSearch(v); setPage(1) }}
            placeholder="Search by name, email, company, referral or coupon code"
            className="flex-1"
          />
          <FilterSelect
            label="Status"
            value={status}
            onChange={(v) => { setStatus(v); setPage(1) }}
            options={[
              { value: '', label: 'All statuses' },
              { value: 'invited', label: 'Invited' },
              { value: 'active', label: 'Active' },
              { value: 'suspended', label: 'Suspended' },
            ]}
          />
        </div>
        <Table>
          <thead>
            <tr>
              <Th>Affiliate</Th>
              <Th>Status</Th>
              <Th>Referral code</Th>
              <Th>Coupon</Th>
              <Th className="text-right">Commission</Th>
              <Th className="text-right">Referrals / conv.</Th>
              <Th className="text-right">Earned</Th>
              <Th className="text-right">Available</Th>
              <Th>Stripe</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            <TableState
              colSpan={9}
              loading={isLoading}
              error={error}
              empty={data?.items.length === 0}
              emptyText={search || status ? 'No affiliates match.' : 'No affiliates yet. Create one to get started.'}
            />
            {data?.items.map((a) => (
              <Tr key={a.id} onClick={() => setOpen(a.id)}>
                <Td>
                  <p className="font-medium text-slate-900">{a.name}</p>
                  <p className="text-xs text-slate-400">{a.email}{a.company ? ` · ${a.company}` : ''}</p>
                </Td>
                <Td><AffiliateStatusBadge status={a.status} /></Td>
                <Td className="font-mono text-xs text-slate-600">{a.referral_code}</Td>
                <Td>
                  {a.coupon ? (
                    <>
                      <p className="font-mono text-xs text-slate-700">{a.coupon.code}</p>
                      <p className="text-xs text-slate-400">{a.coupon.description}</p>
                    </>
                  ) : (
                    <span className="text-slate-400">—</span>
                  )}
                </Td>
                <Td className="text-right tabular-nums">
                  {a.commission_billing_periods === 'monthly' ? (
                    <>{a.commission_percent_monthly ?? a.commission_percent}% <span className="text-xs text-slate-400">monthly</span></>
                  ) : a.commission_billing_periods === 'both' ? (
                    <>
                      {a.commission_percent}% <span className="text-xs text-slate-400">annual</span>
                      <span className="block">{a.commission_percent_monthly ?? a.commission_percent}% <span className="text-xs text-slate-400">monthly</span></span>
                    </>
                  ) : (
                    <>{a.commission_percent}% <span className="text-xs text-slate-400">annual</span></>
                  )}
                </Td>
                <Td className="text-right tabular-nums">{a.stats.referrals} / {a.stats.conversions}</Td>
                <Td className="text-right tabular-nums">{formatMoney(a.balance.lifetime)}</Td>
                <Td className="text-right font-medium tabular-nums">{formatMoney(a.balance.available)}</Td>
                <Td><StripeStateBadge state={a.stripe.state} /></Td>
              </Tr>
            ))}
          </tbody>
        </Table>
        {data && data.total > 0 && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />}
      </div>

      {open && <AffiliateDrawer affiliateId={open} onClose={() => setOpen('')} />}
      <AffiliateFormDialog
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={(created) => {
          if (created.invite_url) setInvite({ url: created.invite_url, sent: !!created.invite_sent, name: created.email ?? undefined })
        }}
      />
      <InviteLinkDialog invite={invite} onClose={() => setInvite(null)} />
    </>
  )
}
