'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import axios from 'axios'
import {
  AlertCircle, ArrowLeft, Bot, Check, CheckCircle2, ChevronDown, Loader2,
  MapPin, Phone, PhoneCall, Plug, RefreshCw, Search,
} from 'lucide-react'
import { PhoneDialog } from './PhoneDialog'
import { PhoneNumberPaywall } from '@/components/billing/PhoneNumberPaywall'
import {
  COUNTRIES, type AvailableNumber, type NumberSource, type OwnProvider, type PhoneNumber,
  formatMonthly, formatPhoneNumber, friendlyPhoneError, hasVoice, locationLabel,
  phoneNumberService, validateSearch,
} from '@/lib/phoneNumbers'
import { appDisplayName } from '@/lib/appNames'

type Step = 'search' | 'review' | 'done'

interface Props {
  open: boolean
  onClose: () => void
  source: NumberSource
  /** The connected account to buy on, for the own-provider flow. */
  ownProvider?: OwnProvider | null
  agents: { id: string; name: string }[]
  canPurchase: boolean
  entitlementsLoading: boolean
  onPurchased: (number: PhoneNumber) => void
  onUpgraded?: () => void
}

const inputClass =
  'h-11 w-full rounded-xl border border-slate-200 bg-white px-3.5 text-[14px] text-slate-900 outline-none transition-colors placeholder:text-slate-400 focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15'
const labelClass = 'mb-1.5 block text-[13px] font-semibold text-slate-700'
const primaryButton =
  'inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-[#0F6A59] px-5 text-[14px] font-semibold text-white shadow-sm transition-colors hover:bg-[#0c5a4b] disabled:cursor-not-allowed disabled:opacity-50'
const secondaryButton =
  'inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-5 text-[14px] font-semibold text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-50'

function CapabilityChip({ icon: Icon, label }: { icon: typeof Phone; label: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-600">
      <Icon className="h-3 w-3" />
      {label}
    </span>
  )
}

function Capabilities({ caps }: { caps: Record<string, boolean> }) {
  return (
    <div className="flex flex-wrap gap-1">
      {hasVoice(caps) && <CapabilityChip icon={PhoneCall} label="Voice" />}
      {/* SMS is switched off (3 Oct 2026): Voicecon is voice-only for now.
      {hasSms(caps) && <CapabilityChip icon={MessageSquare} label="SMS" />}
      */}
    </div>
  )
}

function InlineError({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3">
      <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-500" />
      <p className="flex-1 text-[13px] leading-relaxed text-red-800">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex flex-shrink-0 items-center gap-1 text-[13px] font-semibold text-red-700 hover:underline"
        >
          <RefreshCw className="h-3.5 w-3.5" /> Retry
        </button>
      )}
    </div>
  )
}

/**
 * Search → pick → review → buy → done.
 *
 * In the Voicecon flow nothing names a carrier: the user is buying "a
 * Voicecon number". In the own-provider flow the account they chose is shown,
 * because it's theirs and it's where the number will be billed.
 */
export function BuyNumberDialog({
  open, onClose, source, ownProvider, agents, canPurchase, entitlementsLoading, onPurchased, onUpgraded,
}: Props) {
  const [step, setStep] = useState<Step>('search')
  const [country, setCountry] = useState('US')
  const [areaCode, setAreaCode] = useState('')
  const [contains, setContains] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  const [results, setResults] = useState<AvailableNumber[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [selected, setSelected] = useState<AvailableNumber | null>(null)

  const [agentId, setAgentId] = useState('')
  const [purchasing, setPurchasing] = useState(false)
  const [purchaseError, setPurchaseError] = useState<string | null>(null)
  const [purchased, setPurchased] = useState<PhoneNumber | null>(null)

  const isOwn = source === 'own'
  const accountLabel = isOwn && ownProvider
    ? `${appDisplayName(ownProvider.slug)} · ${ownProvider.connection_name || 'your account'}`
    : null

  const runSearch = useCallback(async (opts?: { country?: string; areaCode?: string; contains?: string }) => {
    const c = opts?.country ?? country
    const a = (opts?.areaCode ?? areaCode).trim()
    const n = (opts?.contains ?? contains).trim()
    const invalid = validateSearch(c, a, n)
    setFormError(invalid)
    if (invalid) return
    setSearching(true)
    setSearchError(null)
    setSelected(null)
    try {
      const found = await phoneNumberService.search({
        source,
        country_code: c,
        area_code: a || undefined,
        contains: n || undefined,
        connection_id: ownProvider?.connection_id,
      })
      setResults(found)
    } catch (err) {
      setResults(null)
      setSearchError(friendlyPhoneError(err, 'search'))
    } finally {
      setSearching(false)
    }
  }, [country, areaCode, contains, source, ownProvider?.connection_id])

  // Fresh state each time it opens, and show numbers straight away rather
  // than an empty panel asking the user to search.
  useEffect(() => {
    if (!open) return
    setStep('search')
    setAreaCode('')
    setContains('')
    setFormError(null)
    setResults(null)
    setSearchError(null)
    setSelected(null)
    setPurchaseError(null)
    setPurchased(null)
    setAgentId(agents.length === 1 ? agents[0].id : '')
    if (canPurchase) runSearch({ country, areaCode: '', contains: '' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, source, ownProvider?.connection_id, canPurchase])

  const buy = async () => {
    if (!selected) return
    if (!agentId) {
      setPurchaseError('Choose which assistant should answer calls to this number.')
      return
    }
    setPurchasing(true)
    setPurchaseError(null)
    try {
      const number = await phoneNumberService.purchase({
        source,
        number: selected,
        agent_id: agentId,
        country_code: country,
        area_code: areaCode.trim() || undefined,
        connection_id: ownProvider?.connection_id,
      })
      setPurchased(number)
      setStep('done')
      onPurchased(number)
    } catch (err) {
      const message = friendlyPhoneError(err, 'purchase')
      // Someone else got it first: drop it and send them back to choose.
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        setResults((r) => r?.filter((n) => n.phone_number !== selected.phone_number) ?? null)
        setSelected(null)
        setStep('search')
        setSearchError(message)
      } else {
        setPurchaseError(message)
      }
    } finally {
      setPurchasing(false)
    }
  }

  const agentName = useMemo(
    () => agents.find((a) => a.id === (purchased?.agent_id ?? agentId))?.name,
    [agents, purchased, agentId]
  )

  const title =
    step === 'done' ? 'Your number is ready' : isOwn ? 'Buy a number on your provider' : 'Buy a phone number'
  const description =
    step === 'search'
      ? isOwn
        ? <>Numbers from <span className="font-medium text-slate-700">{accountLabel}</span>. They’re billed by your provider.</>
        : 'Pick a local number for your AI assistant to answer.'
      : step === 'review'
        ? 'Check the details and choose who answers.'
        : undefined

  // ---- footers -------------------------------------------------------------
  let footer: React.ReactNode = null
  if (canPurchase && step === 'search') {
    footer = (
      <>
        <button type="button" className={secondaryButton} onClick={onClose}>Cancel</button>
        <button type="button" className={primaryButton} disabled={!selected} onClick={() => setStep('review')}>
          Continue
        </button>
      </>
    )
  } else if (step === 'review') {
    footer = (
      <>
        <button type="button" className={secondaryButton} onClick={() => setStep('search')} disabled={purchasing}>
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
        <button type="button" className={primaryButton} onClick={buy} disabled={purchasing || agents.length === 0}>
          {purchasing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
          {purchasing ? 'Buying…' : 'Buy number'}
        </button>
      </>
    )
  } else if (step === 'done') {
    footer = (
      <>
        <button
          type="button"
          className={secondaryButton}
          onClick={() => {
            setStep('search')
            setSelected(null)
            setPurchased(null)
            runSearch()
          }}
        >
          Buy another
        </button>
        <button type="button" className={primaryButton} onClick={onClose}>Done</button>
      </>
    )
  }

  return (
    <PhoneDialog
      open={open}
      onClose={onClose}
      busy={purchasing}
      title={title}
      description={description}
      icon={step === 'done' ? undefined : isOwn ? <Plug className="h-5 w-5" /> : <Phone className="h-5 w-5" />}
      footer={footer}
    >
      {!entitlementsLoading && !canPurchase ? (
        <PhoneNumberPaywall onUpgraded={onUpgraded} />
      ) : step === 'search' ? (
        <div className="space-y-5">
          {/* Filters */}
          <form
            noValidate
            onSubmit={(e) => {
              e.preventDefault()
              runSearch()
            }}
            className="grid grid-cols-2 gap-3 sm:grid-cols-[1.3fr_1fr_1fr_auto] sm:items-end"
          >
            <div className="col-span-2 sm:col-span-1">
              <label htmlFor="pn-country" className={labelClass}>Country</label>
              <div className="relative">
                <select
                  id="pn-country"
                  value={country}
                  onChange={(e) => {
                    setCountry(e.target.value)
                    runSearch({ country: e.target.value })
                  }}
                  className={`${inputClass} appearance-none pr-9`}
                >
                  {COUNTRIES.map((c) => (
                    <option key={c.code} value={c.code}>{c.flag}  {c.name}</option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              </div>
            </div>
            <div>
              <label htmlFor="pn-area" className={labelClass}>Area code</label>
              <input
                id="pn-area"
                inputMode="numeric"
                autoComplete="off"
                value={areaCode}
                onChange={(e) => setAreaCode(e.target.value.replace(/[^\d]/g, '').slice(0, 5))}
                placeholder={country === 'US' || country === 'CA' ? 'e.g. 415' : 'Optional'}
                className={inputClass}
                aria-invalid={!!formError}
              />
            </div>
            <div>
              <label htmlFor="pn-contains" className={labelClass}>Contains</label>
              <input
                id="pn-contains"
                inputMode="numeric"
                autoComplete="off"
                value={contains}
                onChange={(e) => setContains(e.target.value.replace(/[^\d*]/g, '').slice(0, 10))}
                placeholder="e.g. 555"
                className={inputClass}
              />
            </div>
            <button type="submit" className={`${primaryButton} col-span-2 w-full sm:col-span-1 sm:w-auto`} disabled={searching}>
              {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              Search
            </button>
          </form>
          {formError && <p className="-mt-2 text-[13px] text-red-600">{formError}</p>}

          {/* Results */}
          <div aria-live="polite">
            {searchError && <InlineError message={searchError} onRetry={() => runSearch()} />}

            {searching && (
              <ul className="space-y-2" aria-label="Loading numbers">
                {[0, 1, 2, 3].map((i) => (
                  <li key={i} className="flex animate-pulse items-center gap-4 rounded-xl border border-slate-100 p-4">
                    <div className="h-10 w-10 rounded-full bg-slate-100" />
                    <div className="flex-1 space-y-2">
                      <div className="h-4 w-40 rounded bg-slate-100" />
                      <div className="h-3 w-24 rounded bg-slate-100" />
                    </div>
                    <div className="h-4 w-14 rounded bg-slate-100" />
                  </li>
                ))}
              </ul>
            )}

            {!searching && !searchError && results && results.length === 0 && (
              <div className="rounded-xl border border-dashed border-slate-200 px-6 py-10 text-center">
                <Search className="mx-auto h-8 w-8 text-slate-300" />
                <p className="mt-3 text-[14px] font-semibold text-slate-800">No numbers match that search</p>
                <p className="mt-1 text-[13px] text-slate-500">Try a nearby area code, or clear the filters.</p>
                {(areaCode || contains) && (
                  <button
                    type="button"
                    className="mt-4 text-[13px] font-semibold text-[#0F6A59] hover:underline"
                    onClick={() => {
                      setAreaCode('')
                      setContains('')
                      runSearch({ areaCode: '', contains: '' })
                    }}
                  >
                    Clear filters
                  </button>
                )}
              </div>
            )}

            {!searching && results && results.length > 0 && (
              <>
                <p className="mb-2 text-[12px] font-medium uppercase tracking-wide text-slate-400">
                  {results.length} available · select one
                </p>
                <ul role="radiogroup" aria-label="Available numbers" className="space-y-2">
                  {results.map((n) => {
                    const active = selected?.phone_number === n.phone_number
                    const price = formatMonthly(n.monthly_cost, n.currency)
                    const location = locationLabel(n)
                    return (
                      <li key={n.phone_number}>
                        <button
                          type="button"
                          role="radio"
                          aria-checked={active}
                          onClick={() => setSelected(n)}
                          onDoubleClick={() => { setSelected(n); setStep('review') }}
                          className={`flex w-full items-center gap-3 rounded-xl border p-3.5 text-left transition-all sm:gap-4 sm:p-4 ${
                            active
                              ? 'border-[#0F6A59] bg-[#0F6A59]/[0.04] ring-2 ring-[#0F6A59]/15'
                              : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                          }`}
                        >
                          <span
                            className={`flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border-2 ${
                              active ? 'border-[#0F6A59] bg-[#0F6A59]' : 'border-slate-300'
                            }`}
                            aria-hidden="true"
                          >
                            {active && <span className="h-1.5 w-1.5 rounded-full bg-white" />}
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block text-[15px] font-semibold tracking-tight text-slate-900 tabular-nums">
                              {formatPhoneNumber(n.phone_number)}
                            </span>
                            <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-slate-500">
                              {location && (
                                <span className="inline-flex items-center gap-1">
                                  <MapPin className="h-3 w-3" /> {location}
                                </span>
                              )}
                              <Capabilities caps={n.capabilities} />
                            </span>
                          </span>
                          {price && (
                            <span className="flex-shrink-0 text-right text-[13px] font-semibold text-slate-700">{price}</span>
                          )}
                        </button>
                      </li>
                    )
                  })}
                </ul>
              </>
            )}
          </div>
        </div>
      ) : step === 'review' && selected ? (
        <div className="space-y-5">
          <div className="rounded-2xl border border-slate-200 bg-gradient-to-br from-[#0F6A59]/[0.06] to-transparent p-5">
            <p className="text-[12px] font-medium uppercase tracking-wide text-slate-500">
              {isOwn ? `On ${accountLabel}` : 'Your new number'}
            </p>
            <p className="mt-1 text-2xl font-semibold tracking-tight text-slate-900 tabular-nums">
              {formatPhoneNumber(selected.phone_number)}
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-[13px] text-slate-600">
              {locationLabel(selected) && (
                <span className="inline-flex items-center gap-1"><MapPin className="h-3.5 w-3.5" /> {locationLabel(selected)}</span>
              )}
              <Capabilities caps={selected.capabilities} />
            </div>
            {formatMonthly(selected.monthly_cost, selected.currency) && (
              <div className="mt-4 flex items-center justify-between border-t border-slate-200/70 pt-3 text-[14px]">
                <span className="text-slate-600">Monthly price</span>
                <span className="font-semibold text-slate-900">
                  {formatMonthly(selected.monthly_cost, selected.currency)}
                </span>
              </div>
            )}
          </div>

          <div>
            <label htmlFor="pn-agent" className={labelClass}>Who answers calls to this number?</label>
            {agents.length === 0 ? (
              <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] text-amber-900">
                <Bot className="mt-0.5 h-4 w-4 flex-shrink-0" />
                <p>
                  You need an assistant to answer this number.{' '}
                  <Link href="/dashboard/agents/new" className="font-semibold underline">Create one first</Link>, then come back.
                </p>
              </div>
            ) : (
              <div className="relative">
                <select
                  id="pn-agent"
                  value={agentId}
                  onChange={(e) => { setAgentId(e.target.value); setPurchaseError(null) }}
                  className={`${inputClass} appearance-none pr-9`}
                >
                  <option value="">Choose an assistant…</option>
                  {agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              </div>
            )}
            <p className="mt-1.5 text-[12px] text-slate-500">You can change this later from the assistant’s settings.</p>
          </div>

          {purchaseError && <InlineError message={purchaseError} />}
        </div>
      ) : step === 'done' && purchased ? (
        <div className="py-4 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-50">
            <CheckCircle2 className="h-7 w-7 text-emerald-600" />
          </div>
          <p className="mt-4 text-2xl font-semibold tracking-tight text-slate-900 tabular-nums">
            {formatPhoneNumber(purchased.phone_number)}
          </p>
          <p className="mx-auto mt-2 max-w-sm text-[14px] leading-relaxed text-slate-600">
            {agentName ? <>Calls to this number are now answered by <span className="font-semibold text-slate-800">{agentName}</span>.</> : 'Your number is active.'}{' '}
            Give it a try — call it from your phone.
          </p>
        </div>
      ) : null}
    </PhoneDialog>
  )
}
