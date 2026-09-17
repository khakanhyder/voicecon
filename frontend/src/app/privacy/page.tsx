import type { Metadata } from 'next'
import { A, B, Callout, H3, LegalDocument, P, Table, UL, type LegalSection } from '@/components/legal/LegalDocument'
import { LEGAL } from '@/lib/legal'

export const metadata: Metadata = {
  metadataBase: new URL(LEGAL.website),
  title: 'Privacy Policy | Voicecon',
  description:
    'How Voicecon collects, uses, shares and protects personal information, including call recordings, transcripts and account data.',
  alternates: { canonical: '/privacy' },
}

const mail = <A href={`mailto:${LEGAL.contactEmail}`}>{LEGAL.contactEmail}</A>
const privacyMail = <A href={`mailto:${LEGAL.privacyEmail}`}>{LEGAL.privacyEmail}</A>

const SECTIONS: LegalSection[] = [
  {
    id: 'scope',
    title: 'Who we are and what this policy covers',
    body: (
      <>
        <P>
          Voicecon is a product of <B>{LEGAL.company}</B>, a limited liability company registered in the{' '}
          {LEGAL.jurisdiction} (&ldquo;Voicecon&rdquo;, &ldquo;we&rdquo;, &ldquo;us&rdquo;). We provide a platform
          for building AI voice agents, connecting them to phone numbers and business apps, and automating work
          with no-code workflows. This Privacy Policy explains how we handle personal information when you visit{' '}
          <A href={LEGAL.website}>voicecon.ai</A>, use the Voicecon application at{' '}
          <A href={LEGAL.appUrl}>app.voicecon.ai</A>, call the Voicecon API, or interact with an agent or chat
          widget that runs on Voicecon.
        </P>
        <P>We play two different roles, depending on whose data it is:</P>
        <UL>
          <li>
            <B>Account data.</B> For information about our customers and their team members (for example, names,
            email addresses and billing details), Voicecon decides how the data is used and acts as the{' '}
            <B>controller</B>.
          </li>
          <li>
            <B>Customer data.</B> For information our customers process through Voicecon (for example, the voices,
            phone numbers, transcripts and messages of the people who call or chat with their agents, and the
            documents they upload), our customer is the <B>controller</B>. Voicecon acts as a{' '}
            <B>processor</B> or <B>service provider</B> and processes that data only on the customer&apos;s behalf
            and according to their instructions.
          </li>
        </UL>
        <Callout title="Did you speak with a Voicecon-powered agent?">
          If you called or chatted with a business that uses Voicecon, that business controls your information.
          Please contact them first with questions or requests. If you can&apos;t reach them, email {mail} and we
          will pass your request on and help where we can.
        </Callout>
      </>
    ),
  },
  {
    id: 'information-we-collect',
    title: 'Information we collect',
    body: (
      <>
        <H3>Information you give us</H3>
        <UL>
          <li>
            <B>Account details:</B> your name, email address and password. We store only a salted bcrypt hash of
            your password, never the password itself. You can also add a profile photo, which we re-encode and
            strip of metadata such as location.
          </li>
          <li>
            <B>Sign-in with Google or Apple:</B> if you choose either, we receive your name, email address and a
            provider account identifier from that provider.
          </li>
          <li>
            <B>Company and onboarding details:</B> company name, industry, company size, website, your
            assistant&apos;s name, preferred language and what you want your assistant to do.
          </li>
          <li>
            <B>Workspace and team information:</B> workspace names, the email addresses of teammates you invite,
            and the roles you assign them.
          </li>
          <li>
            <B>Billing information:</B> your plan, subscription status and billing history. Card details are
            entered directly with our payment processor, Stripe. Voicecon does not receive or store full card
            numbers.
          </li>
          <li>
            <B>Content you create:</B> agent settings, prompts, greetings, call flows, workflows, tools, knowledge
            base files and text, chat widget settings and similar configuration.
          </li>
          <li>
            <B>Integration credentials:</B> the OAuth tokens, API keys and webhook URLs you provide to connect
            third-party apps. We encrypt these at rest.
          </li>
          <li>
            <B>Communications:</B> messages you send to support, and your email address if you join our waitlist
            or mailing list.
          </li>
        </UL>

        <H3>Information created when your agents are used</H3>
        <UL>
          <li>
            <B>Call data:</B> caller and called phone numbers, call times, duration, status and direction, audio
            recordings, transcripts, AI-generated summaries, detected sentiment, topics and intent, and per-call
            cost details.
          </li>
          <li>
            <B>Chat widget data:</B> messages exchanged with a website chat widget, a random visitor identifier
            stored in the visitor&apos;s browser so a conversation can continue, and the browser&apos;s user-agent
            string.
          </li>
          <li>
            <B>Workflow and tool data:</B> inputs, outputs and logs of workflow runs and tool calls, which can
            include information passed to or returned by connected apps.
          </li>
        </UL>

        <H3>Information collected automatically</H3>
        <UL>
          <li>
            <B>Technical and log data:</B> IP address, browser and device type, pages and API endpoints requested,
            timestamps and error details. We use it to operate, secure and troubleshoot the service, including
            rate limiting.
          </li>
          <li>
            <B>Browser storage:</B> see <A href="#cookies">Cookies and browser storage</A>.
          </li>
        </UL>
      </>
    ),
  },
  {
    id: 'how-we-use',
    title: 'How we use information',
    body: (
      <>
        <P>We use personal information to:</P>
        <UL>
          <li>provide, maintain and secure Voicecon, including answering and placing calls, running workflows and storing call history;</li>
          <li>create and verify accounts, including sending email verification codes, and manage workspaces and permissions;</li>
          <li>process subscriptions, free trials and usage against plan limits;</li>
          <li>send service messages such as security alerts, invitations, billing notices and changes to our terms;</li>
          <li>respond to support requests;</li>
          <li>monitor performance, fix problems and prevent fraud, abuse and violations of our <A href="/terms">Terms of Service</A>;</li>
          <li>send product news and marketing emails if you have signed up for them. You can unsubscribe at any time;</li>
          <li>comply with legal obligations and enforce our rights.</li>
        </UL>
        <Callout title="AI training">
          We do not use call recordings, transcripts, chat messages or knowledge base content to train our own or
          third-party AI models without your prior consent. We send that content to AI providers only to generate
          responses, transcriptions, voices, embeddings and summaries for your account. If we ever offer training
          as an option, it will be something you choose to opt in to.
        </Callout>
        <H3>Legal bases (EEA, UK and similar jurisdictions)</H3>
        <P>
          Where laws such as the GDPR apply, we rely on: <B>performance of a contract</B> to provide the service
          you signed up for; <B>legitimate interests</B> to secure, support and improve Voicecon and to send
          relevant service updates; <B>consent</B> where required, for example for marketing emails; and{' '}
          <B>legal obligation</B> where the law requires us to process or keep information.
        </P>
      </>
    ),
  },
  {
    id: 'ai-processing',
    title: 'AI processing of calls and messages',
    body: (
      <>
        <P>To run a voice or chat agent, Voicecon processes conversation content in real time:</P>
        <UL>
          <li>caller audio is sent to a speech-to-text provider to produce a live transcript;</li>
          <li>the transcript, the agent&apos;s instructions and any relevant knowledge base content are sent to a large language model provider to generate the next reply;</li>
          <li>the reply is sent to a text-to-speech provider to produce the agent&apos;s voice;</li>
          <li>after a call, the transcript is sent to a language model to create a summary and to detect sentiment, topics and intent;</li>
          <li>knowledge base documents are split into passages and converted into embeddings so agents can search them.</li>
        </UL>
        <P>
          AI output can be inaccurate. Summaries, sentiment and other insights are generated automatically and
          should be reviewed before important decisions are based on them. Voicecon does not use these outputs to
          make decisions that have legal or similarly significant effects on individuals. Customers decide how to
          use them.
        </P>
      </>
    ),
  },
  {
    id: 'sharing',
    title: 'How we share information',
    body: (
      <>
        <P>
          We do not sell personal information, and we do not share it for cross-context behavioural advertising.
          We share information only as described below.
        </P>
        <H3>Service providers</H3>
        <P>
          We use trusted providers to run Voicecon. They may process personal information only to provide their
          services to us.
        </P>
        <Table
          headers={['Provider', 'Purpose', 'Data involved']}
          rows={[
            ['OpenAI', 'Language model replies, summaries and knowledge base embeddings', 'Transcripts, prompts, knowledge base content'],
            ['Anthropic', 'Language model replies, when a customer selects an Anthropic model', 'Transcripts, prompts, knowledge base content'],
            ['Deepgram', 'Real-time speech-to-text', 'Caller audio'],
            ['ElevenLabs', 'Text-to-speech voices', 'Agent reply text'],
            ['Twilio and Telnyx', 'Phone numbers, calls and text messages', 'Phone numbers, call audio, SMS content'],
            ['Stripe', 'Payments and subscription billing', 'Billing contact and payment details'],
            ['Google and Apple', 'Optional sign-in, and email delivery through Google', 'Name, email address, account identifier, email content'],
            ['Mailchimp', 'Waitlist and marketing email', 'Email address'],
            ['Cloud hosting and storage providers', 'Hosting the application, databases and stored files', 'All data stored in Voicecon'],
          ]}
        />
        <H3>Apps you connect</H3>
        <P>
          When you connect an integration, such as a CRM, calendar, messaging tool or storage service, and
          configure an agent tool or workflow to use it, Voicecon sends the data you specify to that app. The
          app&apos;s own privacy policy governs how it handles that data.
        </P>
        <H3>Your workspace</H3>
        <P>
          Information in a workspace, including calls, recordings and transcripts, is visible to members of that
          workspace according to the roles the workspace owner and admins assign.
        </P>
        <H3>Legal and business reasons</H3>
        <UL>
          <li>to comply with law, regulation, legal process or an enforceable government request;</li>
          <li>to protect the rights, safety and property of Voicecon, our customers or others, including to prevent fraud and abuse;</li>
          <li>as part of a merger, acquisition, financing or sale of assets, subject to this policy&apos;s protections continuing to apply;</li>
          <li>with your consent or at your direction.</li>
        </UL>
      </>
    ),
  },
  {
    id: 'cookies',
    title: 'Cookies and browser storage',
    body: (
      <>
        <P>
          Voicecon does not use advertising cookies or third-party analytics trackers. We use a small amount of
          browser storage that the service needs to work:
        </P>
        <UL>
          <li><B>Sign-in session:</B> the application keeps your access tokens in your browser&apos;s local storage so you stay signed in.</li>
          <li><B>Preferences:</B> we remember interface choices, such as unsaved editor drafts, in local storage.</li>
          <li><B>Chat widget:</B> the widget stores a random visitor identifier in the visitor&apos;s browser so a conversation can continue on later pages.</li>
          <li><B>Third-party services:</B> Stripe Checkout and Google or Apple sign-in may set their own cookies when you use them, under their own policies.</li>
        </UL>
        <P>
          You can clear local storage and cookies in your browser settings. If you do, you will be signed out and
          widget conversations will restart.
        </P>
      </>
    ),
  },
  {
    id: 'retention',
    title: 'Data retention',
    body: (
      <>
        <P>
          We keep personal information for as long as your account is active, or as long as needed to provide the
          service, and then for as long as necessary for the purposes described in this policy. In particular:
        </P>
        <UL>
          <li>
            <B>Customer data</B>, such as recordings, transcripts, chat logs and knowledge base files, is kept until the
            customer deletes it in the application or asks us to delete it, or until the account is closed and
            the data is deleted as described below.
          </li>
          <li>
            <B>Closed accounts:</B> when you delete your account in Settings, we immediately deactivate it, sign
            out every session and cancel active subscriptions on workspaces you own. We keep the deactivated
            account&apos;s data for <B>30 days</B> so that an accidental deletion can be reversed, and then
            permanently erase it, except where we must keep records for legal or accounting reasons. To have it
            erased sooner, email {privacyMail}.
          </li>
          <li>
            <B>Billing and transaction records</B> are kept for as long as tax, accounting and other laws require.
          </li>
          <li>
            <B>Logs</B> are kept for a limited period for security and troubleshooting.
          </li>
        </UL>
      </>
    ),
  },
  {
    id: 'security',
    title: 'Security',
    body: (
      <>
        <P>We use administrative, technical and physical safeguards appropriate to the data we handle, including:</P>
        <UL>
          <li>encryption in transit with HTTPS and HTTP Strict Transport Security;</li>
          <li>bcrypt hashing for passwords and API keys, and encryption at rest for integration credentials;</li>
          <li>role-based access control within workspaces, and scoped API keys;</li>
          <li>email verification at sign-up, and immediate session invalidation when you change your password or delete your account;</li>
          <li>rate limiting and security headers to reduce abuse.</li>
        </UL>
        <P>
          No system is completely secure. If we learn of a security incident that affects your personal
          information, we will notify you and the authorities as the law requires. Please report suspected
          vulnerabilities to {mail}.
        </P>
      </>
    ),
  },
  {
    id: 'your-rights',
    title: 'Your privacy rights',
    body: (
      <>
        <P>Depending on where you live, you may have the right to:</P>
        <UL>
          <li>access the personal information we hold about you and receive a copy;</li>
          <li>correct inaccurate information;</li>
          <li>delete your information;</li>
          <li>restrict or object to certain processing, including direct marketing;</li>
          <li>receive your information in a portable format;</li>
          <li>withdraw consent where we rely on it, without affecting earlier processing;</li>
          <li>not be discriminated against for exercising these rights.</li>
        </UL>
        <P>
          You can update most account information yourself in Settings, export call data as CSV from Analytics,
          and delete your account from your profile. For other requests, email {privacyMail} from the address on
          your account. We may need to verify your identity. We will respond within the time the law requires, usually
          within 30 days. You may also have the right to complain to your local data protection authority.
        </P>
        <P>
          <B>California residents:</B> in the past 12 months we have collected the categories of information
          described in <A href="#information-we-collect">Information we collect</A> for the business purposes in{' '}
          <A href="#how-we-use">How we use information</A>. We do not sell or share personal information as those
          terms are defined under California law, and we do not use sensitive personal information to infer
          characteristics about you.
        </P>
        <P>
          If your request concerns data that a Voicecon customer controls, such as a recording of a call you made
          to a business, we will refer you to that customer and support them in responding.
        </P>
      </>
    ),
  },
  {
    id: 'customer-responsibilities',
    title: 'Responsibilities of businesses using Voicecon',
    body: (
      <>
        <P>
          Customers who use Voicecon to talk with their own callers and website visitors are responsible for
          complying with the laws that apply to them, including:
        </P>
        <UL>
          <li>giving any notice and obtaining any consent that call-recording and wiretap laws require, which in some places means every party&apos;s consent;</li>
          <li>disclosing that callers are speaking with an AI system where the law requires it;</li>
          <li>obtaining consent for automated or prerecorded calls and text messages, and honouring do-not-call and opt-out requests;</li>
          <li>providing their own privacy notice that explains how they use Voicecon;</li>
          <li>not uploading sensitive data, such as health, financial account or government ID information, unless they have a lawful basis and the appropriate agreements in place.</li>
        </UL>
        <P>
          See our <A href="/terms">Terms of Service</A> for the full set of obligations.
        </P>
      </>
    ),
  },
  {
    id: 'international',
    title: 'International data transfers',
    body: (
      <P>
        Voicecon and our service providers may process information in the United States and other countries whose
        data protection laws may differ from those where you live. When we transfer personal information from the
        EEA, the UK or Switzerland, we rely on appropriate safeguards, such as the European Commission&apos;s
        Standard Contractual Clauses, or on another valid transfer mechanism.
      </P>
    ),
  },
  {
    id: 'children',
    title: 'Children',
    body: (
      <P>
        Voicecon is a business service and is not directed to children. We do not knowingly collect personal
        information from children under 16. If you believe a child has provided personal information to us,
        contact {privacyMail} and we will delete it.
      </P>
    ),
  },
  {
    id: 'changes',
    title: 'Changes to this policy',
    body: (
      <P>
        We may update this Privacy Policy from time to time. When we do, we will change the &ldquo;Last
        updated&rdquo; date above. If a change is material, we will give you notice before it takes effect, by
        email or in the application. Continuing to use Voicecon after an update takes effect means you accept the
        updated policy.
      </P>
    ),
  },
  {
    id: 'contact',
    title: 'Contact us',
    body: (
      <>
        <P>
          The data controller for the information described in this policy is <B>{LEGAL.company}</B>. For
          questions about this policy or to exercise your privacy rights, email {privacyMail}. For anything else,
          including legal notices and security reports, email {mail}. You can also write to us at:
        </P>
        <UL>
          <li>{LEGAL.company}, {LEGAL.registeredAddress}</li>
          <li>{LEGAL.company}, {LEGAL.officeAddress}</li>
          <li>
            Telephone: <A href={`tel:${LEGAL.phoneHref}`}>{LEGAL.phone}</A>
          </li>
        </UL>
        <P>
          If you are in the EEA or the UK and believe we have not addressed your concern, you may also complain
          to your local data protection authority.
        </P>
      </>
    ),
  },
]

export default function PrivacyPolicyPage() {
  return (
    <LegalDocument
      title="Privacy Policy"
      description="How Voicecon collects, uses, shares and protects personal information, for our customers and for the people who talk to their AI agents."
      related={{ label: 'Terms of Service', href: '/terms' }}
      sections={SECTIONS}
      summary={
        <ul>
          <li>We collect the account, billing and workspace details needed to run your account, plus the calls, transcripts and content your agents handle.</li>
          <li>For calls and chats with your agents, you control the data and we process it on your behalf.</li>
          <li>We send conversation content to AI, speech and telephony providers only to deliver the service. We don&apos;t sell personal information, and we don&apos;t train AI models on your data without your consent.</li>
          <li>We don&apos;t use advertising cookies or third-party analytics trackers.</li>
          <li>You can access, correct, export or delete your information. Email {LEGAL.privacyEmail}.</li>
        </ul>
      }
    />
  )
}
