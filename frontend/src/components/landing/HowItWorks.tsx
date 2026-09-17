import {
  Bot,
  Braces,
  CalendarClock,
  GitBranch,
  MessageCircleQuestion,
  PhoneCall,
  PhoneForwarded,
  PhoneOff,
  Play,
  Plug,
  Sparkles,
  Split,
  UploadCloud,
  Volume2,
  Webhook,
  type LucideIcon,
} from 'lucide-react'
import { Accent, GlassCard, IconWell, Section, SectionHeading } from './primitives'
import { Reveal } from './Reveal'

const STEPS = [
  {
    icon: Bot,
    title: 'Create your agent',
    body: 'Start from a template or a blank agent. Write how it should behave, choose its voice and set the first thing it says.',
  },
  {
    icon: UploadCloud,
    title: 'Give it knowledge and tools',
    body: 'Upload your policies, price lists and FAQs to a knowledge base. Add tools so it can transfer, text or run a workflow.',
  },
  {
    icon: PhoneCall,
    title: 'Connect a phone number',
    body: 'Test the agent in your browser, then buy a number or connect your Twilio or Telnyx account and assign it.',
  },
  {
    icon: GitBranch,
    title: 'Automate and improve',
    body: 'Trigger workflows when calls end, then use transcripts, summaries and analytics to refine the prompt.',
  },
]

export function HowItWorks() {
  return (
    <Section id="how-it-works" labelledBy="how-title">
      <SectionHeading
        id="how-title"
        eyebrow="How it works"
        title={
          <>
            From idea to <Accent>live phone agent</Accent> in four steps
          </>
        }
        description="No code or telephony setup required. Guided onboarding gets you from sign-up to your first test call."
      />
      <ol className="relative mt-14 grid gap-5 md:grid-cols-2 lg:grid-cols-4">
        <span
          aria-hidden="true"
          className="pointer-events-none absolute left-[12%] right-[12%] top-[46px] hidden h-px bg-gradient-to-r from-transparent via-brand-300/40 to-transparent lg:block"
        />
        {STEPS.map((step, i) => (
          <Reveal as="li" key={step.title} delay={i * 90}>
            <GlassCard className="h-full p-6">
              <div className="flex items-center justify-between">
                <IconWell className="relative bg-[#15413f]">
                  <step.icon className="h-5 w-5" strokeWidth={1.75} aria-hidden="true" />
                </IconWell>
                <span className="text-4xl font-bold tabular-nums text-white/10" aria-hidden="true">
                  0{i + 1}
                </span>
              </div>
              <h3 className="mt-5 text-lg font-semibold text-white">
                <span className="sr-only">Step {i + 1}: </span>
                {step.title}
              </h3>
              <p className="mt-2 text-[15px] leading-relaxed text-white/65">{step.body}</p>
            </GlassCard>
          </Reveal>
        ))}
      </ol>
    </Section>
  )
}

const TRIGGERS: { icon: LucideIcon; label: string; detail: string }[] = [
  { icon: PhoneOff, label: 'Call completed', detail: 'Runs automatically when one of your agents finishes a call' },
  { icon: CalendarClock, label: 'Schedule', detail: 'Every N minutes, daily, weekly, monthly or cron, in your timezone' },
  { icon: Webhook, label: 'Webhook', detail: 'A unique URL your website, form or backend can post to' },
  { icon: Play, label: 'Manual', detail: 'Run it on demand, or let an agent call it as a tool' },
]

const NODE_GROUPS: { name: string; nodes: { icon: LucideIcon; label: string; accent: string }[] }[] = [
  {
    name: 'Conversation',
    nodes: [
      { icon: Volume2, label: 'Speak', accent: 'bg-blue-500' },
      { icon: MessageCircleQuestion, label: 'Ask Question', accent: 'bg-purple-500' },
      { icon: PhoneForwarded, label: 'Transfer Call', accent: 'bg-teal-500' },
      { icon: PhoneOff, label: 'End Call', accent: 'bg-rose-500' },
    ],
  },
  {
    name: 'Logic',
    nodes: [
      { icon: GitBranch, label: 'Branch', accent: 'bg-amber-500' },
      { icon: Split, label: 'Switch', accent: 'bg-yellow-500' },
      { icon: Braces, label: 'Set Fields', accent: 'bg-sky-500' },
      { icon: CalendarClock, label: 'Wait', accent: 'bg-slate-500' },
    ],
  },
  {
    name: 'Actions & AI',
    nodes: [
      { icon: Plug, label: 'Integration', accent: 'bg-indigo-500' },
      { icon: Webhook, label: 'HTTP request', accent: 'bg-cyan-500' },
      { icon: Sparkles, label: 'AI Response', accent: 'bg-violet-500' },
    ],
  },
]

const TEMPLATES = [
  'Post a call summary to Slack',
  'Send qualified calls to HubSpot',
  'Send a daily digest',
  'Route an incoming webhook',
]

export function Workflows() {
  return (
    <Section id="workflows" labelledBy="workflows-title" className="border-y border-white/[0.06] bg-black/[0.12]">
      <div className="grid grid-cols-1 items-start gap-12 lg:grid-cols-[1fr_1.05fr] lg:gap-16">
        <div className="min-w-0">
          <SectionHeading
            id="workflows-title"
            align="left"
            eyebrow="No-code workflows"
            title={
              <>
                Turn conversations into <Accent>automated follow-through</Accent>
              </>
            }
            description="Build automations on a visual canvas. Branch on what the caller said, let AI write the follow-up, and push the result into your apps. Every run is logged step by step."
          />
          <Reveal className="mt-8">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-white/50">Start from a template</p>
            <ul className="mt-3 flex flex-wrap gap-2">
              {TEMPLATES.map((t) => (
                <li
                  key={t}
                  className="rounded-full border border-white/10 bg-white/[0.05] px-3.5 py-1.5 text-sm text-white/80"
                >
                  {t}
                </li>
              ))}
            </ul>
          </Reveal>
          <Reveal className="mt-8 space-y-5">
            {NODE_GROUPS.map((group) => (
              <div key={group.name}>
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-white/50">{group.name}</p>
                <ul className="mt-2.5 flex flex-wrap gap-2">
                  {group.nodes.map((node) => (
                    <li
                      key={node.label}
                      className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] py-1 pl-1 pr-3 text-sm text-white/80"
                    >
                      <span className={`flex h-6 w-6 items-center justify-center rounded-md text-white ${node.accent}`}>
                        <node.icon className="h-3.5 w-3.5" aria-hidden="true" />
                      </span>
                      {node.label}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </Reveal>
        </div>

        <Reveal delay={120} className="min-w-0">
          <GlassCard interactive={false} className="p-5 sm:p-7">
            <h3 className="text-lg font-semibold text-white">Four ways to start a workflow</h3>
            <ul className="mt-5 divide-y divide-white/[0.07]">
              {TRIGGERS.map((t) => (
                <li key={t.label} className="flex items-start gap-4 py-3.5 first:pt-0 last:pb-0">
                  <IconWell className="h-10 w-10">
                    <t.icon className="h-[18px] w-[18px]" strokeWidth={1.75} aria-hidden="true" />
                  </IconWell>
                  <div className="min-w-0">
                    <p className="font-semibold text-white">{t.label}</p>
                    <p className="mt-0.5 text-sm leading-relaxed text-white/60">{t.detail}</p>
                  </div>
                </li>
              ))}
            </ul>
            <div className="mt-6 overflow-hidden rounded-2xl border border-white/10 bg-[#0a1f1f]">
              <div className="flex items-center justify-between border-b border-white/10 px-4 py-2 text-xs text-white/50">
                <span>Trigger from any system</span>
                <span className="font-mono">POST</span>
              </div>
              <pre className="overflow-x-auto p-4 font-mono text-[12.5px] leading-relaxed text-brand-100">
                <code>
                  <span className="text-white/45">$ </span>curl -X POST \{'\n'}
                  {'  '}https://api.voicecon.ai/api/v1/workflows/webhook/<span className="text-amber-300">{'{key}'}</span> \{'\n'}
                  {'  '}-H <span className="text-brand-300">&quot;Content-Type: application/json&quot;</span> \{'\n'}
                  {'  '}-d <span className="text-brand-300">&apos;{'{"phone": "+14155550142"}'}&apos;</span>
                </code>
              </pre>
            </div>
          </GlassCard>
        </Reveal>
      </div>
    </Section>
  )
}
