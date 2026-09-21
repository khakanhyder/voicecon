'use client'

import { useState } from 'react'
import Link from 'next/link'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { CheckCircle2, ExternalLink, RefreshCcw } from 'lucide-react'
import { adminApi } from '@/lib/admin'
import {
  AdminButton,
  Badge,
  Dialog,
  Field,
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
  inputClass,
} from '@/components/admin/ui'
import { cn } from '@/lib/utils'

const EVENT_TYPES = [
  'trial_started', 'trial_extended', 'trial_expiring', 'trial_expired', 'trial_converted', 'activated', 'renewed',
  'payment_failed', 'past_due', 'grace_started', 'grace_ended', 'canceled', 'reactivated', 'plan_changed',
]

function PaymentFailures() {
  const qc = useQueryClient()
  const [resolved, setResolved] = useState(false)
  const [page, setPage] = useState(1)
  const [resolving, setResolving] = useState<string | null>(null)
  const [notes, setNotes] = useState('')

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin', 'payment-failures', { resolved, page }],
    queryFn: () => adminApi.paymentFailures({ resolved, page, page_size: 20 }),
    placeholderData: keepPreviousData,
  })

  const resolve = useMutation({
    mutationFn: () => adminApi.resolvePaymentFailure(resolving!, notes || undefined),
    onSuccess: () => {
      toast.success('Marked resolved')
      setResolving(null)
      setNotes('')
      qc.invalidateQueries({ queryKey: ['admin', 'payment-failures'] })
      qc.invalidateQueries({ queryKey: ['admin', 'overview'] })
    },
    onError: (e) => toast.error(errorText(e)),
  })

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between gap-3 border-b border-slate-100 p-4">
        <p className="text-sm text-slate-500">Failed card payments reported by Stripe. Stripe keeps retrying on its own schedule.</p>
        <FilterSelect
          label="Resolution"
          value={resolved ? 'resolved' : 'open'}
          onChange={(v) => { setResolved(v === 'resolved'); setPage(1) }}
          options={[{ value: 'open', label: 'Open' }, { value: 'resolved', label: 'Resolved' }]}
        />
      </div>
      <Table>
        <thead>
          <tr><Th>When</Th><Th>Organization</Th><Th>Amount</Th><Th>Reason</Th><Th>Customer notified</Th><Th /></tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          <TableState colSpan={6} loading={isLoading} error={error} empty={data?.items.length === 0}
            emptyText={resolved ? 'No resolved failures.' : 'No open payment failures.'} />
          {data?.items.map((f) => (
            <Tr key={f.id}>
              <Td className="text-slate-500">{formatDate(f.created_at, true)}</Td>
              <Td><Link href={`/admin/organizations/${f.organization_id}`} className="font-medium text-slate-900 hover:underline">{f.organization_name}</Link></Td>
              <Td className="tabular-nums">{formatMoney(f.amount_due, f.currency ?? 'usd')}</Td>
              <Td className="max-w-xs whitespace-normal text-xs text-slate-600">
                {f.failure_message}
                {f.failure_code && <span className="ml-1 font-mono text-slate-400">({f.failure_code})</span>}
                {f.resolution_notes && <p className="mt-1 text-emerald-700">Note: {f.resolution_notes}</p>}
              </Td>
              <Td>{f.customer_notified ? <Badge tone="success">Yes</Badge> : <Badge>No</Badge>}</Td>
              <Td className="text-right">
                <div className="flex justify-end gap-2">
                  {f.hosted_invoice_url && (
                    <a href={f.hosted_invoice_url} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:underline">
                      Invoice <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                  {!f.resolved && (
                    <AdminButton icon={CheckCircle2} onClick={() => setResolving(f.id)}>Resolve</AdminButton>
                  )}
                </div>
              </Td>
            </Tr>
          ))}
        </tbody>
      </Table>
      {data && data.total > 0 && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />}

      <Dialog
        open={!!resolving}
        onClose={() => setResolving(null)}
        title="Mark payment failure resolved"
        description="This only records that it was handled. It does not retry the charge or change the subscription."
        footer={
          <>
            <AdminButton variant="ghost" onClick={() => setResolving(null)}>Cancel</AdminButton>
            <AdminButton variant="primary" loading={resolve.isPending} onClick={() => resolve.mutate()}>Mark resolved</AdminButton>
          </>
        }
      >
        <Field label="Notes">
          <textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} className={`${inputClass} h-auto py-2`} placeholder="e.g. Customer updated their card; Stripe retry succeeded." />
        </Field>
      </Dialog>
    </div>
  )
}

function EventLedger() {
  const [eventType, setEventType] = useState('')
  const [page, setPage] = useState(1)
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin', 'billing-events', { eventType, page }],
    queryFn: () => adminApi.billingEvents({ event_type: eventType, page, page_size: 25 }),
    placeholderData: keepPreviousData,
  })
  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between gap-3 border-b border-slate-100 p-4">
        <p className="text-sm text-slate-500">Every subscription change across all organizations, newest first.</p>
        <FilterSelect
          label="Event type"
          value={eventType}
          onChange={(v) => { setEventType(v); setPage(1) }}
          options={[{ value: '', label: 'All events' }, ...EVENT_TYPES.map((t) => ({ value: t, label: humanize(t) }))]}
        />
      </div>
      <Table>
        <thead><tr><Th>When</Th><Th>Organization</Th><Th>Event</Th><Th>Status change</Th><Th>By</Th></tr></thead>
        <tbody className="divide-y divide-slate-100">
          <TableState colSpan={5} loading={isLoading} error={error} empty={data?.items.length === 0} emptyText="No billing events." />
          {data?.items.map((e) => (
            <Tr key={e.id}>
              <Td className="text-slate-500">{formatDate(e.created_at, true)}</Td>
              <Td><Link href={`/admin/organizations/${e.organization_id}`} className="font-medium text-slate-900 hover:underline">{e.organization_name}</Link></Td>
              <Td>{humanize(e.event_type)}</Td>
              <Td className="text-xs text-slate-500">{e.from_status || e.to_status ? `${e.from_status ?? '—'} → ${e.to_status ?? '—'}` : '—'}</Td>
              <Td><Badge tone={e.actor_type === 'admin' ? 'brand' : 'neutral'}>{humanize(e.actor_type)}</Badge></Td>
            </Tr>
          ))}
        </tbody>
      </Table>
      {data && data.total > 0 && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />}
    </div>
  )
}

export default function BillingPage() {
  const qc = useQueryClient()
  const [tab, setTab] = useState<'failures' | 'events'>('failures')
  const reconcile = useMutation({
    mutationFn: adminApi.reconcile,
    onSuccess: (r) => {
      toast.success(r.changed ? `Reconciler applied ${r.changed} change(s)` : 'Reconciler ran — nothing to change', { description: r.report })
      qc.invalidateQueries({ queryKey: ['admin'] })
    },
    onError: (e) => toast.error(errorText(e)),
  })

  return (
    <>
      <PageHeader
        title="Billing"
        description="Payment failures and the subscription ledger. Use an organization's page to extend trials, grant plans or set overrides."
        actions={
          <AdminButton icon={RefreshCcw} loading={reconcile.isPending} onClick={() => reconcile.mutate()}>
            Run reconciler now
          </AdminButton>
        }
      />
      <div className="mb-4 inline-flex rounded-lg border border-slate-200 bg-white p-1 shadow-sm">
        {([['failures', 'Payment failures'], ['events', 'Billing events']] as const).map(([key, label]) => (
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
      {tab === 'failures' ? <PaymentFailures /> : <EventLedger />}
    </>
  )
}
