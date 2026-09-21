'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { adminApi } from '@/lib/admin'
import {
  FilterSelect,
  PageHeader,
  Pagination,
  SearchInput,
  StatusBadge,
  Table,
  TableState,
  Td,
  Th,
  Tr,
  formatDate,
  formatNumber,
  initialParam,
} from '@/components/admin/ui'

const STATUS_OPTIONS = [
  { value: '', label: 'All plans' },
  { value: 'active', label: 'Active' },
  { value: 'trialing', label: 'Trialing' },
  { value: 'past_due', label: 'Past due' },
  { value: 'grace', label: 'Grace' },
  { value: 'expired', label: 'Expired' },
  { value: 'canceled', label: 'Canceled' },
  { value: 'none', label: 'No subscription' },
]

export default function OrganizationsPage() {
  const router = useRouter()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState(() => initialParam('status'))
  const [suspended, setSuspended] = useState('')
  const [page, setPage] = useState(1)

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin', 'organizations', { search, status, suspended, page }],
    queryFn: () =>
      adminApi.organizations({
        search,
        status,
        suspended: suspended === '' ? undefined : suspended === 'yes',
        page,
        page_size: 25,
      }),
    placeholderData: keepPreviousData,
  })

  return (
    <>
      <PageHeader title="Organizations" description="Every workspace on the platform, with its plan, usage and owner." />

      <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row">
          <SearchInput
            value={search}
            onChange={(v) => { setSearch(v); setPage(1) }}
            placeholder="Search by name, slug or owner email"
            className="flex-1"
          />
          <FilterSelect label="Subscription status" value={status} onChange={(v) => { setStatus(v); setPage(1) }} options={STATUS_OPTIONS} />
          <FilterSelect
            label="Account state"
            value={suspended}
            onChange={(v) => { setSuspended(v); setPage(1) }}
            options={[
              { value: '', label: 'Active & suspended' },
              { value: 'no', label: 'Active only' },
              { value: 'yes', label: 'Suspended only' },
            ]}
          />
        </div>

        <Table>
          <thead>
            <tr>
              <Th>Organization</Th>
              <Th>Owner</Th>
              <Th>Plan</Th>
              <Th>Status</Th>
              <Th className="text-right">Members</Th>
              <Th className="text-right">Agents</Th>
              <Th className="text-right">Numbers</Th>
              <Th className="text-right">Calls 30d</Th>
              <Th>Created</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            <TableState colSpan={9} loading={isLoading} error={error} empty={data?.items.length === 0} emptyText="No organizations match." />
            {data?.items.map((org) => (
              <Tr key={org.id} onClick={() => router.push(`/admin/organizations/${org.id}`)}>
                <Td>
                  <p className="font-medium text-slate-900">{org.name}</p>
                  <p className="text-xs text-slate-400">{org.slug}</p>
                </Td>
                <Td>
                  <p className="text-slate-700">{org.owner.full_name || '—'}</p>
                  <p className="text-xs text-slate-400">{org.owner.email}</p>
                </Td>
                <Td>{org.subscription?.plan?.name ?? '—'}{org.subscription?.source === 'manual' && <span className="ml-1 text-xs text-slate-400">(comp)</span>}</Td>
                <Td>
                  <div className="flex flex-wrap gap-1">
                    <StatusBadge status={org.subscription?.status} />
                    {!org.is_active && <StatusBadge status="failed" label="Suspended" />}
                  </div>
                </Td>
                <Td className="text-right tabular-nums">{formatNumber(org.members)}</Td>
                <Td className="text-right tabular-nums">{formatNumber(org.agents)}</Td>
                <Td className="text-right tabular-nums">{formatNumber(org.phone_numbers)}</Td>
                <Td className="text-right tabular-nums">{formatNumber(org.calls_30d)}</Td>
                <Td className="text-slate-500">{formatDate(org.created_at)}</Td>
              </Tr>
            ))}
          </tbody>
        </Table>
        {data && data.total > 0 && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />}
      </div>
    </>
  )
}
