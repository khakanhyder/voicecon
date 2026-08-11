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

export default function CatalogPage() {
  return (
    <DocPage href="/docs/integrations/catalog">
      <P>
        Every connector, grouped by what it is for, with the actions each exposes. Actions are
        available in both{' '}
        <A href="/docs/nodes/actions#action">workflow Integration nodes</A> and{' '}
        <A href="/docs/tools/integration#connected-integration">Connected Integration tools</A>.
      </P>

      <Callout kind="note" title="Actions are the tested surface">
        Each connector supports more of its provider&rsquo;s API than is listed here; these
        are the actions exposed with published schemas, so they get parameter validation and
        resource pickers. For anything outside the list, use an{' '}
        <A href="/docs/nodes/actions#webhook">API Request or Webhook</A>.
      </Callout>

      <H2 id="crm">CRM and sales</H2>
      <Table
        headers={['App', 'Auth', 'Actions']}
        widths={['w-[18%]', 'w-[14%]']}
        rows={[
          [<Strong>HubSpot</Strong>, <Badge tone="brand">OAuth</Badge>, <Actions items={['create_contact', 'search_contacts', 'update_contact', 'create_deal']} />],
          [<Strong>Salesforce</Strong>, <Badge tone="brand">OAuth</Badge>, <Actions items={['create_contact', 'create_lead', 'search_contacts']} />],
          [<Strong>GoHighLevel</Strong>, <Badge tone="slate">API key</Badge>, <Actions items={['create_contact']} />],
        ]}
      />
      <P>
        The most common voice use: identify the caller with <C>search_contacts</C> at the
        start of the call, then write the outcome back with <C>create_contact</C> or{' '}
        <C>update_contact</C> when it ends.
      </P>

      <H2 id="productivity">Productivity and project management</H2>
      <Table
        headers={['App', 'Auth', 'Actions']}
        widths={['w-[18%]', 'w-[14%]']}
        rows={[
          [<Strong>Notion</Strong>, <Badge tone="brand">OAuth</Badge>, <Actions items={['search', 'create_page', 'append_text']} />],
          [<Strong>ClickUp</Strong>, <Badge tone="brand">OAuth</Badge>, <Actions items={['create_task', 'list_tasks', 'add_comment']} />],
          [<Strong>Trello</Strong>, <Badge tone="slate">API key</Badge>, <Actions items={['create_card', 'add_comment']} />],
          [<Strong>Monday</Strong>, <Badge tone="brand">OAuth</Badge>, <Actions items={['list_boards']} />],
          [<Strong>Airtable</Strong>, <Badge tone="brand">OAuth</Badge>, <Actions items={['create_record']} />],
          [<Strong>Google Sheets</Strong>, <Badge tone="brand">OAuth</Badge>, <Actions items={['append_row']} />],
          [<Strong>Google Drive</Strong>, <Badge tone="brand">OAuth</Badge>, <Actions items={['list_files']} />],
        ]}
      />
      <P>
        Trello, ClickUp, Monday, Notion, and Airtable all expose{' '}
        <A href="/docs/integrations#resource-pickers">resource pickers</A> — pick a board,
        list, or database from a dropdown, or paste its URL.
      </P>

      <H2 id="calendar">Calendar and scheduling</H2>
      <Table
        headers={['App', 'Auth', 'Actions']}
        widths={['w-[18%]', 'w-[14%]']}
        rows={[
          [
            <Strong>Google Calendar</Strong>,
            <Badge tone="brand">OAuth</Badge>,
            <Actions items={['check_availability', 'find_available_slots', 'create_event', 'list_events']} />,
          ],
          [<Strong>Calendly</Strong>, <Badge tone="brand">OAuth</Badge>, <Actions items={['list_scheduled_events']} />],
          [<Strong>Cal.com</Strong>, <Badge tone="slate">API key</Badge>, <Actions items={['list_event_types']} />],
        ]}
      />
      <Callout kind="tip" title="Book properly, in three steps">
        Google Calendar is the only connector with a full booking cycle. Use{' '}
        <C>find_available_slots</C> to offer real options, <C>create_event</C> to book, then
        confirm back to the caller — all inside one{' '}
        <A href="/docs/tools/workflow">workflow tool</A>. Booking without checking
        availability first is how double-bookings happen.
      </Callout>

      <H2 id="messaging">Messaging and email</H2>
      <Table
        headers={['App', 'Auth', 'Actions']}
        widths={['w-[18%]', 'w-[14%]']}
        rows={[
          [<Strong>Slack</Strong>, <Badge tone="brand">OAuth</Badge>, <Actions items={['send_message']} />],
          [<Strong>SendGrid</Strong>, <Badge tone="slate">API key</Badge>, <Actions items={['send_email']} />],
          [<Strong>WhatsApp</Strong>, <Badge tone="slate">API key</Badge>, <Actions items={['send_message', 'send_template']} />],
        ]}
      />
      <UL>
        <LI>
          <Strong>Slack</Strong> offers a channel picker, and a connection default so you can
          change the destination channel in one place.
        </LI>
        <LI>
          <Strong>WhatsApp</Strong> requires pre-approved templates for business-initiated
          messages — that is what <C>send_template</C> is for. Free-form{' '}
          <C>send_message</C> only works inside an open conversation window.
        </LI>
      </UL>

      <H2 id="telephony">Telephony</H2>
      <Table
        headers={['App', 'Auth', 'Actions', 'Numbers?']}
        widths={['w-[16%]', 'w-[13%]', 'w-[30%]']}
        rows={[
          [<Strong>Twilio</Strong>, <Badge tone="slate">API key</Badge>, <Actions items={['send_sms']} />, 'Yes'],
          [<Strong>Telnyx</Strong>, <Badge tone="slate">API key</Badge>, <Actions items={['send_message']} />, 'Yes'],
          [<Strong>Vonage</Strong>, <Badge tone="slate">API key</Badge>, <Actions items={['send_sms']} />, '—'],
        ]}
      />
      <P>
        Twilio and Telnyx double as <A href="/docs/phone-numbers#providers">number
        providers</A>: connect one and you can search for and buy phone numbers directly from
        Voicecon. See <A href="/docs/phone-numbers">Phone Numbers</A>.
      </P>

      <H2 id="data">Data and infrastructure</H2>
      <Table
        headers={['App', 'Auth', 'Actions']}
        widths={['w-[18%]', 'w-[14%]']}
        rows={[
          [<Strong>Supabase</Strong>, <Badge tone="slate">API key</Badge>, <Actions items={['fetch_table']} />],
          [<Strong>Stripe</Strong>, <Badge tone="slate">API key</Badge>, <>Payments and subscription data</>],
          [<Strong>Langfuse</Strong>, <Badge tone="slate">API key</Badge>, <Actions items={['create_trace']} />],
        ]}
      />
      <UL>
        <LI>
          <Strong>Supabase</Strong> — query your own tables mid-call to look up whatever your
          product already knows about the caller.
        </LI>
        <LI>
          <Strong>Langfuse</Strong> — emit traces for LLM observability if you already run it.
        </LI>
      </UL>

      <Callout kind="note" title="Nothing here fits?">
        Use an <A href="/docs/tools/integration#custom-tool">API Request or Custom Tool</A>{' '}
        for a direct HTTP call, or an <A href="/docs/tools/integration#mcp">MCP tool</A> if
        you already expose your systems through a Model Context Protocol server.
      </Callout>
    </DocPage>
  )
}
