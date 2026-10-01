'use client'

/**
 * Phone Numbers.
 *
 * Two separate ways to get a number:
 *  1. Buy a Voicecon number — search, select, buy, done. Provider-agnostic:
 *     nothing here names the carrier behind Voicecon numbers.
 *  2. Connect your own provider — the advanced flow, and the only place
 *     carrier names (Twilio, Telnyx, …) appear.
 */

import { Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { toast } from 'sonner'
import {
  AlertCircle, ArrowRight, Bot, Check, DollarSign, ExternalLink, Loader2, MessageSquare,
  Phone, PhoneCall, Plug, Plus, RefreshCw, Trash2, TrendingUp,
} from 'lucide-react'
import { apiClient } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { FEATURES } from '@/lib/entitlements'
import { useEntitlementStore } from '@/store/entitlementStore'
import { useConfirm } from '@/hooks/use-confirm'
import { formatDate } from '@/lib/datetime'
import { appDisplayName } from '@/lib/appNames'
import {
  type NumberSource, type OwnProvider, type PhoneNumber, type PurchaseOptions,
  formatMonthly, formatPhoneNumber, friendlyPhoneError, hasSms, hasVoice, phoneNumberService,
} from '@/lib/phoneNumbers'
import { BuyNumberDialog } from '@/components/phone-numbers/BuyNumberDialog'
import { ConnectedAccounts, OwnProviderDialog } from '@/components/phone-numbers/OwnProviderDialog'
import { ImportNumbersDialog } from '@/components/phone-numbers/ImportNumbersDialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const statusStyle: Record<string, string> = {
  active: 'bg-emerald-50 text-emerald-700 ring-emerald-600/15',
  inactive: 'bg-slate-100 text-slate-600 ring-slate-500/15',
  pending: 'bg-amber-50 text-amber-700 ring-amber-600/15',
  suspended: 'bg-amber-50 text-amber-700 ring-amber-600/15',
}

/** What the status pill says. "Suspended" is our word, not the customer's. */
const statusLabel = (status: string) => (status === 'suspended' ? 'On hold' : status)

/**
 * Opens the purchase dialog for `?tab=search` — a deep link from elsewhere in
 * the app or the docs — then drops the param
 * so a refresh doesn't reopen it. Its own component so useSearchParams sits in
 * a Suspense boundary.
 */
function OpenPurchaseFromUrl({ onOpen }: { onOpen: () => void }) {
  const searchParams = useSearchParams()
  const router = useRouter()
  const pathname = usePathname()
  const wantsSearch = searchParams.get('tab') === 'search'

  useEffect(() => {
    if (!wantsSearch) return
    onOpen()
    router.replace(pathname, { scroll: false })
  }, [wantsSearch, onOpen, router, pathname])

  return null
}

type AgentOption = { id: string; name: string; is_active?: boolean }

// Radix Select can't use an empty value, so "no assistant" gets a sentinel.
const NO_AGENT = '__none__'

/**
 * Which assistant answers a number, changeable in place — including "No
 * assistant", which detaches it so the number stops answering. Saving
 * re-points the carrier; until the request settles the picker is disabled so a
 * second pick can't race the first.
 */
function AgentPicker({
  number,
  agents,
  saving,
  onChange,
}: {
  number: PhoneNumber
  agents: AgentOption[]
  saving: boolean
  onChange: (agentId: string | null) => void
}) {
  const current = number.agent_id
  const known = !current || agents.some((a) => a.id === current)
  const label = `Assistant that answers ${formatPhoneNumber(number.phone_number)}`

  if (agents.length === 0) {
    return current ? (
      <Link
        href={`/dashboard/agents/${current}`}
        className="inline-flex max-w-full items-center gap-1.5 text-sm font-medium text-[#0F6A59] hover:underline"
      >
        <Bot className="h-3.5 w-3.5 flex-shrink-0" />
        <span className="truncate">View assistant</span>
      </Link>
    ) : (
      <Link href="/dashboard/agents/new" className="text-sm font-medium text-[#0F6A59] hover:underline">
        Create an assistant
      </Link>
    )
  }

  return (
    <div className="flex min-w-0 items-center gap-1">
      <Select value={current ?? NO_AGENT} disabled={saving} onValueChange={(value) => onChange(value === NO_AGENT ? null : value)}>
        <SelectTrigger
          aria-label={label}
          title={label}
          className="h-9 min-w-0 flex-1 gap-2 rounded-lg border-slate-200 bg-white px-2.5 font-poppins text-sm font-medium text-slate-800 transition-colors hover:border-[#0F6A59]/40 focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 data-[state=open]:border-[#0F6A59] data-[state=open]:ring-2 data-[state=open]:ring-[#0F6A59]/15 disabled:cursor-wait disabled:opacity-60"
        >
          {/* A div, not a span: the trigger line-clamps its direct span children,
              which would stack the icon above the name. */}
          <div className="flex min-w-0 items-center gap-2">
            {saving ? (
              <Loader2 className="h-3.5 w-3.5 flex-shrink-0 animate-spin text-slate-400" />
            ) : (
              <Bot className={`h-3.5 w-3.5 flex-shrink-0 ${current ? 'text-[#0F6A59]' : 'text-slate-400'}`} />
            )}
            <span className={`truncate ${current ? '' : 'text-slate-500'}`}>
              {/* Name only, so the options' own icon isn't repeated here. */}
              <SelectValue>
                {current ? (known ? agents.find((a) => a.id === current)?.name : 'Unknown assistant') : 'No assistant'}
              </SelectValue>
            </span>
          </div>
        </SelectTrigger>
        <SelectContent searchable={agents.length > 6}>
          <SelectItem value={NO_AGENT} textValue="No assistant">
            <span className="flex items-center gap-2 text-slate-500">
              <Bot className="h-3.5 w-3.5 flex-shrink-0 text-slate-400" />
              No assistant
            </span>
          </SelectItem>
          {!known && current && (
            <SelectItem value={current} textValue="Unknown assistant">
              <span className="flex items-center gap-2 text-slate-500">
                <Bot className="h-3.5 w-3.5 flex-shrink-0 text-slate-400" />
                Unknown assistant
              </span>
            </SelectItem>
          )}
          {agents.map((a) => (
            <SelectItem
              key={a.id}
              value={a.id}
              textValue={a.name}
              disabled={a.is_active === false && a.id !== current}
            >
              <span className="flex items-center gap-2">
                <Bot className="h-3.5 w-3.5 flex-shrink-0 text-[#0F6A59]" />
                <span>
                  {a.name}
                  {a.is_active === false && <span className="ml-1.5 text-xs text-slate-400">(turned off)</span>}
                </span>
              </span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {current && known && (
        <Link
          href={`/dashboard/agents/${current}`}
          aria-label="Open this assistant"
          title="Open this assistant"
          className="flex h-9 w-8 flex-shrink-0 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-[#0F6A59]"
        >
          <ExternalLink className="h-3.5 w-3.5" />
        </Link>
      )}
    </div>
  )
}

/** One of the two ways to get a number, on the empty state. */
function ChoiceCard({
  icon, badge, title, description, points, cta, onClick, featured = false, disabled = false, disabledNote,
}: {
  icon: React.ReactNode
  badge?: { label: string; tone: 'brand' | 'muted' }
  title: string
  description: string
  points: string[]
  cta: string
  onClick: () => void
  featured?: boolean
  disabled?: boolean
  disabledNote?: string
}) {
  const accent = featured && !disabled
  return (
    <div
      className={`relative flex h-full flex-col rounded-2xl border bg-white p-6 transition-all ${
        disabled
          ? 'border-slate-200 opacity-70'
          : accent
            ? 'border-[#0F6A59]/30 shadow-[0_8px_30px_-12px_rgba(15,106,89,0.35)] hover:border-[#0F6A59]/60'
            : 'border-slate-200 hover:border-slate-300 hover:shadow-[0_8px_30px_-14px_rgba(15,23,42,0.2)]'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <span
          className={`flex h-11 w-11 items-center justify-center rounded-xl ${
            accent ? 'bg-[#0F6A59] text-white' : 'bg-slate-100 text-slate-600'
          }`}
        >
          {icon}
        </span>
        {badge && (
          <span
            className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${
              badge.tone === 'brand' ? 'bg-[#0F6A59]/10 text-[#0F6A59]' : 'bg-slate-100 text-slate-500'
            }`}
          >
            {badge.label}
          </span>
        )}
      </div>

      <h4 className="mt-5 text-[16px] font-semibold tracking-tight text-slate-900">{title}</h4>
      <p className="mt-1 text-[13.5px] leading-relaxed text-slate-500">{description}</p>

      <ul className="mt-5 space-y-2.5">
        {points.map((point) => (
          <li key={point} className="flex items-start gap-2.5 text-[13.5px] text-slate-700">
            <span
              className={`mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full ${
                accent ? 'bg-[#0F6A59]/10 text-[#0F6A59]' : 'bg-slate-100 text-slate-500'
              }`}
            >
              <Check className="h-2.5 w-2.5" strokeWidth={3} />
            </span>
            {point}
          </li>
        ))}
      </ul>

      <div className="mt-auto pt-6">
        {disabled && disabledNote && <p className="mb-3 text-[12px] text-slate-500">{disabledNote}</p>}
        <button
          type="button"
          onClick={onClick}
          disabled={disabled}
          className={`group inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl text-[14px] font-semibold transition-colors disabled:cursor-not-allowed ${
            accent
              ? 'bg-[#0F6A59] text-white shadow-sm hover:bg-[#0c5a4b]'
              : 'border border-slate-200 bg-white text-slate-800 hover:bg-slate-50 disabled:bg-slate-50 disabled:text-slate-400'
          }`}
        >
          {cta}
          {!disabled && <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />}
        </button>
      </div>
    </div>
  )
}

export default function PhoneNumbersPage() {
  const { confirm, ConfirmDialog } = useConfirm()
  const [numbers, setNumbers] = useState<PhoneNumber[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)
  const [agents, setAgents] = useState<AgentOption[]>([])
  // Number ids with a reassignment in flight.
  const [assigning, setAssigning] = useState<Set<string>>(new Set())
  const [options, setOptions] = useState<PurchaseOptions | null>(null)
  // The empty state depends on whether a provider is connected, so it waits
  // for the first answer rather than flashing the wrong one.
  const [optionsLoading, setOptionsLoading] = useState(true)

  // Which dialog is open. `buy` carries the flow and, for own-provider
  // purchases, the connected account to buy on.
  const [buy, setBuy] = useState<{ source: NumberSource; provider?: OwnProvider } | null>(null)
  const [ownOpen, setOwnOpen] = useState(false)
  const [importFrom, setImportFrom] = useState<OwnProvider | null>(null)
  const openVoicecon = useCallback(() => setBuy({ source: 'voicecon' }), [])

  // Whether this plan may buy numbers at all. The API refuses regardless; this
  // decides whether to show the purchase flow or the upgrade card.
  const canPurchase = useEntitlementStore((s) => s.has)(FEATURES.PHONE_NUMBER_PURCHASE)
  const entitlementsLoading = useEntitlementStore((s) => s.isLoading)

  const fetchNumbers = useCallback(async () => {
    setIsLoading(true)
    setListError(null)
    try {
      const res = await apiClient.get<PhoneNumber[]>(API_ENDPOINTS.PHONE_NUMBERS)
      setNumbers(Array.isArray(res.data) ? res.data : [])
    } catch (e) {
      setListError(friendlyPhoneError(e, 'list'))
    } finally {
      setIsLoading(false)
    }
  }, [])

  const fetchOptions = useCallback(async () => {
    try {
      setOptions(await phoneNumberService.purchaseOptions())
    } catch {
      setOptions(null) // the dialogs still work; they report their own errors
    } finally {
      setOptionsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchNumbers()
    fetchOptions()
    apiClient
      .get<{ agents: AgentOption[] }>(API_ENDPOINTS.AGENTS, { params: { limit: 1000 } })
      .then((res) => setAgents(res.data.agents || []))
      .catch(() => setAgents([]))
  }, [fetchNumbers, fetchOptions])

  const agentNames = useMemo(() => new Map(agents.map((a) => [a.id, a.name])), [agents])

  const assignAgent = async (num: PhoneNumber, agentId: string | null) => {
    if (agentId === num.agent_id) return
    const shown = formatPhoneNumber(num.phone_number)
    if (agentId === null) {
      const ok = await confirm({
        title: 'Detach assistant',
        description: `Calls to ${shown} won’t be answered until you attach an assistant again. The number stays in your workspace.`,
        confirmText: 'Detach',
        isDestructive: false,
      })
      if (!ok) return
    }
    const nextName = agentId ? agentNames.get(agentId) || 'the selected assistant' : null
    setAssigning((s) => new Set(s).add(num.id))
    try {
      const updated = await phoneNumberService.assignAgent(num.id, agentId)
      // Only this row changes; every other number keeps its own assistant.
      setNumbers((list) => list.map((n) => (n.id === num.id ? { ...n, ...updated } : n)))
      toast.success(nextName ? `Calls to ${shown} now go to ${nextName}` : `Assistant detached from ${shown}`)
    } catch (e) {
      toast.error(friendlyPhoneError(e, 'assign'))
    } finally {
      setAssigning((s) => {
        const next = new Set(s)
        next.delete(num.id)
        return next
      })
    }
  }

  const releaseNumber = async (num: PhoneNumber) => {
    const shown = formatPhoneNumber(num.phone_number)
    // A number brought from the user's own account is only disconnected; it
    // stays on their account.
    const ok = await confirm(
      num.imported
        ? {
            title: 'Remove from Voicecon',
            description: `Remove ${shown} from Voicecon? It stays on your ${appDisplayName(num.provider)} account and its previous call settings are restored. You can add it again any time.`,
            confirmText: 'Remove',
            isDestructive: true,
          }
        : {
            title: 'Release phone number',
            description: `Release ${shown}? Calls to it will stop reaching your assistant, and the number may be given to someone else. This can’t be undone.`,
            confirmText: 'Release number',
            isDestructive: true,
          }
    )
    if (!ok) return
    try {
      await apiClient.delete(API_ENDPOINTS.PHONE_NUMBER(num.id))
      toast.success(num.imported ? `${shown} removed from Voicecon` : 'Phone number released')
      fetchNumbers()
    } catch (e) {
      toast.error(friendlyPhoneError(e, 'release'))
    }
  }

  const activeCount = numbers.filter((n) => n.status === 'active').length
  const monthlyCost = numbers.reduce((s, n) => s + (n.monthly_cost || 0), 0)
  const assignedCount = numbers.filter((n) => n.agent_id).length
  const statCards = [
    { label: 'Total numbers', value: numbers.length, icon: Phone, color: 'text-[#0F6A59]', bg: 'bg-[#0F6A59]/10' },
    { label: 'Active', value: activeCount, icon: TrendingUp, color: 'text-emerald-600', bg: 'bg-emerald-50' },
    { label: 'Assigned', value: assignedCount, icon: Bot, color: 'text-violet-600', bg: 'bg-violet-50' },
    { label: 'Monthly cost', value: `$${monthlyCost.toFixed(2)}`, icon: DollarSign, color: 'text-amber-600', bg: 'bg-amber-50' },
  ]

  const voiceconDown = options?.voicecon_available === false
  const hasNumbers = numbers.length > 0
  const ownProviders = options?.own_providers ?? []
  const importFromAccount = (provider: OwnProvider) => {
    setOwnOpen(false)
    setImportFrom(provider)
  }
  const buyOnAccount = (provider: OwnProvider) => {
    setOwnOpen(false)
    setBuy({ source: 'own', provider })
  }

  return (
    <div className="space-y-6">
      <Suspense fallback={null}>
        <OpenPurchaseFromUrl onOpen={openVoicecon} />
      </Suspense>

      {/* Actions. While there are no numbers the empty state below offers both
          ways to get one, so they are not repeated here. */}
      <div className="flex flex-wrap items-center justify-end gap-2">
        {hasNumbers && (
          <>
            <button
              onClick={openVoicecon}
              disabled={voiceconDown}
              title={voiceconDown ? 'Voicecon numbers are temporarily unavailable' : undefined}
              className="inline-flex h-10 items-center gap-1.5 rounded-xl bg-[#0F6A59] px-4 text-sm font-semibold text-white shadow-sm hover:bg-[#0c5a4b] disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Plus className="h-4 w-4" /> Buy a number
            </button>
            <button
              onClick={() => setOwnOpen(true)}
              className="inline-flex h-10 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              <Plug className="h-4 w-4" /> Use your own provider
            </button>
          </>
        )}
        <button
          onClick={() => { fetchNumbers(); fetchOptions() }}
          className="inline-flex h-10 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
          aria-label="Refresh numbers"
        >
          <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          <span className="hidden sm:inline">Refresh</span>
        </button>
      </div>

      {voiceconDown && (
        <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] text-amber-900">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <p>
            Voicecon numbers are temporarily unavailable. You can still use your own provider.
          </p>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {statCards.map((card) => {
          const Icon = card.icon
          return (
            <div key={card.label} className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 card-shadow">
              <div className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl ${card.bg}`}>
                <Icon className={`h-5 w-5 ${card.color}`} />
              </div>
              <div className="min-w-0">
                <div className="text-xl font-bold text-slate-900">{card.value}</div>
                <div className="text-xs text-slate-500">{card.label}</div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Numbers */}
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white card-shadow">
        {(isLoading || optionsLoading) && numbers.length === 0 ? (
          <div className="divide-y divide-slate-100">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex animate-pulse items-center gap-4 px-6 py-4">
                <div className="h-10 w-10 flex-shrink-0 rounded-xl bg-slate-100" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 w-40 rounded bg-slate-100" />
                  <div className="h-3 w-24 rounded bg-slate-100" />
                </div>
                <div className="h-5 w-16 rounded-full bg-slate-100" />
              </div>
            ))}
          </div>
        ) : listError ? (
          <div className="flex flex-col items-center px-6 py-14 text-center">
            <AlertCircle className="h-8 w-8 text-red-400" />
            <p className="mt-3 text-[14px] font-semibold text-slate-800">{listError}</p>
            <button
              onClick={fetchNumbers}
              className="mt-4 inline-flex h-10 items-center gap-1.5 rounded-xl border border-slate-200 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              <RefreshCw className="h-4 w-4" /> Try again
            </button>
          </div>
        ) : ownProviders.length > 0 && numbers.length === 0 ? (
          // A provider is connected: offer its account instead of the two
          // ways to get started, which the user has already chosen between.
          <div className="px-5 py-10 sm:px-10 sm:py-14">
            <div className="mx-auto max-w-lg text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[#0F6A59]/10 ring-8 ring-[#0F6A59]/[0.04]">
                <Plug className="h-6 w-6 text-[#0F6A59]" />
              </div>
              <h3 className="mt-5 font-poppins text-xl font-semibold tracking-tight text-slate-900 sm:text-[22px]">
                Your provider is connected
              </h3>
              <p className="mt-1.5 text-[14px] text-slate-500">
                Use a number you already have on your account, or buy a new one on it.
              </p>
            </div>
            <div className="mx-auto mt-8 max-w-2xl">
              <ConnectedAccounts providers={ownProviders} onImportFrom={importFromAccount} onUseAccount={buyOnAccount} />
              <div className="mt-5 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-[13px]">
                <button
                  type="button"
                  onClick={() => setOwnOpen(true)}
                  className="inline-flex min-h-[44px] items-center gap-1.5 font-semibold text-[#0F6A59] hover:underline sm:min-h-0"
                >
                  <Plug className="h-3.5 w-3.5" /> Connect another provider
                </button>
                {!voiceconDown && (
                  <button
                    type="button"
                    onClick={openVoicecon}
                    className="inline-flex min-h-[44px] items-center gap-1.5 font-semibold text-slate-600 hover:underline sm:min-h-0"
                  >
                    <Phone className="h-3.5 w-3.5" /> Buy a Voicecon number instead
                  </button>
                )}
              </div>
            </div>
          </div>
        ) : numbers.length === 0 ? (
          <div className="px-5 py-10 sm:px-10 sm:py-14">
            <div className="mx-auto max-w-lg text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[#0F6A59]/10 ring-8 ring-[#0F6A59]/[0.04]">
                <Phone className="h-6 w-6 text-[#0F6A59]" />
              </div>
              <h3 className="mt-5 font-poppins text-xl font-semibold tracking-tight text-slate-900 sm:text-[22px]">
                Get a phone number
              </h3>
              <p className="mt-1.5 text-[14px] text-slate-500">
                Give your AI assistant a number so customers can call it.
              </p>
            </div>
            <div className="mx-auto mt-8 grid max-w-3xl grid-cols-1 gap-4 md:grid-cols-2">
              <ChoiceCard
                featured
                icon={<Phone className="h-5 w-5" />}
                badge={voiceconDown ? { label: 'Unavailable', tone: 'muted' } : { label: 'Recommended', tone: 'brand' }}
                title="Buy a Voicecon number"
                description="Pick a local number and start taking calls right away."
                points={['Search by country and area code', 'Assigned to your assistant instantly', 'No accounts or credentials needed']}
                cta="Find a number"
                disabled={voiceconDown}
                disabledNote="Temporarily unavailable — use your own provider for now."
                onClick={openVoicecon}
              />
              <ChoiceCard
                // The only working option while Voicecon numbers are down.
                featured={voiceconDown}
                icon={<Plug className="h-5 w-5" />}
                badge={{ label: 'Advanced', tone: 'muted' }}
                title="Use your own provider"
                description="Already have a phone provider account? Connect it here."
                points={['Keep your existing numbers', 'Billed by your provider', 'Requires your account’s API credentials']}
                cta="Connect a provider"
                onClick={() => setOwnOpen(true)}
              />
            </div>
          </div>
        ) : (
          <>
            <div className="hidden grid-cols-[minmax(0,1.6fr)_7rem_minmax(0,1fr)_6rem_7rem_3rem] gap-4 border-b border-slate-200 bg-slate-50 px-6 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500 md:grid">
              <div>Number</div>
              <div>Capabilities</div>
              <div>Answered by</div>
              <div>Status</div>
              <div>Monthly</div>
              <div className="sr-only">Actions</div>
            </div>
            <ul className="divide-y divide-slate-100">
              {numbers.map((num) => {
                return (
                  <li
                    key={num.id}
                    className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-2 px-4 py-4 transition-colors hover:bg-slate-50/70 md:grid-cols-[minmax(0,1.6fr)_7rem_minmax(0,1fr)_6rem_7rem_3rem] md:px-6"
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <div className="hidden h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-[#0F6A59]/10 sm:flex">
                        <Phone className="h-4 w-4 text-[#0F6A59]" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-[15px] font-semibold tracking-tight text-slate-900 tabular-nums">
                          {formatPhoneNumber(num.phone_number)}
                        </p>
                        <p className="mt-0.5 truncate text-xs text-slate-500">
                          {num.source === 'own'
                            ? `Your ${appDisplayName(num.provider)} account`
                            : 'Voicecon number'}
                        </p>
                        {num.status === 'suspended' && (
                          <p className="mt-1 text-xs text-amber-700">
                            Not taking calls: your workspace has no active plan.{' '}
                            {num.release_after
                              ? `It will be released on ${formatDate(num.release_after, { month: 'long' })}. `
                              : ''}
                            <Link href="/dashboard/settings/billing" className="font-medium underline">
                              Choose a plan
                            </Link>{' '}
                            to keep it.
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="order-last col-span-2 flex flex-wrap gap-1 md:order-none md:col-span-1">
                      {hasVoice(num.capabilities) && (
                        <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-600">
                          <PhoneCall className="h-3 w-3" /> Voice
                        </span>
                      )}
                      {hasSms(num.capabilities) && (
                        <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-600">
                          <MessageSquare className="h-3 w-3" /> SMS
                        </span>
                      )}
                    </div>

                    <div className="order-last col-span-2 min-w-0 md:order-none md:col-span-1">
                      <AgentPicker
                        number={num}
                        agents={agents}
                        saving={assigning.has(num.id)}
                        onChange={(agentId) => assignAgent(num, agentId)}
                      />
                    </div>

                    <div className="hidden md:block">
                      <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ring-1 ring-inset ${statusStyle[num.status] || statusStyle.inactive}`}>
                        {statusLabel(num.status)}
                      </span>
                    </div>

                    <div className="hidden text-sm text-slate-600 md:block">
                      {formatMonthly(num.monthly_cost) ?? '—'}
                    </div>

                    <div className="flex items-center justify-end gap-2">
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium capitalize ring-1 ring-inset md:hidden ${statusStyle[num.status] || statusStyle.inactive}`}>
                        {statusLabel(num.status)}
                      </span>
                      <button
                        onClick={() => releaseNumber(num)}
                        aria-label={`${num.imported ? 'Remove' : 'Release'} ${formatPhoneNumber(num.phone_number)}`}
                        title={num.imported ? 'Remove from Voicecon' : 'Release number'}
                        className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </li>
                )
              })}
            </ul>
          </>
        )}
      </div>

      <BuyNumberDialog
        open={buy !== null}
        onClose={() => setBuy(null)}
        source={buy?.source ?? 'voicecon'}
        ownProvider={buy?.provider ?? null}
        agents={agents}
        canPurchase={canPurchase}
        entitlementsLoading={entitlementsLoading}
        onPurchased={() => fetchNumbers()}
        onUpgraded={fetchOptions}
      />
      <OwnProviderDialog
        open={ownOpen}
        onClose={() => setOwnOpen(false)}
        options={options}
        onUseAccount={buyOnAccount}
        onImportFrom={importFromAccount}
      />
      <ImportNumbersDialog
        provider={importFrom}
        onClose={() => setImportFrom(null)}
        agents={agents}
        onImported={() => fetchNumbers()}
        onBuy={(provider) => {
          setImportFrom(null)
          setBuy({ source: 'own', provider })
        }}
      />
      <ConfirmDialog />
    </div>
  )
}
