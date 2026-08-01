'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Check, ChevronDown, Loader2, Phone, Search } from 'lucide-react'
import { VoiceconLogo } from '@/lib/icons'
import { BrandPanel } from '@/components/auth/BrandPanel'
import {
  onboardingService,
  type AvailableNumber,
  type ClaimedNumber,
  type CompanyProfilePayload,
  type TelephonyProvider,
} from '@/lib/onboarding'

const INDUSTRY_TYPES = [
  'Business',
  'Real Estate',
  'Healthcare',
  'E-commerce',
  'Finance',
  'Education',
  'Technology',
  'Other',
]
const COMPANY_SIZES = ['1 - 10', '10 - 40', '40 - 100', '100 - 500', '500+']
const LANGUAGES = ['English', 'Spanish', 'French', 'German', 'Arabic', 'Hindi', 'Portuguese']
const COUNTRY_CODES = [
  { code: '+1', flag: '🇺🇸' },
  { code: '+44', flag: '🇬🇧' },
  { code: '+91', flag: '🇮🇳' },
  { code: '+92', flag: '🇵🇰' },
  { code: '+61', flag: '🇦🇺' },
  { code: '+971', flag: '🇦🇪' },
]
/** Countries we can buy numbers in, as ISO codes the carrier search expects. */
const NUMBER_COUNTRIES = [
  { code: 'US', label: 'United States' },
  { code: 'CA', label: 'Canada' },
  { code: 'GB', label: 'United Kingdom' },
  { code: 'AU', label: 'Australia' },
]

/** Providers are keyed by account, so the same carrier can appear twice. */
const providerKey = (p: TelephonyProvider) => p.connection_id ?? p.slug

/** Which account a number would be billed to. */
const providerAccountLabel = (p: TelephonyProvider) =>
  p.source === 'platform'
    ? 'Voicecon shared account'
    : p.connection_name || 'Your connected account'

const inputClass =
  'w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none transition-all placeholder:text-slate-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 disabled:opacity-50'
const labelClass = 'mb-1.5 block text-sm font-semibold text-slate-800'

function Select({
  value,
  onChange,
  options,
  disabled,
}: {
  value: string
  onChange: (v: string) => void
  options: string[]
  disabled?: boolean
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className={`${inputClass} appearance-none pr-9`}
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
    </div>
  )
}

export default function CompanyInformationPage() {
  const router = useRouter()
  const [form, setForm] = useState({
    company_name: '',
    industry_type: 'Business',
    company_size: '10 - 40',
    company_url: '',
    assistant_name: '',
    preferred_language: 'English',
    assistant_instructions: '',
    phone_number: '',
  })
  const [dialCode, setDialCode] = useState('+1')

  // ── Claiming a number on a carrier account ──────────────────────────────
  const [providers, setProviders] = useState<TelephonyProvider[]>([])
  const [selectedProvider, setSelectedProvider] = useState('')
  const [phoneMode, setPhoneMode] = useState<'claim' | 'manual'>('manual')
  const [numberCountry, setNumberCountry] = useState('US')
  const [areaCode, setAreaCode] = useState('')
  const [results, setResults] = useState<AvailableNumber[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [claiming, setClaiming] = useState<string | null>(null)
  const [claimed, setClaimed] = useState<ClaimedNumber | null>(null)

  const set = (key: keyof typeof form) => (value: string) =>
    setForm((f) => ({ ...f, [key]: value }))

  // Offer number-buying only if there is actually an account to buy on.
  useEffect(() => {
    onboardingService
      .getPhoneProviders()
      .then((list) => {
        setProviders(list)
        if (list.length) {
          const fallback = list.find((p) => p.is_default) ?? list[0]
          setSelectedProvider(providerKey(fallback))
          setPhoneMode('claim')
        }
      })
      .catch(() => setProviders([]))
  }, [])

  const activeProvider =
    providers.find((p) => providerKey(p) === selectedProvider) ?? providers[0] ?? null

  const searchNumbers = async () => {
    if (!activeProvider) return
    setIsSearching(true)
    setResults([])
    try {
      const found = await onboardingService.searchPhoneNumbers({
        country_code: numberCountry,
        area_code: areaCode || undefined,
        provider: activeProvider.slug,
        connection_id: activeProvider.connection_id,
      })
      setResults(found)
      if (!found.length) toast.info('No numbers found. Try a different area code.')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not search for numbers')
    } finally {
      setIsSearching(false)
    }
  }

  const claimNumber = async (number: AvailableNumber) => {
    if (!activeProvider) return
    setClaiming(number.phone_number)
    try {
      const result = await onboardingService.claimPhoneNumber({
        phone_number: number.phone_number,
        provider: number.provider || activeProvider.slug,
        connection_id: activeProvider.connection_id,
        country_code: numberCountry,
        area_code: areaCode || undefined,
        monthly_cost: number.monthly_cost,
        assistant_name: form.assistant_name || undefined,
        assistant_instructions: form.assistant_instructions || undefined,
      })
      setClaimed(result)
      setResults([])
      set('phone_number')(result.phone_number)
      toast.success(`${result.phone_number} is yours — ${result.agent_name} will answer it`)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not get that number')
    } finally {
      setClaiming(null)
    }
  }

  const mutation = useMutation({
    mutationFn: (payload: CompanyProfilePayload) => onboardingService.saveCompany(payload),
    onSuccess: () => {
      toast.success('Company details saved')
      router.push('/onboarding/pricing')
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Could not save company details')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.company_name.trim()) {
      toast.error('Company name is required')
      return
    }
    mutation.mutate({
      ...form,
      // A claimed number is already in E.164 and must not be re-prefixed.
      phone_number: claimed
        ? claimed.phone_number
        : form.phone_number
          ? `${dialCode} ${form.phone_number}`.trim()
          : undefined,
    })
  }

  return (
    <div className="mx-auto grid min-h-[calc(100vh-3rem)] max-w-7xl grid-cols-1 items-stretch gap-4 overflow-hidden md:rounded-3xl md:bg-white p-3 md:shadow-xl md:shadow-slate-200/60 lg:grid-cols-2">
      {/* Left — form */}
      <div className="flex flex-col md:px-4 py-6 sm:px-8 lg:px-10">
        <div className="mb-5 flex items-center gap-2">
          <VoiceconLogo className="h-7 w-7" />
          <span className="text-xl font-bold text-slate-900">Voicecon</span>
        </div>

        <h1 className="text-[28px] font-medium md:font-bold text-slate-900">Company Information</h1>
        <p className="mt-1 text-sm text-slate-500">Tell us about your company and assistant</p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-5">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className={labelClass}>Company Name</label>
              <input
                className={inputClass}
                placeholder="Acme Inc."
                value={form.company_name}
                onChange={(e) => set('company_name')(e.target.value)}
                disabled={mutation.isPending}
              />
            </div>
            <div>
              <label className={labelClass}>Industry Type</label>
              <Select
                value={form.industry_type}
                onChange={set('industry_type')}
                options={INDUSTRY_TYPES}
                disabled={mutation.isPending}
              />
            </div>
            <div>
              <label className={labelClass}>Company Size</label>
              <Select
                value={form.company_size}
                onChange={set('company_size')}
                options={COMPANY_SIZES}
                disabled={mutation.isPending}
              />
            </div>
            <div>
              <label className={labelClass}>Company URL</label>
              <input
                className={inputClass}
                placeholder="www.acme.com"
                value={form.company_url}
                onChange={(e) => set('company_url')(e.target.value)}
                disabled={mutation.isPending}
              />
            </div>
          </div>

          {/* Assistant divider */}
          <div className="flex items-center gap-3 pt-1">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-400">
              Assistant
            </span>
            <div className="h-px flex-1 bg-slate-200" />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className={labelClass}>Assistant Name</label>
              <input
                className={inputClass}
                placeholder="e.g. Aria, Max, Sales Assistant"
                value={form.assistant_name}
                onChange={(e) => set('assistant_name')(e.target.value)}
                disabled={mutation.isPending}
              />
            </div>
            <div>
              <label className={labelClass}>Preferred Language</label>
              <Select
                value={form.preferred_language}
                onChange={set('preferred_language')}
                options={LANGUAGES}
                disabled={mutation.isPending}
              />
            </div>
          </div>

          <div>
            <label className={labelClass}>What should your AI assistant do?</label>
            <textarea
              className={`${inputClass} min-h-[90px] resize-none`}
              placeholder="e.g. Answer customer calls, qualify leads, and book appointments"
              value={form.assistant_instructions}
              onChange={(e) => set('assistant_instructions')(e.target.value)}
              disabled={mutation.isPending}
            />
          </div>

          {/* Assistant divider */}
          <div className="flex items-center gap-3">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-400">
              Assistant
            </span>
            <div className="h-px flex-1 bg-slate-200" />
          </div>

          <div>
            <label className={labelClass}>
              Phone Number<span className="text-slate-400"> (Optional)</span>
            </label>

            {claimed ? (
              /* Bought and wired up — nothing left to fill in. */
              <div className="rounded-lg border border-brand-200 bg-brand-50/60 p-4">
                <div className="flex items-center gap-2">
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-600">
                    <Check className="h-4 w-4 text-white" />
                  </span>
                  <div>
                    <p className="font-mono text-sm font-bold text-slate-900">
                      {claimed.phone_number}
                    </p>
                    <p className="text-xs text-slate-600">
                      Answered by {claimed.agent_name} · on {claimed.account_name}
                    </p>
                  </div>
                </div>
                <p className="mt-3 text-xs text-slate-500">
                  Calls to this number reach your assistant as soon as onboarding
                  finishes. You can change or release it later under Phone Numbers.
                </p>
              </div>
            ) : (
              <>
                {providers.length > 0 && (
                  <div className="mb-3 flex gap-2">
                    <button
                      type="button"
                      onClick={() => setPhoneMode('claim')}
                      className={`flex-1 rounded-lg border px-3 py-2 text-xs font-semibold transition-all ${
                        phoneMode === 'claim'
                          ? 'border-brand-600 bg-brand-50 text-brand-700'
                          : 'border-slate-300 bg-white text-slate-600 hover:border-slate-400'
                      }`}
                    >
                      Get a number for my assistant
                    </button>
                    <button
                      type="button"
                      onClick={() => setPhoneMode('manual')}
                      className={`flex-1 rounded-lg border px-3 py-2 text-xs font-semibold transition-all ${
                        phoneMode === 'manual'
                          ? 'border-brand-600 bg-brand-50 text-brand-700'
                          : 'border-slate-300 bg-white text-slate-600 hover:border-slate-400'
                      }`}
                    >
                      Enter my own number
                    </button>
                  </div>
                )}

                {phoneMode === 'claim' && activeProvider ? (
                  <div className="rounded-lg border border-slate-200 bg-slate-50/60 p-3">
                    <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
                      <p className="text-xs text-slate-500">
                        Bought on <span className="font-semibold text-slate-700">
                          {activeProvider.name} · {providerAccountLabel(activeProvider)}
                        </span>
                      </p>
                      {providers.length > 1 && (
                        <select
                          value={selectedProvider}
                          onChange={(e) => {
                            setSelectedProvider(e.target.value)
                            setResults([])
                          }}
                          aria-label="Account to buy on"
                          className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-700 outline-none"
                        >
                          {providers.map((p) => (
                            <option key={providerKey(p)} value={providerKey(p)}>
                              {p.name} · {providerAccountLabel(p)}
                            </option>
                          ))}
                        </select>
                      )}
                    </div>

                    <div className="flex gap-2">
                      <div className="relative">
                        <select
                          value={numberCountry}
                          onChange={(e) => setNumberCountry(e.target.value)}
                          aria-label="Country"
                          className={`${inputClass} appearance-none pr-8 py-2 text-xs`}
                        >
                          {NUMBER_COUNTRIES.map((c) => (
                            <option key={c.code} value={c.code}>
                              {c.label}
                            </option>
                          ))}
                        </select>
                        <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
                      </div>
                      <input
                        className={`${inputClass} flex-1 py-2 text-xs`}
                        placeholder="Area code (e.g. 301)"
                        value={areaCode}
                        onChange={(e) => setAreaCode(e.target.value)}
                      />
                      <button
                        type="button"
                        onClick={searchNumbers}
                        disabled={isSearching}
                        className="flex items-center gap-1.5 rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white transition-all hover:bg-slate-800 disabled:opacity-60"
                      >
                        {isSearching ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Search className="h-3.5 w-3.5" />
                        )}
                        Search
                      </button>
                    </div>

                    {results.length > 0 && (
                      <ul className="mt-2.5 max-h-44 divide-y divide-slate-200 overflow-y-auto rounded-lg border border-slate-200 bg-white">
                        {results.map((n) => (
                          <li
                            key={n.phone_number}
                            className="flex items-center gap-3 px-3 py-2"
                          >
                            <Phone className="h-4 w-4 flex-shrink-0 text-brand-600" />
                            <div className="min-w-0 flex-1">
                              <p className="font-mono text-sm font-semibold text-slate-900">
                                {n.phone_number}
                              </p>
                              <p className="truncate text-[11px] text-slate-500">
                                {[n.locality, n.region].filter(Boolean).join(', ') ||
                                  'Unknown region'}
                                {n.monthly_cost != null && ` · $${n.monthly_cost.toFixed(2)}/mo`}
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={() => claimNumber(n)}
                              disabled={claiming !== null}
                              className="flex items-center gap-1.5 rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white transition-all hover:bg-brand-700 disabled:opacity-60"
                            >
                              {claiming === n.phone_number && (
                                <Loader2 className="h-3 w-3 animate-spin" />
                              )}
                              Get this number
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}

                    <p className="mt-2 text-[11px] text-slate-500">
                      Picking a number buys it right away and points it at your
                      assistant. Skip this if you would rather do it later.
                    </p>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    <div className="relative">
                      <select
                        value={dialCode}
                        onChange={(e) => setDialCode(e.target.value)}
                        disabled={mutation.isPending}
                        aria-label="Country code"
                        className={`${inputClass} appearance-none pr-7`}
                      >
                        {COUNTRY_CODES.map((c) => (
                          <option key={c.code} value={c.code}>
                            {c.flag} {c.code}
                          </option>
                        ))}
                      </select>
                    </div>
                    <input
                      className={`${inputClass} flex-1`}
                      placeholder="(301) 798 1897"
                      value={form.phone_number}
                      onChange={(e) => set('phone_number')(e.target.value)}
                      disabled={mutation.isPending}
                    />
                  </div>
                )}
              </>
            )}
          </div>

          <button
            type="submit"
            disabled={mutation.isPending}
            className="w-full rounded-lg bg-brand-600 px-4 py-3 text-sm font-semibold text-white transition-all hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-500/40 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {mutation.isPending ? (
              <span className="flex items-center justify-center gap-2">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                Saving…
              </span>
            ) : (
              'Continue'
            )}
          </button>
        </form>
      </div>

      {/* Right — brand panel */}
      <div className="hidden lg:block">
        <BrandPanel />
      </div>
    </div>
  )
}
