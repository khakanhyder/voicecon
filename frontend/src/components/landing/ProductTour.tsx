'use client'

import { useRef, useState, type KeyboardEvent } from 'react'
import { BarChart3, Bot, GitBranch, Phone } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Accent, Section, SectionHeading } from './primitives'
import { Reveal } from './Reveal'
import { AgentScreen, AnalyticsScreen, AppFrame, CallsScreen, WorkflowScreen } from './mockups'

const TABS = [
  {
    id: 'agents',
    label: 'Agents',
    icon: Bot,
    path: '/dashboard/agents',
    nav: 'Agents',
    title: 'Configure and test an agent in one screen',
    body: 'Set the prompt, model, voice and transcriber, link knowledge bases, then call your agent straight from the browser to hear how it sounds before it goes live.',
    screen: AgentScreen,
    alt: 'Agent editor with the system prompt, OpenAI model, ElevenLabs voice, Deepgram transcriber and a live browser test call',
  },
  {
    id: 'workflows',
    label: 'Workflows',
    icon: GitBranch,
    path: '/dashboard/workflows',
    nav: 'Workflows',
    title: 'Automate what happens after the call',
    body: 'Drag triggers, logic, AI and integration steps onto the canvas. Test run it, then check each execution in the run history.',
    screen: WorkflowScreen,
    alt: 'Workflow canvas: a call-completed trigger branches on sentiment to post in Slack or draft a follow-up and create a HubSpot contact',
  },
  {
    id: 'calls',
    label: 'Calls',
    icon: Phone,
    path: '/dashboard/calls',
    nav: 'Calls',
    title: 'Understand every conversation',
    body: 'Browse calls by agent and date. Each call has its recording, transcript, AI summary and sentiment, so you can check quality without listening to every minute.',
    screen: CallsScreen,
    alt: 'Call log listing recent calls with agent, caller number, AI summary, sentiment and duration',
  },
  {
    id: 'analytics',
    label: 'Analytics',
    icon: BarChart3,
    path: '/dashboard/analytics',
    nav: 'Analytics',
    title: 'Measure what your agents deliver',
    body: 'Total calls, average duration, success rate and cost at a glance, with call outcomes, sentiment and top agents. Export to CSV whenever you need it.',
    screen: AnalyticsScreen,
    alt: 'Analytics dashboard with total calls, average duration, success rate, total cost, call outcomes and sentiment breakdown',
  },
] as const

export function ProductTour() {
  const [active, setActive] = useState(0)
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([])
  const tab = TABS[active]
  const Screen = tab.screen

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const moves: Record<string, number> = {
      ArrowRight: active + 1,
      ArrowLeft: active - 1,
      Home: 0,
      End: TABS.length - 1,
    }
    if (!(e.key in moves)) return
    e.preventDefault()
    const next = (moves[e.key] + TABS.length) % TABS.length
    setActive(next)
    tabRefs.current[next]?.focus()
  }

  return (
    <Section id="product" labelledBy="tour-title" className="border-y border-white/[0.06] bg-black/[0.12]">
      <SectionHeading
        id="tour-title"
        eyebrow="Product tour"
        title={
          <>
            One dashboard, <Accent>from first call to insight</Accent>
          </>
        }
        description="Take a look at the Voicecon workspace your team will use every day."
      />

      <Reveal className="mt-12">
        <div
          role="tablist"
          aria-label="Product areas"
          onKeyDown={onKeyDown}
          className="mx-auto grid max-w-2xl grid-cols-2 gap-1.5 rounded-2xl border border-white/10 bg-white/[0.04] p-1.5 sm:flex sm:rounded-full"
        >
          {TABS.map((t, i) => (
            <button
              key={t.id}
              ref={(el) => {
                tabRefs.current[i] = el
              }}
              id={`tab-${t.id}`}
              type="button"
              role="tab"
              aria-selected={i === active}
              aria-controls={`panel-${t.id}`}
              tabIndex={i === active ? 0 : -1}
              onClick={() => setActive(i)}
              className={cn(
                'flex flex-1 items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-200 sm:rounded-full',
                i === active
                  ? 'bg-gradient-to-r from-brand-400 to-brand-600 text-white shadow-[0_8px_24px_-8px_rgba(47,155,126,0.7)]'
                  : 'text-white/65 hover:bg-white/[0.06] hover:text-white'
              )}
            >
              <t.icon className="h-4 w-4" aria-hidden="true" />
              {t.label}
            </button>
          ))}
        </div>

        <div
          id={`panel-${tab.id}`}
          role="tabpanel"
          aria-labelledby={`tab-${tab.id}`}
          className="mt-10 grid grid-cols-1 items-center gap-8 lg:grid-cols-[0.8fr_1.6fr] lg:gap-12"
        >
          <div key={`copy-${tab.id}`} className="animate-rise-in text-center lg:text-left">
            <h3 className="text-2xl font-bold tracking-[-0.01em] text-white sm:text-[1.75rem]">{tab.title}</h3>
            <p className="mt-4 text-base leading-relaxed text-white/65">{tab.body}</p>
          </div>
          <div key={`screen-${tab.id}`} className="min-w-0 animate-rise-in">
            <AppFrame label={tab.alt} path={tab.path} active={tab.nav}>
              <Screen />
            </AppFrame>
          </div>
        </div>
      </Reveal>
    </Section>
  )
}
