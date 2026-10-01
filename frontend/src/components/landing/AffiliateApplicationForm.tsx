'use client'

import { useState, type FormEvent } from 'react'
import { ArrowRight, CheckCircle2 } from 'lucide-react'
import { applyToAffiliateProgram } from '@/lib/affiliateApplication'
import { cn } from '@/lib/utils'
import { buttonClass } from './primitives'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const MESSAGE_MIN = 10
const MESSAGE_MAX = 3000

const fieldClass =
  'w-full rounded-xl border border-white/[0.14] bg-white/[0.05] px-4 text-base text-white outline-none transition-colors placeholder:text-white/35 focus:border-brand-300/70 focus:bg-white/[0.08] focus-visible:ring-2 focus-visible:ring-brand-200/40 aria-[invalid=true]:border-[#fca5a5]/70'

type Errors = Partial<Record<'name' | 'email' | 'message', string>>

function Label({ htmlFor, children, optional }: { htmlFor: string; children: string; optional?: boolean }) {
  return (
    <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium text-white/85">
      {children}
      {optional && <span className="ml-1.5 font-normal text-white/45">(optional)</span>}
    </label>
  )
}

function FieldError({ id, children }: { id: string; children?: string }) {
  if (!children) return null
  return (
    <p id={id} className="mt-1.5 text-sm text-[#fca5a5]">
      {children}
    </p>
  )
}

/** The public "apply to the affiliate program" form. Staff review each request in the admin console. */
export function AffiliateApplicationForm() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [company, setCompany] = useState('')
  const [website, setWebsite] = useState('')
  const [message, setMessage] = useState('')
  const [fax, setFax] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const [failure, setFailure] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<string | null>(null)

  const validate = (): Errors => {
    const next: Errors = {}
    if (name.trim().length < 2) next.name = 'Enter your name.'
    if (!EMAIL_RE.test(email.trim())) next.email = 'Enter a valid email address.'
    if (message.trim().length < MESSAGE_MIN) next.message = 'Tell us a little about your audience and how you would promote Voicecon.'
    return next
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (busy) return
    const problems = validate()
    setErrors(problems)
    setFailure(null)
    if (Object.keys(problems).length > 0) return
    setBusy(true)
    try {
      setDone(
        await applyToAffiliateProgram({
          name: name.trim(),
          email: email.trim(),
          company: company.trim() || undefined,
          website: website.trim() || undefined,
          message: message.trim(),
          fax: fax || undefined,
        })
      )
    } catch (err) {
      setFailure(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  if (done) {
    return (
      <div role="status" className="py-6 text-center">
        <CheckCircle2 className="mx-auto h-12 w-12 text-brand-300" aria-hidden="true" />
        <h2 className="mt-4 text-xl font-semibold text-white">Request received</h2>
        <p className="mx-auto mt-2 max-w-sm text-[15px] leading-relaxed text-white/70">{done}</p>
      </div>
    )
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <Label htmlFor="aff-name">Full name</Label>
          <input
            id="aff-name"
            name="name"
            autoComplete="name"
            maxLength={255}
            value={name}
            onChange={(e) => setName(e.target.value)}
            aria-invalid={!!errors.name}
            aria-describedby={errors.name ? 'aff-name-error' : undefined}
            className={cn(fieldClass, 'h-12')}
            placeholder="Jane Doe"
          />
          <FieldError id="aff-name-error">{errors.name}</FieldError>
        </div>
        <div>
          <Label htmlFor="aff-email">Email</Label>
          <input
            id="aff-email"
            name="email"
            type="email"
            autoComplete="email"
            maxLength={255}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            aria-invalid={!!errors.email}
            aria-describedby={errors.email ? 'aff-email-error' : undefined}
            className={cn(fieldClass, 'h-12')}
            placeholder="you@company.com"
          />
          <FieldError id="aff-email-error">{errors.email}</FieldError>
        </div>
        <div>
          <Label htmlFor="aff-company" optional>Company</Label>
          <input
            id="aff-company"
            name="company"
            autoComplete="organization"
            maxLength={255}
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            className={cn(fieldClass, 'h-12')}
            placeholder="Your company or brand"
          />
        </div>
        <div>
          <Label htmlFor="aff-website" optional>Website or channel</Label>
          <input
            id="aff-website"
            name="website"
            inputMode="url"
            autoComplete="url"
            maxLength={500}
            value={website}
            onChange={(e) => setWebsite(e.target.value)}
            className={cn(fieldClass, 'h-12')}
            placeholder="https://"
          />
        </div>
      </div>

      <div>
        <Label htmlFor="aff-message">Your audience and how you would promote Voicecon</Label>
        <textarea
          id="aff-message"
          name="message"
          rows={5}
          maxLength={MESSAGE_MAX}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          aria-invalid={!!errors.message}
          aria-describedby={errors.message ? 'aff-message-error' : undefined}
          className={cn(fieldClass, 'resize-y py-3 leading-relaxed')}
          placeholder="For example: who follows you, roughly how many people, and where you would share your link."
        />
        <FieldError id="aff-message-error">{errors.message}</FieldError>
      </div>

      {/* Honeypot: off-screen and out of the tab order, so only bots fill it in. */}
      <div aria-hidden="true" className="absolute -left-[9999px] h-0 w-0 overflow-hidden">
        <label htmlFor="aff-fax">Fax</label>
        <input id="aff-fax" name="fax" tabIndex={-1} autoComplete="off" value={fax} onChange={(e) => setFax(e.target.value)} />
      </div>

      {failure && (
        <p role="alert" className="text-sm text-[#fca5a5]">
          {failure}
        </p>
      )}

      <button type="submit" disabled={busy} className={buttonClass('primary', 'lg', 'group w-full disabled:cursor-not-allowed disabled:opacity-70')}>
        {busy ? (
          <>
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" aria-hidden="true" />
            Sending…
          </>
        ) : (
          <>
            Send request
            <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
          </>
        )}
      </button>

      <p className="text-center text-xs leading-relaxed text-white/50">
        We use these details only to review your request. See our{' '}
        <a href="/privacy" className="underline decoration-white/30 underline-offset-2 hover:text-white">
          Privacy Policy
        </a>
        .
      </p>
    </form>
  )
}
