'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { ChevronDown } from 'lucide-react'
import { VoiceconLogo } from '@/lib/icons'
import { BrandPanel } from '@/components/auth/BrandPanel'
import { FieldError, errorInputClass, fieldErrorProps } from '@/components/ui/field-error'
import { isPlausiblePhoneNumber, normalizeWebsiteUrl } from '@/lib/validation'
import {
  COMPANY_SIZES,
  INDUSTRY_TYPES,
  LANGUAGES,
  onboardingService,
  type CompanyProfilePayload,
} from '@/lib/onboarding'
import { getErrorMessage } from '@/lib/api'

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
  // Per-field messages, rendered under the field they belong to. A toast was
  // wrong for this: it names a field the user then has to go find, it covers
  // the form while they look, and it can only ever report one problem.
  const [errors, setErrors] = useState<Partial<Record<keyof typeof form, string>>>({})

  const set = (key: keyof typeof form) => (value: string) => {
    setForm((f) => ({ ...f, [key]: value }))
    // Clear as soon as they start fixing it — leaving the message up while the
    // field is being corrected reads as "still wrong".
    setErrors((e) => (e[key] ? { ...e, [key]: undefined } : e))
  }

  const mutation = useMutation({
    mutationFn: (payload: CompanyProfilePayload) => onboardingService.saveCompany(payload),
    onSuccess: () => {
      toast.success('Company details saved')
      router.push('/onboarding/pricing')
    },
    onError: (err: any) => {
      toast.error(getErrorMessage(err, 'Could not save company details'))
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    // Every field is checked and every failure is reported at once, under the
    // field it belongs to. The API enforces all of this again — these checks
    // exist to answer immediately, not to be the gate.
    const found: typeof errors = {}

    const companyName = form.company_name.trim()
    if (!companyName) {
      found.company_name = 'Enter your company name'
    } else if (companyName.length < 2) {
      found.company_name = 'Company name is too short'
    }

    // Optional, but if it is filled in it has to be a website. It is stored on
    // the profile and later rendered as a link, so a bare word like "dcsdcs"
    // becomes a broken link nobody notices until a customer clicks it.
    let companyUrl: string | null = null
    try {
      companyUrl = normalizeWebsiteUrl(form.company_url)
    } catch (err: any) {
      found.company_url = err.message
    }

    const assistantName = form.assistant_name.trim()
    if (assistantName && assistantName.length < 2) {
      found.assistant_name = 'Assistant name is too short'
    }

    if (form.phone_number.trim() && !isPlausiblePhoneNumber(form.phone_number)) {
      found.phone_number = 'Enter a valid phone number'
    }

    setErrors(found)
    const firstInvalid = (
      ['company_name', 'company_url', 'assistant_name', 'phone_number'] as const
    ).find((field) => found[field])
    if (firstInvalid) {
      document.getElementById(firstInvalid)?.focus()
      return
    }

    // Show the canonical form back to the user, so what they see saved is what
    // was actually stored ("acme.com" → "https://acme.com").
    if (companyUrl && companyUrl !== form.company_url) {
      setForm((f) => ({ ...f, company_url: companyUrl as string }))
    }

    mutation.mutate({
      ...form,
      company_name: companyName,
      company_url: companyUrl ?? undefined,
      assistant_name: assistantName || undefined,
      phone_number: form.phone_number.trim()
        ? `${dialCode} ${form.phone_number.trim()}`
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

        {/* noValidate: errors are rendered under each field instead of in the
            browser's own bubble — see components/ui/field-error.tsx. */}
        <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-5">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className={labelClass} htmlFor="company_name">
                Company Name
              </label>
              <input
                id="company_name"
                className={`${inputClass} ${errors.company_name ? errorInputClass : ''}`}
                placeholder="Acme Inc."
                value={form.company_name}
                onChange={(e) => set('company_name')(e.target.value)}
                disabled={mutation.isPending}
                {...fieldErrorProps('company_name', errors.company_name)}
              />
              <FieldError id="company_name-error" message={errors.company_name} />
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
              <label className={labelClass} htmlFor="company_url">
                Company URL<span className="text-slate-400"> (Optional)</span>
              </label>
              <input
                id="company_url"
                type="url"
                inputMode="url"
                autoComplete="url"
                className={`${inputClass} ${errors.company_url ? errorInputClass : ''}`}
                placeholder="www.acme.com"
                value={form.company_url}
                onChange={(e) => set('company_url')(e.target.value)}
                disabled={mutation.isPending}
                {...fieldErrorProps('company_url', errors.company_url)}
              />
              <FieldError id="company_url-error" message={errors.company_url} />
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
              <label className={labelClass} htmlFor="assistant_name">
                Assistant Name
              </label>
              <input
                id="assistant_name"
                className={`${inputClass} ${errors.assistant_name ? errorInputClass : ''}`}
                placeholder="e.g. Aria, Max, Sales Assistant"
                value={form.assistant_name}
                onChange={(e) => set('assistant_name')(e.target.value)}
                disabled={mutation.isPending}
                {...fieldErrorProps('assistant_name', errors.assistant_name)}
              />
              <FieldError id="assistant_name-error" message={errors.assistant_name} />
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

          {/* Contact divider */}
          <div className="flex items-center gap-3">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-400">
              Contact
            </span>
            <div className="h-px flex-1 bg-slate-200" />
          </div>

          {/* A contact number only. Numbers for the assistant are bought on the
              Phone Numbers page, once the workspace has a plan. */}
          <div>
            <label className={labelClass} htmlFor="phone_number">
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
                id="phone_number"
                type="tel"
                inputMode="tel"
                className={`${inputClass} flex-1 ${errors.phone_number ? errorInputClass : ''}`}
                placeholder="(301) 798 1897"
                value={form.phone_number}
                onChange={(e) => set('phone_number')(e.target.value)}
                disabled={mutation.isPending}
                {...fieldErrorProps('phone_number', errors.phone_number)}
              />
            </div>
            <FieldError id="phone_number-error" message={errors.phone_number} />
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
