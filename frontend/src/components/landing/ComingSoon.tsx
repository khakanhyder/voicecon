'use client'

import { useState, type FormEvent } from 'react'
import Image from 'next/image'
import { ArrowRight, CheckCircle2, Mail } from 'lucide-react'
import { joinWaitlist } from '@/lib/waitlist'
import { Logo, ROUTES, buttonClass } from './primitives'

/**
 * The voicecon.ai coming-soon page, rebuilt as a React component so the primary
 * domain can serve it from this deployment. The layout, spacing, colours and
 * motion are a one-to-one port of the original static coming-soon.html; the two
 * additions are the Log in / Get started buttons in the nav, which point at the
 * same app routes as the marketing navbar.
 *
 * The full marketing site it replaces at the root still lives at /landing-page.
 */

const FEATURES = [
  {
    art: '/landing/01-voice-to-voice.gif',
    title: 'VOICE TO VOICE',
    body: 'Natural conversations between agents. Fast, reliable and context-aware.',
    // The voice-to-action art sits right-of-centre — nudge it back into frame.
    artClass: 'scale-[1.15]',
  },
  {
    art: '/landing/02-voice-to-action.gif',
    title: 'VOICE TO ACTION',
    body: 'From intent to impact. Agents that take real-world action across your tools and systems.',
    artClass: 'scale-[1.08] -translate-x-[4%]',
  },
  {
    art: '/landing/03-generality.gif',
    title: 'Generality (AGI)',
    body: 'Building agent intelligence that generalizes across tasks, domains and environments.',
    artClass: 'scale-[1.15]',
  },
]

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function ComingSoon() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [joined, setJoined] = useState<string | null>(null)

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')

    const value = email.trim()
    if (!value || !EMAIL_PATTERN.test(value)) {
      setError('Please enter a valid email address.')
      return
    }

    setLoading(true)
    try {
      const result = await joinWaitlist(value)
      setJoined(result.message)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Network error — please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative min-h-screen overflow-x-clip bg-[#10302f] bg-[radial-gradient(120%_90%_at_50%_-10%,#1c5453_0%,#16403f_45%,#10302f_100%)] text-white antialiased">
      {/* Ambient grid + glow orbs, fixed behind the content. */}
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 z-0">
        <div className="absolute inset-0 opacity-[0.15] [background-image:linear-gradient(rgba(255,255,255,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.08)_1px,transparent_1px)] [background-size:54px_54px] [mask-image:radial-gradient(circle_at_50%_30%,black,transparent_78%)]" />
        <div className="absolute -top-40 left-[calc(50%-280px)] h-[560px] w-[560px] animate-glow-pulse rounded-full bg-[radial-gradient(circle,rgba(47,155,126,0.55),transparent_65%)] blur-[70px] motion-reduce:animate-none" />
        <div className="absolute -left-32 top-1/3 h-[420px] w-[420px] animate-glow-pulse rounded-full bg-[radial-gradient(circle,rgba(36,50,117,0.45),transparent_65%)] blur-[70px] [animation-delay:2s] motion-reduce:animate-none" />
        <div className="absolute -right-32 bottom-0 h-[460px] w-[460px] animate-glow-pulse rounded-full bg-[radial-gradient(circle,rgba(19,128,102,0.5),transparent_65%)] blur-[70px] [animation-delay:4s] motion-reduce:animate-none" />
      </div>

      <div className="relative z-10 flex min-h-screen flex-col overflow-x-hidden">
        {/* ── Nav ─────────────────────────────────────────────────────── */}
        <nav className="mx-auto flex w-full max-w-[1120px] items-center justify-between gap-4 px-[18px] py-5 sm:px-6 sm:py-4">
          <a
            href="/"
            aria-label="Voicecon home"
            className="rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-200"
          >
            <Logo />
          </a>

          <div className="flex items-center gap-2">
            <a
              href={ROUTES.login}
              className="inline-flex rounded-full px-3 py-2 text-[15px] font-medium text-white/80 transition-colors hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-200 sm:px-4"
            >
              Log in
            </a>
            <a
              href={ROUTES.register}
              className={buttonClass('primary', 'md', 'h-10 px-4 text-sm sm:px-5 sm:text-[15px]')}
            >
              Get started
            </a>
          </div>
        </nav>

        {/* ── Hero ────────────────────────────────────────────────────── */}
        <main className="mx-auto flex w-full max-w-[760px] flex-1 flex-col items-center justify-center px-5 py-10 text-center sm:px-6 sm:py-6">
          <span className="inline-flex animate-rise-in items-center gap-2 rounded-full border border-white/[0.14] bg-white/[0.05] py-[5px] pl-[5px] pr-3.5 text-[12.5px] font-medium tracking-[0.01em] text-white/[0.78] backdrop-blur-[6px] motion-reduce:animate-none">
            <span className="inline-flex items-center rounded-full bg-gradient-to-b from-brand-400 to-brand-600 px-[9px] py-[3px] text-[10.5px] font-bold uppercase tracking-[0.08em] text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.18),0_1px_2px_rgba(0,0,0,0.25)]">
              Beta
            </span>
            COMING SOON
          </span>

          <h1 className="mt-7 animate-rise-in text-[clamp(2.25rem,6vw,3.75rem)] font-bold leading-[1.08] tracking-[-0.02em] [animation-delay:0.05s] motion-reduce:animate-none">
            Native{' '}
            <span className="animate-gradient-pan bg-[linear-gradient(90deg,#63b9a0,#9fd3c2,#cfe9e0,#63b9a0)] bg-[length:200%_auto] bg-clip-text text-transparent motion-reduce:animate-none">
              AI Voice{' '}
            </span>
            Large Language Model
          </h1>

          <p className="mx-auto mt-5 max-w-[560px] animate-rise-in text-[clamp(1rem,2.2vw,1.125rem)] leading-[1.6] text-white/70 [animation-delay:0.12s] motion-reduce:animate-none">
            Voicecon AI talks naturally, grasps what callers mean, and answers in milliseconds
          </p>

          {/* ── Waitlist form ─────────────────────────────────────────── */}
          <div className="mt-6 w-full max-w-[448px] animate-rise-in [animation-delay:0.18s] motion-reduce:animate-none">
            {joined === null ? (
              <>
                <form
                  onSubmit={onSubmit}
                  noValidate
                  className="flex flex-col items-center gap-3 rounded-[20px] border border-white/[0.12] bg-white/[0.06] p-2 backdrop-blur-[16px] sm:flex-row sm:rounded-full sm:py-2 sm:pl-5 sm:pr-2"
                >
                  <div className="relative flex w-full flex-1 items-center">
                    <Mail
                      aria-hidden="true"
                      className="pointer-events-none absolute left-4 h-5 w-5 text-white/40 sm:left-0"
                    />
                    <input
                      type="email"
                      id="email"
                      name="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      disabled={loading}
                      placeholder="Enter your email address"
                      required
                      aria-label="Email address"
                      autoComplete="email"
                      className="w-full border-0 bg-transparent py-3 pl-12 pr-3 text-base text-white outline-none placeholder:text-white/40 sm:pl-8"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={loading}
                    className={buttonClass(
                      'primary',
                      'md',
                      'h-auto w-full px-6 py-3 text-base disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto'
                    )}
                  >
                    {loading ? (
                      <>
                        <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                        Joining…
                      </>
                    ) : (
                      <>
                        Notify Me
                        <ArrowRight className="h-5 w-5" aria-hidden="true" />
                      </>
                    )}
                  </button>
                </form>
                {error && (
                  <p role="alert" className="mt-3.5 text-sm text-[#fca5a5]">
                    {error}
                  </p>
                )}
              </>
            ) : (
              <div className="rounded-[20px] border border-brand-300/25 bg-white/[0.06] p-7 text-center backdrop-blur-[16px]">
                <CheckCircle2 className="mx-auto h-11 w-11 text-brand-300" aria-hidden="true" />
                <h2 className="mt-3 text-lg font-semibold">You&apos;re on the list!</h2>
                <p className="mt-1.5 text-sm leading-[1.6] text-white/70">{joined}</p>
              </div>
            )}
          </div>

          {/* ── Features ──────────────────────────────────────────────── */}
          <div className="mt-8 grid w-[min(1000px,92vw)] shrink-0 animate-rise-in grid-cols-1 items-stretch gap-[18px] [animation-delay:0.26s] motion-reduce:animate-none min-[560px]:grid-cols-2 min-[560px]:gap-5 min-[860px]:grid-cols-3 min-[860px]:gap-[26px]">
            {FEATURES.map((feature, index) => (
              <div
                key={feature.title}
                className={[
                  'group relative mx-auto flex h-full w-full max-w-[400px] flex-col items-center overflow-hidden rounded-3xl border border-white/[0.08] bg-gradient-to-b from-white/[0.06] to-white/[0.02] px-5 py-[26px] text-center shadow-[inset_0_1px_0_rgba(255,255,255,0.05),0_18px_40px_-24px_rgba(0,0,0,0.6)] transition-[transform,border-color,box-shadow,background] duration-[350ms] ease-[cubic-bezier(0.22,1,0.36,1)] hover:scale-[1.045] hover:border-brand-300/35 hover:from-white/[0.09] hover:to-white/[0.03] hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.08),0_30px_60px_-28px_rgba(0,0,0,0.75)] motion-reduce:hover:scale-100 min-[380px]:px-6 min-[380px]:py-[30px] min-[860px]:max-w-none min-[860px]:px-8 min-[860px]:py-10',
                  // Tablet: the lone third card spans both columns, centred.
                  index === 2 ? 'min-[560px]:col-span-2 min-[560px]:max-w-[440px] min-[860px]:col-span-1' : '',
                ].join(' ')}
              >
                {/* Soft brand glow that fades in on hover. */}
                <span
                  aria-hidden="true"
                  className="pointer-events-none absolute -top-[40%] left-1/2 h-[220px] w-[220px] -translate-x-1/2 rounded-full bg-[radial-gradient(circle,rgba(47,224,138,0.18)_0%,rgba(47,224,138,0)_70%)] opacity-0 transition-opacity duration-[400ms] group-hover:opacity-100"
                />
                <div className="relative flex h-[92px] w-[92px] items-center justify-center overflow-hidden rounded-[26px] p-1 min-[380px]:h-[104px] min-[380px]:w-[104px]">
                  <Image
                    src={feature.art}
                    alt=""
                    width={104}
                    height={104}
                    unoptimized
                    className={`block h-full w-full object-contain [filter:brightness(1.55)_contrast(1.05)_saturate(1.15)] ${feature.artClass}`}
                  />
                </div>
                <h3 className="mt-[22px] text-[13px] font-bold uppercase tracking-[0.08em] text-white">
                  {feature.title}
                </h3>
                <p className="mt-2.5 text-sm leading-[1.65] text-white/[0.62] min-[860px]:max-w-[26ch]">
                  {feature.body}
                </p>
              </div>
            ))}
          </div>
        </main>

        {/* ── Footer ──────────────────────────────────────────────────── */}
        <footer className="mx-auto flex w-full max-w-[1120px] flex-wrap items-center justify-center gap-4 border-t border-white/10 px-6 py-3 text-center text-sm text-white/50 sm:justify-between sm:text-left">
          <p>© 2026 Voicecon.ai All rights reserved.</p>
          <div className="flex gap-3">
            <a
              href="https://www.linkedin.com/company/voicecon-ai/"
              target="_blank"
              rel="noreferrer"
              aria-label="Voicecon on LinkedIn"
              className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/[0.05] text-white/70 transition-colors hover:border-brand-300/40 hover:text-white"
            >
              <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4" aria-hidden="true">
                <path d="M4.98 3.5C4.98 4.88 3.87 6 2.5 6S0 4.88 0 3.5 1.12 1 2.5 1 4.98 2.12 4.98 3.5zM.24 8h4.52v13.5H.24V8zm7.5 0h4.33v1.85h.06c.6-1.14 2.08-2.35 4.28-2.35 4.58 0 5.42 3.01 5.42 6.93v8.07h-4.52v-7.15c0-1.71-.03-3.9-2.38-3.9-2.38 0-2.75 1.86-2.75 3.78v7.27H7.74V8z" />
              </svg>
            </a>
          </div>
        </footer>
      </div>
    </div>
  )
}
