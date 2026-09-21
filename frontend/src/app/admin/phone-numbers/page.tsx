'use client'

import { useState } from 'react'
import Link from 'next/link'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { adminApi } from '@/lib/admin'
import {
  Badge,
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
  formatMoney,
  humanize,
} from '@/components/admin/ui'

export default function PhoneNumbersPage() {
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [provider, setProvider] = useState('')
  const [page, setPage] = useState(1)

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin', 'phone-numbers', { search, status, provider, page }],
    queryFn: () => adminApi.phoneNumbers({ search, status, provider, page, page_size: 25 }),
    placeholderData: keepPreviousData,
  })

  return (
    <>
      <PageHeader
        title="Phone Numbers"
        description="Every number on the platform and who owns it. Numbers on a suspended organization still cost money until released."
      />
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row">
          <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1) }} placeholder="Search by number or organization" className="flex-1" />
          <FilterSelect label="Status" value={status} onChange={(v) => { setStatus(v); setPage(1) }} options={[
            { value: '', label: 'Any status' },
            { value: 'active', label: 'Active' },
            { value: 'inactive', label: 'Inactive' },
            { value: 'released', label: 'Released' },
          ]} />
          <FilterSelect label="Provider" value={provider} onChange={(v) => { setProvider(v); setPage(1) }} options={[
            { value: '', label: 'Any provider' },
            { value: 'twilio', label: 'Twilio' },
            { value: 'telnyx', label: 'Telnyx' },
          ]} />
        </div>
        <Table>
          <thead>
            <tr><Th>Number</Th><Th>Organization</Th><Th>Agent</Th><Th>Provider</Th><Th>Status</Th><Th className="text-right">Monthly cost</Th><Th>Added</Th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            <TableState colSpan={7} loading={isLoading} error={error} empty={data?.items.length === 0} emptyText="No numbers match." />
            {data?.items.map((n) => (
              <Tr key={n.id}>
                <Td className="font-mono font-medium text-slate-900">{n.phone_number}</Td>
                <Td>
                  <Link href={`/admin/organizations/${n.organization_id}`} className="text-slate-800 hover:underline">{n.organization_name}</Link>
                  {!n.organization_active && <Badge tone="danger">Org suspended</Badge>}
                </Td>
                <Td>{n.agent_name ?? <span className="text-slate-400">Unassigned</span>}</Td>
                <Td>
                  {humanize(n.provider)}
                  {n.bring_your_own && <span className="ml-1 text-xs text-slate-400">(customer account)</span>}
                </Td>
                <Td><StatusBadge status={n.status} /></Td>
                <Td className="text-right tabular-nums">{formatMoney(n.monthly_cost)}</Td>
                <Td className="text-slate-500">{formatDate(n.created_at)}</Td>
              </Tr>
            ))}
          </tbody>
        </Table>
        {data && data.total > 0 && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />}
      </div>
    </>
  )
}
