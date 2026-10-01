'use client'

import { useState } from 'react'
import Link from 'next/link'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { CalendarPlus, Loader2, Trash2 } from 'lucide-react'
import { adminApi, type NumberRow } from '@/lib/admin'
import {
  AdminButton,
  Badge,
  Callout,
  Dialog,
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
  errorText,
  formatDate,
  formatMoney,
  humanize,
} from '@/components/admin/ui'

/** How much longer "Keep" holds a number before it is released. */
const KEEP_DAYS = 14

/** Confirmation step for releasing a number — nothing happens until "Release number" is pressed. */
function ReleaseDialog({ number, onClose }: { number: NumberRow | null; onClose: () => void }) {
  const qc = useQueryClient()
  const release = useMutation({
    mutationFn: (id: string) => adminApi.releasePhoneNumber(id),
    onSuccess: (res) => {
      toast.success(`${res.phone_number} was released.`)
      qc.invalidateQueries({ queryKey: ['admin', 'phone-numbers'] })
      qc.invalidateQueries({ queryKey: ['admin', 'overview'] })
      onClose()
    },
    onError: (e) => toast.error(errorText(e)),
  })

  return (
    <Dialog
      open={!!number}
      onClose={() => !release.isPending && onClose()}
      title="Release this number?"
      description={
        <>
          <span className="font-mono font-medium text-slate-700">{number?.phone_number}</span> will be
          given back to the carrier and removed from {number?.organization_name}.
        </>
      }
      footer={
        <>
          <AdminButton variant="ghost" onClick={onClose} disabled={release.isPending}>Cancel</AdminButton>
          <AdminButton variant="danger" icon={Trash2} loading={release.isPending} onClick={() => number && release.mutate(number.id)}>
            Release number
          </AdminButton>
        </>
      }
    >
      <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
        <li>Calls to it stop immediately and the monthly charge ends.</li>
        <li>The customer cannot get this number back, even if they subscribe again.</li>
        {number?.status === 'active' && (
          <li className="font-medium text-rose-700">This number is in use by a paying workspace.</li>
        )}
      </ul>
      <p className="mt-3 text-sm text-slate-500">This cannot be undone.</p>
    </Dialog>
  )
}

export default function PhoneNumbersPage() {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [provider, setProvider] = useState('')
  const [page, setPage] = useState(1)
  const [releasing, setReleasing] = useState<NumberRow | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin', 'phone-numbers', { search, status, provider, page }],
    queryFn: () => adminApi.phoneNumbers({ search, status, provider, page, page_size: 25 }),
    placeholderData: keepPreviousData,
  })

  const keep = useMutation({
    mutationFn: (n: NumberRow) => adminApi.holdPhoneNumber(n.id, KEEP_DAYS),
    onSuccess: (res) => {
      toast.success(`${res.phone_number} will be kept until ${formatDate(res.release_after)}.`)
      qc.invalidateQueries({ queryKey: ['admin', 'phone-numbers'] })
    },
    onError: (e) => toast.error(errorText(e)),
  })

  const summary = data?.summary
  const capReached = !!summary && summary.purchases_24h >= summary.daily_purchase_cap

  return (
    <>
      <PageHeader
        title="Phone Numbers"
        description="Every number on the platform and who owns it. A Voicecon number costs money every month until it is released."
      />

      {summary && (
        <div className="mb-4 space-y-3">
          {summary.on_hold > 0 && (
            <Callout tone="warning">
              {summary.on_hold} number{summary.on_hold === 1 ? ' is' : 's are'} on hold for
              workspaces without an active plan.{' '}
              {summary.release_grace_days > 0
                ? `Each is released automatically ${summary.release_grace_days} days after it was put on hold, unless the workspace subscribes again.`
                : 'Automatic release is switched off, so they stay on the account until released here.'}{' '}
              <button
                type="button"
                className="font-medium underline"
                onClick={() => { setStatus('suspended'); setPage(1) }}
              >
                Show them
              </button>
            </Callout>
          )}
          <Callout tone={capReached ? 'danger' : 'info'}>
            {summary.purchases_24h} of {summary.daily_purchase_cap} Voicecon number purchases used in the
            last 24 hours.{' '}
            {capReached
              ? 'The daily limit is reached, so customers cannot buy a Voicecon number right now.'
              : 'Customers are refused once the limit is reached.'}{' '}
            <Link href="/admin/api-keys" className="font-medium underline">Change the limit</Link>
          </Callout>
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row">
          <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1) }} placeholder="Search by number or organization" className="flex-1" />
          <FilterSelect label="Status" value={status} onChange={(v) => { setStatus(v); setPage(1) }} options={[
            { value: '', label: 'Any status' },
            { value: 'active', label: 'Active' },
            { value: 'suspended', label: 'On hold' },
            { value: 'inactive', label: 'Inactive' },
          ]} />
          <FilterSelect label="Provider" value={provider} onChange={(v) => { setProvider(v); setPage(1) }} options={[
            { value: '', label: 'Any provider' },
            { value: 'twilio', label: 'Twilio' },
            { value: 'telnyx', label: 'Telnyx' },
          ]} />
        </div>
        <Table>
          <thead>
            <tr>
              <Th>Number</Th><Th>Organization</Th><Th>Agent</Th><Th>Provider</Th><Th>Status</Th>
              <Th className="text-right">Monthly cost</Th><Th>Added</Th><Th className="w-px px-2"><span className="sr-only">Actions</span></Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            <TableState colSpan={8} loading={isLoading} error={error} empty={data?.items.length === 0} emptyText="No numbers match." />
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
                <Td>
                  {n.status === 'suspended' ? (
                    <>
                      <Badge tone="warning" dot>On hold</Badge>
                      <p className="mt-1 text-xs text-slate-500">
                        {n.release_after ? `Releases ${formatDate(n.release_after)}` : 'No release date'}
                      </p>
                      {n.release_error && (
                        <p className="mt-0.5 text-xs text-rose-600">Last release attempt failed</p>
                      )}
                    </>
                  ) : (
                    <StatusBadge status={n.status} />
                  )}
                </Td>
                <Td className="text-right tabular-nums">{formatMoney(n.monthly_cost)}</Td>
                <Td className="text-slate-500">{formatDate(n.created_at)}</Td>
                <Td className="w-px px-2 text-right">
                  {n.voicecon ? (
                    <div className="flex justify-end">
                      {n.status === 'suspended' && (
                        <button
                          type="button"
                          onClick={() => keep.mutate(n)}
                          disabled={keep.isPending}
                          aria-label="Keep"
                          title={`Keep for ${KEEP_DAYS} more days from today`}
                          className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900 disabled:opacity-50"
                        >
                          {keep.isPending && keep.variables?.id === n.id
                            ? <Loader2 className="h-4 w-4 animate-spin" />
                            : <CalendarPlus className="h-4 w-4" />}
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => setReleasing(n)}
                        aria-label="Release"
                        title="Release this number at the carrier"
                        className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-rose-50 hover:text-rose-600"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  ) : null}
                </Td>
              </Tr>
            ))}
          </tbody>
        </Table>
        {data && data.total > 0 && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />}
      </div>

      <ReleaseDialog number={releasing} onClose={() => setReleasing(null)} />
    </>
  )
}
