import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { CodeBlock } from '@/components/docs/CodeBlock'
import {
  A, C, Callout, H2, H3, LI, P, ParamTable, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/calls')

export default function CallsPage() {
  return (
    <DocPage href="/docs/calls">
      <H2 id="call-lifecycle">The call lifecycle</H2>
      <P>
        Every call — inbound, outbound, or a browser test — produces a record. That record is
        both your audit trail and your primary debugging tool.
      </P>
      <Table
        headers={['Stage', 'Recorded']}
        widths={['w-[24%]']}
        rows={[
          ['Initiated', <>The call is created. <C>started_at</C> is set.</>],
          ['Answered', <><C>answered_at</C> is set. Billing starts here, not at initiation.</>],
          ['In progress', 'Transcript and event log accumulate turn by turn.'],
          ['Ended', <><C>ended_at</C>, duration, and a disconnection reason.</>],
          ['Processed', 'Recording stored, summary written, analysis run, costs totalled.'],
        ]}
      />
      <Callout kind="note" title="Summaries arrive slightly late">
        Summary and analysis are produced after the call ends, so a call opened the instant it
        finishes may show a transcript but no summary yet. Refresh in a few seconds.
      </Callout>

      <H2 id="directions">Directions and statuses</H2>
      <Table
        headers={['Direction', 'Meaning']}
        widths={['w-[20%]']}
        rows={[
          [<C>inbound</C>, 'Someone called one of your numbers.'],
          [<C>outbound</C>, 'Voicecon placed the call, via the API or a workflow.'],
          [<C>test</C>, 'A browser test. No telephony involved and no carrier cost.'],
        ]}
      />
      <Table
        headers={['Status', 'Meaning']}
        widths={['w-[20%]']}
        rows={[
          [<C>initiated</C>, 'Created but not yet connected.'],
          [<C>in_progress</C>, 'Live right now.'],
          [<C>completed</C>, 'Ended normally.'],
          [<C>missed</C>, 'Never answered.'],
          [<C>failed</C>, 'Could not connect — bad number, carrier rejection, or a platform error.'],
        ]}
      />
      <Callout kind="tip" title="A rising failed count is a signal">
        Occasional failures are normal. A cluster usually means a carrier problem, an expired
        credential, or a number whose configuration has drifted. Check the connection under{' '}
        <A href="/docs/integrations#testing-a-connection">Integrations</A> first.
      </Callout>

      <H2 id="the-call-list">The call list</H2>
      <P>
        <Strong>Calls</Strong> shows every call, most recent first. Each row gives you the
        assistant side and the customer side of the conversation, the status, the duration,
        and the end reason — so you can spot a pattern without opening anything.
      </P>
      <UL>
        <LI><Strong>Search</Strong> across numbers and content.</LI>
        <LI><Strong>Filter by status</Strong> to isolate failures or missed calls.</LI>
        <LI>
          The <Strong>end reason</Strong> column comes from the disconnection reason on the
          call record, which is more specific than the status alone.
        </LI>
      </UL>

      <H2 id="call-detail">The call detail view</H2>
      <P>Opening a call gives you five things, in roughly the order you will want them.</P>
      <ParamTable
        params={[
          {
            name: 'Transcript',
            type: 'text + json',
            description: 'The conversation, turn by turn. The first place to look, always.',
          },
          {
            name: 'Recording',
            type: 'audio',
            description: 'The audio, when recording is enabled. Reveals tone and timing the transcript cannot.',
          },
          {
            name: 'Summary',
            type: 'text',
            description: 'An AI-written recap. Good enough to paste into a CRM note.',
          },
          {
            name: 'Analysis',
            type: 'object',
            description: 'Sentiment, intent, topics — when the corresponding agent settings are enabled.',
          },
          {
            name: 'Event log',
            type: 'entry[]',
            description: 'Per-stage timings, tool calls, and errors. The forensic layer.',
          },
        ]}
      />

      <H2 id="transcripts">Transcripts and recordings</H2>
      <P>
        The transcript is stored both as plain text and as structured JSON with speaker and
        timing on each turn — the plain text for reading, the JSON for programmatic analysis.
      </P>
      <H3>Reading a transcript well</H3>
      <UL>
        <LI>
          <Strong>Look for the first divergence</Strong>, not the worst moment. Calls usually
          go wrong once and then compound.
        </LI>
        <LI>
          <Strong>Distinguish mishearing from misjudging.</Strong> If the transcript shows the
          agent answering a question the caller did not ask, the transcriber failed — that is
          an <A href="/docs/agents/configuration#transcriber">STT</A> problem, not a prompt
          problem.
        </LI>
        <LI>
          <Strong>Watch for missing tool calls.</Strong> An agent that says &ldquo;let me check
          that&rdquo; and then answers from nothing never invoked the tool. Check the event
          log to confirm.
        </LI>
      </UL>
      <Callout kind="warning" title="Recordings carry legal obligations">
        Many jurisdictions require notifying callers that a call is recorded, and some require
        consent. Retention limits may also apply. Put the notification in the agent&rsquo;s
        first message.
      </Callout>

      <H2 id="analysis">Summary and analysis</H2>
      <Table
        headers={['Field', 'What it holds']}
        widths={['w-[24%]']}
        rows={[
          [<C>summary</C>, 'A short recap of what happened and what was agreed.'],
          [<C>sentiment_score</C>, 'A numeric score. Requires sentiment analysis on the agent.'],
          [<C>sentiment_label</C>, <>A readable label — <C>positive</C>, <C>neutral</C>, <C>negative</C>.</>],
          [<C>emotions</C>, 'Finer-grained signals. Requires emotion detection on the agent.'],
          [<C>intent</C>, 'What the caller wanted, in one phrase.'],
          [<C>topics</C>, 'Subjects covered. Aggregate across calls to see what people actually ring about.'],
          [<C>tags</C>, 'Your own labels, applied manually or by a workflow.'],
        ]}
      />
      <Callout kind="tip" title="Act on analysis automatically">
        A <A href="/docs/workflows/triggers#call-completed">call completed</A> workflow with a{' '}
        <A href="/docs/nodes/logic#filter">Filter</A> on{' '}
        <C>trigger.sentiment_label equals negative</C> turns a passive metric into a
        same-day follow-up.
      </Callout>

      <H2 id="event-log">The event log</H2>
      <P>
        Beneath each call sits a timestamped log of what the system did. It is the difference
        between &ldquo;the call felt slow&rdquo; and &ldquo;the model took 2.1 seconds on turn
        four&rdquo;.
      </P>
      <ParamTable
        params={[
          {
            name: 'log_type',
            type: 'enum',
            description: (
              <>
                Which stage — <C>stt</C>, <C>llm</C>, <C>tts</C>, <C>function</C>, and others.
              </>
            ),
          },
          {
            name: 'severity',
            type: 'enum',
            default: 'info',
            description: <><C>debug</C>, <C>info</C>, <C>warning</C>, or <C>error</C>.</>,
          },
          {
            name: 'message',
            type: 'string',
            description: 'What happened.',
          },
          {
            name: 'details',
            type: 'object',
            description: 'Stage-specific payload — the model request, the tool arguments, the error body.',
          },
          {
            name: 'duration_ms',
            type: 'number',
            description: 'How long that stage took. This is the column to sort by when tuning latency.',
          },
          {
            name: 'cost',
            type: 'decimal',
            description: 'What that stage cost, summing into the call total.',
          },
        ]}
      />
      <CodeBlock
        language="What a slow turn looks like"
        code={`12:04:11.204  stt        Transcribed caller turn                    412ms
12:04:11.618  llm        Model call — gpt-4o                       2,140ms   ← the cost
12:04:13.760  function   Tool: look_up_customer                      680ms
12:04:14.441  tts        Synthesised reply — ElevenLabs              390ms

# Total ≈3.6s before the caller heard anything.
# The fix here is a faster model, not a faster voice.`}
      />

      <H2 id="costs">Cost breakdown</H2>
      <P>Every call is costed across four components, so you can see where the money goes.</P>
      <Table
        headers={['Field', 'Covers']}
        widths={['w-[24%]']}
        rows={[
          [<C>cost_stt</C>, 'Transcribing caller audio.'],
          [<C>cost_llm</C>, 'Model calls — usually the largest share on a conversational agent.'],
          [<C>cost_tts</C>, 'Speech synthesis. Scales with how much the agent says.'],
          [<C>cost_telephony</C>, 'Carrier charges. Zero on browser tests.'],
          [<C>cost_total</C>, 'The sum.'],
        ]}
      />
      <UL>
        <LI>
          <Strong>LLM cost high?</Strong> Use a smaller model, shorten the system prompt, or
          reduce the number of assigned tools — all three shrink every request.
        </LI>
        <LI>
          <Strong>TTS cost high?</Strong> The agent is talking too much. Ask for shorter
          replies in the prompt; the caller will prefer it too.
        </LI>
        <LI>
          <Strong>Telephony cost high?</Strong> Calls are running long. Check{' '}
          <C>max_call_duration</C> and look for flows where callers get stuck.
        </LI>
      </UL>
      <P>
        Aggregate figures across agents and date ranges live in{' '}
        <A href="/docs/analytics">Analytics</A>.
      </P>

      <H2 id="contacts">Contacts</H2>
      <P>
        Calls are also grouped by the other party&rsquo;s number, giving you a per-contact
        history. Opening a contact shows every call with that number, which is how you spot a
        caller who has now rung four times about the same unresolved thing.
      </P>
      <Callout kind="tip" title="Repeat callers are your best signal">
        Someone calling repeatedly about one issue is the clearest evidence of a gap — a
        missing tool, a knowledge base that does not cover something, or a flow with no way
        out. Sort by repeat frequency and read those transcripts first.
      </Callout>
    </DocPage>
  )
}
