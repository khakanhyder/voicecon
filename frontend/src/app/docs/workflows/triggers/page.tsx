import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { CodeBlock } from '@/components/docs/CodeBlock'
import {
  A, C, Callout, H2, H3, LI, P, ParamTable, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/workflows/triggers')

export default function TriggersPage() {
  return (
    <DocPage href="/docs/workflows/triggers">
      <H2 id="trigger-types">The six trigger types</H2>
      <P>
        Every workflow has exactly one trigger. It decides when the workflow runs and what
        data arrives in <C>{'{{trigger.*}}'}</C>.
      </P>

      <Table
        headers={['Trigger', 'Fires when', 'Typical use']}
        widths={['w-[20%]', 'w-[34%]']}
        rows={[
          [<C>manual</C>, 'You run it, or a tool invokes it', 'Mid-call actions, one-off jobs'],
          [<C>schedule</C>, 'A recurring time arrives', 'Nightly sync, daily digest'],
          [<C>webhook</C>, 'An HTTP request hits its URL', 'External systems pushing events'],
          [<C>call_started</C>, 'A call connects', 'Screen-pop, log the start'],
          [<C>call_completed</C>, 'A call ends', 'Post-call CRM write, follow-up'],
          [<C>integration_event</C>, 'A connected app emits an event', 'Deal moves stage, form submitted'],
        ]}
      />

      <H2 id="manual">Manual</H2>
      <P>
        Runs when something explicitly asks it to — the <Strong>Run</Strong> button, an API
        call, or a <A href="/docs/tools/workflow">workflow tool</A> invoked by an agent
        mid-call.
      </P>
      <P>
        This is the most common trigger by a wide margin, because it is the one that makes a
        workflow usable from a live conversation.
      </P>
      <CodeBlock
        language="bash"
        code={`curl -X POST https://api.your-voicecon-host.com/api/v1/workflows/{workflow_id}/execute \\
  -H "Authorization: Bearer $VOICECON_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{ "trigger_data": { "customer_email": "ada@example.com" } }'`}
      />
      <P>
        Whatever you pass as <C>trigger_data</C> is available as{' '}
        <C>{'{{trigger.customer_email}}'}</C> and so on.
      </P>

      <H2 id="schedule">Schedule</H2>
      <P>
        Runs on a timetable, with no caller involved. There are three kinds, chosen with{' '}
        <C>schedule_type</C>.
      </P>
      <ParamTable
        params={[
          {
            name: 'schedule_type',
            type: 'enum',
            required: true,
            description: (
              <>
                <C>cron</C>, <C>interval</C>, or <C>one_time</C>. Each needs its own companion
                field below.
              </>
            ),
          },
          {
            name: 'cron_expression',
            type: 'string',
            description: (
              <>
                Required when <C>schedule_type</C> is <C>cron</C>. A standard five-field cron
                expression: <C>0 9 * * 1-5</C> is 09:00 on weekdays, <C>*/15 * * * *</C> is
                every fifteen minutes. Rejected at save time if it does not parse.
              </>
            ),
          },
          {
            name: 'interval_seconds',
            type: 'number',
            description: (
              <>
                Required when <C>schedule_type</C> is <C>interval</C>. A positive whole number
                of seconds between runs — simpler than cron when you just want &ldquo;every
                ten minutes&rdquo;.
              </>
            ),
          },
          {
            name: 'scheduled_at',
            type: 'ISO 8601 datetime',
            description: (
              <>
                Required when <C>schedule_type</C> is <C>one_time</C>. Runs once, then never
                again — e.g. <C>2026-09-01T09:00:00Z</C>.
              </>
            ),
          },
        ]}
      />
      <Callout kind="warning" title="Schedules run in UTC">
        Cron expressions are evaluated in UTC; there is no timezone setting. Convert your
        local time yourself — 09:00 London in winter is <C>0 9 * * *</C>, and in summer it is{' '}
        <C>0 8 * * *</C>. If the hour matters, either accept the seasonal drift or use two
        workflows with date-bounded schedules.
      </Callout>
      <Callout kind="warning" title="Scheduled runs have no caller">
        Conversation nodes — Speak, Ask, Transfer, End Call — have nobody to talk to on a
        scheduled run. Keep scheduled workflows to Logic and Action nodes.
      </Callout>

      <H2 id="webhook">Webhook</H2>
      <P>
        Gives the workflow a URL. Any system that can send an HTTP request can start it, and
        the request body arrives as the trigger data. The endpoint is public — the key in the
        path is what authorises the call.
      </P>
      <CodeBlock
        language="Starting a workflow by webhook"
        code={`POST https://<your-host>/api/v1/workflows/webhook/<webhook_key>
Content-Type: application/json

{ "order_id": 4021, "status": "shipped" }`}
      />
      <ParamTable
        params={[
          {
            name: 'webhook_key',
            type: 'string',
            required: true,
            description: (
              <>
                The shared secret that authorises a request, and the last path segment of the
                URL above. At least 16 characters; a 32-byte random key is generated for you
                when you create a webhook workflow without supplying one.
              </>
            ),
          },
          {
            name: 'allowed_ips',
            type: 'string[]',
            description: (
              <>
                Optional source-IP allowlist. When present, a request from any other address
                is refused even with the right key.
              </>
            ),
          },
        ]}
      />

      <Callout kind="warning" title="No key means no runs">
        A webhook workflow with no <C>webhook_key</C> configured never fires — requests are
        refused rather than accepted. That is deliberate: treating a missing key as &ldquo;no
        check needed&rdquo; would let anyone who found the public endpoint run your workflow.
        If your webhook workflow appears to do nothing, this is the first thing to check.
      </Callout>
      <P>
        A request body of <C>{'{"order_id": 4021, "status": "shipped"}'}</C> makes{' '}
        <C>{'{{trigger.order_id}}'}</C> the number <C>4021</C> — types are preserved, not
        stringified. See <A href="/docs/workflows/variables#type-preservation">Type
        preservation</A>.
      </P>

      <H2 id="call-started">Call started</H2>
      <P>
        Fires the moment a call connects, in parallel with the conversation. The workflow runs
        alongside the call rather than inside it.
      </P>
      <UL>
        <LI>Look the caller up in your CRM and log an inbound contact.</LI>
        <LI>Post a notification so a human can listen in if needed.</LI>
      </UL>
      <P>
        Trigger data is the same shape for both call triggers — see{' '}
        <A href="#call-trigger-data">what a call trigger passes in</A>.
      </P>
      <Callout kind="note" title="This does not shape the call">
        A call-started workflow cannot speak to the caller — the agent is already handling
        the conversation. To act <em>within</em> a call, give the agent a{' '}
        <A href="/docs/tools/workflow">workflow tool</A> instead.
      </Callout>

      <H2 id="call-completed">Call completed</H2>
      <P>
        Fires after a call ends, once the transcript, summary, and analysis exist. This is the
        workhorse trigger for everything that happens because a call happened.
      </P>
      <UL>
        <LI>Write the summary into the CRM against the contact.</LI>
        <LI>Create a task when the caller asked for a callback.</LI>
        <LI>Send a follow-up SMS or email.</LI>
        <LI>Alert a supervisor when sentiment came back negative.</LI>
      </UL>
      <P>
        By this point the transcript, intent, and sentiment have been worked out, so they are
        all available to the workflow.
      </P>
      <CodeBlock
        language="Filtering to the calls you care about"
        code={`Trigger (call_completed)
  → Filter: trigger.duration greater_than 30
  → Filter: trigger.sentiment equals negative
  → Integration: create a follow-up task`}
      />

      <H3 id="call-trigger-data">What a call trigger passes in</H3>
      <P>
        Both call triggers deliver the same fixed set of fields. Anything not listed here is
        not available — reach for it and you get an empty value.
      </P>
      <Table
        headers={['Reference', 'Is']}
        widths={['w-[34%]']}
        rows={[
          [<C>{'{{trigger.call_id}}'}</C>, 'The call’s id in Voicecon.'],
          [<C>{'{{trigger.call_sid}}'}</C>, 'The carrier’s own id for the call.'],
          [<C>{'{{trigger.status}}'}</C>, 'How the call ended — completed, failed, no-answer, and so on.'],
          [<C>{'{{trigger.duration}}'}</C>, 'Length in seconds.'],
          [<C>{'{{trigger.agent_id}}'}</C>, 'Which agent handled it.'],
          [<C>{'{{trigger.phone_number}}'}</C>, 'The number on the other end.'],
          [<C>{'{{trigger.transcript}}'}</C>, 'The conversation as text.'],
          [<C>{'{{trigger.intent}}'}</C>, 'The detected intent.'],
          [<C>{'{{trigger.sentiment}}'}</C>, 'The detected sentiment.'],
          [<C>{'{{trigger.metadata}}'}</C>, 'Any extra data attached to the call. Reach into it with dots.'],
          [<C>{'{{trigger.triggered_at}}'}</C>, 'When the trigger fired, as an ISO 8601 timestamp.'],
        ]}
      />

      <H3 id="call-trigger-filters">Firing on only some calls</H3>
      <P>
        Both call triggers accept a <C>filters</C> object, so the workflow starts only for
        calls that match. Filtering here is cheaper than starting every run and stopping it
        with a <A href="/docs/nodes/logic#filter">Filter</A> node — though the Filter node is
        the right tool for anything these do not cover.
      </P>
      <Table
        headers={['Filter', 'Matches when']}
        widths={['w-[24%]']}
        rows={[
          [<C>status</C>, 'The call’s status is exactly this.'],
          [<C>duration_min</C>, 'The call lasted at least this many seconds.'],
          [<C>duration_max</C>, 'The call lasted no more than this many seconds.'],
          [<C>agent_id</C>, 'This agent handled the call.'],
          [<C>phone_number</C>, 'The number matches.'],
          [<C>sentiment</C>, 'The detected sentiment matches.'],
          [<C>intent</C>, 'The detected intent matches.'],
          [<C>keywords</C>, 'The transcript contains the given words.'],
        ]}
      />
      <Callout kind="note" title="No filters means every call">
        A call trigger with no <C>filters</C> fires for every call in the workspace. On a busy
        line that is a lot of runs — add at least a <C>duration_min</C> so hang-ups and
        wrong numbers do not each create a CRM record.
      </Callout>

      <H2 id="integration-event">Integration event</H2>
      <P>
        Fires when a connected app reports something happened — available on connectors that
        support webhooks.
      </P>
      <ParamTable
        params={[
          {
            name: 'connection_id',
            type: 'connection',
            required: true,
            description: 'Which connected account to listen to.',
          },
          {
            name: 'event_type',
            type: 'string',
            required: true,
            description: (
              <>
                The event to match, e.g. <C>deal.stage_changed</C>. Available events depend on
                the connector.
              </>
            ),
          },
          {
            name: 'filters',
            type: 'object',
            description: 'Narrow further — only deals above a value, only a given pipeline.',
          },
        ]}
      />

      <H2 id="declaring-inputs">Declaring inputs</H2>
      <P>
        The Trigger node has an <Strong>Inputs</Strong> field where you declare the values the
        workflow expects. Declaring them does two jobs at once:
      </P>
      <UL>
        <LI>
          They become references — an input named <C>customer_email</C> is available
          everywhere as <C>{'{{trigger.customer_email}}'}</C>.
        </LI>
        <LI>
          When the workflow is used as a <A href="/docs/tools/workflow">workflow tool</A>,
          they become the tool&rsquo;s parameters — the values the agent must collect from the
          caller before it can run the workflow.
        </LI>
      </UL>

      <Callout kind="tip" title="Name inputs for the agent, not for yourself">
        Because inputs become the parameters an agent extracts from speech, their names and
        descriptions are read by the model. <C>customer_email</C> with the description
        &ldquo;the caller&rsquo;s email address&rdquo; is extracted reliably; <C>e1</C> is not.
        The same rules as <A href="/docs/tools/parameters">tool parameters</A> apply.
      </Callout>
    </DocPage>
  )
}
