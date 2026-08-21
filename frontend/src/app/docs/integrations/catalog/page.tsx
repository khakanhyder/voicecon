import { DocPage, docMetadata } from '@/components/docs/DocPage'
import {
  A, Badge, C, Callout, H2, LI, P, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/integrations/catalog')

/** Renders an action list as inline code chips, so long rows stay scannable. */
function Actions({ items }: { items: string[] }) {
  return (
    <span className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <C key={item}>{item}</C>
      ))}
    </span>
  )
}

/** OAuth and API-key badges, written once so the tables stay readable. */
const OAUTH = <Badge tone="brand">OAuth</Badge>
const KEY = <Badge tone="slate">API key</Badge>
const HOOK = <Badge tone="slate">Webhook URL</Badge>

export default function CatalogPage() {
  return (
    <DocPage href="/docs/integrations/catalog">
      <P>
        All thirty-five connectors, grouped by what they are for, with the actions each
        exposes. Every action listed here is available in both{' '}
        <A href="/docs/nodes/actions#action">workflow Integration nodes</A> and{' '}
        <A href="/docs/tools/integration#connected-integration">Connected Integration tools</A>,
        under exactly the name shown.
      </P>

      <Callout kind="note" title="Actions are the tested surface">
        Each connector supports more of its provider&rsquo;s API than is listed here; these
        are the actions exposed with published schemas, so they get parameter validation and
        resource pickers. An action that is not in this list is refused rather than attempted
        — for anything outside it, use an{' '}
        <A href="/docs/nodes/actions#webhook">API Request or Webhook</A>.
      </Callout>

      <P>
        <Strong>How you connect</Strong> differs by app. {OAUTH} sends you to the provider to
        approve access. {KEY} asks for a key or token you generate in the provider&rsquo;s own
        console. {HOOK} asks only for an incoming webhook URL you paste in.
      </P>

      <H2 id="crm">CRM and support</H2>
      <Table
        headers={['App', 'Auth', 'Actions']}
        widths={['w-[18%]', 'w-[14%]']}
        rows={[
          [<Strong>HubSpot</Strong>, OAUTH, <Actions items={['create_contact', 'search_contacts', 'update_contact', 'create_deal']} />],
          [<Strong>Salesforce</Strong>, OAUTH, <Actions items={['create_contact', 'create_lead', 'search_contacts']} />],
          [<Strong>Pipedrive</Strong>, KEY, <Actions items={['create_person', 'search_persons', 'create_deal', 'add_note']} />],
          [<Strong>Zendesk</Strong>, KEY, <Actions items={['create_ticket', 'add_comment', 'search_tickets']} />],
          [<Strong>Intercom</Strong>, KEY, <Actions items={['create_contact', 'search_contacts', 'add_note', 'create_conversation']} />],
          [<Strong>GoHighLevel</Strong>, KEY, <Actions items={['create_contact']} />],
        ]}
      />
      <P>
        The most common voice pattern: identify the caller with a search action at the start
        of the call, then write the outcome back when it ends. HubSpot, Salesforce, Pipedrive
        and Intercom all support that pair. Zendesk is the one to reach for when the outcome is
        a support ticket rather than a contact record — <C>create_ticket</C> during the call,{' '}
        <C>add_comment</C> from a{' '}
        <A href="/docs/workflows/triggers#call-completed">call completed</A> workflow carrying
        the summary.
      </P>

      <H2 id="productivity">Productivity and project management</H2>
      <Table
        headers={['App', 'Auth', 'Actions']}
        widths={['w-[18%]', 'w-[14%]']}
        rows={[
          [<Strong>Notion</Strong>, OAUTH, <Actions items={['search', 'create_page', 'append_text']} />],
          [<Strong>ClickUp</Strong>, OAUTH, <Actions items={['create_task', 'list_tasks', 'add_comment']} />],
          [<Strong>Monday.com</Strong>, OAUTH, <Actions items={['list_boards']} />],
          [<Strong>Google Sheets</Strong>, OAUTH, <Actions items={['append_row']} />],
          [<Strong>Google Drive</Strong>, OAUTH, <Actions items={['list_files']} />],
          [<Strong>Trello</Strong>, KEY, <Actions items={['create_card', 'add_comment']} />],
          [<Strong>Airtable</Strong>, KEY, <Actions items={['create_record']} />],
          [<Strong>Zapier</Strong>, HOOK, <Actions items={['send_webhook']} />],
          [<Strong>Make (Integromat)</Strong>, HOOK, <Actions items={['send_webhook']} />],
        ]}
      />
      <UL>
        <LI>
          Trello, ClickUp, Monday, Notion, and Airtable all expose{' '}
          <A href="/docs/integrations#resource-pickers">resource pickers</A> — pick a board,
          list, or database from a dropdown, or paste its URL.
        </LI>
        <LI>
          <Strong>Google Sheets</Strong> with <C>append_row</C> is the quickest useful thing
          you can build: one row per call, written from a call-completed workflow. No schema
          to design, and everyone can already read a spreadsheet.
        </LI>
        <LI>
          <Strong>Zapier</Strong> and <Strong>Make</Strong> are the escape hatch. Both connect
          by pasting one webhook URL — a Zapier Catch Hook or a Make custom webhook — and{' '}
          <C>send_webhook</C> then hands your call data to whatever those platforms already
          reach. Use them when the app you need has no connector here and you would rather not
          build the HTTP call yourself.
        </LI>
      </UL>

      <H2 id="calendar">Calendar and scheduling</H2>
      <Table
        headers={['App', 'Auth', 'Actions']}
        widths={['w-[18%]', 'w-[14%]']}
        rows={[
          [
            <Strong>Google Calendar</Strong>,
            OAUTH,
            <Actions items={['check_availability', 'find_available_slots', 'create_event', 'list_events']} />,
          ],
          [<Strong>Calendly</Strong>, OAUTH, <Actions items={['list_scheduled_events']} />],
          [<Strong>Cal.com</Strong>, KEY, <Actions items={['list_event_types']} />],
        ]}
      />
      <Callout kind="tip" title="Book properly, in three steps">
        Google Calendar is the only connector with a full booking cycle. Use{' '}
        <C>find_available_slots</C> to offer real options, <C>create_event</C> to book, then
        confirm back to the caller — all inside one{' '}
        <A href="/docs/tools/workflow">workflow tool</A>. Booking without checking
        availability first is how double-bookings happen.
      </Callout>
      <P>
        Calendly and Cal.com are read-only here: they tell you what is already scheduled or
        what can be booked, but neither creates a booking. Where an agent must actually book,
        use Google Calendar.
      </P>

      <H2 id="messaging">Messaging and email</H2>
      <Table
        headers={['App', 'Auth', 'Actions']}
        widths={['w-[18%]', 'w-[14%]']}
        rows={[
          [<Strong>Slack</Strong>, OAUTH, <Actions items={['send_message']} />],
          [<Strong>Microsoft Teams</Strong>, HOOK, <Actions items={['send_message']} />],
          [<Strong>WhatsApp</Strong>, KEY, <Actions items={['send_message', 'send_template']} />],
          [<Strong>SendGrid</Strong>, KEY, <Actions items={['send_email']} />],
          [<Strong>Gmail SMTP</Strong>, KEY, <Actions items={['send_email']} />],
          [<Strong>Outlook SMTP</Strong>, KEY, <Actions items={['send_email']} />],
          [<Strong>Custom SMTP</Strong>, KEY, <Actions items={['send_email']} />],
        ]}
      />
      <UL>
        <LI>
          <Strong>Slack</Strong> offers a channel picker, and a connection default so you can
          change the destination channel in one place.
        </LI>
        <LI>
          <Strong>Microsoft Teams</Strong> connects with an Incoming Webhook URL, which is
          bound to one channel. To post to a second channel, add a second connection.
        </LI>
        <LI>
          <Strong>WhatsApp</Strong> requires pre-approved templates for business-initiated
          messages — that is what <C>send_template</C> is for. Free-form{' '}
          <C>send_message</C> only works inside an open conversation window.
        </LI>
        <LI>
          <Strong>Email</Strong> comes in two shapes. SendGrid is an email API and the right
          choice at volume. Gmail, Outlook and Custom SMTP are one connector with three
          presets — they send through a mailbox you already own, which is simpler to set up
          and appropriate for low volumes. All four take the same <C>send_email</C> parameters:{' '}
          <C>to_email</C>, <C>subject</C>, <C>body</C>, and optionally <C>html_body</C>,{' '}
          <C>cc</C> and <C>reply_to</C>.
        </LI>
      </UL>

      <H2 id="telephony">Telephony</H2>
      <Table
        headers={['App', 'Auth', 'Actions', 'Numbers?']}
        widths={['w-[16%]', 'w-[13%]', 'w-[30%]']}
        rows={[
          [<Strong>Twilio</Strong>, KEY, <Actions items={['send_sms']} />, 'Yes'],
          [<Strong>Telnyx</Strong>, KEY, <Actions items={['send_message']} />, 'Yes'],
          [<Strong>Vonage (Nexmo)</Strong>, KEY, <Actions items={['send_sms']} />, '—'],
        ]}
      />
      <P>
        Twilio and Telnyx double as <A href="/docs/phone-numbers#providers">number
        providers</A>: connect one and you can search for and buy phone numbers directly from
        Voicecon. See <A href="/docs/phone-numbers">Phone Numbers</A>.
      </P>
      <Callout kind="note" title="Sending a text mid-call">
        For an SMS the agent decides to send, the{' '}
        <A href="/docs/tools/phone-call#send-sms">Send Text tool</A> is usually the better
        route — it uses the number the call is already on, with nothing extra to connect.
        Reach for these connectors when you need a different sender, or are texting somebody
        who is not the caller.
      </Callout>

      <H2 id="storage">File and object storage</H2>
      <P>
        Four providers share one action surface, so a workflow written against one moves to
        another by swapping the connection. Azure calls its container a container; the other
        three call it a bucket, and the field is named to match.
      </P>
      <Table
        headers={['App', 'Auth', 'Actions']}
        widths={['w-[20%]', 'w-[14%]']}
        rows={[
          [<Strong>AWS S3</Strong>, KEY, <Actions items={['upload_text', 'upload_from_url', 'list_objects', 'delete_object', 'generate_presigned_url']} />],
          [<Strong>Cloudflare R2</Strong>, KEY, <Actions items={['upload_text', 'upload_from_url', 'list_objects', 'delete_object', 'generate_presigned_url']} />],
          [<Strong>Google Cloud Storage</Strong>, KEY, <Actions items={['upload_text', 'upload_from_url', 'list_objects', 'delete_object', 'generate_presigned_url']} />],
          [<Strong>Azure Blob Storage</Strong>, KEY, <Actions items={['upload_text', 'upload_from_url', 'list_objects', 'delete_object', 'generate_presigned_url']} />],
        ]}
      />
      <UL>
        <LI>
          <C>upload_text</C> stores a transcript, summary or note as a file. Give it a{' '}
          <C>key</C> — the object path, e.g. <C>transcripts/call-123.txt</C> — and the text.
        </LI>
        <LI>
          <C>upload_from_url</C> copies a file into the bucket, which is how you archive a
          call recording into storage you control.
        </LI>
        <LI>
          <C>generate_presigned_url</C> creates a time-limited download link, so a recording
          can be shared without making the bucket public. The lifetime defaults to an hour and
          caps at seven days.
        </LI>
        <LI>
          Each action can override the connection&rsquo;s bucket per call, so one connection
          can write to several buckets if you need it to.
        </LI>
      </UL>
      <Callout kind="tip" title="Retention is a good reason to use these">
        Recordings and transcripts held in your own bucket are subject to your retention
        policy, your encryption, and your access controls. If compliance has an opinion about
        where call audio lives, this is the connector group that answers it.
      </Callout>

      <H2 id="data">Data, payments, and observability</H2>
      <Table
        headers={['App', 'Auth', 'Actions']}
        widths={['w-[18%]', 'w-[14%]']}
        rows={[
          [<Strong>Supabase</Strong>, KEY, <Actions items={['fetch_table']} />],
          [<Strong>Stripe</Strong>, KEY, <Actions items={['create_customer', 'get_customer', 'create_payment_intent', 'create_subscription', 'create_refund']} />],
          [<Strong>Langfuse</Strong>, KEY, <Actions items={['create_trace']} />],
        ]}
      />
      <UL>
        <LI>
          <Strong>Supabase</Strong> — query your own tables mid-call to look up whatever your
          product already knows about the caller.
        </LI>
        <LI>
          <Strong>Stripe</Strong> — look a customer up with <C>get_customer</C>, take money
          with <C>create_payment_intent</C>, start a plan with <C>create_subscription</C>, or
          put it right with <C>create_refund</C>.
        </LI>
        <LI>
          <Strong>Langfuse</Strong> — emit traces for LLM observability if you already run it.
        </LI>
      </UL>
      <Callout kind="danger" title="Think hard before taking card details by voice">
        <C>create_payment_intent</C> is designed to charge a customer who already exists in
        Stripe with a saved payment method — that is the safe shape. Reading a card number to
        a voice agent brings the whole call, its recording, and its transcript into PCI scope.
        Prefer confirming a charge against a stored method, or sending a payment link.
      </Callout>

      <Callout kind="note" title="Nothing here fits?">
        Use an <A href="/docs/tools/integration#custom-tool">API Request or Custom Tool</A>{' '}
        for a direct HTTP call, an <A href="/docs/tools/integration#mcp">MCP tool</A> if you
        already expose your systems through a Model Context Protocol server, or Zapier and
        Make to reach an app either of them already supports.
      </Callout>
    </DocPage>
  )
}
