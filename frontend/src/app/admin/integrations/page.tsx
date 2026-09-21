'use client'

import { useState } from 'react'
import Link from 'next/link'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { adminApi } from '@/lib/admin'
import {
  FilterSelect,
  PageHeader,
  Pagination,
  StatusBadge,
  Table,
  TableState,
  Td,
  Th,
  Tr,
  formatDate,
  humanize,
  initialParam,
  timeAgo,
} from '@/components/admin/ui'
import { cn } from '@/lib/utils'

function Connections() {
  const [status, setStatus] = useState('problem')
  const [page, setPage] = useState(1)
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin', 'connections', { status, page }],
    queryFn: () => adminApi.connections({ status, page, page_size: 25 }),
    placeholderData: keepPreviousData,
  })
  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between gap-3 border-b border-slate-100 p-4">
        <p className="text-sm text-slate-500">
          Customer connections to third-party apps. Expired Google tokens usually mean the OAuth app is still in testing mode (tokens die after 7 days).
        </p>
        <FilterSelect label="Status" value={status} onChange={(v) => { setStatus(v); setPage(1) }} options={[
          { value: 'problem', label: 'Expired or failing' },
          { value: '', label: 'All connections' },
          { value: 'connected', label: 'Connected' },
        ]} />
      </div>
      <Table>
        <thead><tr><Th>Integration</Th><Th>Organization</Th><Th>Status</Th><Th>Last error</Th><Th>Token expires</Th><Th>Updated</Th></tr></thead>
        <tbody className="divide-y divide-slate-100">
          <TableState colSpan={6} loading={isLoading} error={error} empty={data?.items.length === 0}
            emptyText={status === 'problem' ? 'No broken connections.' : 'No connections.'} />
          {data?.items.map((c) => (
            <Tr key={c.id}>
              <Td>
                <p className="font-medium text-slate-900">{c.connector_name}</p>
                {c.name && <p className="text-xs text-slate-400">{c.name}</p>}
              </Td>
              <Td><Link href={`/admin/organizations/${c.organization_id}`} className="hover:underline">{c.organization_name}</Link></Td>
              <Td><StatusBadge status={c.status} /></Td>
              <Td className="max-w-sm whitespace-normal text-xs text-rose-700">
                {c.last_error ?? <span className="text-slate-400">—</span>}
                {c.error_count > 0 && <span className="ml-1 text-slate-400">({c.error_count}×)</span>}
              </Td>
              <Td className="text-slate-500">{formatDate(c.token_expires_at, true)}</Td>
              <Td className="text-slate-500">{timeAgo(c.updated_at)}</Td>
            </Tr>
          ))}
        </tbody>
      </Table>
      {data && data.total > 0 && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />}
    </div>
  )
}

function WorkflowRuns() {
  const [status, setStatus] = useState('failed')
  const [hours, setHours] = useState('72')
  const [page, setPage] = useState(1)
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin', 'workflow-runs', { status, hours, page }],
    queryFn: () => adminApi.workflowRuns({ status, hours, page, page_size: 25 }),
    placeholderData: keepPreviousData,
  })
  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-slate-500">Workflow executions across every organization.</p>
        <div className="flex gap-2">
          <FilterSelect label="Status" value={status} onChange={(v) => { setStatus(v); setPage(1) }} options={[
            { value: 'failed', label: 'Failed' },
            { value: '', label: 'All runs' },
            { value: 'completed', label: 'Completed' },
            { value: 'running', label: 'Running' },
          ]} />
          <FilterSelect label="Period" value={hours} onChange={(v) => { setHours(v); setPage(1) }} options={[
            { value: '24', label: 'Last 24 hours' },
            { value: '72', label: 'Last 3 days' },
            { value: '168', label: 'Last 7 days' },
            { value: '720', label: 'Last 30 days' },
          ]} />
        </div>
      </div>
      <Table>
        <thead><tr><Th>Started</Th><Th>Workflow</Th><Th>Organization</Th><Th>Trigger</Th><Th>Status</Th><Th>Error</Th></tr></thead>
        <tbody className="divide-y divide-slate-100">
          <TableState colSpan={6} loading={isLoading} error={error} empty={data?.items.length === 0} emptyText="No runs match." />
          {data?.items.map((r) => (
            <Tr key={r.id}>
              <Td className="text-slate-500">{formatDate(r.started_at, true)}</Td>
              <Td className="font-medium text-slate-900">{r.workflow_name}</Td>
              <Td><Link href={`/admin/organizations/${r.organization_id}`} className="hover:underline">{r.organization_name}</Link></Td>
              <Td>{humanize(r.trigger_type)}</Td>
              <Td>
                <StatusBadge status={r.status} />
                {r.steps_failed > 0 && <span className="ml-1 text-xs text-slate-400">{r.steps_failed}/{r.steps_executed} steps failed</span>}
              </Td>
              <Td className="max-w-md whitespace-normal text-xs text-rose-700">{r.error_message ?? <span className="text-slate-400">—</span>}</Td>
            </Tr>
          ))}
        </tbody>
      </Table>
      {data && data.total > 0 && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />}
    </div>
  )
}

export default function IntegrationsPage() {
  const [tab, setTab] = useState<'connections' | 'runs'>(() => (initialParam('tab') === 'runs' ? 'runs' : 'connections'))
  return (
    <>
      <PageHeader title="Integrations & Workflows" description="Broken customer connections and failing workflow runs, across all tenants." />
      <div className="mb-4 inline-flex rounded-lg border border-slate-200 bg-white p-1 shadow-sm">
        {([['connections', 'Connections'], ['runs', 'Workflow runs']] as const).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={cn('rounded-md px-3 py-1.5 text-sm font-medium transition-colors', tab === key ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-50')}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === 'connections' ? <Connections /> : <WorkflowRuns />}
    </>
  )
}
