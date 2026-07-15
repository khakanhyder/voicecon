'use client'

import { useState } from 'react'
import Image from 'next/image'
import { toast } from 'sonner'
import {
  Mail,
  ArrowRight,
  CheckCircle2,
  Mic,
  Blocks,
  Workflow,
  Sparkles,
  Linkedin,
  Twitter,
} from 'lucide-react'
import { VoiceconLogo, BrandPanelIcons } from '@/lib/icons'
import { joinWaitlist } from '@/lib/waitlist'

const FEATURES = [
  {
    icon: Mic,
    title: 'Lifelike voice agents',
    desc: 'Natural, real-time conversations that sound human.',
  },
  {
    icon: Blocks,
    title: '500+ integrations',
    desc: 'Connect the tools your business already runs on.',
  },
  {
    icon: Workflow,
    title: 'No-code workflows',
    desc: 'Design powerful automations without writing a line.',
  },
]

export default function ComingSoonPage() {
  const [email, setEmail] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [done, setDone] = useState(false)
  const [successMessage, setSuccessMessage] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (submitting) return
    setSubmitting(true)
    try {
      const result = await joinWaitlist(email)
      setSuccessMessage(result.message)
      setDone(true)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main
      className="relative flex min-h-screen flex-col overflow-hidden text-white"
      style={{
        background:
          'radial-gradient(120% 90% at 50% -10%, #1c5453 0%, #16403f 45%, #10302f 100%)',
      }}
    >
      {/* ── Ambient background ─────────────────────────────────────────── */}
      {/* Faint grid */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.15]"
        style={{
          backgroundImage:
            'linear-gradient(rgba(255,255,255,0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.08) 1px, transparent 1px)',
          backgroundSize: '54px 54px',
          maskImage: 'radial-gradient(circle at 50% 30%, black, transparent 78%)',
          WebkitMaskImage: 'radial-gradient(circle at 50% 30%, black, transparent 78%)',
        }}
      />
      {/* Glow orbs */}
      <div
        aria-hidden
        className="animate-glow-pulse pointer-events-none absolute -top-40 left-1/2 h-[560px] w-[560px] -translate-x-1/2 rounded-full blur-3xl"
        style={{ background: 'radial-gradient(circle, rgba(47,155,126,0.55), transparent 65%)' }}
      />
      <div
        aria-hidden
        className="animate-glow-pulse pointer-events-none absolute -left-32 top-1/3 h-[420px] w-[420px] rounded-full blur-3xl"
        style={{
          background: 'radial-gradient(circle, rgba(36,50,117,0.45), transparent 65%)',
          animationDelay: '2s',
        }}
      />
      <div
        aria-hidden
        className="animate-glow-pulse pointer-events-none absolute -right-32 bottom-0 h-[460px] w-[460px] rounded-full blur-3xl"
        style={{
          background: 'radial-gradient(circle, rgba(19,128,102,0.5), transparent 65%)',
          animationDelay: '4s',
        }}
      />

      {/* ── Nav ───────────────────────────────────────────────────────── */}
      <nav className="relative z-10 mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-6 sm:px-8">
        <div className="flex items-center gap-2.5">
          <VoiceconLogo className="h-8 w-8" />
          <span className="text-xl font-bold tracking-tight">Voicecon</span>
        </div>
        <span className="hidden items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3.5 py-1.5 text-xs font-medium text-white/70 backdrop-blur sm:inline-flex">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand-300 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-brand-300" />
          </span>
          In active development
        </span>
      </nav>

      {/* ── Hero ──────────────────────────────────────────────────────── */}
      <section className="relative z-10 mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center px-6 py-12 text-center sm:px-8">
        {/* Badge */}
        <div className="animate-rise-in inline-flex items-center gap-2 rounded-full border border-brand-300/30 bg-brand-500/10 px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-brand-200 backdrop-blur">
          <Sparkles className="h-3.5 w-3.5" />
          Launching Soon
        </div>

        {/* Headline */}
        <h1
          className="animate-rise-in mt-7 text-4xl font-bold leading-[1.08] tracking-tight sm:text-6xl"
          style={{ animationDelay: '0.05s' }}
        >
          The future of{' '}
          <span
            className="animate-gradient-pan bg-clip-text text-transparent"
            style={{
              backgroundImage:
                'linear-gradient(90deg, #63b9a0, #9fd3c2, #cfe9e0, #63b9a0)',
              backgroundSize: '200% auto',
            }}
          >
            AI voice agents
          </span>{' '}
          is almost here.
        </h1>

        {/* Subtitle */}
        <p
          className="animate-rise-in mx-auto mt-5 max-w-xl text-base leading-relaxed text-white/70 sm:text-lg"
          style={{ animationDelay: '0.12s' }}
        >
          Build, deploy, and manage AI voice agents with unlimited integrations — no code
          required. Join the waitlist and be first through the door on launch day.
        </p>

        {/* Waitlist form / success */}
        <div
          className="animate-rise-in mt-9 w-full max-w-md"
          style={{ animationDelay: '0.18s' }}
        >
          {done ? (
            <div className="rounded-2xl border border-brand-300/25 bg-white/[0.06] p-7 backdrop-blur-xl">
              <CheckCircle2 className="mx-auto h-11 w-11 text-brand-300" />
              <h2 className="mt-3 text-lg font-semibold text-white">You&apos;re on the list!</h2>
              <p className="mt-1.5 text-sm leading-relaxed text-white/70">{successMessage}</p>
            </div>
          ) : (
            <>
              <form
                onSubmit={handleSubmit}
                className="flex flex-col gap-3 rounded-2xl border border-white/12 bg-white/[0.06] p-2 backdrop-blur-xl sm:flex-row sm:items-center sm:rounded-full sm:p-2 sm:pl-5"
              >
                <div className="relative flex flex-1 items-center">
                  <Mail className="pointer-events-none absolute left-4 h-5 w-5 text-white/40 sm:left-0" />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Enter your email address"
                    required
                    disabled={submitting}
                    aria-label="Email address"
                    className="w-full border-0 bg-transparent py-3 pl-12 pr-3 text-base text-white outline-none ring-0 focus:border-0 focus:outline-none focus:ring-0 placeholder:text-white/40 disabled:opacity-50 sm:pl-8"
                  />
                </div>
                <button
                  type="submit"
                  disabled={submitting}
                  className="group inline-flex items-center justify-center gap-2 rounded-full bg-gradient-to-r from-brand-400 to-brand-600 px-6 py-3 text-base font-semibold text-white shadow-[0_10px_30px_-6px_rgba(47,155,126,0.6)] transition-all hover:from-brand-300 hover:to-brand-500 focus:outline-none focus:ring-3 focus:ring-brand-300/40 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submitting ? (
                    <>
                      <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                      Joining…
                    </>
                  ) : (
                    <>
                      Notify Me
                      <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-0.5" />
                    </>
                  )}
                </button>
              </form>
              <p className="mt-3.5 text-sm text-white/50">
                No spam, ever — just one email the day we go live.
              </p>
            </>
          )}
        </div>

        {/* Feature trio */}
        <div
          className="animate-rise-in mt-14 grid w-full grid-cols-1 gap-3 sm:grid-cols-3 sm:gap-4"
          style={{ animationDelay: '0.26s' }}
        >
          {FEATURES.map(({ icon: Icon, title, desc }) => (
            <div
              key={title}
              className="rounded-2xl border border-white/10 bg-white/[0.04] p-5 text-left backdrop-blur-sm transition-colors hover:border-brand-300/30 hover:bg-white/[0.07]"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500/20 text-brand-200 ring-1 ring-inset ring-brand-300/20">
                <Icon className="h-5 w-5" />
              </div>
              <h3 className="mt-3.5 text-sm font-semibold text-white">{title}</h3>
              <p className="mt-1 text-sm leading-relaxed text-white/60">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Integration marquee ───────────────────────────────────────── */}
      <div className="relative z-10 mx-auto w-full max-w-3xl px-6 pb-4">
        <p className="mb-5 text-center text-xs font-medium uppercase tracking-[0.16em] text-white/40">
          Plays nicely with your stack
        </p>
        <div
          className="relative overflow-hidden"
          style={{
            maskImage:
              'linear-gradient(90deg, transparent, black 12%, black 88%, transparent)',
            WebkitMaskImage:
              'linear-gradient(90deg, transparent, black 12%, black 88%, transparent)',
          }}
        >
          <div className="animate-marquee flex w-max items-center gap-14 py-1">
            {[...BrandPanelIcons, ...BrandPanelIcons, ...BrandPanelIcons, ...BrandPanelIcons].map(
              (icon, i) => (
                <Image
                  key={`${icon.key}-${i}`}
                  src={icon.src}
                  alt={icon.alt}
                  width={36}
                  height={36}
                  className="h-9 w-9 opacity-70 grayscale transition hover:opacity-100 hover:grayscale-0"
                />
              )
            )}
          </div>
        </div>
      </div>

      {/* ── Footer ────────────────────────────────────────────────────── */}
      <footer className="relative z-10 mx-auto flex w-full max-w-6xl flex-col items-center justify-between gap-4 border-t border-white/10 px-6 py-6 text-sm text-white/50 sm:flex-row sm:px-8">
        <p>© 2026 Voicecon. All rights reserved.</p>
        <div className="flex items-center gap-3">
          <a
            href="#"
            aria-label="Voicecon on LinkedIn"
            className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/5 text-white/70 transition hover:border-brand-300/40 hover:text-white"
          >
            <Linkedin className="h-4 w-4" />
          </a>
          <a
            href="#"
            aria-label="Voicecon on X"
            className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/5 text-white/70 transition hover:border-brand-300/40 hover:text-white"
          >
            <Twitter className="h-4 w-4" />
          </a>
        </div>
      </footer>
    </main>
  )
}
