import type { Metadata } from 'next'
import { A, B, Callout, H3, LegalDocument, P, UL, type LegalSection } from '@/components/legal/LegalDocument'
import { LEGAL } from '@/lib/legal'

export const metadata: Metadata = {
  metadataBase: new URL(LEGAL.website),
  title: 'Terms of Service | Voicecon',
  description:
    'The terms that govern your use of Voicecon, including free trials, subscriptions, phone numbers, acceptable use and AI-generated output.',
  alternates: { canonical: '/terms' },
}

const mail = <A href={`mailto:${LEGAL.contactEmail}`}>{LEGAL.contactEmail}</A>

const SECTIONS: LegalSection[] = [
  {
    id: 'agreement',
    title: 'Agreement to these terms',
    body: (
      <>
        <P>
          These Terms of Service (the &ldquo;Terms&rdquo;) are an agreement between you and{' '}
          <B>{LEGAL.company}</B>, a limited liability company registered in the {LEGAL.jurisdiction}, which
          operates Voicecon (&ldquo;Voicecon&rdquo;, &ldquo;we&rdquo;, &ldquo;us&rdquo;). They govern your access to and use of the
          Voicecon website, web application, API, chat widget, voice agents, workflows and related services
          (together, the &ldquo;Service&rdquo;).
        </P>
        <P>
          By creating an account, starting a free trial, subscribing or otherwise using the Service, you agree to
          these Terms and to our <A href="/privacy">Privacy Policy</A>. If you use the Service on behalf of a
          company or other organisation, you confirm that you have authority to bind it, and &ldquo;you&rdquo;
          means that organisation.
        </P>
        <P>
          The Service is intended for business use, and you must be able to form a binding contract to use it. If
          you do not agree to these Terms, do not use the Service.
        </P>
      </>
    ),
  },
  {
    id: 'service',
    title: 'The Service',
    body: (
      <>
        <P>
          Voicecon lets you build AI voice and chat agents, give them knowledge and tools, connect them to phone
          numbers and third-party apps, and automate tasks with workflows. The features available to you depend on
          your plan.
        </P>
        <P>
          We continually improve the Service and may add, change or remove features. If we remove a material
          feature from a paid plan you are using, we will give you reasonable notice. Some features may be labelled
          as beta or preview. They are provided as-is, may change or be discontinued, and are excluded from any
          commitments we make about availability.
        </P>
      </>
    ),
  },
  {
    id: 'accounts',
    title: 'Accounts, workspaces and API keys',
    body: (
      <>
        <UL>
          <li>You must provide accurate information when you register and keep it up to date.</li>
          <li>
            You are responsible for keeping your password, sign-in methods and API keys confidential, and for all
            activity under your account and workspaces. Tell us immediately at {mail} if you suspect unauthorised
            access.
          </li>
          <li>
            The owner of a workspace controls it. They decide who is invited and what role each member has, and
            they are responsible for their members&apos; use of the Service.
          </li>
          <li>
            API keys are for your own systems. Don&apos;t share them publicly or embed them in client-side code. You
            are responsible for requests made with your keys.
          </li>
          <li>You may not create accounts by automated means or to get around plan limits or free-trial rules.</li>
        </UL>
      </>
    ),
  },
  {
    id: 'free-trial',
    title: 'Free trial',
    body: (
      <>
        <P>
          New customers may be eligible for one free trial, currently 30 days, with no payment method required.
          During the trial, plan limits apply (for example, a limited number of agents, knowledge bases, workflows
          and team members), and some features, including purchasing phone numbers, are available only on paid
          plans.
        </P>
        <P>
          When the trial ends, access to features that need a subscription stops until you choose a paid plan.
          We may change or end trial offers, and we may refuse or end a trial that is being abused. Each
          organisation may use only one free trial.
        </P>
      </>
    ),
  },
  {
    id: 'billing',
    title: 'Plans, billing and renewal',
    body: (
      <>
        <UL>
          <li>
            <B>Subscriptions.</B> Paid plans are billed in advance, monthly or yearly, at the price shown when you
            subscribe. Plan limits and included allowances, such as agents, phone numbers, texts and emails, are
            described at checkout and in your billing settings.
          </li>
          <li>
            <B>Automatic renewal.</B> Subscriptions renew automatically at the end of each billing period for the
            same length of time until cancelled. By subscribing, you authorise us and our payment processor,
            Stripe, to charge your payment method on each renewal date.
          </li>
          <li>
            <B>Usage charges.</B> Usage beyond your plan&apos;s allowances may be billed at the rates shown in your
            plan details or at checkout.
          </li>
          <li>
            <B>Taxes.</B> Prices exclude taxes unless stated otherwise. You are responsible for any applicable
            sales, use, value-added and similar taxes.
          </li>
          <li>
            <B>Promotions.</B> Promotional codes apply only as described when issued, cannot be exchanged for
            cash, and may expire.
          </li>
          <li>
            <B>Price changes.</B> We may change prices. Changes take effect at your next renewal, and we will give
            you at least 30 days&apos; notice first. If you don&apos;t agree, cancel before the change takes effect.
          </li>
          <li>
            <B>Failed payments.</B> If a payment fails, we may retry the charge, and we may suspend paid features
            until the balance is paid.
          </li>
        </UL>
      </>
    ),
  },
  {
    id: 'cancellation',
    title: 'Cancellation and refunds',
    body: (
      <>
        <P>
          You can cancel your subscription at any time in your billing settings. Cancellation takes effect at the
          end of the current billing period, and you keep access to paid features until then.
        </P>
        <P>
          Fees already paid are non-refundable, including for partially used billing periods and unused
          allowances, except where the law requires otherwise or where we expressly agree in writing. If we end
          your subscription for convenience rather than for your breach of these Terms, we will refund the prepaid
          fees for the unused part of the billing period.
        </P>
      </>
    ),
  },
  {
    id: 'telephony',
    title: 'Phone numbers and telephony',
    body: (
      <>
        <UL>
          <li>
            Phone numbers are provided through third-party carriers, such as Twilio and Telnyx, and are subject to
            their availability, regulatory requirements and policies. We may need identity, business or use-case
            information to provision a number or to register it for messaging.
          </li>
          <li>
            Numbers provided by Voicecon are assigned to you for as long as your subscription is active, and you do
            not own them. If your subscription ends, numbers may be released and reassigned. Porting a number to
            another provider depends on the carrier and on applicable rules.
          </li>
          <li>
            If you connect your own carrier account, your agreement with that carrier also applies, and you are
            responsible for its charges.
          </li>
          <li>
            Call quality and message delivery depend on carriers and networks that we don&apos;t control. Carriers
            may filter or block traffic they consider unwanted.
          </li>
        </UL>
        <Callout title="No emergency calling">
          Voicecon is not a replacement for a traditional telephone service and does not support calls to
          emergency services such as 911, 112 or 999. Do not rely on the Service, or on any agent built with it,
          for emergency communications.
        </Callout>
      </>
    ),
  },
  {
    id: 'compliance',
    title: 'Your legal and compliance obligations',
    body: (
      <>
        <P>
          You decide who your agents call, text and talk to, and what they say. You are solely responsible for
          making sure your use of the Service complies with all applicable laws and regulations, including:
        </P>
        <UL>
          <li>
            <B>Telemarketing and messaging laws</B>, such as the U.S. Telephone Consumer Protection Act (TCPA), the
            Telemarketing Sales Rule, do-not-call registries, CAN-SPAM, carrier messaging requirements (including
            10DLC registration) and their equivalents elsewhere, including obtaining any required prior express
            consent and honouring opt-outs promptly;
          </li>
          <li>
            <B>Call-recording and wiretap laws</B>, including giving notice and obtaining the consent of all
            parties where required;
          </li>
          <li>
            <B>AI disclosure laws</B> that require you to tell people they are interacting with an automated or
            artificial voice;
          </li>
          <li>
            <B>Privacy and data protection laws</B>, including providing privacy notices to the people your agents
            interact with and having a lawful basis to process their data;
          </li>
          <li>
            <B>Consumer protection, anti-discrimination and industry-specific rules</B> that apply to your
            business.
          </li>
        </UL>
        <H3>Sensitive and regulated data</H3>
        <P>
          Unless we have signed a separate written agreement that covers it, you must not use the Service to
          collect or store protected health information under HIPAA, full payment card numbers, government
          identification numbers or other data subject to heightened legal protection. Voicecon does not enter
          into business associate agreements by default.
        </P>
      </>
    ),
  },
  {
    id: 'acceptable-use',
    title: 'Acceptable use',
    body: (
      <>
        <P>You agree not to use the Service, or allow anyone else to use it, to:</P>
        <UL>
          <li>make robocalls, spam, or unsolicited calls or messages without the consent the law requires;</li>
          <li>impersonate a real person, business or government agency, or mislead people about who they are speaking with;</li>
          <li>clone or imitate someone&apos;s voice without their permission;</li>
          <li>defraud, harass, threaten, scam or phish anyone, or collect credentials or payment details under false pretences;</li>
          <li>carry out debt collection, political campaigning or emergency alerting in violation of the rules that govern those activities;</li>
          <li>create, send or store unlawful, defamatory, hateful, sexually exploitative or infringing content;</li>
          <li>violate anyone&apos;s privacy, intellectual property or other rights;</li>
          <li>interfere with or disrupt the Service or its infrastructure, including through excessive load, or circumvent plan limits, rate limits or security controls;</li>
          <li>probe, scan or test the vulnerability of the Service without our written permission;</li>
          <li>reverse engineer the Service, except to the extent the law allows;</li>
          <li>resell or provide the Service to third parties without our written agreement;</li>
          <li>build a competing product using the Service or its non-public information;</li>
          <li>violate the policies of the AI providers, carriers and integrations the Service relies on.</li>
        </UL>
      </>
    ),
  },
  {
    id: 'your-data',
    title: 'Your content and data',
    body: (
      <>
        <P>
          <B>You own your content.</B> As between you and Voicecon, you keep all rights in the data and content you
          and your end users submit to the Service, including prompts, knowledge base files, recordings, transcripts
          and messages (&ldquo;Customer Data&rdquo;).
        </P>
        <P>
          <B>Licence to operate the Service.</B> You grant Voicecon a worldwide, non-exclusive, royalty-free licence
          to host, copy, process, transmit and display Customer Data only as needed to provide, secure and support
          the Service for you. This includes sending it to our service providers as described in our{' '}
          <A href="/privacy">Privacy Policy</A>. We will not use Customer Data to train AI models without your
          prior consent.
        </P>
        <P>
          <B>Your responsibility.</B> You confirm that you have all the rights, notices and consents needed to
          provide Customer Data to us and to have it processed through the Service.
        </P>
        <P>
          <B>Usage data and feedback.</B> We may use aggregated and de-identified data about how the Service is
          used, which doesn&apos;t identify you or any individual, to operate and improve the Service. If you send us
          feedback or suggestions, we may use them without any obligation to you.
        </P>
        <P>
          <B>Exporting and deletion.</B> You can export call data from the application and delete content you
          created. After your account is closed, we handle your data as described in our Privacy Policy.
        </P>
      </>
    ),
  },
  {
    id: 'ai-output',
    title: 'AI-generated output',
    body: (
      <>
        <P>
          Agents, summaries, sentiment scores, generated messages and other outputs are produced by machine learning
          models. By their nature, they can be inaccurate, incomplete or inappropriate, even when your instructions
          and knowledge base are correct.
        </P>
        <UL>
          <li>You are responsible for configuring, testing and monitoring your agents and for how you use their outputs.</li>
          <li>Review outputs before relying on them, especially for decisions that affect people&apos;s rights, finances, health or safety.</li>
          <li>Outputs are not professional legal, medical, financial or other advice.</li>
          <li>Similar prompts can produce similar outputs for other customers, so outputs may not be unique to you.</li>
        </UL>
      </>
    ),
  },
  {
    id: 'third-parties',
    title: 'Third-party services and integrations',
    body: (
      <P>
        The Service lets you connect third-party apps and relies on third-party providers, including AI model,
        speech, telephony and payment providers. When you connect an integration, you authorise Voicecon to access
        that app and exchange data with it on your behalf. Your use of each third-party service is governed by its
        own terms. We don&apos;t control third-party services and aren&apos;t responsible for their availability,
        changes, security or behaviour. A connector may stop working if the provider changes or discontinues its
        product.
      </P>
    ),
  },
  {
    id: 'our-ip',
    title: 'Our intellectual property',
    body: (
      <P>
        Voicecon and its licensors own the Service, including the software, design, templates, documentation and
        branding. Subject to these Terms and payment of applicable fees, we grant you a limited, non-exclusive,
        non-transferable, revocable right to use the Service for your internal business purposes during your
        subscription. You may use the templates and documentation to build and operate your own agents and
        workflows. No other rights are granted, and you may not use our trademarks without our permission.
      </P>
    ),
  },
  {
    id: 'termination',
    title: 'Suspension and termination',
    body: (
      <>
        <P>
          You may stop using the Service and delete your account at any time in Settings. Deleting your account
          cancels active subscriptions on workspaces you own, and we erase the account&apos;s data after 30 days as
          described in our <A href="/privacy">Privacy Policy</A>.
        </P>
        <P>
          We may suspend or terminate your access, in whole or in part, if you breach these Terms, fail to pay, use
          the Service in a way that creates legal, security or reputational risk, or if a carrier, AI provider or
          authority requires us to. Where practical and lawful, we will notify you first and give you a chance to
          fix the problem. We may act immediately to stop abuse, such as unlawful calling, or to protect the
          Service or others.
        </P>
        <P>
          The sections of these Terms that by their nature should survive termination will do so. These include
          fees owed, your content and data, disclaimers, limitation of liability, indemnification and dispute
          terms.
        </P>
      </>
    ),
  },
  {
    id: 'disclaimers',
    title: 'Disclaimers',
    body: (
      <P>
        <span className="uppercase">
          To the fullest extent permitted by law, the Service is provided &ldquo;as is&rdquo; and &ldquo;as
          available&rdquo;. Voicecon disclaims all warranties, express or implied, including warranties of
          merchantability, fitness for a particular purpose, title and non-infringement. We don&apos;t warrant that
          the Service will be uninterrupted, error-free or secure, that AI outputs will be accurate, or that calls
          and messages will be delivered.
        </span>
      </P>
    ),
  },
  {
    id: 'liability',
    title: 'Limitation of liability',
    body: (
      <>
        <P>
          <span className="uppercase">
            To the fullest extent permitted by law, Voicecon will not be liable for any indirect, incidental,
            special, consequential, exemplary or punitive damages, or for any loss of profits, revenue, business,
            goodwill or data, however caused, even if advised of the possibility of such damages.
          </span>
        </P>
        <P>
          <span className="uppercase">
            Voicecon&apos;s total liability for all claims relating to the Service or these Terms will not exceed
            the greater of (a) the amounts you paid to Voicecon for the Service in the 12 months before the event
            giving rise to the claim, and (b) one hundred U.S. dollars (US$100).
          </span>
        </P>
        <P>
          Some jurisdictions don&apos;t allow certain limitations of liability, so some of these limitations may not
          apply to you. Nothing in these Terms limits liability that cannot be limited by law.
        </P>
      </>
    ),
  },
  {
    id: 'indemnification',
    title: 'Indemnification',
    body: (
      <P>
        You will defend, indemnify and hold harmless Voicecon and its affiliates, officers, employees and agents
        from any claims, damages, fines, penalties, losses and expenses, including reasonable legal fees, arising
        from: your Customer Data; your use of the Service, including calls and messages placed by your agents; your
        breach of these Terms; or your violation of any law or third-party right, including telemarketing,
        call-recording and privacy laws.
      </P>
    ),
  },
  {
    id: 'disputes',
    title: 'Governing law and disputes',
    body: (
      <>
        <P>
          These Terms and any dispute arising out of them or the Service are governed by the laws of the{' '}
          {LEGAL.jurisdiction}, without regard to conflict-of-law rules and excluding the United Nations
          Convention on Contracts for the International Sale of Goods. You and {LEGAL.company} agree to the
          exclusive jurisdiction of {LEGAL.courts}, and each party waives any objection to venue there. Either
          party may still seek injunctive relief in any court of competent jurisdiction to protect its
          intellectual property or confidential information.
        </P>
        <P>
          Before starting formal proceedings, please contact us at {mail} and describe the issue. We will try in
          good faith to resolve it within 30 days. Nothing in this section removes rights you have under mandatory
          consumer protection laws where you live.
        </P>
      </>
    ),
  },
  {
    id: 'changes',
    title: 'Changes to these terms',
    body: (
      <P>
        We may update these Terms from time to time. When we do, we will change the &ldquo;Last updated&rdquo;
        date above. For material changes, we will give you at least 30 days&apos; notice by email or in the
        application before they take effect, unless a change is required by law or addresses new functionality,
        in which case it may take effect sooner. Continuing to use the Service after a change takes effect means
        you accept the updated Terms.
      </P>
    ),
  },
  {
    id: 'general',
    title: 'General',
    body: (
      <UL>
        <li><B>Entire agreement.</B> These Terms, the Privacy Policy and any order or plan details you accept form the entire agreement between you and Voicecon about the Service.</li>
        <li><B>Assignment.</B> You may not transfer these Terms without our consent. We may transfer them as part of a merger, acquisition or sale of assets.</li>
        <li><B>Severability and waiver.</B> If any provision is found unenforceable, the rest stays in effect. Not enforcing a provision is not a waiver of it.</li>
        <li><B>Force majeure.</B> Neither party is liable for delays or failures caused by events beyond its reasonable control, including outages at carriers or cloud and AI providers.</li>
        <li><B>Notices.</B> We may send notices to your account email address or through the application. You can send notices to {mail}, or by post to {LEGAL.company}, {LEGAL.registeredAddress}.</li>
        <li><B>Export and sanctions.</B> You will comply with export control and sanctions laws and will not use the Service where it is prohibited.</li>
        <li><B>Independent parties.</B> These Terms don&apos;t create a partnership, joint venture, employment or agency relationship.</li>
      </UL>
    ),
  },
  {
    id: 'contact',
    title: 'Contact us',
    body: (
      <>
        <P>Questions about these Terms? Contact us at:</P>
        <UL>
          <li>Email: {mail}</li>
          <li>
            Telephone: <A href={`tel:${LEGAL.phoneHref}`}>{LEGAL.phone}</A>
          </li>
          <li>{LEGAL.company}, {LEGAL.registeredAddress}</li>
          <li>{LEGAL.company}, {LEGAL.officeAddress}</li>
        </UL>
      </>
    ),
  },
]

export default function TermsOfServicePage() {
  return (
    <LegalDocument
      title="Terms of Service"
      description="The rules for using Voicecon, covering trials, subscriptions, phone numbers, acceptable use and what you can expect from AI-generated output."
      related={{ label: 'Privacy Policy', href: '/privacy' }}
      sections={SECTIONS}
      summary={
        <ul>
          <li>Voicecon is a business service for companies and the people who work in them.</li>
          <li>Trials last 30 days with no card. Paid plans renew automatically until you cancel, and cancellation takes effect at the end of the billing period.</li>
          <li>You own your data. We use it only to run the Service for you, and never to train AI models without your consent.</li>
          <li>You are responsible for complying with calling, texting, recording, AI disclosure and privacy laws. No robocalls, spam or impersonation.</li>
          <li>AI output can be wrong, so test and monitor your agents. Voicecon can&apos;t be used to call emergency services.</li>
        </ul>
      }
    />
  )
}
