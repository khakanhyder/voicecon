'use client'

/**
 * Add credit to the Pay As You Go balance.
 *
 * One dialog for every place credit is bought: the wallet card, the Pay As You
 * Go plan card (where the first top-up is also what starts the plan), the
 * banners and the "your balance is too low" dialog. It follows the active
 * payment provider like checkout does — a card form for Stripe, a hand-off to
 * the hosted page for Polar.
 *
 * The balance is never changed from here. The server credits it when the
 * payment provider confirms the money moved; this only reports what it said.
 */
import { useEffect, useMemo, useState } from 'react'
import { Elements, CardElement, useStripe, useElements } from '@stripe/react-stripe-js'
import { toast } from 'sonner'
import { Lock } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { ModalOverlay } from '@/components/ui/modal-overlay'
import { getErrorMessage } from '@/lib/api'
import { getStripe, isStripeConfigured } from '@/lib/stripe'
import { perMinute } from '@/lib/pricing'
import {
  formatMoney,
  minutesFor,
  topupAmountProblem,
  walletService,
  type TopupResult,
  type Wallet,
} from '@/lib/wallet'
import { cn } from '@/lib/utils'
import { BillingOwnerNotice, useBillingAccess } from './BillingOwnerNotice'

interface Props {
  wallet: Wallet
  /**
   * The first top-up of a workspace that is choosing Pay As You Go: the
   * payment also moves it onto the plan.
   */
  activate?: boolean
  onClose: () => void
  /** The payment went through (or is settling) — refresh what shows the balance. */
  onSuccess: (result: TopupResult) => void
  /** Where to land after a hosted (Polar) top-up. Defaults to the current page. */
  returnPath?: string
}

interface PayProps {
  amount: number
  /** Why the amount cannot be paid; null when it can. */
  problem: string | null
  activate: boolean
  busy: boolean
  setBusy: (v: boolean) => void
  onError: (message: string | null) => void
  onSuccess: (result: TopupResult) => void
  returnPath?: string
  cancelPath?: string
  wallet: Wallet
  /** Words on the pay button, before the amount. */
  payLabel: string
}

/** Stripe: the card is collected here. Must render inside <Elements>. */
function CardTopup({ amount, problem, activate, busy, setBusy, onError, onSuccess, wallet, payLabel }: PayProps) {
  const stripe = useStripe()
  const elements = useElements()
  const auto = wallet.auto_recharge
  const [saveCard, setSaveCard] = useState(false)
  const [threshold, setThreshold] = useState(String(auto.threshold ?? wallet.low_balance ?? 5))
  const [rechargeAmount, setRechargeAmount] = useState(String(auto.amount ?? ''))

  const pay = async () => {
    if (problem) {
      onError(problem)
      return
    }
    if (!stripe || !elements) {
      toast.error('Payment form is still loading')
      return
    }
    const card = elements.getElement(CardElement)
    if (!card) return

    const autoAmount = Number(rechargeAmount || amount)
    const autoThreshold = Number(threshold)
    if (saveCard) {
      const autoProblem = topupAmountProblem(autoAmount, wallet.topup)
      if (autoProblem) return onError(`Auto-recharge: ${autoProblem}`)
      if (!(autoThreshold >= 1)) {
        return onError('Auto-recharge needs a balance of at least $1.00 to trigger on.')
      }
    }

    setBusy(true)
    onError(null)
    try {
      const { error, paymentMethod } = await stripe.createPaymentMethod({ type: 'card', card })
      if (error) throw new Error(error.message || 'Invalid card details')
      const result = await walletService.topUpWithCard(stripe, {
        amount,
        payment_method_id: paymentMethod.id,
        save_card: saveCard,
        activate,
        auto_recharge: saveCard
          ? { enabled: true, threshold: autoThreshold, amount: autoAmount }
          : undefined,
      })
      onSuccess(result)
    } catch (err) {
      onError(getErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="rounded-lg border border-gray-300 p-3">
        <CardElement options={{ style: { base: { fontSize: '15px' } } }} />
      </div>

      {auto.supported && (
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
          <label className="flex cursor-pointer items-start gap-2.5 text-sm text-gray-800">
            <input
              type="checkbox"
              checked={saveCard}
              onChange={(e) => setSaveCard(e.target.checked)}
              disabled={busy}
              className="mt-0.5 h-4 w-4 rounded border-gray-300 text-[#106959] focus:ring-[#106959]"
            />
            <span>
              <span className="font-medium">Save this card and top up automatically</span>
              <span className="mt-0.5 block text-xs text-gray-500">
                So calls never stop because the balance ran out. You can switch it off at any time.
              </span>
            </span>
          </label>
          {saveCard && (
            <div className="mt-3 grid grid-cols-2 gap-3">
              <label className="text-xs font-medium text-gray-600">
                When my balance falls below
                <div className="mt-1 flex items-center rounded-md border border-gray-300 bg-white px-2">
                  <span className="text-sm text-gray-500">$</span>
                  <input
                    inputMode="decimal"
                    value={threshold}
                    onChange={(e) => setThreshold(e.target.value)}
                    disabled={busy}
                    aria-label="Auto-recharge trigger balance"
                    className="w-full border-0 bg-transparent px-1.5 py-1.5 text-sm text-gray-900 outline-none focus:ring-0"
                  />
                </div>
              </label>
              <label className="text-xs font-medium text-gray-600">
                Add
                <div className="mt-1 flex items-center rounded-md border border-gray-300 bg-white px-2">
                  <span className="text-sm text-gray-500">$</span>
                  <input
                    inputMode="decimal"
                    value={rechargeAmount}
                    placeholder={String(amount || '')}
                    onChange={(e) => setRechargeAmount(e.target.value)}
                    disabled={busy}
                    aria-label="Auto-recharge amount"
                    className="w-full border-0 bg-transparent px-1.5 py-1.5 text-sm text-gray-900 outline-none focus:ring-0"
                  />
                </div>
              </label>
            </div>
          )}
        </div>
      )}

      <Button className="w-full bg-[#106959] text-white hover:bg-[#0c5044]" onClick={pay} disabled={busy}>
        {busy ? 'Processing…' : `${payLabel} ${formatMoney(amount || 0)}`}
      </Button>
      <p className="flex items-center justify-center gap-1.5 text-xs text-gray-500">
        <Lock className="h-3 w-3" aria-hidden="true" />
        Card details go straight to Stripe. Your bank may ask you to approve the payment.
      </p>
    </>
  )
}

/** Polar: the customer pays on the hosted page and comes back. */
function HostedTopup({ amount, problem, activate, busy, setBusy, onError, returnPath, cancelPath }: PayProps) {
  const pay = async () => {
    if (problem) {
      onError(problem)
      return
    }
    setBusy(true)
    onError(null)
    try {
      await walletService.startHostedTopup({
        amount,
        activate,
        return_path: returnPath ?? window.location.pathname,
        ...(cancelPath ? { cancel_path: cancelPath } : {}),
      })
      // Still busy: the page is leaving for the provider's checkout.
    } catch (err) {
      onError(getErrorMessage(err))
      setBusy(false)
    }
  }

  return (
    <>
      <p className="flex items-start gap-2 rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm text-gray-700">
        <Lock className="mt-0.5 h-4 w-4 flex-shrink-0 text-gray-500" />
        You&apos;ll pay on our payment partner&apos;s secure checkout page, then come straight back
        here. Sales tax, where it applies, is added there and is not part of your credit.
      </p>
      <Button className="w-full bg-[#106959] text-white hover:bg-[#0c5044]" onClick={pay} disabled={busy}>
        {busy ? 'Opening checkout…' : `Continue to payment · ${formatMoney(amount || 0)}`}
      </Button>
    </>
  )
}

interface FormProps {
  wallet: Wallet
  activate?: boolean
  onSuccess: (result: TopupResult) => void
  /** Where to land after a hosted (Polar) top-up. Defaults to the current page. */
  returnPath?: string
  /** Where the hosted checkout's back button goes. Defaults to the current page. */
  cancelPath?: string
  /** Reports whether a payment is in flight, so a host can lock its own buttons. */
  onBusyChange?: (busy: boolean) => void
  /** Words on the pay button, before the amount. Defaults to "Pay". */
  payLabel?: string
}

/**
 * The amount picker and the payment step, without a dialog around them. The
 * top-up dialog wraps this; onboarding places it straight on the page.
 */
export function TopUpForm({
  wallet,
  activate = false,
  onSuccess,
  returnPath,
  cancelPath,
  onBusyChange,
  payLabel = 'Pay',
}: FormProps) {
  const presets = wallet.topup.presets
  const [selected, setSelected] = useState<number | 'custom'>(presets[1] ?? presets[0] ?? 'custom')
  const [custom, setCustom] = useState('')
  const [busy, setBusyState] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const setBusy = (value: boolean) => {
    setBusyState(value)
    onBusyChange?.(value)
  }

  const hosted = wallet.checkout_mode === 'hosted'
  const amount = selected === 'custom' ? Number(custom) : selected
  const problem = topupAmountProblem(amount, wallet.topup)
  const minutes = problem ? null : minutesFor(amount, wallet.per_minute)

  const stripePromise = useMemo(
    () => (!hosted ? getStripe(wallet.publishable_key) : null),
    [hosted, wallet.publishable_key]
  )
  // <Elements> never surfaces a failed Stripe.js load; without this the form
  // shows an empty card box and "Pay" does nothing useful.
  const [stripeFailed, setStripeFailed] = useState(false)
  useEffect(() => {
    if (!stripePromise) return
    let active = true
    setStripeFailed(false)
    stripePromise
      .then((stripe) => active && !stripe && setStripeFailed(true))
      .catch(() => active && setStripeFailed(true))
    return () => {
      active = false
    }
  }, [stripePromise])

  const configured = wallet.can_topup && (hosted || isStripeConfigured(wallet.publishable_key))

  const succeed = (result: TopupResult) => {
    if (result.status === 'processing') {
      toast.success('Payment received. Your balance updates as soon as your bank settles it.')
    } else if (result.activated) {
      toast.success(`You're on ${wallet.plan_name ?? 'Pay As You Go'}. ${formatMoney(amount)} of credit added.`)
    } else {
      toast.success(`${formatMoney(amount)} of credit added.`)
    }
    onSuccess(result)
  }

  const payProps: PayProps = {
    amount,
    problem,
    activate,
    busy,
    setBusy,
    onError: setError,
    onSuccess: succeed,
    returnPath,
    cancelPath,
    wallet,
    payLabel,
  }

  const amountButton = (active: boolean) =>
    cn(
      'rounded-lg border px-2 py-2.5 text-sm font-semibold transition-colors',
      active
        ? 'border-[#106959] bg-[#106959]/10 text-[#106959]'
        : 'border-gray-300 text-gray-700 hover:border-[#106959]'
    )

  return (
    <div className="space-y-4">
      <fieldset disabled={busy}>
        <legend className="mb-2 text-sm font-medium text-gray-700">Amount</legend>
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
          {presets.map((preset) => (
            <button
              key={preset}
              type="button"
              aria-pressed={selected === preset}
              onClick={() => {
                setSelected(preset)
                setError(null)
              }}
              className={amountButton(selected === preset)}
            >
              ${preset.toLocaleString('en-US')}
            </button>
          ))}
          <button
            type="button"
            aria-pressed={selected === 'custom'}
            onClick={() => {
              setSelected('custom')
              setError(null)
            }}
            className={amountButton(selected === 'custom')}
          >
            Other
          </button>
        </div>
        {selected === 'custom' && (
          <div className="mt-2 flex items-center rounded-lg border border-gray-300 px-3">
            <span className="text-gray-500">$</span>
            <input
              autoFocus
              inputMode="decimal"
              value={custom}
              onChange={(e) => {
                setCustom(e.target.value.replace(/[^0-9.]/g, ''))
                setError(null)
              }}
              placeholder={`${wallet.topup.minimum} to ${wallet.topup.maximum.toLocaleString('en-US')}`}
              aria-label="Amount to add"
              className="w-full border-0 bg-transparent px-2 py-2.5 text-sm text-gray-900 outline-none focus:ring-0"
            />
          </div>
        )}
        <p className="mt-2 text-xs text-gray-500" aria-live="polite">
          {minutes != null
            ? `About ${minutes.toLocaleString('en-US')} minutes of calls. Credit does not expire.`
            : selected === 'custom' && custom && problem
              ? problem
              : 'Credit does not expire.'}
        </p>
      </fieldset>

      {!configured ? (
        <p className="rounded-lg border border-yellow-200 bg-yellow-50 p-3 text-sm text-yellow-800">
          Payments are not available right now. Please try again later.
        </p>
      ) : hosted ? (
        <HostedTopup {...payProps} />
      ) : stripeFailed ? (
        <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          The secure payment form couldn&apos;t load. Check your connection or disable any content
          blocker for this site, then reload the page and try again.
        </p>
      ) : (
        <Elements key={wallet.publishable_key ?? ''} stripe={stripePromise}>
          <CardTopup {...payProps} />
        </Elements>
      )}

      {error && (
        <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </p>
      )}
    </div>
  )
}

export function TopUpModal({ wallet, activate = false, onClose, onSuccess, returnPath }: Props) {
  const { canManage } = useBillingAccess()
  const [busy, setBusy] = useState(false)

  return (
    // No backdrop close: a stray click outside would throw away a typed card.
    <ModalOverlay onClose={onClose} busy={busy} closeOnBackdrop={false} className="bg-black/40">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="topup-modal-title"
        className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl"
      >
        <div className="space-y-4">
          <div>
            <h3 id="topup-modal-title" className="text-lg font-bold text-gray-900">
              {activate ? `Start ${wallet.plan_name ?? 'Pay As You Go'}` : 'Add credit'}
            </h3>
            <p className="text-sm text-gray-600">
              {activate
                ? `No monthly fee. Calls cost ${perMinute(wallet.per_minute)} a minute, paid from the credit you add.`
                : `Calls cost ${perMinute(wallet.per_minute)} a minute, paid from your balance.`}
            </p>
          </div>

          {!canManage ? (
            <BillingOwnerNotice />
          ) : (
            <TopUpForm
              wallet={wallet}
              activate={activate}
              onSuccess={onSuccess}
              returnPath={returnPath}
              onBusyChange={setBusy}
            />
          )}

          <div className="flex justify-end">
            <Button variant="ghost" onClick={onClose} disabled={busy}>
              {canManage ? 'Cancel' : 'Close'}
            </Button>
          </div>
        </div>
      </div>
    </ModalOverlay>
  )
}
