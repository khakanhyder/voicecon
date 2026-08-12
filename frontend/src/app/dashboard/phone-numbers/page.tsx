'use client'

import { useState, useEffect } from 'react'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'
import {
  Phone, Plus, Search, DollarSign, TrendingUp,
  CheckCircle, Bot, Loader2, RefreshCw,
  ChevronDown, X, Plug, ChevronUp
} from 'lucide-react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { FEATURES } from '@/lib/entitlements'
import { useEntitlementStore } from '@/store/entitlementStore'
import { PhoneNumberPaywall } from '@/components/billing/PhoneNumberPaywall'

interface PhoneNumber {
  id: string
  phone_number: string
  country_code: string | null
  area_code: string | null
  provider: string
  agent_id: string | null
  capabilities: Record<string, boolean>
  status: string
  monthly_cost: number | null
  created_at: string
}

interface AvailableNumber {
  phone_number: string
  friendly_name: string
  provider: string
  locality: string | null
  region: string | null
  capabilities: Record<string, boolean>
  monthly_cost: number | null
  setup_cost: number | null
  currency: string | null
}

/**
 * A carrier account the user can buy numbers from — either Voicecon's own
 * Twilio ('platform') or a carrier they connected under Integrations.
 */
interface TelephonyProvider {
  slug: string
  name: string
  source: 'integration' | 'platform'
  connection_id: string | null
  connection_name: string | null
  is_default?: boolean
}

/** Keyed by account, so the same carrier can appear as platform *and* own. */
const providerKey = (p: TelephonyProvider) => p.connection_id ?? p.slug

/** Which account the number is billed to — the thing users actually pick on. */
const providerAccountLabel = (p: TelephonyProvider) =>
  p.source === 'platform'
    ? 'Voicecon shared account'
    : p.connection_name || 'Your connected account'

const statusStyle: Record<string, string> = {
  active: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  inactive: 'bg-slate-50 text-slate-600 border-slate-200',
  pending: 'bg-amber-50 text-amber-700 border-amber-200',
}

function CapBadge({ label, active }: { label: string; active: boolean }) {
  return (
    <span className={`px-1.5 py-0.5 rounded-[4px] text-[10px] font-bold uppercase tracking-wide ${active ? 'bg-[#ECF3F2] text-[#106959]' : 'bg-slate-50 text-slate-400 line-through'
      }`}>
      {label}
    </span>
  )
}

export default function PhoneNumbersPage() {
  const [numbers, setNumbers] = useState<PhoneNumber[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)

  // Search state
  const [countryCode, setCountryCode] = useState('US')
  const [areaCode, setAreaCode] = useState('')
  const [contains, setContains] = useState('')
  const [searchResults, setSearchResults] = useState<AvailableNumber[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [isPurchasing, setIsPurchasing] = useState<string | null>(null)

  // Whether this plan may buy numbers at all. The backend refuses the purchase
  // regardless; this only decides whether we show someone a flow that would.
  const canPurchase = useEntitlementStore((s) => s.has)(FEATURES.PHONE_NUMBER_PURCHASE)
  const entitlementsLoading = useEntitlementStore((s) => s.isLoading)

  // Agent selector state for provisioning
  const [agents, setAgents] = useState<{ id: string; name: string }[]>([])
  const [selectedAgent, setSelectedAgent] = useState('')
  const [purchaseTarget, setPurchaseTarget] = useState<AvailableNumber | null>(null)

  // Connected carriers the user can buy from
  const [providers, setProviders] = useState<TelephonyProvider[]>([])
  const [selectedProvider, setSelectedProvider] = useState('')
  const [providersLoading, setProvidersLoading] = useState(true)

  useEffect(() => {
    fetchNumbers()
    fetchAgents()
    fetchProviders()
  }, [])

  const fetchNumbers = async () => {
    setIsLoading(true)
    try {
      const res = await apiClient.get<PhoneNumber[]>(API_ENDPOINTS.PHONE_NUMBERS)
      setNumbers(Array.isArray(res.data) ? res.data : [])
    } catch (e) {
      toast.error(getErrorMessage(e))
    } finally {
      setIsLoading(false)
    }
  }

  const fetchAgents = async () => {
    try {
      const res = await apiClient.get<{ agents: { id: string; name: string }[] }>(API_ENDPOINTS.AGENTS)
      setAgents(res.data.agents || [])
    } catch { }
  }

  const fetchProviders = async () => {
    setProvidersLoading(true)
    try {
      const res = await apiClient.get<TelephonyProvider[]>(API_ENDPOINTS.PHONE_NUMBERS_PROVIDERS)
      const list = Array.isArray(res.data) ? res.data : []
      setProviders(list)
      // Keep the current pick if it survived a refresh, else fall back to the
      // account the API marks as default (Twilio, own connection before shared).
      const fallback = list.find(p => p.is_default) ?? list[0]
      setSelectedProvider(prev =>
        list.some(p => providerKey(p) === prev) ? prev : (fallback ? providerKey(fallback) : '')
      )
    } catch (e) {
      setProviders([])
    } finally {
      setProvidersLoading(false)
    }
  }

  const activeProvider = providers.find(p => providerKey(p) === selectedProvider) || null

  const searchNumbers = async () => {
    if (!activeProvider) {
      toast.error('Connect a phone provider before searching for numbers')
      return
    }
    setIsSearching(true)
    setSearchResults([])
    try {
      const params = new URLSearchParams({ country_code: countryCode, limit: '10' })
      if (areaCode) params.set('area_code', areaCode)
      if (contains) params.set('contains', contains)
      params.set('provider', activeProvider.slug)
      if (activeProvider.connection_id) params.set('connection_id', activeProvider.connection_id)
      const res = await apiClient.get<AvailableNumber[]>(
        `${API_ENDPOINTS.PHONE_NUMBERS_SEARCH}?${params}`
      )
      setSearchResults(Array.isArray(res.data) ? res.data : [])
      if (!res.data?.length) toast.info('No numbers found for that search. Try different criteria.')
    } catch (e) {
      toast.error(getErrorMessage(e))
    } finally {
      setIsSearching(false)
    }
  }

  const purchaseNumber = async (num: AvailableNumber) => {
    if (!selectedAgent) { toast.error('Please select an agent to assign this number to'); return }
    if (!activeProvider) { toast.error('Connect a phone provider before purchasing'); return }
    setIsPurchasing(num.phone_number)
    try {
      await apiClient.post(API_ENDPOINTS.PHONE_NUMBERS_PROVISION, {
        phone_number: num.phone_number,
        agent_id: selectedAgent,
        provider: num.provider || activeProvider.slug,
        connection_id: activeProvider.connection_id,
        country_code: countryCode,
        area_code: areaCode || null,
        monthly_cost: num.monthly_cost,
      })
      toast.success(`${num.phone_number} provisioned successfully`)
      setPurchaseTarget(null)
      setSelectedAgent('')
      fetchNumbers()
      setIsCreateModalOpen(false) // Close modal on success
    } catch (e) {
      toast.error(getErrorMessage(e))
    } finally {
      setIsPurchasing(null)
    }
  }

  const releaseNumber = async (id: string) => {
    if (!confirm('Release this phone number? This cannot be undone.')) return
    try {
      await apiClient.delete(API_ENDPOINTS.PHONE_NUMBER(id))
      toast.success('Phone number released')
      fetchNumbers()
    } catch (e) {
      toast.error(getErrorMessage(e))
    }
  }

  const activeCount = numbers.filter(n => n.status === 'active').length
  const monthlyCost = numbers.reduce((s, n) => s + (n.monthly_cost || 0), 0)
  const assignedCount = numbers.filter(n => n.agent_id).length

  const statCards = [
    { label: 'Total Numbers', value: numbers.length, icon: Phone, color: 'text-blue-600', bg: 'bg-blue-50' },
    { label: 'Active', value: activeCount, icon: TrendingUp, color: 'text-emerald-600', bg: 'bg-emerald-50' },
    { label: 'Assigned', value: assignedCount, icon: Bot, color: 'text-violet-600', bg: 'bg-violet-50' },
    { label: 'Monthly Cost', value: `$${monthlyCost.toFixed(2)}`, icon: DollarSign, color: 'text-amber-600', bg: 'bg-amber-50' },
  ]

  return (
    <div className="space-y-6 relative">
      {/* Search & Purchase Phone Number Modal */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-4xl flex flex-col rounded-[16px] bg-[#ECF3F2] border border-[#2E2E2E] shadow-xl overflow-hidden relative max-h-[90vh]">
            <div className="flex items-center justify-between p-5 pb-3">
              <h2 className="text-[18px] font-bold text-[#000000] tracking-tight">Purchase Phone Number</h2>
              <button onClick={() => setIsCreateModalOpen(false)} className="text-[#3c7849] hover:bg-[#106959]/10 p-1 rounded-sm transition-colors mt-[-5px]">
                <X className="h-6 w-6" strokeWidth={2} />
              </button>
            </div>

            <div className="px-5 pb-6 overflow-y-auto w-full">
              {/* A plan without the purchase feature never sees the search UI.
                  Letting someone pick a number and only then telling them they
                  cannot have it wastes their time and reads as a bug. */}
              {!entitlementsLoading && !canPurchase ? (
                <PhoneNumberPaywall onUpgraded={fetchProviders} />
              ) : (
              <>
              {providersLoading && (
                <div className="flex flex-col items-center justify-center py-16 bg-white rounded-[6px] border border-gray-300">
                  <Loader2 className="h-8 w-8 text-blue-500 animate-spin mb-3" />
                  <p className="text-sm text-slate-500">Checking your connected phone providers…</p>
                </div>
              )}

              {!providersLoading && providers.length === 0 && (
                <div className="flex flex-col items-center justify-center py-16 px-8 text-center bg-white rounded-[6px] border border-gray-300 shadow-sm">
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-50 mb-5">
                    <Plug className="h-8 w-8 text-amber-500" />
                  </div>
                  <h3 className="text-lg font-semibold text-slate-800">No phone provider available</h3>
                  <p className="text-slate-500 text-sm mt-1.5 max-w-sm">
                    Voicecon&apos;s shared Twilio account isn&apos;t configured on this server, so
                    numbers have to be bought on your own carrier account. Connect Twilio or
                    Telnyx under Integrations, then come back here to buy a number.
                  </p>
                  <Link
                    href="/dashboard/integrations"
                    className="mt-6 flex items-center gap-2 rounded-[6px] !bg-[#106959] hover:!bg-[#0c5044] px-5 py-2.5 text-sm font-semibold text-white transition-all"
                  >
                    <Plug className="h-4 w-4" />
                    Connect a provider
                  </Link>
                </div>
              )}

              {!providersLoading && providers.length > 0 && (
                <div className="space-y-6 pt-2">
                  {/* Provider picker */}
                  <div className="text-[13px]">
                    <div className="flex items-start justify-between gap-4 flex-wrap">
                      <div>
                        <h3 className="text-[14px] font-bold text-[#000000]">Phone Provider</h3>
                        <p className="text-xs text-slate-500 mt-0.5">
                          {providers.length > 1
                            ? 'Choose which account to buy this number on — it is billed there'
                            : `Buying on ${providers[0].name} · ${providerAccountLabel(providers[0])}`}
                        </p>
                      </div>
                      {/* <Link
                        href="/dashboard/integrations"
                        className="text-xs font-medium text-[#106959] hover:underline"
                      >
                        Manage providers
                      </Link> */}

                      <div className="mt-3 flex flex-wrap gap-2">
                        {providers.map(p => {
                          const key = providerKey(p)
                          const isSelected = key === selectedProvider
                          return (
                            <button
                              key={key}
                              onClick={() => { setSelectedProvider(key); setSearchResults([]); setPurchaseTarget(null) }}
                              className={`flex items-center gap-2.5 rounded-[6px] border px-4 py-2 font-medium transition-all text-left ${isSelected
                                ? 'border-[#106959] bg-[#106959]/10 text-[#106959]'
                                : 'border-[#2E2E2E] bg-white text-black hover:border-black'
                                }`}
                            >
                              <Plug className={`h-4 w-4 flex-shrink-0 ${isSelected ? 'text-[#106959]' : 'text-slate-500'}`} />
                              <span className="flex flex-col leading-tight">
                                <span className="flex items-center gap-1.5">
                                  {p.name}
                                  {p.source === 'platform' && (
                                    <span className="rounded bg-[#ECF3F2] border border-[#2e2e2e]/20 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-700">
                                      Included
                                    </span>
                                  )}
                                </span>
                                <span className={`text-[11px] font-normal ${isSelected ? 'text-[#106959]/80' : 'text-slate-500'}`}>
                                  {providerAccountLabel(p)}
                                </span>
                              </span>
                              {isSelected && <CheckCircle className="h-3.5 w-3.5 flex-shrink-0 text-[#106959]" />}
                            </button>
                          )
                        })}
                      </div>
                    </div>

                    {/*  */}
                  </div>

                  {/* Search form */}
                  <div>
                    <h3 className="text-[14px] font-bold text-[#000000] mb-3">
                      Search Available Numbers
                      {activeProvider && (
                        <span className="ml-2 font-normal text-slate-500">
                          on {activeProvider.name} · {providerAccountLabel(activeProvider)}
                        </span>
                      )}
                    </h3>
                    <div className="space-y-4">
                      <div className="flex flex-col md:flex-row gap-4">
                        <div className="flex-1 space-y-1.5">
                          <label className="text-[14px] font-bold text-[#000000]">Country</label>
                          <div className="relative">
                            <select
                              value={countryCode}
                              onChange={e => setCountryCode(e.target.value)}
                              className="w-full appearance-none h-[45px] rounded-[6px] border border-[#2E2E2E] bg-white pl-3 pr-8 py-2 text-[13px] font-medium text-black outline-none focus:border-[#106959] transition-all"
                            >
                              <option value="US">United States</option>
                              <option value="GB">United Kingdom</option>
                              <option value="CA">Canada</option>
                              <option value="AU">Australia</option>
                              <option value="DE">Germany</option>
                              <option value="FR">France</option>
                            </select>
                            <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500 pointer-events-none" />
                          </div>
                        </div>
                        <div className="flex-1 space-y-1.5">
                          <label className="text-[14px] font-bold text-[#000000]">Area Code</label>
                          <input
                            type="text"
                            value={areaCode}
                            onChange={e => setAreaCode(e.target.value)}
                            placeholder="e.g. 415"
                            className="w-full h-[45px] rounded-[6px] border border-[#2E2E2E] bg-white px-3 py-2 text-[13px] font-medium text-black placeholder:text-gray-400 outline-none focus:border-[#106959] transition-all"
                          />
                        </div>
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[14px] font-bold text-[#000000]">Contains</label>
                        <input
                          type="text"
                          value={contains}
                          onChange={e => setContains(e.target.value)}
                          placeholder="e.g. 555"
                          className="w-full h-[45px] rounded-[6px] border border-[#2E2E2E] bg-white px-3 py-2 text-[13px] font-medium text-black placeholder:text-gray-400 outline-none focus:border-[#106959] transition-all"
                        />
                      </div>
                      <div className="flex items-center gap-4 pt-2">
                        <button
                          onClick={() => setIsCreateModalOpen(false)}
                          className="flex-1 h-[45px] flex items-center justify-center gap-2 rounded-[6px] border border-[#2e2e2e] bg-[#b5b5b5] hover:bg-[#a0a0a0] text-[14px] font-bold text-black transition-all"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={searchNumbers}
                          disabled={isSearching}
                          className="flex-1 h-[45px] flex items-center justify-center gap-2 rounded-[6px] !bg-[#106959] hover:!bg-[#0c5044] text-[14px] font-bold text-white transition-all disabled:opacity-60"
                        >
                          {isSearching ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                          Search
                        </button>
                      </div>
                    </div>
                  </div>                  {/* Results & Loading States Wrapper - Fixed Height to prevent jumping */}
                  <div className="h-[300px] mt-4 w-full">
                    {/* Results */}
                    {searchResults.length > 0 && (
                      <div className="h-full flex flex-col bg-white rounded-[6px] border border-[#2E2E2E] overflow-hidden text-[13px]">
                        <div className="px-5 py-3 border-b border-gray-200 bg-[#f8faf9] flex-shrink-0">
                          <p className="font-bold text-[#000000]">
                            {searchResults.length} numbers available
                            {activeProvider && (
                              <span className="ml-1.5 font-normal text-slate-500">from {activeProvider.name}</span>
                            )}
                          </p>
                        </div>
                        <div className="flex-1 divide-y divide-gray-200 overflow-y-auto custom-scrollbar">
                          {searchResults.map(num => (
                            <div key={num.phone_number} className="flex flex-col sm:flex-row sm:items-center gap-4 px-5 py-3 hover:bg-gray-50 transition-colors">
                              <div className="flex items-center gap-4 flex-1">
                                <div className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-[8px] bg-[#ECF3F2]">
                                  <Phone className="h-5 w-5 text-[#106959]" />
                                </div>
                                <div className="flex-1 min-w-0">
                                  <p className="font-bold text-black font-mono">{num.phone_number}</p>
                                  <p className="text-[12px] text-slate-500 mt-0.5">
                                    {[num.locality, num.region].filter(Boolean).join(', ') || 'Unknown region'}
                                    {num.monthly_cost != null && (
                                      <span className="ml-1.5 text-slate-500">
                                        · {num.currency === 'USD' || !num.currency ? '$' : ''}
                                        {num.monthly_cost.toFixed(2)}/mo
                                      </span>
                                    )}
                                  </p>
                                </div>
                                <div className="hidden md:flex items-center gap-1.5">
                                  {num.capabilities?.voice && <CapBadge label="Voice" active />}
                                  {(num.capabilities?.SMS || num.capabilities?.sms) && <CapBadge label="SMS" active />}
                                </div>
                              </div>

                              {purchaseTarget?.phone_number === num.phone_number ? (
                                <div className="flex items-center gap-2 w-full sm:w-auto">
                                  <div className="relative flex-1 sm:flex-none">
                                    <select
                                      value={selectedAgent}
                                      onChange={e => setSelectedAgent(e.target.value)}
                                      className="w-full appearance-none rounded-[6px] border border-[#2E2E2E] bg-white pl-3 pr-8 py-2 text-[13px] text-black outline-none font-bold h-[36px]"
                                    >
                                      <option value="">Select agent…</option>
                                      {agents.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
                                    </select>
                                    <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-black pointer-events-none" />
                                  </div>
                                  <button
                                    onClick={() => purchaseNumber(num)}
                                    disabled={isPurchasing === num.phone_number}
                                    className="h-[36px] flex items-center justify-center gap-1.5 rounded-[6px] !bg-[#106959] hover:!bg-[#0c5044] px-3 font-bold text-white transition-all disabled:opacity-60 text-[13px]"
                                  >
                                    {isPurchasing === num.phone_number ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle className="h-3.5 w-3.5" />}
                                    Confirm
                                  </button>
                                  <button
                                    onClick={() => { setPurchaseTarget(null); setSelectedAgent('') }}
                                    className="h-[36px] items-center justify-center rounded-[6px] border border-[#2E2E2E] px-3 font-bold text-black hover:bg-gray-100 transition-colors text-[13px] hidden sm:flex"
                                  >
                                    Cancel
                                  </button>
                                </div>
                              ) : (
                                <button
                                  onClick={() => setPurchaseTarget(num)}
                                  className="flex items-center justify-center gap-1.5 rounded-[6px] border border-[#106959] bg-[#106959] px-4 py-2 font-bold text-white hover:bg-[#0c5044] hover:text-white transition-colors h-[36px] w-full sm:w-auto shadow-sm"
                                >
                                  <Plus className="h-4 w-4" />
                                  Purchase
                                </button>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {searchResults.length === 0 && !isSearching && (
                      <div className="h-full flex flex-col items-center justify-center text-center bg-white rounded-[6px] border border-[#2E2E2E]">
                        <Search className="h-10 w-10 text-slate-300 mb-3" />
                        <p className="text-[14px] font-medium text-slate-500">Search to see available phone numbers</p>
                        <p className="text-[12px] text-slate-400 mt-1">Filter by country, area code, or pattern</p>
                      </div>
                    )}

                    {isSearching && (
                      <div className="h-full flex flex-col items-center justify-center bg-white rounded-[6px] border border-[#2E2E2E]">
                        <Loader2 className="h-8 w-8 text-[#106959] animate-spin mb-3" />
                        <p className="text-[14px] font-medium text-[#106959]">Searching available numbers…</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
              </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Header operations */}
      <div className="flex items-center justify-end -mb-2 gap-3">
        <button
          onClick={() => setIsCreateModalOpen(true)}
          className="flex items-center gap-1.5 rounded-[8px] bg-[#106959] hover:bg-[#0c5044] px-4 py-2 text-sm font-semibold text-white transition-all shadow-sm"
        >
          <Plus className="h-4 w-4" />
          Purchase Number
        </button>
        <button
          onClick={fetchNumbers}
          className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors"
          title="Refresh Numbers"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {statCards.map(card => {
          const Icon = card.icon
          return (
            <div key={card.label} className="flex items-center justify-between bg-white rounded-xl border border-slate-200 p-4 card-shadow">
              <div className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg ${card.bg}`}>
                <Icon className={`h-5 w-5 ${card.color}`} />
              </div>
              <div>
                <div className="text-xl font-bold text-slate-900">{card.value}</div>
                <div className="text-xs text-slate-500 mt-0.5">{card.label}</div>
              </div>
            </div>
          )
        })}
      </div>

      {/* MY NUMBERS TABLE */}
      <div className="bg-white rounded-xl border border-slate-200 card-shadow overflow-hidden">
        {isLoading ? (
          <div className="space-y-0 divide-y divide-slate-100">
            {[1, 2, 3].map(i => (
              <div key={i} className="flex items-center gap-4 px-6 py-4 animate-pulse">
                <div className="h-10 w-10 bg-slate-100 rounded-lg flex-shrink-0" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 w-36 bg-slate-100 rounded" />
                  <div className="h-3 w-24 bg-slate-100 rounded" />
                </div>
                <div className="h-5 w-16 bg-slate-100 rounded-full" />
              </div>
            ))}
          </div>
        ) : numbers.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 px-8 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[#0F6A590A] border border-slate-200 p-3 shadow-sm mb-5">
              <Phone className="h-8 w-8 text-[#106959]" />
            </div>
            <h3 className="text-[20px] font-bold text-[#000000] mb-2">No phone numbers yet</h3>
            <p className="text-[14px] text-black/60 mt-1.5 max-w-sm">
              Purchase or link a phone number to start receiving inbound calls with your AI agents.
            </p>
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="mt-6 flex items-center gap-2 rounded-[8px] bg-[#106959] px-6 py-2.5 text-[14px] font-semibold text-white hover:opacity-90 transition-all shadow-sm"
            >
              <Plus className="h-4 w-4" />
              Create your first number
            </button>
          </div>
        ) : (
          <>
            <div className="hidden md:grid grid-cols-[2.5rem_1fr_8rem_9rem_6rem_7rem_5rem] gap-4 px-6 py-3 bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wide">
              <div />
              <div>Number</div>
              <div>Capabilities</div>
              <div>Agent</div>
              <div>Status</div>
              <div>Monthly Cost</div>
              <div>Actions</div>
            </div>
            <div className="divide-y divide-slate-100">
              {numbers.map(num => (
                <div key={num.id} className="flex flex-col md:grid md:grid-cols-[2.5rem_1fr_8rem_9rem_6rem_7rem_5rem] gap-2 md:gap-4 px-4 md:px-6 py-4 hover:bg-slate-50 transition-colors">
                  <div className="hidden md:flex items-center">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50">
                      <Phone className="h-4 w-4 text-blue-600" />
                    </div>
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-900 font-mono">{num.phone_number}</p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {num.country_code || 'US'}{num.area_code ? ` · ${num.area_code}` : ''} · {num.provider}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 flex-wrap">
                    <CapBadge label="Voice" active={num.capabilities?.voice ?? true} />
                    <CapBadge label="SMS" active={num.capabilities?.SMS ?? num.capabilities?.sms ?? false} />
                  </div>
                  <div className="flex items-center">
                    {num.agent_id ? (
                      <Link href={`/dashboard/agents/${num.agent_id}`} className="flex items-center gap-1.5 text-sm text-blue-600 hover:underline">
                        <Bot className="h-3.5 w-3.5" />
                        <span className="truncate max-w-[6rem]">View agent</span>
                      </Link>
                    ) : (
                      <span className="text-sm text-slate-400 italic">Unassigned</span>
                    )}
                  </div>
                  <div className="flex items-center">
                    <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium ${statusStyle[num.status] || statusStyle.inactive}`}>
                      {num.status}
                    </span>
                  </div>
                  <div className="hidden md:flex items-center text-sm text-slate-600">
                    {num.monthly_cost ? `$${num.monthly_cost.toFixed(2)}/mo` : '—'}
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => releaseNumber(num.id)}
                      title="Release number"
                      className="flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 hover:bg-red-50 hover:text-red-600 transition-colors"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
