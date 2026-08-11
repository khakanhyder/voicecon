import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { CodeBlock } from '@/components/docs/CodeBlock'
import {
  A, C, Callout, H2, LI, P, ParamTable, Strong, Table, UL,
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
      <P>Runs on a recurring timetable, with no caller involved.</P>
      <ParamTable
        params={[
          {
            name: 'cron',
            type: 'string',
            required: true,
            description: (
              <>
                Standard five-field cron expression. <C>0 9 * * 1-5</C> is 09:00 on weekdays;{' '}
                <C>*/15 * * * *</C> is every fifteen minutes.
              </>
            ),
          },
          {
            name: 'timezone',
            type: 'IANA zone',
            default: 'UTC',
            description: (
              <>
                The zone the expression is read in. Set this to your business timezone or
                &ldquo;9am&rdquo; will drift by an hour twice a year.
              </>
            ),
          },
        ]}
      />
      <Callout kind="warning" title="Scheduled runs have no caller">
        Conversation nodes — Speak, Ask, Transfer, End Call — have nobody to talk to on a
        scheduled run. Keep scheduled workflows to Logic and Action nodes.
      </Callout>

      <H2 id="webhook">Webhook</H2>
      <P>
        Gives the workflow a URL. Any system that can send an HTTP request can start it, and
        the request body arrives as the trigger data.
      </P>
      <ParamTable
        params={[
          {
            name: 'url',
            type: 'string',
            description: 'Generated for you when you select this trigger. Copy it into the sending system.',
          },
          {
            name: 'secret',
            type: 'string',
            description: (
              <>
                Shared secret for verifying the sender. Set it whenever the URL is known
                outside your organisation — an unauthenticated webhook URL is an open door.
              </>
            ),
          },
          {
            name: 'method',
            type: 'enum',
            default: 'POST',
            description: 'The HTTP method the endpoint accepts.',
          },
        ]}
      />
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
        Trigger data includes the call id, direction, from and to numbers, and the agent.
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
        Trigger data carries the full call record: duration, status, transcript, summary,
        sentiment, intent, topics, and cost.
      </P>
      <CodeBlock
        language="Filtering to the calls you care about"
        code={`Trigger (call_completed)
  → Filter: trigger.duration_seconds greater_than 30
  → Filter: trigger.sentiment_label equals negative
  → Integration: create a follow-up task`}
      />

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
