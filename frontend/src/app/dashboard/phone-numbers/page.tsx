'use client'

import { useState, useEffect } from 'react'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'
import {
  Phone, Plus, Search, DollarSign, TrendingUp,
  CheckCircle, Bot, Loader2, RefreshCw,
  ChevronDown, X, Plug,
} from 'lucide-react'
import Link from 'next/link'

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

/** A carrier the user has connected and can buy numbers from. */
interface TelephonyProvider {
  slug: string
  name: string
  source: 'integration' | 'platform'
  connection_id: string | null
  connection_name: string | null
}

/** Providers are keyed by connection so the same carrier can be connected twice. */
const providerKey = (p: TelephonyProvider) => p.connection_id ?? p.slug

const statusStyle: Record<string, string> = {
  active:   'bg-emerald-50 text-emerald-700 border-emerald-200',
  inactive: 'bg-slate-50 text-slate-600 border-slate-200',
  pending:  'bg-amber-50 text-amber-700 border-amber-200',
}

function CapBadge({ label, active }: { label: string; active: boolean }) {
  return (
    <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
      active ? 'bg-blue-50 text-blue-700' : 'bg-slate-50 text-slate-400 line-through'
    }`}>
      {label}
    </span>
  )
}

export default function PhoneNumbersPage() {
  const [activeTab, setActiveTab] = useState<'numbers' | 'search'>('numbers')
  const [numbers, setNumbers] = useState<PhoneNumber[]>([])
  const [isLoading, setIsLoading] = useState(true)

  // Search state
  const [countryCode, setCountryCode] = useState('US')
  const [areaCode, setAreaCode] = useState('')
  const [contains, setContains] = useState('')
  const [searchResults, setSearchResults] = useState<AvailableNumber[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [isPurchasing, setIsPurchasing] = useState<string | null>(null)

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
    } catch {}
  }

  const fetchProviders = async () => {
    setProvidersLoading(true)
    try {
      const res = await apiClient.get<TelephonyProvider[]>(API_ENDPOINTS.PHONE_NUMBERS_PROVIDERS)
      const list = Array.isArray(res.data) ? res.data : []
      setProviders(list)
      // Keep the current pick if it survived a refresh, else default to the first.
      setSelectedProvider(prev =>
        list.some(p => providerKey(p) === prev) ? prev : (list[0] ? providerKey(list[0]) : '')
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
      setActiveTab('numbers')
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

  const activeCount  = numbers.filter(n => n.status === 'active').length
  const monthlyCost  = numbers.reduce((s, n) => s + (n.monthly_cost || 0), 0)
  const assignedCount = numbers.filter(n => n.agent_id).length

  const statCards = [
    { label: 'Total Numbers', value: numbers.length, icon: Phone,       color: 'text-blue-600', bg: 'bg-blue-50' },
    { label: 'Active',        value: activeCount,    icon: TrendingUp,  color: 'text-emerald-600', bg: 'bg-emerald-50' },
    { label: 'Assigned',      value: assignedCount,  icon: Bot,         color: 'text-violet-600', bg: 'bg-violet-50' },
    { label: 'Monthly Cost',  value: `$${monthlyCost.toFixed(2)}`, icon: DollarSign, color: 'text-amber-600', bg: 'bg-amber-50' },
  ]

  const tabs = [
    { id: 'numbers' as const, label: 'My Numbers', icon: Phone },
    { id: 'search'  as const, label: 'Search & Purchase', icon: Search },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Phone Numbers</h1>
          <p className="text-sm text-slate-500 mt-0.5">Manage voice-enabled phone numbers for your agents</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchNumbers}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={() => setActiveTab('search')}
            className="flex items-center gap-2 rounded-xl gradient-primary px-4 py-2 text-sm font-semibold text-white hover:opacity-90 transition-all shadow-sm"
          >
            <Plus className="h-4 w-4" />
            Purchase Number
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {statCards.map(card => {
          const Icon = card.icon
          return (
            <div key={card.label} className="bg-white rounded-xl border border-slate-200 p-4 card-shadow">
              <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${card.bg} mb-3`}>
                <Icon className={`h-4 w-4 ${card.color}`} />
              </div>
              <div className="text-xl font-bold text-slate-900">{card.value}</div>
              <div className="text-xs text-slate-500 mt-0.5">{card.label}</div>
            </div>
          )
        })}
      </div>

      {/* Tab bar */}
      <div className="flex gap-0 border-b border-slate-200">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-2 px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === id
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {/* MY NUMBERS tab */}
      {activeTab === 'numbers' && (
        <div className="bg-white rounded-xl border border-slate-200 card-shadow overflow-hidden">
          {isLoading ? (
            <div className="space-y-0 divide-y divide-slate-100">
              {[1,2,3].map(i => (
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
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-100 mb-5">
                <Phone className="h-8 w-8 text-slate-300" />
              </div>
              <h3 className="text-lg font-semibold text-slate-800">No phone numbers yet</h3>
              <p className="text-slate-500 text-sm mt-1.5 max-w-xs">
                Purchase a phone number to start receiving inbound calls with your AI agents.
              </p>
              <button
                onClick={() => setActiveTab('search')}
                className="mt-6 flex items-center gap-2 rounded-xl gradient-primary px-5 py-2.5 text-sm font-semibold text-white hover:opacity-90 transition-all"
              >
                <Plus className="h-4 w-4" />
                Purchase your first number
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
      )}

      {/* SEARCH & PURCHASE tab */}
      {activeTab === 'search' && providersLoading && (
        <div className="flex flex-col items-center justify-center py-16 bg-white rounded-xl border border-slate-200">
          <Loader2 className="h-8 w-8 text-blue-500 animate-spin mb-3" />
          <p className="text-sm text-slate-500">Checking your connected phone providers…</p>
        </div>
      )}

      {/* No carrier connected — nothing can be purchased until one is */}
      {activeTab === 'search' && !providersLoading && providers.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 px-8 text-center bg-white rounded-xl border border-slate-200 card-shadow">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-50 mb-5">
            <Plug className="h-8 w-8 text-amber-500" />
          </div>
          <h3 className="text-lg font-semibold text-slate-800">No phone provider connected</h3>
          <p className="text-slate-500 text-sm mt-1.5 max-w-sm">
            Numbers are purchased on your own carrier account. Connect Twilio or Telnyx
            under Integrations, then come back here to buy a number.
          </p>
          <Link
            href="/dashboard/integrations"
            className="mt-6 flex items-center gap-2 rounded-xl gradient-primary px-5 py-2.5 text-sm font-semibold text-white hover:opacity-90 transition-all"
          >
            <Plug className="h-4 w-4" />
            Connect a provider
          </Link>
        </div>
      )}

      {activeTab === 'search' && !providersLoading && providers.length > 0 && (
        <div className="space-y-5">
          {/* Provider picker — only carriers the user has connected */}
          <div className="bg-white rounded-xl border border-slate-200 card-shadow p-5">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div>
                <h3 className="text-sm font-semibold text-slate-800">Phone Provider</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  {providers.length > 1
                    ? 'Choose which connected carrier to buy this number from'
                    : `Buying on your connected ${providers[0].name} account`}
                </p>
              </div>
              <Link
                href="/dashboard/integrations"
                className="text-xs font-medium text-blue-600 hover:underline"
              >
                Manage providers
              </Link>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              {providers.map(p => {
                const key = providerKey(p)
                const isSelected = key === selectedProvider
                return (
                  <button
                    key={key}
                    onClick={() => { setSelectedProvider(key); setSearchResults([]); setPurchaseTarget(null) }}
                    className={`flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium transition-all ${
                      isSelected
                        ? 'border-blue-500 bg-blue-50 text-blue-700 ring-2 ring-indigo-500/20'
                        : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50'
                    }`}
                  >
                    <Plug className={`h-4 w-4 ${isSelected ? 'text-blue-600' : 'text-slate-400'}`} />
                    <span>{p.name}</span>
                    {p.source === 'platform' && (
                      <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                        Platform
                      </span>
                    )}
                    {isSelected && <CheckCircle className="h-3.5 w-3.5 text-blue-600" />}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Search form */}
          <div className="bg-white rounded-xl border border-slate-200 card-shadow p-5">
            <h3 className="text-sm font-semibold text-slate-800 mb-4">
              Search Available Numbers
              {activeProvider && (
                <span className="ml-2 font-normal text-slate-400">on {activeProvider.name}</span>
              )}
            </h3>
            <div className="grid gap-3 sm:grid-cols-4">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Country</label>
                <div className="relative">
                  <select
                    value={countryCode}
                    onChange={e => setCountryCode(e.target.value)}
                    className="w-full appearance-none rounded-lg border border-slate-300 bg-white pl-3 pr-8 py-2 text-sm text-slate-700 outline-none focus:border-blue-500 focus:ring-2 focus:ring-indigo-500/20 transition-all"
                  >
                    <option value="US">United States</option>
                    <option value="GB">United Kingdom</option>
                    <option value="CA">Canada</option>
                    <option value="AU">Australia</option>
                    <option value="DE">Germany</option>
                    <option value="FR">France</option>
                  </select>
                  <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Area Code</label>
                <input
                  type="text"
                  value={areaCode}
                  onChange={e => setAreaCode(e.target.value)}
                  placeholder="e.g. 415"
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 placeholder:text-slate-400 outline-none focus:border-blue-500 focus:ring-2 focus:ring-indigo-500/20 transition-all"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Contains</label>
                <input
                  type="text"
                  value={contains}
                  onChange={e => setContains(e.target.value)}
                  placeholder="e.g. 555"
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 placeholder:text-slate-400 outline-none focus:border-blue-500 focus:ring-2 focus:ring-indigo-500/20 transition-all"
                />
              </div>
              <div className="flex items-end">
                <button
                  onClick={searchNumbers}
                  disabled={isSearching}
                  className="w-full flex items-center justify-center gap-2 rounded-xl gradient-primary py-2 text-sm font-semibold text-white hover:opacity-90 transition-all disabled:opacity-60"
                >
                  {isSearching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                  Search
                </button>
              </div>
            </div>
          </div>

          {/* Results */}
          {searchResults.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 card-shadow overflow-hidden">
              <div className="px-5 py-3 border-b border-slate-100 bg-slate-50">
                <p className="text-sm font-semibold text-slate-700">
                  {searchResults.length} numbers available
                  {activeProvider && (
                    <span className="ml-1.5 font-normal text-slate-500">from {activeProvider.name}</span>
                  )}
                </p>
              </div>
              <div className="divide-y divide-slate-100">
                {searchResults.map(num => (
                  <div key={num.phone_number} className="flex items-center gap-4 px-5 py-4">
                    <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-slate-100">
                      <Phone className="h-4 w-4 text-slate-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-slate-900 font-mono">{num.phone_number}</p>
                      <p className="text-xs text-slate-400">
                        {[num.locality, num.region].filter(Boolean).join(', ') || 'Unknown region'}
                        {num.monthly_cost != null && (
                          <span className="ml-1.5 text-slate-500">
                            · {num.currency === 'USD' || !num.currency ? '$' : ''}
                            {num.monthly_cost.toFixed(2)}/mo
                          </span>
                        )}
                      </p>
                    </div>
                    <div className="flex items-center gap-1">
                      {num.capabilities?.voice && <CapBadge label="Voice" active />}
                      {(num.capabilities?.SMS || num.capabilities?.sms) && <CapBadge label="SMS" active />}
                    </div>
                    {purchaseTarget?.phone_number === num.phone_number ? (
                      <div className="flex items-center gap-2">
                        <div className="relative">
                          <select
                            value={selectedAgent}
                            onChange={e => setSelectedAgent(e.target.value)}
                            className="appearance-none rounded-lg border border-slate-300 bg-white pl-3 pr-8 py-1.5 text-sm text-slate-700 outline-none focus:border-blue-500 focus:ring-2 focus:ring-indigo-500/20"
                          >
                            <option value="">Select agent…</option>
                            {agents.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
                          </select>
                          <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
                        </div>
                        <button
                          onClick={() => purchaseNumber(num)}
                          disabled={isPurchasing === num.phone_number}
                          className="flex items-center gap-1.5 rounded-lg gradient-primary px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90 transition-all disabled:opacity-60"
                        >
                          {isPurchasing === num.phone_number ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle className="h-3.5 w-3.5" />}
                          Confirm
                        </button>
                        <button
                          onClick={() => { setPurchaseTarget(null); setSelectedAgent('') }}
                          className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setPurchaseTarget(num)}
                        className="flex items-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-100 transition-colors"
                      >
                        <Plus className="h-3.5 w-3.5" />
                        Purchase
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {searchResults.length === 0 && !isSearching && (
            <div className="flex flex-col items-center justify-center py-16 text-center bg-white rounded-xl border border-slate-200">
              <Search className="h-10 w-10 text-slate-200 mb-3" />
              <p className="text-sm text-slate-400">Search to see available phone numbers</p>
              <p className="text-xs text-slate-300 mt-1">Filter by country, area code, or pattern</p>
            </div>
          )}

          {isSearching && (
            <div className="flex flex-col items-center justify-center py-16 bg-white rounded-xl border border-slate-200">
              <Loader2 className="h-8 w-8 text-blue-500 animate-spin mb-3" />
              <p className="text-sm text-slate-500">Searching available numbers…</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
