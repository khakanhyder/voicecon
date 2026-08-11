import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { CodeBlock } from '@/components/docs/CodeBlock'
import {
  A, C, Callout, H2, LI, P, ParamTable, RefHeader, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/tools/integration')

export default function IntegrationToolsPage() {
  return (
    <DocPage href="/docs/tools/integration">
      <P>
        Integration tools let the agent reach outside Voicecon during a call. Where a
        connector exists, use <A href="#connected-integration">Connected Integration</A> — it
        handles credentials, schemas, and rate limits for you.
      </P>

      <RefHeader id="connected-integration" name="Connected Integration" chip="Integration · Recommended" tone="blue">
        Turns any action on a connected app into an AI-callable tool.
      </RefHeader>

      <ParamTable
        params={[
          {
            name: 'connection_id',
            type: 'connection',
            required: true,
            description: (
              <>
                Which connected account to use. The picker lists every connection you have,
                with the number of actions each exposes. Connect apps under{' '}
                <A href="/docs/integrations">Integrations</A> first.
              </>
            ),
          },
          {
            name: 'action',
            type: 'action',
            required: true,
            description: (
              <>
                What to do — <C>create_contact</C>, <C>send_message</C>,{' '}
                <C>create_event</C>. Loaded from the chosen connection.
              </>
            ),
          },
          {
            name: 'parameters',
            type: 'auto',
            description: (
              <>
                Generated from the action&rsquo;s published schema — names, types, descriptions
                and required flags, all correct without typing.
              </>
            ),
          },
        ]}
      />

      <Callout kind="tip" title="Why this beats hand-rolling an API request">
        Credentials are encrypted and refreshed for you, parameters match the real API,
        requests are rate-limited and logged, and OAuth token expiry is handled. An API
        Request tool pointed at the same endpoint gives you none of that.
      </Callout>

      <CodeBlock
        language="A CRM lookup the agent can call"
        code={`Name:         look_up_customer
Description:  Finds a customer record in HubSpot by phone or email.
              Use at the start of a call to identify who is calling.
Connection:   HubSpot — Production
Action:       search_contacts

Parameters (auto-populated)
  query       string   "Search query (name, email, or phone)"   required`}
      />

      <RefHeader id="api-request" name="API Request" chip="Integration" tone="blue">
        Calls any HTTP endpoint. For services without a connector.
      </RefHeader>

      <ParamTable
        params={[
          {
            name: 'url',
            type: 'string',
            required: true,
            description: 'The endpoint. May contain parameter references.',
          },
          {
            name: 'method',
            type: 'enum',
            default: 'POST',
            description: <><C>GET</C>, <C>POST</C>, <C>PUT</C>, <C>PATCH</C>, or <C>DELETE</C>.</>,
          },
          {
            name: 'timeout',
            type: 'seconds',
            default: '20',
            description: (
              <>
                How long to wait. Keep it well below what a caller will tolerate — 20 seconds
                of silence is already too long, so pair a slow endpoint with a workflow tool
                and a holding line.
              </>
            ),
          },
          {
            name: 'headers',
            type: 'JSON',
            default: '{"Content-Type": "application/json"}',
            description: 'Request headers, including authorization.',
          },
          {
            name: 'body',
            type: 'JSON',
            default: '{}',
            description: (
              <>
                Body template. Insert collected values with <C>{'{{parameter_name}}'}</C>.
              </>
            ),
          },
        ]}
      />

      <CodeBlock
        language="Order lookup"
        code={`URL       https://api.example.com/orders/lookup
Method    POST
Headers   { "Authorization": "Bearer sk_live_…",
            "Content-Type": "application/json" }
Body      { "order_id": "{{order_id}}",
            "email":    "{{customer_email}}" }

Parameters
  order_id        string   "The order number the caller reads out"   required
  customer_email  string   "The caller's email address"              optional`}
      />

      <RefHeader id="custom-tool" name="Custom Tool" chip="Integration" tone="blue">
        A webhook tool with first-class authentication handling.
      </RefHeader>

      <P>
        Functionally similar to API Request, but auth is a structured field rather than
        something you hand-assemble into a header.
      </P>

      <ParamTable
        params={[
          {
            name: 'url',
            type: 'string',
            required: true,
            description: 'Your handler endpoint.',
          },
          {
            name: 'method',
            type: 'enum',
            default: 'POST',
            description: <><C>POST</C>, <C>GET</C>, <C>PUT</C>, or <C>PATCH</C>.</>,
          },
          {
            name: 'timeout',
            type: 'seconds',
            default: '20',
            description: 'Request timeout.',
          },
          {
            name: 'auth_type',
            type: 'enum',
            default: 'none',
            description: (
              <>
                <C>none</C>, <C>bearer</C>, <C>basic</C>, or <C>custom_header</C>. The
                relevant credential fields appear once you choose.
              </>
            ),
          },
          {
            name: 'auth_token',
            type: 'secret',
            description: <>Shown for <C>bearer</C>. Sent as <C>Authorization: Bearer …</C>.</>,
          },
          {
            name: 'auth_user / auth_pass',
            type: 'secret',
            description: <>Shown for <C>basic</C>.</>,
          },
          {
            name: 'auth_header / auth_value',
            type: 'secret',
            description: (
              <>
                Shown for <C>custom_header</C> — for APIs using <C>X-API-Key</C> or similar.
              </>
            ),
          },
          {
            name: 'headers',
            type: 'JSON',
            default: '{}',
            description: 'Any additional headers beyond authentication.',
          },
        ]}
      />

      <Callout kind="note" title="Custom Tool or API Request?">
        Use Custom Tool when the endpoint needs authentication — the structured fields are
        clearer and less error-prone than assembling a header by hand. Use API Request for
        unauthenticated endpoints or when you need full control over every header.
      </Callout>

      <RefHeader id="mcp" name="MCP" chip="Integration" tone="blue">
        Calls a tool on a Model Context Protocol server.
      </RefHeader>

      <ParamTable
        params={[
          {
            name: 'server_url',
            type: 'string',
            required: true,
            description: 'The MCP server endpoint.',
          },
          {
            name: 'tool_name',
            type: 'string',
            required: true,
            description: <>The tool function to invoke on that server, e.g. <C>search_crm</C>.</>,
          },
          {
            name: 'timeout',
            type: 'seconds',
            default: '20',
            description: 'Request timeout.',
          },
        ]}
      />

      <P>
        MCP is a standard interface for exposing tools to language models. If your team
        already runs an MCP server, this connects the voice agent to it without rebuilding
        each capability as a separate tool.
      </P>

      <RefHeader id="slack" name="Slack" chip="Integration" tone="blue">
        Posts a message to Slack via an incoming webhook.
      </RefHeader>

      <ParamTable
        params={[
          {
            name: 'webhook_url',
            type: 'string',
            required: true,
            description: 'From Slack App → Incoming Webhooks.',
          },
          {
            name: 'message',
            type: 'text',
            required: true,
            description: <>The message. Supports <C>{'{{parameter}}'}</C> references.</>,
          },
          {
            name: 'channel',
            type: 'string',
            description: <>Overrides the webhook&rsquo;s default channel, e.g. <C>#leads</C>.</>,
          },
        ]}
      />

      <Callout kind="tip" title="Prefer the connected Slack integration">
        This webhook tool is quick to set up but limited to posting. A connected Slack
        integration exposes richer actions and does not require pasting a webhook URL into
        every tool.
      </Callout>

      <RefHeader id="google-sheets" name="Google Sheets" chip="Integration" tone="blue">
        Appends a row to a spreadsheet.
      </RefHeader>

      <ParamTable
        params={[
          {
            name: 'spreadsheet_id',
            type: 'string',
            required: true,
            description: (
              <>
                From the sheet&rsquo;s URL — the long id between <C>/d/</C> and <C>/edit</C>.
              </>
            ),
          },
          {
            name: 'sheet_name',
            type: 'string',
            default: 'Sheet1',
            description: 'The tab within the spreadsheet.',
          },
          {
            name: 'row',
            type: 'JSON array',
            description: (
              <>
                The values to append, in column order —{' '}
                <C>{'["{{caller_name}}", "{{phone}}", "{{date}}"]'}</C>.
              </>
            ),
          },
        ]}
      />

      <P>
        A pragmatic way to capture leads or call outcomes when you do not yet have a CRM, and
        a good staging ground before you commit to one.
      </P>

      <RefHeader id="google-calendar" name="Google Calendar" chip="Integration" tone="blue">
        Creates or retrieves calendar events.
      </RefHeader>

      <ParamTable
        params={[
          {
            name: 'calendar_id',
            type: 'string',
            default: 'primary',
            description: <>Which calendar. <C>primary</C> is the account&rsquo;s default.</>,
          },
          {
            name: 'title',
            type: 'string',
            description: (
              <>
                Event title template —{' '}
                <C>Appointment with {'{{customer_name}}'}</C>.
              </>
            ),
          },
          {
            name: 'duration',
            type: 'minutes',
            default: '30',
            description: 'Event length.',
          },
        ]}
      />

      <Callout kind="warning" title="Booking needs availability">
        This tool creates an event; it does not check whether the slot is free. For real
        booking — check availability, then create, then confirm — use a{' '}
        <A href="/docs/tools/workflow">workflow tool</A> that does all three.
      </Callout>

      <RefHeader id="gohighlevel" name="GoHighLevel" chip="Integration" tone="blue">
        Creates contacts, updates opportunities, and triggers automations in GoHighLevel CRM.
      </RefHeader>

      <ParamTable
        params={[
          {
            name: 'api_key',
            type: 'secret',
            required: true,
            description: 'From GHL Settings → API Keys.',
          },
          {
            name: 'location_id',
            type: 'string',
            required: true,
            description: 'From GHL Settings → Business Profile.',
          },
          {
            name: 'action',
            type: 'enum',
            default: 'create_contact',
            description: (
              <>
                <C>create_contact</C>, <C>update_contact</C>, <C>create_opportunity</C>,{' '}
                <C>add_note</C>, or <C>trigger_workflow</C>.
              </>
            ),
          },
          {
            name: 'pipeline_id',
            type: 'string',
            description: <>Required for <C>create_opportunity</C>; ignored otherwise.</>,
          },
        ]}
      />

      <H2 id="choosing">Choosing between them</H2>
      <Table
        headers={['Destination', 'Use']}
        widths={['w-[40%]']}
        rows={[
          ['An app in the catalog', <><Strong>Connected Integration</Strong> — always the better option</>],
          ['Your own API, with auth', <><Strong>Custom Tool</Strong></>],
          ['Your own API, no auth', <><Strong>API Request</Strong></>],
          ['An MCP server you run', <><Strong>MCP</Strong></>],
          ['Several steps, or branching', <>A <A href="/docs/tools/workflow">workflow tool</A></>],
        ]}
      />
      <UL>
        <LI>
          Check the <A href="/docs/integrations/catalog">catalog</A> before building anything
          by hand.
        </LI>
        <LI>
          If a tool needs to do two things in sequence, it should be a workflow tool, not a
          tool that calls an endpoint which does both.
        </LI>
      </UL>
    </DocPage>
  )
}
