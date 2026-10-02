'use client'

/**
 * An organization's Pay As You Go balance in the admin console: what it holds,
 * every movement that got it there, and a way to add or remove credit by hand.
 *
 * An adjustment always takes a reason. It is written to the wallet's ledger as
 * a row of its own and to the admin audit log, so the customer's history and
 * ours agree on why the balance changed.
 */
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { PlusCircle } from 'lucide-react'

import { adminApi } from '@/lib/admin'
import { perMinute } from '@/lib/pricing'
import {
  AdminButton,
  Badge,
  Callout,
  Detail,
  Dialog,
  Field,
  Pagination,
  Panel,
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

const PAGE_SIZE = 10

export function OrgWalletPanel({ organizationId, onChanged }: { organizationId: string; onChanged?: () => void }) {
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [adjusting, setAdjusting] = useState(false)
  const [direction, setDirection] = useState<'add' | 'remove'>('add')
  const [amount, setAmount] = useState('')
  const [reason, setReason] = useState('')

  const queryKey = ['admin', 'organization', organizationId, 'wallet', page]
  const { data: wallet, isLoading, error } = useQuery({
    queryKey,
    queryFn: () => adminApi.organizationWallet(organizationId, { page, page_size: PAGE_SIZE }),
    placeholderData: (previous) => previous,
  })

  const value = Number(amount)
  const valid = value > 0 && reason.trim().length >= 3

  const adjust = useMutation({
    mutationFn: () => adminApi.adjustWallet(organizationId, direction === 'add' ? value : -value, reason.trim()),
    onSuccess: (res) => {
      toast.success(`Balance is now ${formatMoney(res.balance, wallet?.currency)}`)
      setAdjusting(false)
      setAmount('')
      setReason('')
      setPage(1)
      qc.invalidateQueries({ queryKey: ['admin', 'organization', organizationId] })
      onChanged?.()
    },
    onError: (e) => toast.error(errorText(e)),
  })

  // A subscriber who has never held credit: nothing to show but the button.
  const empty = !!wallet && !wallet.exists && !wallet.prepaid

  return (
    <>
      <Panel
        className="mt-6"
        title="Pay As You Go balance"
        description={
          wallet?.prepaid
            ? `On the prepaid plan: calls cost ${perMinute(wallet.per_minute)} a minute from this balance.`
            : 'Not on the prepaid plan. Credit held here is used if the organization moves to it.'
        }
        actions={
          <AdminButton icon={PlusCircle} onClick={() => setAdjusting(true)} disabled={!wallet}>
            Adjust credit
          </AdminButton>
        }
        bodyClassName="p-0"
      >
        {error ? (
          <div className="p-4">
            <Callout tone="danger" title="Could not load the balance">{errorText(error)}</Callout>
          </div>
        ) : isLoading || !wallet ? (
          <div className="m-4 h-24 animate-pulse rounded-lg bg-slate-100" />
        ) : (
          <>
            {!wallet.ledger_matches && (
              <div className="p-4 pb-0">
                <Callout tone="danger" title="Balance and ledger disagree">
                  The stored balance is not the sum of the movements below. Nothing is corrected
                  automatically; check the server log for this wallet before adjusting it.
                </Callout>
              </div>
            )}
            <dl className="grid gap-4 p-4 sm:grid-cols-4">
              <Detail label="Balance">
                <span className={wallet.balance <= 0 && wallet.prepaid ? 'font-semibold text-red-600' : 'font-semibold'}>
                  {formatMoney(wallet.balance, wallet.currency)}
                </span>
              </Detail>
              <Detail label="Reserved by live calls">{formatMoney(wallet.held, wallet.currency)}</Detail>
              <Detail label="Auto-recharge">
                {wallet.auto_recharge.enabled ? (
                  <>
                    Adds {formatMoney(wallet.auto_recharge.amount, wallet.currency)} below{' '}
                    {formatMoney(wallet.auto_recharge.threshold, wallet.currency)}
                  </>
                ) : (
                  'Off'
                )}
                {wallet.auto_recharge.failures > 0 && (
                  <span className="ml-2 text-xs text-amber-700">
                    {wallet.auto_recharge.failures} declined
                  </span>
                )}
              </Detail>
              <Detail label="Saved card">
                {wallet.auto_recharge.card_last4
                  ? `${humanize(wallet.auto_recharge.card_brand ?? 'card')} ending ${wallet.auto_recharge.card_last4}`
                  : 'None'}
              </Detail>
            </dl>
            {!empty && (
              <>
                <Table>
                  <thead>
                    <tr>
                      <Th>When</Th>
                      <Th>Type</Th>
                      <Th>Detail</Th>
                      <Th className="text-right">Amount</Th>
                      <Th className="text-right">Balance</Th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    <TableState
                      colSpan={5}
                      empty={wallet.transactions.items.length === 0}
                      emptyText="No movements yet."
                    />
                    {wallet.transactions.items.map((row) => (
                      <Tr key={row.id}>
                        <Td className="whitespace-nowrap text-slate-500">{formatDate(row.created_at, true)}</Td>
                        <Td>
                          <Badge tone={row.actor_type === 'admin' ? 'brand' : 'neutral'}>{humanize(row.type)}</Badge>
                        </Td>
                        <Td className="text-xs text-slate-600">
                          {row.description ?? '—'}
                          {row.reason && <p className="text-slate-500">Reason: {row.reason}</p>}
                          {row.admin_email && <p className="text-slate-400">{row.admin_email}</p>}
                          {row.reference_id && row.type !== 'adjustment' && (
                            <p className="font-mono text-[11px] text-slate-400">{row.reference_id}</p>
                          )}
                        </Td>
                        <Td className={`text-right tabular-nums ${row.amount > 0 ? 'text-emerald-700' : ''}`}>
                          {row.amount > 0 ? '+' : ''}
                          {formatMoney(row.amount, wallet.currency)}
                        </Td>
                        <Td className="text-right tabular-nums text-slate-500">
                          {formatMoney(row.balance_after, wallet.currency)}
                        </Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
                {wallet.transactions.pages > 1 && (
                  <Pagination
                    page={wallet.transactions.page}
                    pages={wallet.transactions.pages}
                    total={wallet.transactions.total}
                    onPage={setPage}
                  />
                )}
              </>
            )}
          </>
        )}
      </Panel>

      <Dialog
        open={adjusting}
        onClose={() => setAdjusting(false)}
        title="Adjust credit"
        description="Adds a row to the organization's balance history, which the customer can see, and to the audit log."
        footer={
          <>
            <AdminButton variant="ghost" onClick={() => setAdjusting(false)}>Cancel</AdminButton>
            <AdminButton
              variant={direction === 'remove' ? 'danger' : 'primary'}
              loading={adjust.isPending}
              disabled={!valid}
              onClick={() => adjust.mutate()}
            >
              {direction === 'add' ? 'Add credit' : 'Remove credit'}
            </AdminButton>
          </>
        }
      >
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="Direction">
            {(['add', 'remove'] as const).map((option) => (
              <button
                key={option}
                type="button"
                role="radio"
                aria-checked={direction === option}
                onClick={() => setDirection(option)}
                className={`rounded-lg border px-3 py-2 text-sm font-medium ${
                  direction === option
                    ? 'border-brand-600 bg-brand-50 text-brand-700'
                    : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                }`}
              >
                {option === 'add' ? 'Add credit' : 'Remove credit'}
              </button>
            ))}
          </div>
          <Field label={`Amount (${(wallet?.currency ?? 'usd').toUpperCase()})`}>
            <input
              type="number"
              min={0}
              step="0.01"
              className={inputClass}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.00"
            />
          </Field>
          <Field label="Reason (shown in the audit log)">
            <input
              className={inputClass}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Goodwill credit, support ticket #123"
            />
          </Field>
          {direction === 'remove' && wallet && value > wallet.balance && (
            <Callout tone="warning" title="This takes the balance below zero">
              Calls are blocked for a prepaid organization until the balance is positive again.
            </Callout>
          )}
        </div>
      </Dialog>
    </>
  )
}
