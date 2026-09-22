import { ArrowRight } from 'lucide-react'
import { Accent, Logo, ROUTES, Section, SectionHeading, buttonClass } from './primitives'
import { Reveal } from './Reveal'
import { FaqList } from './FaqList'

const FAQS = [
  {
    q: 'What is Voicecon?',
    a: 'Voicecon is a platform for building AI voice agents that answer and make phone calls for your business. Each agent follows your instructions, answers from your documents, uses tools during the call, and triggers no-code workflows that update the apps your team works in.',
  },
  {
    q: 'Do I need to know how to code?',
    a: 'No. Agents, call flows and workflows are all set up in the dashboard with forms and a visual canvas, and you can start from ready-made templates. Developers can still use API keys, webhook triggers and HTTP request steps when they need to.',
  },
  {
    q: 'Which AI models and voices does Voicecon use?',
    a: 'Agents reason with OpenAI or Anthropic models, speak with ElevenLabs voices and transcribe callers in real time with Deepgram. You choose the model, voice, speed and language for each agent.',
  },
  {
    q: 'How do I get a phone number?',
    a: 'On a paid plan you can search for a number by country and area code and buy it from the dashboard, or connect your own Twilio or Telnyx account. Then assign the number to an agent and it starts answering calls.',
  },
  {
    q: 'Can I test an agent before it goes live?',
    a: 'Yes. Every agent has a test call panel that lets you talk to it from your browser, so you can hear the voice and refine the prompt before you connect a phone number.',
  },
  {
    q: 'What can I upload to the knowledge base?',
    a: 'PDF, Word (.docx), Excel (.xlsx, .xls), CSV, JSON, Markdown and plain text files up to 50 MB each, or text pasted directly. You can link several knowledge bases to one agent.',
  },
  {
    q: 'What happens after a call ends?',
    a: 'The call is saved with its recording, transcript, AI summary, sentiment and cost. Any workflow with a “call completed” trigger then runs, for example to create a CRM contact, post to Slack or log the call in Google Sheets.',
  },
  {
    q: 'How does the free trial work?',
    a: 'Create an account, add your company details and choose “Skip for now” on the pricing step to start a 30-day trial with no credit card. The trial includes 1 agent, 1 knowledge base, 2 workflows and 2 team members. Buying phone numbers requires a paid plan.',
  },
  {
    q: 'Can my team work in Voicecon together?',
    a: 'Yes. Invite teammates by email as admins, members or viewers, switch between multiple workspaces, and create scoped API keys for your own systems.',
  },
]

export function Faq() {
  return (
    <Section id="faq" labelledBy="faq-title" className="border-t border-white/[0.06] bg-black/[0.12]">
      <div className="grid grid-cols-1 gap-12 lg:grid-cols-[0.8fr_1.2fr] lg:gap-16">
        <div className="min-w-0 lg:sticky lg:top-28 lg:self-start">
          <SectionHeading
            id="faq-title"
            align="left"
            eyebrow="FAQ"
            title={
              <>
                Questions, <Accent>answered</Accent>
              </>
            }
            description={
              <>
                Can&apos;t find what you need? The{' '}
                <a
                  href={ROUTES.docs}
                  className="font-medium text-brand-200 underline decoration-brand-300/40 underline-offset-4 hover:decoration-brand-200"
                >
                  documentation
                </a>{' '}
                covers every feature step by step.
              </>
            }
          />
        </div>
        <Reveal className="divide-y divide-white/[0.08] rounded-3xl border border-white/[0.08] bg-white/[0.03]">
          <FaqList items={FAQS} />
        </Reveal>
      </div>
    </Section>
  )
}

export function FinalCta() {
  return (
    <section aria-labelledby="cta-title" className="relative px-4 py-20 sm:px-6 md:py-28">
      <Reveal className="relative mx-auto max-w-5xl overflow-hidden rounded-[2rem] border border-brand-300/25 bg-gradient-to-br from-[#1c5453] via-[#16403f] to-[#10302f] px-6 py-14 text-center shadow-[0_40px_120px_-40px_rgba(19,128,102,0.6)] sm:px-12 md:py-20">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 opacity-30 [background-image:linear-gradient(rgba(255,255,255,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.08)_1px,transparent_1px)] [background-size:44px_44px] [mask-image:radial-gradient(circle_at_50%_40%,black,transparent_75%)]"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-40 left-[calc(50%-10rem)] h-80 w-80 animate-glow-pulse rounded-full bg-[radial-gradient(circle,rgba(47,155,126,0.6),transparent_65%)] blur-2xl motion-reduce:animate-none"
        />
        <div className="relative">
          <h2 id="cta-title" className="mx-auto max-w-3xl text-balance text-[clamp(1.9rem,4.6vw,3.25rem)] font-bold leading-[1.1] tracking-[-0.02em] text-white">
            Put your first AI voice agent <Accent>on the phone this week</Accent>
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-base leading-relaxed text-white/70 sm:text-lg">
            Start from a template, test it in your browser and connect a number when you&apos;re ready.
            30 days free, no credit card.
          </p>
          <div className="mt-9 flex flex-col items-stretch justify-center gap-3 sm:flex-row sm:items-center">
            <a href={ROUTES.register} className={buttonClass('primary', 'lg', 'group')}>
              Start your free trial
              <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
            </a>
            <a href={ROUTES.quickstart} className={buttonClass('ghost', 'lg')}>
              Read the quickstart
            </a>
          </div>
        </div>
      </Reveal>
    </section>
  )
}

const FOOTER_COLUMNS = [
  {
    title: 'Product',
    links: [
      { label: 'Features', href: '/landing-page#features' },
      { label: 'Product tour', href: '/landing-page#product' },
      { label: 'Workflows', href: '/landing-page#workflows' },
      { label: 'Integrations', href: '/landing-page#integrations' },
      { label: 'Pricing', href: '/landing-page#pricing' },
    ],
  },
  {
    title: 'Solutions',
    links: [
      { label: 'Customer support', href: '/landing-page#use-cases' },
      { label: 'Lead qualification', href: '/landing-page#use-cases' },
      { label: 'Appointment booking', href: '/landing-page#use-cases' },
      { label: 'Order status', href: '/landing-page#use-cases' },
    ],
  },
  {
    title: 'Resources',
    links: [
      { label: 'Documentation', href: ROUTES.docs },
      { label: 'Quickstart', href: ROUTES.quickstart },
      { label: 'Integrations catalog', href: '/docs/integrations/catalog' },
      { label: 'API reference', href: ROUTES.api },
      { label: 'Troubleshooting', href: '/docs/troubleshooting' },
    ],
  },
  {
    title: 'Account',
    links: [
      { label: 'Start free trial', href: ROUTES.register },
      { label: 'Log in', href: ROUTES.login },
      { label: 'Reset password', href: '/forgot-password' },
      { label: 'FAQ', href: '/landing-page#faq' },
    ],
  },
  {
    title: 'Legal',
    links: [
      { label: 'Privacy Policy', href: '/privacy' },
      { label: 'Terms of Service', href: '/terms' },
      { label: 'Contact', href: 'mailto:support@voicecon.ai' },
    ],
  },
]

export function Footer() {
  return (
    <footer className="border-t border-white/10 px-4 pb-10 pt-16 sm:px-6">
      <div className="mx-auto max-w-6xl">
        <div className="grid gap-10 lg:grid-cols-[1.2fr_repeat(5,1fr)] lg:gap-8">
          <div className="max-w-xs">
            <a href="/landing-page" aria-label="Voicecon home" className="inline-block rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-200">
              <Logo />
            </a>
            <p className="mt-4 text-sm leading-relaxed text-white/55">
              AI voice agents that answer your calls and finish the work with no-code workflows.
            </p>
            <a
              href="https://www.linkedin.com/company/voicecon-ai/"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Voicecon on LinkedIn (opens in a new tab)"
              className="mt-5 inline-flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/5 text-white/70 transition-colors hover:border-brand-300/40 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-200"
            >
              <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4" aria-hidden="true">
                <path d="M4.98 3.5C4.98 4.88 3.87 6 2.5 6S0 4.88 0 3.5 1.12 1 2.5 1 4.98 2.12 4.98 3.5zM.24 8h4.52v13.5H.24V8zm7.5 0h4.33v1.85h.06c.6-1.14 2.08-2.35 4.28-2.35 4.58 0 5.42 3.01 5.42 6.93v8.07h-4.52v-7.15c0-1.71-.03-3.9-2.38-3.9-2.38 0-2.75 1.86-2.75 3.78v7.27H7.74V8z" />
              </svg>
            </a>
          </div>
          <div className="grid grid-cols-2 gap-8 sm:grid-cols-3 md:grid-cols-5 lg:col-span-5">
            {FOOTER_COLUMNS.map((col) => (
              <nav key={col.title} aria-label={col.title}>
                <h3 className="text-sm font-semibold text-white">{col.title}</h3>
                <ul className="mt-4 space-y-3">
                  {col.links.map((link) => (
                    <li key={link.label}>
                      <a href={link.href} className="text-sm text-white/55 transition-colors hover:text-white focus-visible:text-white focus-visible:outline-none">
                        {link.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </nav>
            ))}
          </div>
        </div>
        <div className="mt-14 flex flex-col items-center justify-between gap-3 border-t border-white/10 pt-6 text-sm text-white/45 sm:flex-row">
          <p>© {new Date().getFullYear()} Voicecon.ai. All rights reserved.</p>
          <p>Built for businesses that run on phone calls.</p>
        </div>
      </div>
    </footer>
  )
}
