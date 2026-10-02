'use client'

/**
 * The Pay As You Go balance on the billing page: what is left, a way to add
 * more, auto-recharge, and the history of every credit and charge.
 *
 * Shown to a workspace that is on the plan, is about to move onto it, or has
 * credit from an earlier time on it. Everyone who can see billing can see
 * this; only the workspace owner gets the buttons that spend money.
 */
import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { AlertCircle, CreditCard, ExternalLink, Plus, RefreshCw, Wallet as WalletIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { getErrorMessage } from '@/lib/api'
import { formatDate, formatDateTime } from '@/lib/datetime'
import { perMinute } from '@/lib/pricing'
import { useConfirm } from '@/hooks/use-confirm'
import {
  TRANSACTION_LABELS,
  WALLET_TRANSACTIONS_KEY,
  formatMoney,
  formatSigned,
  minutesLeftLabel,
  topupAmountProblem,
  walletService,
  type Wallet,
} from '@/lib/wallet'
import { useBillingAccess } from './BillingOwnerNotice'

/** The id the "Add credit" banners and emails scroll to (`#wallet`). */
export const WALLET_CARD_ID = 'wallet'

const HISTORY_PAGE_SIZE = 10

function cardName(brand: string | null, last4: string | null): string {
  const name = brand ? brand.charAt(0).toUpperCase() + brand.slice(1) : 'Card'
  return last4 ? `${name} ending ${last4}` : name
}

function AutoRechargePanel({
  wallet,
  canManage,
  onChanged,
}: {
  wallet: Wallet
  canManage: boolean
  onChanged: () => void
}) {
  const { confirm, ConfirmDialog } = useConfirm()
  const auto = wallet.auto_recharge
  const [threshold, setThreshold] = useState(String(auto.threshold ?? wallet.low_balance ?? 5))
  const [amount, setAmount] = useState(String(auto.amount ?? wallet.topup.presets[1] ?? wallet.topup.minimum))
  const [busy, setBusy] = useState(false)
  const hasCard = !!auto.card_last4 || !!auto.card_brand

  // Follow the server after a save or a top-up that changed the settings.
  useEffect(() => {
    if (auto.threshold != null) setThreshold(String(auto.threshold))
    if (auto.amount != null) setAmount(String(auto.amount))
  }, [auto.threshold, auto.amount])

  if (!auto.supported) {
    return (
      <p className="text-[13px] font-poppins text-black/60">
        Auto-recharge is not available with our current payment partner. We email you when your
        balance runs low, so you can add credit before calls stop.
      </p>
    )
  }

  if (!hasCard) {
    return (
      <p className="text-[13px] font-poppins text-black/60">
        To top up automatically when your balance runs low, add credit with your card and tick
        &ldquo;Save this card and top up automatically&rdquo;.
      </p>
    )
  }

  const save = async (enabled: boolean) => {
    const thresholdValue = Number(threshold)
    const amountValue = Number(amount)
    if (enabled) {
      const problem = topupAmountProblem(amountValue, wallet.topup)
      if (problem) return void toast.error(problem)
      if (!(thresholdValue >= 1)) {
        return void toast.error('Choose a balance of at least $1.00 to top up at.')
      }
    }
    setBusy(true)
    try {
      await walletService.setAutoRecharge(
        enabled ? { enabled, threshold: thresholdValue, amount: amountValue } : { enabled }
      )
      toast.success(enabled ? 'Auto-recharge is on' : 'Auto-recharge is off')
      onChanged()
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const removeCard = async () => {
    const ok = await confirm({
      title: 'Remove saved card',
      description:
        'Remove this card? Auto-recharge will be switched off, and you will need to add credit yourself when your balance runs low.',
      confirmText: 'Remove card',
      cancelText: 'Keep card',
      isDestructive: true,
    })
    if (!ok) return
    setBusy(true)
    try {
      await walletService.removeCard()
      toast.success('Card removed')
      onChanged()
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span
          className={`rounded px-2 py-0.5 text-xs font-semibold ${
            auto.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
          }`}
        >
          {auto.enabled ? 'ON' : 'OFF'}
        </span>
        <span className="flex items-center gap-1.5 text-[13px] font-poppins text-black/70">
          <CreditCard className="h-4 w-4 text-black/40" aria-hidden="true" />
          {cardName(auto.card_brand, auto.card_last4)}
        </span>
      </div>

      {canManage ? (
        <>
          <div className="mt-3 flex flex-wrap items-end gap-3">
            <label className="text-[12px] font-medium font-poppins text-black/60">
              When my balance falls below
              <div className="mt-1 flex w-32 items-center rounded-md border border-slate-300 bg-white px-2">
                <span className="text-sm text-black/50">$</span>
                <input
                  inputMode="decimal"
                  value={threshold}
                  onChange={(e) => setThreshold(e.target.value.replace(/[^0-9.]/g, ''))}
                  disabled={busy}
                  aria-label="Auto-recharge trigger balance"
                  className="w-full border-0 bg-transparent px-1.5 py-1.5 text-sm text-black outline-none focus:ring-0"
                />
              </div>
            </label>
            <label className="text-[12px] font-medium font-poppins text-black/60">
              Add
              <div className="mt-1 flex w-32 items-center rounded-md border border-slate-300 bg-white px-2">
                <span className="text-sm text-black/50">$</span>
                <input
                  inputMode="decimal"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value.replace(/[^0-9.]/g, ''))}
                  disabled={busy}
                  aria-label="Auto-recharge amount"
                  className="w-full border-0 bg-transparent px-1.5 py-1.5 text-sm text-black outline-none focus:ring-0"
                />
              </div>
            </label>
            <Button variant="outline" onClick={() => save(true)} disabled={busy}>
              {auto.enabled ? 'Save' : 'Switch on'}
            </Button>
            {auto.enabled && (
              <Button variant="outline" onClick={() => save(false)} disabled={busy}>
                Switch off
              </Button>
            )}
            <Button
              variant="outline"
              className="border-red-200 text-red-600 hover:bg-red-50"
              onClick={removeCard}
              disabled={busy}
            >
              Remove card
            </Button>
          </div>
          <p className="mt-2 text-[12px] font-poppins text-black/50">
            We charge this card for the amount above whenever your balance falls below the level you set.
          </p>
        </>
      ) : auto.enabled ? (
        <p className="mt-2 text-[13px] font-poppins text-black/60">
          Adds {formatMoney(auto.amount ?? 0)} when the balance falls below {formatMoney(auto.threshold ?? 0)}.
        </p>
      ) : null}
      <ConfirmDialog />
    </div>
  )
}

function History() {
  const [page, setPage] = useState(1)
  const { data, isLoading, isFetching } = useQuery({
    queryKey: [...WALLET_TRANSACTIONS_KEY, page],
    queryFn: () => walletService.transactions(page, HISTORY_PAGE_SIZE),
    placeholderData: (previous) => previous,
  })

  if (isLoading) {
    return (
      <div className="space-y-2" aria-busy="true">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-9 animate-pulse rounded bg-gray-100" />
        ))}
      </div>
    )
  }
  if (!data || data.items.length === 0) {
    return <p className="text-[13px] font-poppins text-black/50">Nothing yet. Top-ups and call charges appear here.</p>
  }

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px]">
          <thead className="border-b border-slate-200 text-left text-xs font-medium uppercase text-gray-500">
            <tr>
              <th className="py-2 pr-4">Date</th>
              <th className="py-2 pr-4">Activity</th>
              <th className="py-2 pr-4 text-right">Amount</th>
              <th className="py-2 text-right">Balance</th>
            </tr>
          </thead>
          <tbody className={`divide-y divide-slate-100 ${isFetching ? 'opacity-60' : ''}`}>
            {data.items.map((row) => (
              <tr key={row.id}>
                <td className="whitespace-nowrap py-2.5 pr-4 text-[13px] text-black/60">
                  {formatDateTime(row.created_at)}
                </td>
                <td className="py-2.5 pr-4 text-[13px] text-black">
                  {/* The description already says what it was ("Call from …, 3 min");
                      the type's own label is only the fallback. */}
                  <span className="font-medium">
                    {row.description || TRANSACTION_LABELS[row.type] || 'Activity'}
                  </span>
                  {row.receipt_url && (
                    <a
                      href={row.receipt_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-2 inline-flex items-center gap-1 text-blue-600 hover:text-blue-800"
                    >
                      Receipt
                      <ExternalLink className="h-3 w-3" aria-hidden="true" />
                    </a>
                  )}
                </td>
                <td
                  className={`whitespace-nowrap py-2.5 pr-4 text-right text-[13px] font-semibold ${
                    row.amount > 0 ? 'text-green-700' : 'text-black'
                  }`}
                >
                  {formatSigned(row.amount)}
                </td>
                <td className="whitespace-nowrap py-2.5 text-right text-[13px] text-black/60">
                  {formatMoney(row.balance_after)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.pages > 1 && (
        <div className="mt-3 flex items-center justify-between text-[13px] text-black/60">
          <span>
            Page {data.page} of {data.pages}
          </span>
          <div className="flex gap-2">
            <Button variant="outline" disabled={page <= 1 || isFetching} onClick={() => setPage((p) => p - 1)}>
              Newer
            </Button>
            <Button
              variant="outline"
              disabled={page >= data.pages || isFetching}
              onClick={() => setPage((p) => p + 1)}
            >
              Older
            </Button>
          </div>
        </div>
      )}
    </>
  )
}

export function WalletCard({
  wallet,
  onTopUp,
  onChanged,
  refreshing = false,
}: {
  wallet: Wallet
  /** Open the top-up dialog. */
  onTopUp: () => void
  /** Settings changed here; refetch the wallet. */
  onChanged: () => void
  refreshing?: boolean
}) {
  const { canManage } = useBillingAccess()
  const minutes = minutesLeftLabel(wallet)
  const tone = wallet.is_empty ? 'text-red-600' : wallet.is_low ? 'text-amber-600' : 'text-[#106959]'

  return (
    <section
      id={WALLET_CARD_ID}
      aria-labelledby="wallet-heading"
      className="scroll-mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-[0_4px_20px_-4px_rgba(16,105,89,0.1)]"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 id="wallet-heading" className="text-[20px] font-bold font-poppins text-[#000000]">
            Balance
          </h2>
          <p className="mt-1 text-[14px] font-poppins text-black/60">
            {wallet.on_plan
              ? `Calls cost ${perMinute(wallet.per_minute)} a minute and are paid for from this balance.`
              : wallet.switching_at
                ? `You move to ${wallet.plan_name ?? 'Pay As You Go'} on ${formatDate(wallet.switching_at)}. From then, calls cost ${perMinute(wallet.per_minute)} a minute from this balance.`
                : `Credit for ${wallet.plan_name ?? 'Pay As You Go'}. It is kept while you are on a subscription and used if you switch.`}
          </p>
        </div>
        {canManage && (
          <Button
            className="bg-[#106959] text-white hover:bg-[#0c5044]"
            onClick={onTopUp}
          >
            <Plus className="mr-1.5 h-4 w-4" />
            Add credit
          </Button>
        )}
      </div>

      <div className="mt-5 flex flex-wrap items-end gap-x-8 gap-y-3">
        <div>
          <div className="flex items-center gap-2 text-[14px] font-poppins text-black/60">
            <WalletIcon className="h-4 w-4" aria-hidden="true" />
            Available credit
            {refreshing && <RefreshCw className="h-3.5 w-3.5 animate-spin text-black/30" aria-hidden="true" />}
          </div>
          <p className={`mt-1 text-[36px] font-bold font-poppins leading-none ${tone}`} data-testid="wallet-balance">
            {formatMoney(wallet.balance)}
          </p>
        </div>
        <div className="text-[13px] font-poppins text-black/60">
          {wallet.on_plan && minutes && <p>{minutes}</p>}
          {wallet.held > 0 && <p>{formatMoney(wallet.held)} is reserved for calls in progress</p>}
          {wallet.on_plan && wallet.number_monthly_fee > 0 && (
            <p>Each phone number costs {formatMoney(wallet.number_monthly_fee)} a month from this balance</p>
          )}
        </div>
      </div>

      {wallet.on_plan && (wallet.is_empty || wallet.is_low) && (
        <div
          role="status"
          className={`mt-4 flex items-start gap-3 rounded-lg border p-4 text-sm ${
            wallet.is_empty
              ? 'border-red-200 bg-red-50 text-red-900'
              : 'border-amber-200 bg-amber-50 text-amber-900'
          }`}
        >
          <AlertCircle
            className={`mt-0.5 h-5 w-5 flex-shrink-0 ${wallet.is_empty ? 'text-red-600' : 'text-amber-600'}`}
            aria-hidden="true"
          />
          <div>
            <p className="font-semibold">
              {wallet.is_empty ? 'Your balance has run out' : 'Your balance is running low'}
            </p>
            <p className="mt-1">
              {wallet.is_empty
                ? 'Your agents have stopped making and answering calls. Add credit and they start again straight away.'
                : 'Calls stop when the balance runs out. Add credit now to avoid an interruption.'}
            </p>
          </div>
        </div>
      )}

      <div className="mt-6 border-t border-slate-200 pt-5">
        <h3 className="mb-2 text-[15px] font-semibold font-poppins text-[#000000]">Auto-recharge</h3>
        <AutoRechargePanel wallet={wallet} canManage={canManage} onChanged={onChanged} />
      </div>

      <div className="mt-6 border-t border-slate-200 pt-5">
        <h3 className="mb-3 text-[15px] font-semibold font-poppins text-[#000000]">History</h3>
        <History />
      </div>
    </section>
  )
}
