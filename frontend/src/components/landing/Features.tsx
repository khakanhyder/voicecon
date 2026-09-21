import Image from 'next/image'
import {
  AudioLines,
  BarChart3,
  BookOpenText,
  Bot,
  FileText,
  Hash,
  MessagesSquare,
  UsersRound,
  Waypoints,
  Wrench,
} from 'lucide-react'
import { Accent, GlassCard, IconWell, Section, SectionHeading } from './primitives'
import { Reveal } from './Reveal'

const PILLARS = [
  {
    art: '/landing/01-voice-to-voice.gif',
    artScale: 'scale-[1.3]',
    title: 'Voice to voice',
    body: 'Callers speak naturally and your agent answers in a lifelike voice. They can interrupt mid-sentence, and it listens, keeps the context and replies.',
    points: ['Real-time speech recognition by Deepgram', 'OpenAI or Anthropic models do the reasoning', 'Natural ElevenLabs voices'],
  },
  {
    art: '/landing/02-voice-to-action.gif',
    // The app icons reach the GIF's right edge, so a 1.3 zoom clips them.
    artScale: 'scale-[1.12]',
    title: 'Voice to action',
    body: 'Your agents do more than talk. During the call they transfer, text or look things up, and when it ends a workflow updates your CRM, books the meeting or alerts your team.',
    points: ['Tools the agent calls during a live conversation', 'Workflows that start when a call ends', 'Actions in 35 connected apps'],
  },
]

export function Pillars() {
  return (
    <Section labelledBy="pillars-title">
      <SectionHeading
        id="pillars-title"
        eyebrow="Why Voicecon"
        title={
          <>
            A conversation that <Accent>ends with a result</Accent>
          </>
        }
        description="Most voice bots stop when the call ends. Voicecon connects the conversation to the systems where your work actually happens."
      />
      <div className="mt-14 grid gap-6 md:grid-cols-2">
        {PILLARS.map((p, i) => (
          <Reveal key={p.title} delay={i * 100}>
            <GlassCard className="flex h-full flex-col items-center p-8 text-center sm:p-10">
              <div className="h-36 w-36 overflow-hidden rounded-[30px]">
                <Image
                  src={p.art}
                  alt=""
                  width={144}
                  height={144}
                  unoptimized
                  className={`h-full w-full ${p.artScale} object-contain [filter:brightness(1.55)_contrast(1.05)_saturate(1.15)]`}
                />
              </div>
              <h3 className="mt-6 text-[13px] font-bold uppercase tracking-[0.1em] text-white">{p.title}</h3>
              <p className="mt-3 max-w-md text-[15px] leading-relaxed text-white/65">{p.body}</p>
              <ul className="mt-6 w-full max-w-sm space-y-2 text-left">
                {p.points.map((point) => (
                  <li
                    key={point}
                    className="flex items-center gap-2.5 rounded-xl border border-white/[0.07] bg-white/[0.03] px-3.5 py-2.5 text-sm text-white/80"
                  >
                    <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-brand-300" aria-hidden="true" />
                    {point}
                  </li>
                ))}
              </ul>
            </GlassCard>
          </Reveal>
        ))}
      </div>
    </Section>
  )
}

const FEATURES = [
  {
    icon: Bot,
    title: 'Voice agents',
    body: 'Write the prompt and first message, then pick the model, voice and transcriber. Start from a ready-made template for support, sales, scheduling, order status or lead capture.',
  },
  {
    icon: Waypoints,
    title: 'Visual call flows',
    body: 'Lay out the conversation on a canvas: greet, ask questions (by voice or keypad), branch on the answer, transfer or end the call.',
  },
  {
    icon: BookOpenText,
    title: 'Knowledge base',
    body: 'Upload PDFs, Word files, spreadsheets, CSV, JSON, Markdown or plain text. Agents search them to answer with your facts, not guesses.',
  },
  {
    icon: Hash,
    title: 'Phone numbers',
    body: 'Search and buy numbers by country and area code, or bring your own Twilio or Telnyx account. Assign a number to an agent and it answers calls.',
  },
  {
    icon: Wrench,
    title: 'Tools during the call',
    body: 'Let agents transfer calls, send SMS, press keypad tones, leave voicemails, query a knowledge base or run a workflow in the middle of the conversation.',
  },
  {
    icon: FileText,
    title: 'Recordings & transcripts',
    body: 'Every call is saved with its recording and full transcript. You also get an AI summary, sentiment score, intent and a cost breakdown.',
  },
  {
    icon: BarChart3,
    title: 'Analytics',
    body: 'Track total calls, average duration, success rate and cost. See call outcomes, sentiment trends and your top agents, then export to CSV.',
  },
  {
    icon: MessagesSquare,
    title: 'Website chat widget',
    body: 'Put the same agent on your website with one script tag. Set the greeting, colours and position to match your brand.',
  },
  {
    icon: UsersRound,
    title: 'Workspaces & teams',
    body: 'Invite teammates as owners, admins, members or viewers, run several workspaces, and create scoped API keys for your own systems.',
  },
]

export function Features() {
  return (
    <Section id="features" labelledBy="features-title">
      <SectionHeading
        id="features-title"
        eyebrow="Platform"
        title={
          <>
            Everything you need to run <Accent>AI phone agents</Accent>
          </>
        }
        description="From the first prompt to the monthly report, Voicecon covers building, deploying and improving voice agents in one dashboard."
      />
      <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((f, i) => (
          <Reveal key={f.title} delay={(i % 3) * 80}>
            <GlassCard className="h-full p-6 sm:p-7">
              <IconWell>
                <f.icon className="h-5 w-5" strokeWidth={1.75} aria-hidden="true" />
              </IconWell>
              <h3 className="mt-5 text-lg font-semibold text-white">{f.title}</h3>
              <p className="mt-2 text-[15px] leading-relaxed text-white/65">{f.body}</p>
            </GlassCard>
          </Reveal>
        ))}
      </div>
      <Reveal className="mt-8 flex justify-center">
        <p className="inline-flex items-center gap-2 text-sm text-white/55">
          <AudioLines className="h-4 w-4 text-brand-300" aria-hidden="true" />
          Tune barge-in, silence timeouts, maximum call length and end-call phrases for each agent.
        </p>
      </Reveal>
    </Section>
  )
}
