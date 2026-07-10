'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { ChevronDown } from 'lucide-react'
import { VoiceconLogo } from '@/lib/icons'
import { BrandPanel } from '@/components/auth/BrandPanel'
import { onboardingService, type CompanyProfilePayload } from '@/lib/onboarding'

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

  const set = (key: keyof typeof form) => (value: string) =>
    setForm((f) => ({ ...f, [key]: value }))

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
      phone_number: form.phone_number ? `${dialCode} ${form.phone_number}`.trim() : undefined,
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
