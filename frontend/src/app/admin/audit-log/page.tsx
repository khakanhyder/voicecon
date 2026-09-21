'use client'

import { Fragment, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { adminApi } from '@/lib/admin'
import {
  Badge,
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
  timeAgo,
} from '@/components/admin/ui'

const ACTIONS = [
  { value: '', label: 'All actions' },
  { value: 'setting', label: 'Settings & keys' },
  { value: 'organization', label: 'Organizations' },
  { value: 'user', label: 'Users' },
  { value: 'plan', label: 'Plans' },
  { value: 'payment_failure', label: 'Payment failures' },
  { value: 'billing', label: 'Billing jobs' },
]

export default function AuditLogPage() {
  const [search, setSearch] = useState('')
  const [action, setAction] = useState('')
  const [page, setPage] = useState(1)
  const [expanded, setExpanded] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin', 'audit', { search, action, page }],
    queryFn: () => adminApi.auditLogs({ search, action, page, page_size: 30 }),
    placeholderData: keepPreviousData,
  })

  return (
    <>
      <PageHeader title="Audit Log" description="Every change made from this console: who, what, when and from where. Secret values are never recorded." />
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row">
          <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1) }} placeholder="Search summaries or admin email" className="flex-1" />
          <FilterSelect label="Action" value={action} onChange={(v) => { setAction(v); setPage(1) }} options={ACTIONS} />
        </div>
        <Table>
          <thead><tr><Th className="w-8" /><Th>When</Th><Th>Admin</Th><Th>Action</Th><Th>Summary</Th><Th>IP</Th></tr></thead>
          <tbody className="divide-y divide-slate-100">
            <TableState colSpan={6} loading={isLoading} error={error} empty={data?.items.length === 0} emptyText="No admin activity yet." />
            {data?.items.map((row) => {
              const open = expanded === row.id
              const hasDetails = Boolean(row.details && Object.keys(row.details as object).length > 0)
              return (
                <Fragment key={row.id}>
                  <Tr onClick={hasDetails ? () => setExpanded(open ? null : row.id) : undefined}>
                    <Td className="text-slate-400">
                      {hasDetails && (open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />)}
                    </Td>
                    <Td>
                      <p className="text-slate-700">{timeAgo(row.created_at)}</p>
                      <p className="text-xs text-slate-400">{formatDate(row.created_at, true)}</p>
                    </Td>
                    <Td className="text-slate-700">{row.actor_email ?? '—'}</Td>
                    <Td><Badge tone="brand">{row.action}</Badge></Td>
                    <Td className="max-w-lg whitespace-normal text-slate-700">{row.summary}</Td>
                    <Td className="font-mono text-xs text-slate-400">{row.ip_address ?? '—'}</Td>
                  </Tr>
                  {open && (
                    <tr>
                      <td colSpan={6} className="bg-slate-50 px-12 py-3">
                        <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-slate-600">{JSON.stringify(row.details, null, 2)}</pre>
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </Table>
        {data && data.total > 0 && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />}
      </div>
    </>
  )
}
