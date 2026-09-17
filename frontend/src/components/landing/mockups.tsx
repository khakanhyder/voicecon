import type { ReactNode } from 'react'
import {
  BarChart3,
  BookOpen,
  Bot,
  CheckCircle2,
  GitBranch,
  Hash,
  LayoutDashboard,
  MessageSquare,
  Mic,
  Pause,
  Phone,
  PhoneIncoming,
  Play,
  Plug,
  Sparkles,
  Wrench,
  type LucideIcon,
} from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * Product mockups for the marketing page, drawn from the real dashboard: the
 * #0F6A59 sidebar and its nav order, the workflow node accents from
 * lib/workflow/nodeTypes.ts, and the analytics page's cards. They are
 * decorative, so each frame exposes one text label to assistive tech and hides
 * its internals.
 */

const NAV: { name: string; icon: LucideIcon }[] = [
  { name: 'Dashboard', icon: LayoutDashboard },
  { name: 'Agents', icon: Bot },
  { name: 'Calls', icon: Phone },
  { name: 'Phone Numbers', icon: Hash },
  { name: 'Tools', icon: Wrench },
  { name: 'Knowledge Base', icon: BookOpen },
  { name: 'Workflows', icon: GitBranch },
  { name: 'Integrations', icon: Plug },
  { name: 'Analytics', icon: BarChart3 },
]

/** Browser chrome + app sidebar around a screen. */
export function AppFrame({
  label,
  path,
  active,
  children,
  className,
}: {
  label: string
  path: string
  active: string
  children: ReactNode
  className?: string
}) {
  return (
    <div
      role="img"
      aria-label={label}
      className={cn(
        'overflow-hidden rounded-2xl border border-white/15 bg-[#0c2626] shadow-[0_40px_120px_-40px_rgba(0,0,0,0.8)] ring-1 ring-black/20',
        className
      )}
    >
      <div aria-hidden="true" className="flex items-center gap-3 border-b border-white/10 px-4 py-2.5">
        <div className="flex gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-white/20" />
          <span className="h-2.5 w-2.5 rounded-full bg-white/20" />
          <span className="h-2.5 w-2.5 rounded-full bg-white/20" />
        </div>
        <div className="mx-auto flex min-w-0 max-w-xs flex-1 items-center justify-center truncate rounded-md bg-white/[0.07] px-3 py-1 text-[11px] text-white/55">
          app.voicecon.ai{path}
        </div>
        <span className="hidden w-10 sm:block" />
      </div>
      <div aria-hidden="true" className="flex bg-slate-50 text-slate-900">
        <aside className="hidden w-44 shrink-0 flex-col gap-0.5 bg-[#0F6A59] p-3 md:flex">
          <div className="mb-3 flex items-center gap-2 px-2 pt-1 text-sm font-bold text-white">
            <Mic className="h-4 w-4 text-brand-200" />
            Voicecon
          </div>
          {NAV.map(({ name, icon: Icon }) => (
            <div
              key={name}
              className={cn(
                'flex items-center gap-2 rounded-lg px-2 py-1.5 text-[11.5px]',
                name === active ? 'bg-white/15 font-medium text-white' : 'text-white/75'
              )}
            >
              <Icon className="h-3.5 w-3.5 shrink-0" strokeWidth={1.75} />
              <span className="truncate">{name}</span>
              {name === active && <span className="ml-auto h-1 w-1 rounded-full bg-white/80" />}
            </div>
          ))}
        </aside>
        <div className="min-w-0 flex-1">{children}</div>
      </div>
    </div>
  )
}

function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('rounded-xl border border-slate-200 bg-white p-3 shadow-sm', className)}>
      {children}
    </div>
  )
}

function Pill({ children, tone }: { children: ReactNode; tone: 'green' | 'amber' | 'rose' | 'slate' }) {
  const tones = {
    green: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
    amber: 'bg-amber-50 text-amber-700 ring-amber-200',
    rose: 'bg-rose-50 text-rose-700 ring-rose-200',
    slate: 'bg-slate-100 text-slate-600 ring-slate-200',
  }
  return (
    <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium ring-1', tones[tone])}>
      {children}
    </span>
  )
}

/* ─────────────────────────── Call detail (hero) ─────────────────────────── */

const WAVE = [4, 9, 14, 7, 18, 11, 22, 15, 8, 19, 26, 13, 9, 17, 24, 12, 6, 15, 21, 10, 16, 23, 9, 14, 7, 12, 19, 8, 13, 5]

export function CallDetailScreen() {
  return (
    <div className="space-y-3 p-3 sm:p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#0F6A59] text-white">
            <PhoneIncoming className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-[13px] font-semibold">Inbound call · Appointment Scheduler</p>
            <p className="text-[10.5px] text-slate-500">+1 (415) 555-0142 · 3m 42s</p>
          </div>
        </div>
        <Pill tone="green">Completed</Pill>
      </div>

      <Card className="flex items-center gap-3 py-2.5">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#0F6A59] text-white">
          <Pause className="h-3 w-3" fill="currentColor" />
        </span>
        <div className="flex h-7 flex-1 items-center gap-[3px] overflow-hidden">
          {WAVE.map((h, i) => (
            <span
              key={i}
              className={cn('w-[3px] shrink-0 rounded-full', i < 12 ? 'bg-[#0F6A59]' : 'bg-slate-300')}
              style={{ height: h }}
            />
          ))}
        </div>
        <span className="text-[10px] tabular-nums text-slate-500">1:27</span>
      </Card>

      <div className="grid gap-3 sm:grid-cols-[1.35fr_1fr]">
        <Card className="space-y-2">
          <p className="text-[11px] font-semibold text-slate-700">Transcript</p>
          <Bubble who="agent">Thanks for calling Harbor Dental, this is Ava. How can I help?</Bubble>
          <Bubble who="caller">Hi, I&apos;d like to book a cleaning next week.</Bubble>
          <Bubble who="agent">I have Tuesday at 10:00 or Thursday at 2:30. Which works?</Bubble>
          <Bubble who="caller">Thursday at 2:30, please.</Bubble>
        </Card>
        <div className="space-y-3">
          <Card>
            <p className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-700">
              <Sparkles className="h-3 w-3 text-[#0F6A59]" /> AI summary
            </p>
            <p className="mt-1.5 text-[10.5px] leading-relaxed text-slate-600">
              Caller booked a cleaning for Thursday at 2:30 PM and confirmed their contact number.
            </p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <Pill tone="green">Positive · 0.86</Pill>
              <Pill tone="slate">Intent: booking</Pill>
            </div>
          </Card>
          <Card>
            <p className="text-[11px] font-semibold text-slate-700">Workflow runs</p>
            <RunRow name="Post a call summary to Slack" />
            <RunRow name="Send qualified calls to HubSpot" />
          </Card>
        </div>
      </div>
    </div>
  )
}

function Bubble({ who, children }: { who: 'agent' | 'caller'; children: ReactNode }) {
  return (
    <div className={cn('flex', who === 'caller' && 'justify-end')}>
      <p
        className={cn(
          'max-w-[85%] rounded-xl px-2.5 py-1.5 text-[10.5px] leading-snug',
          who === 'agent' ? 'rounded-tl-sm bg-slate-100 text-slate-700' : 'rounded-tr-sm bg-[#0F6A59] text-white'
        )}
      >
        {children}
      </p>
    </div>
  )
}

function RunRow({ name }: { name: string }) {
  return (
    <div className="mt-1.5 flex items-center gap-1.5 text-[10.5px] text-slate-600">
      <CheckCircle2 className="h-3 w-3 shrink-0 text-emerald-600" />
      <span className="truncate">{name}</span>
    </div>
  )
}

/* ─────────────────────────────── Agent editor ─────────────────────────────── */

export function AgentScreen() {
  return (
    <div className="grid gap-3 p-3 sm:p-4 lg:grid-cols-[1.4fr_1fr]">
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-[13px] font-semibold">Customer Support Agent</p>
          <Pill tone="green">Active</Pill>
        </div>
        <Card className="space-y-2.5">
          <Field label="First message" value="Hi, thanks for calling! How can I help you today?" />
          <div>
            <p className="text-[10px] font-medium uppercase tracking-wide text-slate-500">System prompt</p>
            <div className="mt-1 rounded-lg border border-slate-200 bg-slate-50 p-2 text-[10.5px] leading-relaxed text-slate-600">
              You are a friendly support agent. Answer from the linked knowledge base, collect the
              caller&apos;s order number, and transfer to a human when asked.
            </div>
          </div>
        </Card>
        <div className="grid grid-cols-3 gap-2">
          <Stack label="Model" provider="OpenAI" detail="gpt-5.4-nano" />
          <Stack label="Voice" provider="ElevenLabs" detail="Rachel · Calm" />
          <Stack label="Transcriber" provider="Deepgram" detail="nova-2 · en" />
        </div>
        <Card className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <Toggle label="Barge-in" on />
          <Toggle label="Sentiment analysis" on />
          <Toggle label="Noise reduction" on />
        </Card>
      </div>
      <Card className="flex flex-col">
        <p className="text-[11px] font-semibold text-slate-700">Test call</p>
        <div className="mt-3 flex flex-col items-center gap-2">
          <span className="relative flex h-14 w-14 items-center justify-center rounded-full bg-[#0F6A59] text-white">
            <span className="absolute inset-0 animate-ping rounded-full bg-[#0F6A59]/30 motion-reduce:animate-none" />
            <Mic className="relative h-5 w-5" />
          </span>
          <p className="text-[10px] text-slate-500">Live · 00:48</p>
        </div>
        <div className="mt-3 space-y-2">
          <Bubble who="agent">Hi, thanks for calling! How can I help you today?</Bubble>
          <Bubble who="caller">Where is my order 10482?</Bubble>
          <Bubble who="agent">It shipped yesterday and should arrive Friday.</Bubble>
        </div>
        <div className="mt-3 border-t border-slate-100 pt-2 text-[10px] text-slate-500">
          Knowledge base: <span className="font-medium text-slate-700">Shipping policy.pdf</span>
        </div>
      </Card>
    </div>
  )
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <div className="mt-1 truncate rounded-lg border border-slate-200 px-2 py-1.5 text-[10.5px] text-slate-700">
        {value}
      </div>
    </div>
  )
}

function Stack({ label, provider, detail }: { label: string; provider: string; detail: string }) {
  return (
    <Card className="p-2.5">
      <p className="text-[9.5px] font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-0.5 truncate text-[11px] font-semibold">{provider}</p>
      <p className="truncate text-[10px] text-slate-500">{detail}</p>
    </Card>
  )
}

function Toggle({ label, on }: { label: string; on?: boolean }) {
  return (
    <span className="flex items-center gap-1.5 text-[10.5px] text-slate-600">
      <span className={cn('flex h-3.5 w-6 items-center rounded-full p-0.5', on ? 'justify-end bg-[#0F6A59]' : 'bg-slate-300')}>
        <span className="h-2.5 w-2.5 rounded-full bg-white" />
      </span>
      {label}
    </span>
  )
}

/* ───────────────────────────── Workflow canvas ───────────────────────────── */

type NodeSpec = { title: string; summary: string; icon: LucideIcon; accent: string }

function FlowNode({ node, className }: { node: NodeSpec; className?: string }) {
  const Icon = node.icon
  return (
    <div className={cn('flex w-full items-start gap-2 rounded-xl border border-slate-200 bg-white p-2.5 shadow-sm', className)}>
      <span className={cn('flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-white', node.accent)}>
        <Icon className="h-3.5 w-3.5" />
      </span>
      <div className="min-w-0">
        <p className="truncate text-[11px] font-semibold leading-tight">{node.title}</p>
        <p className="mt-0.5 truncate text-[10px] text-slate-500">{node.summary}</p>
      </div>
    </div>
  )
}

function Connector({ className }: { className?: string }) {
  return <span className={cn('mx-auto block h-5 w-px bg-slate-300', className)} />
}

export function WorkflowScreen() {
  return (
    <div
      className="relative p-4 sm:p-6"
      style={{
        backgroundImage: 'radial-gradient(rgb(203 213 225) 1px, transparent 1px)',
        backgroundSize: '16px 16px',
      }}
    >
      <div className="mx-auto flex max-w-md flex-col items-stretch">
        <FlowNode
          className="mx-auto max-w-[240px]"
          node={{ title: 'Trigger', summary: 'Call completed', icon: Play, accent: 'bg-emerald-500' }}
        />
        <Connector />
        <FlowNode
          className="mx-auto max-w-[240px]"
          node={{ title: 'Branch', summary: 'sentiment equals negative', icon: GitBranch, accent: 'bg-amber-500' }}
        />
        <div className="mx-auto flex w-full max-w-[240px] border-t border-slate-200 text-[9px] font-semibold uppercase tracking-wide">
          <span className="flex-1 py-1 text-center text-emerald-600">True</span>
          <span className="flex-1 py-1 text-center text-rose-600">False</span>
        </div>
        <div className="relative grid grid-cols-2 gap-3">
          <span className="absolute left-1/4 right-1/4 top-0 h-px bg-slate-300" />
          <div className="flex flex-col">
            <Connector />
            <FlowNode node={{ title: 'Integration', summary: 'Slack · Send message', icon: Plug, accent: 'bg-indigo-500' }} />
          </div>
          <div className="flex flex-col">
            <Connector />
            <FlowNode node={{ title: 'AI Response', summary: 'Draft follow-up email', icon: Sparkles, accent: 'bg-violet-500' }} />
            <Connector />
            <FlowNode node={{ title: 'Integration', summary: 'HubSpot · Create contact', icon: Plug, accent: 'bg-indigo-500' }} />
          </div>
        </div>
      </div>
      <div className="absolute right-3 top-3 hidden items-center gap-1.5 rounded-full border border-emerald-200 bg-white px-2.5 py-1 text-[10px] font-medium text-emerald-700 shadow-sm sm:flex">
        <CheckCircle2 className="h-3 w-3" /> Last run succeeded
      </div>
    </div>
  )
}

/* ──────────────────────────────── Analytics ──────────────────────────────── */

const BARS = [38, 52, 44, 61, 57, 72, 66, 80, 74, 88, 69, 92]

export function AnalyticsScreen() {
  return (
    <div className="space-y-3 p-3 sm:p-4">
      <div className="flex items-center justify-between">
        <p className="text-[13px] font-semibold">Analytics</p>
        <span className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-[10px] text-slate-600">Export CSV</span>
      </div>
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        <Stat label="Total Calls" value="1,284" />
        <Stat label="Avg Duration" value="2m 51s" />
        <Stat label="Success Rate" value="94.2%" />
        <Stat label="Total Cost" value="$212.40" />
      </div>
      <div className="grid gap-3 sm:grid-cols-[1.5fr_1fr]">
        <Card>
          <p className="text-[11px] font-semibold text-slate-700">Call Outcomes</p>
          <div className="mt-3 flex h-24 items-end gap-1.5">
            {BARS.map((h, i) => (
              <span
                key={i}
                className="flex-1 rounded-t bg-gradient-to-t from-[#0F6A59] to-[#2f9b7e]"
                style={{ height: `${h}%` }}
              />
            ))}
          </div>
          <div className="mt-2 flex gap-3 text-[10px] text-slate-500">
            <Legend color="bg-[#0F6A59]" label="Completed" />
            <Legend color="bg-amber-400" label="Missed" />
            <Legend color="bg-rose-400" label="Failed" />
          </div>
        </Card>
        <Card className="space-y-2">
          <p className="text-[11px] font-semibold text-slate-700">Sentiment Analysis</p>
          <Meter label="Positive" pct={68} color="bg-emerald-500" />
          <Meter label="Neutral" pct={24} color="bg-slate-400" />
          <Meter label="Negative" pct={8} color="bg-rose-500" />
          <p className="pt-1 text-[11px] font-semibold text-slate-700">Top Performing Agents</p>
          <p className="flex justify-between text-[10.5px] text-slate-600">
            <span className="truncate">Appointment Scheduler</span> <span>612</span>
          </p>
          <p className="flex justify-between text-[10.5px] text-slate-600">
            <span className="truncate">Customer Support Agent</span> <span>438</span>
          </p>
        </Card>
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Card className="p-2.5">
      <p className="text-[10px] text-slate-500">{label}</p>
      <p className="mt-0.5 text-sm font-bold tabular-nums">{value}</p>
    </Card>
  )
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className={cn('h-2 w-2 rounded-sm', color)} /> {label}
    </span>
  )
}

function Meter({ label, pct, color }: { label: string; pct: number; color: string }) {
  return (
    <div>
      <div className="flex justify-between text-[10px] text-slate-500">
        <span>{label}</span>
        <span className="tabular-nums">{pct}%</span>
      </div>
      <div className="mt-1 h-1.5 rounded-full bg-slate-100">
        <div className={cn('h-full rounded-full', color)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

/* ─────────────────────────────── Calls list ─────────────────────────────── */

const CALLS = [
  { agent: 'Appointment Scheduler', number: '+1 (415) 555-0142', dur: '3m 42s', sentiment: 'Positive', tone: 'green' as const, summary: 'Booked a cleaning for Thursday 2:30 PM.' },
  { agent: 'Customer Support Agent', number: '+1 (212) 555-0198', dur: '1m 58s', sentiment: 'Neutral', tone: 'slate' as const, summary: 'Asked for order status; shipped, arriving Friday.' },
  { agent: 'Sales Qualification Agent', number: '+44 20 7946 0321', dur: '5m 06s', sentiment: 'Positive', tone: 'green' as const, summary: 'Qualified lead, 40 seats, wants a demo next week.' },
  { agent: 'Customer Support Agent', number: '+1 (646) 555-0117', dur: '2m 20s', sentiment: 'Negative', tone: 'rose' as const, summary: 'Damaged item reported; transferred to a human.' },
]

export function CallsScreen() {
  return (
    <div className="space-y-3 p-3 sm:p-4">
      <div className="flex items-center justify-between">
        <p className="text-[13px] font-semibold">Calls</p>
        <div className="flex gap-1.5">
          <Pill tone="slate">All agents</Pill>
          <Pill tone="slate">Last 7 days</Pill>
        </div>
      </div>
      <Card className="divide-y divide-slate-100 p-0">
        {CALLS.map((c) => (
          <div key={c.number} className="flex items-start gap-2.5 p-2.5">
            <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-500">
              <MessageSquare className="h-3.5 w-3.5" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                <p className="truncate text-[11px] font-semibold">{c.agent}</p>
                <p className="text-[10px] text-slate-500">{c.number}</p>
              </div>
              <p className="mt-0.5 truncate text-[10.5px] text-slate-600">{c.summary}</p>
            </div>
            <div className="flex shrink-0 flex-col items-end gap-1">
              <Pill tone={c.tone}>{c.sentiment}</Pill>
              <span className="text-[10px] tabular-nums text-slate-500">{c.dur}</span>
            </div>
          </div>
        ))}
      </Card>
    </div>
  )
}
