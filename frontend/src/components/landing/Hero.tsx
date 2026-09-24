import Image from 'next/image'
import { ArrowRight, CheckCircle2 } from 'lucide-react'
import { Accent, ROUTES, buttonClass } from './primitives'
import { AppFrame, CallDetailScreen } from './mockups'

export function Hero({ trialDays }: { trialDays: number }) {
  const trust = [`${trialDays}-day free trial`, 'No credit card required', 'Live on a real phone number']
  return (
    <section
      id="top"
      aria-labelledby="hero-title"
      className="relative px-4 pb-16 pt-32 sm:px-6 md:pb-24 md:pt-40"
    >
      <div className="mx-auto flex max-w-6xl flex-col items-center text-center">
        <span className="inline-flex animate-rise-in items-center gap-2 rounded-full border border-white/15 bg-white/5 py-1 pl-1 pr-3.5 text-[12.5px] font-medium text-white/80 backdrop-blur">
          <span className="rounded-full bg-gradient-to-b from-brand-400 to-brand-600 px-2.5 py-0.5 text-[10.5px] font-bold uppercase tracking-[0.08em] text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.18)]">
            New
          </span>
          Voice agents + no-code workflows in one platform
        </span>

        <h1
          id="hero-title"
          className="mt-7 max-w-4xl animate-rise-in text-balance text-[clamp(2.4rem,6.4vw,4.5rem)] font-bold leading-[1.05] tracking-[-0.025em] text-white [animation-delay:50ms]"
        >
          AI voice agents that <Accent>answer the call</Accent> and finish the work
        </h1>

        <p className="mt-6 max-w-2xl animate-rise-in text-[clamp(1rem,2.2vw,1.2rem)] leading-relaxed text-white/70 [animation-delay:120ms]">
          Voicecon lets you build voice agents that talk with your callers in real time, answer
          from your own documents, and then update your CRM, book the meeting or alert your team
          through 35 connected apps.
        </p>

        <div className="mt-9 flex w-full animate-rise-in flex-col items-stretch justify-center gap-3 [animation-delay:180ms] sm:w-auto sm:flex-row sm:items-center">
          <a href={ROUTES.register} className={buttonClass('primary', 'lg', 'group')}>
            Start your free trial
            <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-0.5" />
          </a>
          <a href="/how-it-works" className={buttonClass('ghost', 'lg')}>
            See how it works
          </a>
        </div>

        <ul className="mt-7 flex animate-rise-in flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm text-white/60 [animation-delay:220ms]">
          {trust.map((item) => (
            <li key={item} className="flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4 text-brand-300" aria-hidden="true" />
              {item}
            </li>
          ))}
        </ul>

        {/* Product preview */}
        <div className="relative mt-16 w-full max-w-5xl animate-rise-in [animation-delay:280ms] md:mt-20">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -inset-x-10 -top-10 bottom-10 rounded-[3rem] bg-[radial-gradient(60%_60%_at_50%_30%,rgba(47,155,126,0.35),transparent_70%)] blur-2xl"
          />
          <AppFrame
            label="Voicecon dashboard showing a completed call with its recording, transcript, AI summary, sentiment and the workflows it triggered"
            path="/dashboard/calls"
            active="Calls"
            className="relative text-left"
          >
            <CallDetailScreen />
          </AppFrame>
        </div>
      </div>
    </section>
  )
}

const LOGOS = [
  { src: 'hubspot.png', name: 'HubSpot' },
  { src: 'slack.png', name: 'Slack' },
  { src: 'calender.png', name: 'Google Calendar' },
  { src: 'twilio.png', name: 'Twilio' },
  { src: 'gohightlevel.png', name: 'GoHighLevel' },
  { src: 'gmail.png', name: 'Gmail' },
  { src: 'stripe.png', name: 'Stripe' },
  { src: 'zapier.png', name: 'Zapier' },
  { src: 'teams.png', name: 'Microsoft Teams' },
  { src: 'gdrive.png', name: 'Google Drive' },
  { src: 'clickup.png', name: 'ClickUp' },
  { src: 'moday.png', name: 'Monday.com' },
  { src: 'trello.png', name: 'Trello' },
  { src: 'outlook.png', name: 'Outlook' },
  { src: 'telnyx.png', name: 'Telnyx' },
]

/** Scrolling strip of apps agents and workflows can act in. */
export function LogoStrip() {
  const row = (hidden: boolean) => (
    <ul className="flex shrink-0 items-center gap-3 pr-3" aria-hidden={hidden || undefined}>
      {LOGOS.map((logo) => (
        <li
          key={logo.name}
          className="flex items-center gap-2.5 rounded-full border border-white/10 bg-white/[0.05] py-1.5 pl-1.5 pr-4"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white p-1.5">
            <Image
              src={`/brand/apps-icons/${logo.src}`}
              alt=""
              width={20}
              height={20}
              className="h-5 w-5 object-contain"
            />
          </span>
          <span className="whitespace-nowrap text-sm font-medium text-white/75">{logo.name}</span>
        </li>
      ))}
    </ul>
  )

  return (
    <section aria-label="Apps Voicecon connects to" className="relative px-4 pb-8 sm:px-6">
      <p className="text-center text-sm font-medium text-white/55">
        Your agents take action in the tools your team already uses
      </p>
      <div className="mx-auto mt-6 max-w-6xl overflow-hidden [mask-image:linear-gradient(90deg,transparent,black_12%,black_88%,transparent)]">
        <div className="flex w-max animate-marquee hover:[animation-play-state:paused] motion-reduce:animate-none">
          {row(false)}
          {row(true)}
        </div>
      </div>
    </section>
  )
}
