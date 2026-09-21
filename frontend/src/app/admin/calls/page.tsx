'use client'

import { useState } from 'react'
import Link from 'next/link'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { FileText, Mic } from 'lucide-react'
import { adminApi } from '@/lib/admin'
import {
  Detail,
  Drawer,
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
  formatDuration,
  formatMoney,
  humanize,
  initialParam,
  timeAgo,
} from '@/components/admin/ui'

type Turn = { role?: string; speaker?: string; text?: string; content?: string }

function transcriptTurns(json: unknown): Turn[] | null {
  const list = Array.isArray(json) ? json : Array.isArray((json as any)?.messages) ? (json as any).messages : null
  if (!list) return null
  return list.filter((t: Turn) => t && (t.text || t.content))
}

function CallDrawer({ callId, onClose }: { callId: string; onClose: () => void }) {
  const { data: call, isLoading } = useQuery({ queryKey: ['admin', 'call', callId], queryFn: () => adminApi.call(callId) })
  const turns = call ? transcriptTurns(call.transcript_json) : null
  return (
    <Drawer open onClose={onClose} title={call ? `${humanize(call.direction)} call` : 'Call'} subtitle={call ? `${call.from_number} → ${call.to_number}` : undefined}>
      {isLoading || !call ? (
        <div className="h-40 animate-pulse rounded-lg bg-slate-50" />
      ) : (
        <div className="space-y-6">
          <dl className="grid grid-cols-2 gap-4">
            <Detail label="Organization">
              <Link href={`/admin/organizations/${call.organization_id}`} className="text-brand-700 hover:underline">{call.organization_name}</Link>
            </Detail>
            <Detail label="Agent">{call.agent_name ?? '—'}</Detail>
            <Detail label="Status"><StatusBadge status={call.status} /></Detail>
            <Detail label="Duration">{formatDuration(call.duration_seconds)}</Detail>
            <Detail label="Started">{formatDate(call.started_at ?? call.created_at, true)}</Detail>
            <Detail label="Ended">{formatDate(call.ended_at, true)}</Detail>
            <Detail label="Provider">{call.provider ?? '—'}</Detail>
            <Detail label="Provider call ID"><span className="font-mono text-xs">{call.provider_call_sid ?? '—'}</span></Detail>
            <Detail label="Sentiment">{humanize(call.sentiment_label)}</Detail>
            <Detail label="Cost">{call.costs.total == null ? 'Not recorded' : formatMoney(call.costs.total)}</Detail>
          </dl>

          {call.recording_url && (
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Recording</p>
              <audio controls src={call.recording_url} className="w-full" />
            </div>
          )}

          {call.summary && (
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Summary</p>
              <p className="text-sm text-slate-700">{call.summary}</p>
            </div>
          )}

          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Transcript</p>
            {turns && turns.length > 0 ? (
              <ol className="space-y-2">
                {turns.map((t, i) => {
                  const who = (t.role || t.speaker || '').toLowerCase()
                  const agent = who.includes('assistant') || who.includes('agent') || who.includes('bot')
                  return (
                    <li key={i} className={agent ? 'pr-8' : 'pl-8'}>
                      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">{agent ? 'Agent' : who || 'Caller'}</p>
                      <p className={`mt-0.5 rounded-lg px-3 py-2 text-sm ${agent ? 'bg-brand-50 text-slate-800' : 'bg-slate-100 text-slate-800'}`}>
                        {t.text || t.content}
                      </p>
                    </li>
                  )
                })}
              </ol>
            ) : call.transcript ? (
              <pre className="whitespace-pre-wrap rounded-lg bg-slate-50 p-3 font-sans text-sm text-slate-700">{call.transcript}</pre>
            ) : (
              <p className="text-sm text-slate-500">No transcript.</p>
            )}
          </div>
        </div>
      )}
    </Drawer>
  )
}

export default function CallsPage() {
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState(() => initialParam('status'))
  const [direction, setDirection] = useState('')
  const [days, setDays] = useState('30')
  const [orgId] = useState(() => initialParam('organization_id'))
  const [page, setPage] = useState(1)
  const [open, setOpen] = useState('')

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin', 'calls', { search, status, direction, days, orgId, page }],
    queryFn: () => adminApi.calls({ search, status, direction, days, organization_id: orgId, page, page_size: 25 }),
    placeholderData: keepPreviousData,
  })

  return (
    <>
      <PageHeader title="Calls" description="Calls across every organization, for support and troubleshooting." />
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-100 p-4 lg:flex-row">
          <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1) }} placeholder="Search by number, organization or agent" className="flex-1" />
          <FilterSelect label="Status" value={status} onChange={(v) => { setStatus(v); setPage(1) }} options={[
            { value: '', label: 'Any status' },
            { value: 'completed', label: 'Completed' },
            { value: 'in-progress', label: 'In progress' },
            { value: 'failed', label: 'Failed / unanswered' },
          ]} />
          <FilterSelect label="Direction" value={direction} onChange={(v) => { setDirection(v); setPage(1) }} options={[
            { value: '', label: 'Both directions' },
            { value: 'inbound', label: 'Inbound' },
            { value: 'outbound', label: 'Outbound' },
          ]} />
          <FilterSelect label="Period" value={days} onChange={(v) => { setDays(v); setPage(1) }} options={[
            { value: '1', label: 'Last 24 hours' },
            { value: '7', label: 'Last 7 days' },
            { value: '30', label: 'Last 30 days' },
            { value: '90', label: 'Last 90 days' },
          ]} />
        </div>
        <Table>
          <thead>
            <tr><Th>When</Th><Th>Organization</Th><Th>Agent</Th><Th>From → To</Th><Th>Status</Th><Th className="text-right">Duration</Th><Th /></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            <TableState colSpan={7} loading={isLoading} error={error} empty={data?.items.length === 0} emptyText="No calls in this period." />
            {data?.items.map((c) => (
              <Tr key={c.id} onClick={() => setOpen(c.id)}>
                <Td>
                  <p className="text-slate-700">{timeAgo(c.created_at)}</p>
                  <p className="text-xs text-slate-400">{formatDate(c.created_at, true)}</p>
                </Td>
                <Td className="font-medium text-slate-900">{c.organization_name}</Td>
                <Td>{c.agent_name ?? '—'}</Td>
                <Td className="font-mono text-xs text-slate-600">
                  {c.from_number} → {c.to_number}
                  <span className="ml-1 font-sans text-slate-400">({c.direction})</span>
                </Td>
                <Td><StatusBadge status={c.status} /></Td>
                <Td className="text-right tabular-nums">{formatDuration(c.duration_seconds)}</Td>
                <Td>
                  <span className="flex gap-1.5 text-slate-400">
                    {c.has_recording && <Mic className="h-3.5 w-3.5" aria-label="Recording" />}
                    {c.has_transcript && <FileText className="h-3.5 w-3.5" aria-label="Transcript" />}
                  </span>
                </Td>
              </Tr>
            ))}
          </tbody>
        </Table>
        {data && data.total > 0 && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />}
      </div>
      {open && <CallDrawer callId={open} onClose={() => setOpen('')} />}
    </>
  )
}
