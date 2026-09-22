import Image from 'next/image'
import {
  CalendarCheck,
  Check,
  Headphones,
  KeyRound,
  Mail,
  PackageSearch,
  ShieldCheck,
  UserRoundCheck,
  Webhook,
  type LucideProps,
} from 'lucide-react'
import { Accent, GlassCard, IconWell, ROUTES, Section, SectionHeading } from './primitives'
import { Reveal } from './Reveal'

/** The 35 connectors in the integrations catalog, grouped for scanning. */
const CATEGORIES = [
  { name: 'CRM & sales', apps: ['HubSpot', 'Salesforce', 'Pipedrive', 'GoHighLevel'] },
  { name: 'Scheduling', apps: ['Google Calendar', 'Calendly', 'Cal.com'] },
  {
    name: 'Messaging & telephony',
    apps: ['Slack', 'Microsoft Teams', 'WhatsApp', 'Twilio', 'Telnyx', 'Vonage', 'SendGrid', 'Gmail', 'Outlook', 'Custom SMTP'],
  },
  { name: 'Support', apps: ['Zendesk', 'Intercom'] },
  {
    name: 'Productivity',
    apps: ['Google Sheets', 'Google Drive', 'Notion', 'Airtable', 'ClickUp', 'Monday.com', 'Trello'],
  },
  { name: 'Automation', apps: ['Zapier', 'Make'] },
  { name: 'Storage & data', apps: ['AWS S3', 'Google Cloud Storage', 'Azure Blob Storage', 'Cloudflare R2', 'Supabase'] },
  { name: 'Payments & monitoring', apps: ['Stripe', 'Langfuse'] },
]

const LOGO: Record<string, string> = {
  HubSpot: 'hubspot.png',
  Salesforce: 'salesforce.svg',
  Pipedrive: 'pipedrive.png',
  GoHighLevel: 'gohightlevel.png',
  'Google Calendar': 'calender.png',
  Calendly: 'calendly.svg',
  'Cal.com': 'cal-com.png',
  Slack: 'slack.png',
  'Microsoft Teams': 'teams.png',
  WhatsApp: 'whatsapp.svg',
  Twilio: 'twilio.png',
  Telnyx: 'telnyx.png',
  Vonage: 'vonage.svg',
  SendGrid: 'sendgrid.svg',
  Gmail: 'gmail.png',
  Outlook: 'outlook.png',
  Zendesk: 'zendesk.svg',
  Intercom: 'intercom.svg',
  'Google Sheets': 'google-sheets.svg',
  'Google Drive': 'gdrive.png',
  Notion: 'notion.svg',
  Airtable: 'airtable.svg',
  ClickUp: 'clickup.png',
  'Monday.com': 'moday.png',
  Trello: 'trello.png',
  Zapier: 'zapier.png',
  Make: 'make.svg',
  'AWS S3': 'aws-s3.svg',
  'Google Cloud Storage': 'google-cloud-storage.svg',
  'Azure Blob Storage': 'azure.svg',
  'Cloudflare R2': 'cloudflare.svg',
  Supabase: 'supabase.svg',
  Stripe: 'stripe.png',
  Langfuse: 'langfuse.png',
}

export function Integrations() {
  return (
    <Section id="integrations" labelledBy="integrations-title">
      <SectionHeading
        id="integrations-title"
        eyebrow="Integrations"
        title={
          <>
            <Accent>35 connectors</Accent> ready for your agents and workflows
          </>
        }
        description="Connect an app once and use it everywhere: as a tool during calls or as a step in a workflow. Popular apps like HubSpot, Salesforce, Google, Slack and Notion connect in one click with OAuth."
      />

      <div className="mt-14 columns-1 gap-5 sm:columns-2 lg:columns-4">
        {CATEGORIES.map((cat, i) => (
          <Reveal key={cat.name} delay={(i % 4) * 70} className="mb-5 break-inside-avoid">
            <GlassCard className="p-5">
              <h3 className="flex items-center justify-between text-sm font-semibold text-white">
                {cat.name}
                <span className="rounded-full bg-white/[0.07] px-2 py-0.5 text-xs font-medium text-white/55">
                  {cat.apps.length}
                </span>
              </h3>
              <ul className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-1">
                {cat.apps.map((app) => (
                  <li key={app} className="flex min-w-0 items-center gap-2.5 text-sm text-white/75">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white p-1">
                      {LOGO[app] ? (
                        // unoptimized: the optimizer refuses SVG, and these are tiny static files anyway.
                        <Image src={`/brand/apps-icons/${LOGO[app]}`} alt="" width={20} height={20} unoptimized className="h-5 w-5 object-contain" />
                      ) : (
                        // Brandless connectors (Custom SMTP) get a generic mark.
                        <Mail className="h-4 w-4 text-slate-600" aria-hidden="true" />
                      )}
                    </span>
                    {app}
                  </li>
                ))}
              </ul>
            </GlassCard>
          </Reveal>
        ))}
      </div>

      <Reveal className="mt-3 grid gap-4 md:grid-cols-3">
        {[
          { icon: ShieldCheck, text: 'One-click OAuth for 10 popular apps, with API keys or webhook URLs for the rest.' },
          { icon: Webhook, text: 'Need something else? Call any REST API with an HTTP request step.' },
          { icon: KeyRound, text: 'Connections are shared across the workspace, so set them up once.' },
        ].map(({ icon: Icon, text }) => (
          <p key={text} className="flex items-start gap-3 rounded-2xl border border-white/[0.07] bg-white/[0.03] p-4 text-sm leading-relaxed text-white/70">
            <Icon className="mt-0.5 h-4 w-4 shrink-0 text-brand-300" aria-hidden="true" />
            {text}
          </p>
        ))}
      </Reveal>
      <p className="mt-6 text-center text-sm text-white/55">
        See every action each connector supports in the{' '}
        <a
          href="/docs/integrations/catalog"
          className="font-medium text-brand-200 underline decoration-brand-300/40 underline-offset-4 hover:decoration-brand-200"
        >
          integrations catalog
        </a>
        .
      </p>
    </Section>
  )
}

/** Support headset, drawn to match lucide's stroke style (this lucide-react predates its Headset icon). */
function HeadsetIcon({ strokeWidth = 2, size = 24, absoluteStrokeWidth: _a, ...props }: LucideProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M3 11h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-5Zm0 0a9 9 0 1 1 18 0m0 0v5a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3Z" />
      <path d="M21 16v2a4 4 0 0 1-4 4h-5" />
    </svg>
  )
}

const USE_CASES = [
  {
    icon: HeadsetIcon,
    title: 'Customer support',
    who: 'Support teams, e-commerce, SaaS',
    during: ['Answers questions from your help docs', 'Collects account or order details', 'Transfers to a person when asked'],
    after: 'Opens a Zendesk ticket and posts the summary to Slack.',
  },
  {
    icon: UserRoundCheck,
    title: 'Lead qualification',
    who: 'Sales teams, agencies, real estate',
    during: ['Answers inbound calls from new leads', 'Asks your qualifying questions', 'Captures name, need and budget'],
    after: 'Creates the contact in HubSpot, Salesforce or GoHighLevel.',
  },
  {
    icon: CalendarCheck,
    title: 'Appointment booking',
    who: 'Clinics, salons, home services',
    during: ['Finds open slots in your Google Calendar', 'Offers real times and confirms the choice', 'Books the appointment while the caller is on the line'],
    after: 'Texts a confirmation through Twilio and posts the booking to Slack.',
  },
  {
    icon: PackageSearch,
    title: 'Order status',
    who: 'Retail, restaurants, logistics',
    during: ['Checks the order through your own API', 'Explains delivery timing and policy', 'Escalates problems to your team'],
    after: 'Logs the call in Google Sheets or Airtable for follow-up.',
  },
]

export function UseCases() {
  return (
    <Section id="use-cases" labelledBy="usecases-title" className="border-y border-white/[0.06] bg-black/[0.12]">
      <SectionHeading
        id="usecases-title"
        eyebrow="Use cases"
        title={
          <>
            Built for teams that <Accent>live on the phone</Accent>
          </>
        }
        description="Each use case has a ready-made agent template, so you start from a working setup instead of a blank page."
      />
      <div className="mt-14 grid gap-5 md:grid-cols-2">
        {USE_CASES.map((u, i) => (
          <Reveal key={u.title} delay={(i % 2) * 90}>
            <GlassCard className="flex h-full flex-col p-6 sm:p-8">
              <div className="flex items-start gap-4">
                <IconWell className="h-12 w-12">
                  <u.icon className="h-5 w-5" strokeWidth={1.75} aria-hidden="true" />
                </IconWell>
                <div>
                  <h3 className="text-xl font-semibold text-white">{u.title}</h3>
                  <p className="mt-0.5 text-sm text-white/55">{u.who}</p>
                </div>
              </div>
              <p className="mt-6 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-white/45">
                <Headphones className="h-3.5 w-3.5" aria-hidden="true" /> On the call
              </p>
              <ul className="mt-3 flex-1 space-y-2">
                {u.during.map((d) => (
                  <li key={d} className="flex items-start gap-2.5 text-[15px] text-white/75">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-300" aria-hidden="true" />
                    {d}
                  </li>
                ))}
              </ul>
              <div className="mt-6 rounded-2xl border border-brand-300/20 bg-brand-500/10 p-4 text-sm leading-relaxed text-brand-100">
                <span className="font-semibold text-white">After the call: </span>
                {u.after}
              </div>
            </GlassCard>
          </Reveal>
        ))}
      </div>
      <p className="mt-10 text-center">
        <a
          href={ROUTES.register}
          className="text-sm font-medium text-brand-200 underline decoration-brand-300/40 underline-offset-4 hover:decoration-brand-200"
        >
          Start with a template, free for 30 days
        </a>
      </p>
    </Section>
  )
}
