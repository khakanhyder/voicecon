import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { Chain, Figure } from '@/components/docs/Diagram'
import {
  A, C, Callout, H2, LI, P, ParamTable, Step, Steps, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/phone-numbers')

export default function PhoneNumbersPage() {
  return (
    <DocPage href="/docs/phone-numbers">
      <H2 id="how-numbers-work">How numbers work</H2>
      <P>
        A phone number is bought from a carrier through a connected account, and pointed at
        one agent. When someone dials it, that agent answers.
      </P>

      <Figure caption="Voicecon configures the carrier’s voice webhook when you assign an agent. You never set webhooks by hand.">
        <Chain
          stages={[
            { label: 'Caller dials', tone: 'slate' },
            { label: 'Carrier', caption: 'Twilio / Telnyx', tone: 'blue' },
            { label: 'Voicecon', caption: 'routes by number', tone: 'brand' },
            { label: 'Agent answers', tone: 'violet' },
          ]}
        />
      </Figure>

      <UL>
        <LI>A number points at <Strong>at most one agent</Strong>.</LI>
        <LI>An agent may hold <Strong>several numbers</Strong> — useful for tracking which campaign a call came from.</LI>
        <LI>A number with no agent assigned will ring with nothing answering.</LI>
      </UL>

      <H2 id="providers">Choosing a provider</H2>
      <P>
        Numbers are provisioned through a connected carrier account, which is also the account
        billed for them.
      </P>
      <Table
        headers={['Provider', 'Buy numbers', 'Notes']}
        widths={['w-[18%]', 'w-[16%]']}
        rows={[
          [<Strong>Twilio</Strong>, 'Yes', 'Widest country coverage and the most familiar console. The default choice.'],
          [<Strong>Telnyx</Strong>, 'Yes', 'Often cheaper per minute. Uses a TeXML application, created for you at purchase.'],
          [<Strong>Vonage</Strong>, '—', 'Available as an integration for SMS; numbers are not provisioned through Voicecon.'],
        ]}
      />
      <Callout kind="note" title="With more than one carrier connected">
        When you have both Twilio and Telnyx connected, search and purchase require you to say
        which one. With a single carrier connected, it is chosen for you.
      </Callout>

      <H2 id="searching">Searching for a number</H2>
      <P>
        <Strong>Phone Numbers</Strong> → <Strong>Purchase Number</Strong> searches the
        carrier&rsquo;s live inventory.
      </P>
      <ParamTable
        params={[
          {
            name: 'country',
            type: 'ISO code',
            description: (
              <>
                Which country to search. Regulations differ — some countries require a local
                address or business documentation before a number can be issued.
              </>
            ),
          },
          {
            name: 'area_code',
            type: 'string',
            description: (
              <>
                Narrows to a region. A local area code measurably improves answer rates on
                outbound calls.
              </>
            ),
          },
          {
            name: 'capabilities',
            type: 'voice / sms',
            description: (
              <>
                Filter to numbers that support what you need. A number without SMS cannot send
                confirmations, and that is not something you can add later.
              </>
            ),
          },
          {
            name: 'provider',
            type: 'enum',
            description: 'Which connected carrier to search. Required when more than one is connected.',
          },
        ]}
      />
      <Callout kind="tip" title="Buy voice + SMS even if you only need voice today">
        Texting confirmations, links, and reference numbers is one of the highest-value things
        a voice agent does. A voice-only number closes that door, and switching numbers later
        means updating everywhere the old one is printed.
      </Callout>

      <H2 id="provisioning">Buying a number</H2>
      <Steps>
        <Step n={1} title="Select from the results">
          <P>Each result shows the number, its capabilities, and its monthly cost.</P>
        </Step>
        <Step n={2} title="Confirm the purchase">
          <P>
            The number is provisioned on your carrier account and appears in your list. Billing
            is between you and the carrier.
          </P>
        </Step>
        <Step n={3} title="Assign an agent">
          <P>
            Until you do, the number exists but nothing answers it. See{' '}
            <A href="#assigning">below</A>.
          </P>
        </Step>
      </Steps>
      <Callout kind="note" title="Numbers remember where they came from">
        Each number records the carrier connection it was bought on, so later operations —
        updating its webhook, releasing it — go to the right account even if you connect
        several.
      </Callout>

      <H2 id="assigning">Assigning an agent</H2>
      <P>
        Open the number and set its agent. Voicecon points the carrier&rsquo;s voice webhook at
        the platform as part of this, so there is no manual console work.
      </P>
      <UL>
        <LI>Reassigning to a different agent takes effect on the next call.</LI>
        <LI>Unassigning leaves the number provisioned and still billed, but unanswered.</LI>
        <LI>Deleting the assigned agent leaves the number stranded — reassign before deleting.</LI>
      </UL>
      <Callout kind="tip" title="Use separate numbers to segment reporting">
        One number per campaign, region, or channel, all pointing at the same agent, gives you
        free attribution: every call record carries the number it arrived on.
      </Callout>

      <H2 id="configuration">Configuration reference</H2>
      <ParamTable
        params={[
          {
            name: 'phone_number',
            type: 'E.164',
            description: <>The number itself, e.g. <C>+14155550123</C>. Set at purchase and immutable.</>,
          },
          {
            name: 'name',
            type: 'string',
            description: (
              <>
                A friendly label — <C>Main Support Line</C>. Makes the list readable once you
                hold more than a handful.
              </>
            ),
          },
          {
            name: 'agent_id',
            type: 'agent',
            description: 'The agent that answers calls to this number.',
          },
          {
            name: 'status',
            type: 'enum',
            default: 'active',
            description: (
              <>
                <C>active</C> takes calls; <C>inactive</C> does not; <C>pending</C> is still
                being provisioned by the carrier.
              </>
            ),
          },
          {
            name: 'capabilities',
            type: 'object',
            default: '{ voice: true, sms: true }',
            description: 'What the carrier issued this number with. Read-only — set at purchase.',
          },
          {
            name: 'provider',
            type: 'string',
            description: <>Which carrier — <C>twilio</C> or <C>telnyx</C>.</>,
          },
          {
            name: 'provider_sid',
            type: 'string',
            description: 'The carrier’s own identifier. Useful when raising a support ticket with them.',
          },
          {
            name: 'voice_webhook_url',
            type: 'url',
            description: (
              <>
                Where the carrier sends incoming calls. Managed for you — override only for a
                bespoke telephony setup.
              </>
            ),
          },
          {
            name: 'sms_webhook_url',
            type: 'url',
            description: 'Where inbound SMS is delivered.',
          },
          {
            name: 'status_callback_url',
            type: 'url',
            description: 'Where the carrier reports call status changes.',
          },
          {
            name: 'monthly_cost',
            type: 'decimal',
            description: 'The carrier’s recurring charge, shown for reference.',
          },
        ]}
      />

      <H2 id="releasing">Releasing a number</H2>
      <P>
        Deleting a number releases it back to the carrier and stops the monthly charge. Before
        you do:
      </P>
      <UL>
        <LI>Check nothing published — a website, an ad, an email signature — still points at it.</LI>
        <LI>Note the number for your records; call history references it.</LI>
        <LI>Reassign anything that was routing through it.</LI>
      </UL>
      <Callout kind="danger" title="Releasing is not reversible">
        Once released, the number returns to the carrier&rsquo;s pool and may be issued to
        somebody else. You will not get it back. Deactivate first if you are unsure — an
        inactive number still costs its monthly fee but stays yours.
      </Callout>
    </DocPage>
  )
}
