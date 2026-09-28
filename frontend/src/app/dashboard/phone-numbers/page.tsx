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
  AlertCircle, ArrowRight, Bot, Check, DollarSign, MessageSquare, Phone, PhoneCall,
  Plug, Plus, RefreshCw, Trash2, TrendingUp,
} from 'lucide-react'
import { apiClient } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { FEATURES } from '@/lib/entitlements'
import { useEntitlementStore } from '@/store/entitlementStore'
import { useConfirm } from '@/hooks/use-confirm'
import { appDisplayName } from '@/lib/appNames'
import {
  type NumberSource, type OwnProvider, type PhoneNumber, type PurchaseOptions,
  formatMonthly, formatPhoneNumber, friendlyPhoneError, hasSms, hasVoice, phoneNumberService,
} from '@/lib/phoneNumbers'
import { BuyNumberDialog } from '@/components/phone-numbers/BuyNumberDialog'
import { OwnProviderDialog } from '@/components/phone-numbers/OwnProviderDialog'

const statusStyle: Record<string, string> = {
  active: 'bg-emerald-50 text-emerald-700 ring-emerald-600/15',
  inactive: 'bg-slate-100 text-slate-600 ring-slate-500/15',
  pending: 'bg-amber-50 text-amber-700 ring-amber-600/15',
}

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
  const [agents, setAgents] = useState<{ id: string; name: string }[]>([])
  const [options, setOptions] = useState<PurchaseOptions | null>(null)

  // Which dialog is open. `buy` carries the flow and, for own-provider
  // purchases, the connected account to buy on.
  const [buy, setBuy] = useState<{ source: NumberSource; provider?: OwnProvider } | null>(null)
  const [ownOpen, setOwnOpen] = useState(false)
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
    }
  }, [])

  useEffect(() => {
    fetchNumbers()
    fetchOptions()
    apiClient
      .get<{ agents: { id: string; name: string }[] }>(API_ENDPOINTS.AGENTS)
      .then((res) => setAgents(res.data.agents || []))
      .catch(() => setAgents([]))
  }, [fetchNumbers, fetchOptions])

  const agentNames = useMemo(() => new Map(agents.map((a) => [a.id, a.name])), [agents])

  const releaseNumber = async (num: PhoneNumber) => {
    const ok = await confirm({
      title: 'Release phone number',
      description: `Release ${formatPhoneNumber(num.phone_number)}? Calls to it will stop reaching your assistant, and the number may be given to someone else. This can’t be undone.`,
      confirmText: 'Release number',
      isDestructive: true,
    })
    if (!ok) return
    try {
      await apiClient.delete(API_ENDPOINTS.PHONE_NUMBER(num.id))
      toast.success('Phone number released')
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
        {isLoading && numbers.length === 0 ? (
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
                const agentName = num.agent_id ? agentNames.get(num.agent_id) : null
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
                      {num.agent_id ? (
                        <Link
                          href={`/dashboard/agents/${num.agent_id}`}
                          className="inline-flex max-w-full items-center gap-1.5 text-sm font-medium text-[#0F6A59] hover:underline"
                        >
                          <Bot className="h-3.5 w-3.5 flex-shrink-0" />
                          <span className="truncate">{agentName || 'View assistant'}</span>
                        </Link>
                      ) : (
                        <span className="text-sm text-slate-400">No assistant</span>
                      )}
                    </div>

                    <div className="hidden md:block">
                      <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ring-1 ring-inset ${statusStyle[num.status] || statusStyle.inactive}`}>
                        {num.status}
                      </span>
                    </div>

                    <div className="hidden text-sm text-slate-600 md:block">
                      {formatMonthly(num.monthly_cost) ?? '—'}
                    </div>

                    <div className="flex items-center justify-end gap-2">
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium capitalize ring-1 ring-inset md:hidden ${statusStyle[num.status] || statusStyle.inactive}`}>
                        {num.status}
                      </span>
                      <button
                        onClick={() => releaseNumber(num)}
                        aria-label={`Release ${formatPhoneNumber(num.phone_number)}`}
                        title="Release number"
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
        onUseAccount={(provider) => {
          setOwnOpen(false)
          setBuy({ source: 'own', provider })
        }}
      />
      <ConfirmDialog />
    </div>
  )
}
