import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { CodeBlock } from '@/components/docs/CodeBlock'
import { Chain, Figure } from '@/components/docs/Diagram'
import {
  A, C, Callout, H2, LI, P, ParamTable, RefHeader, Strong, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/tools/workflow')

export default function WorkflowToolsPage() {
  return (
    <DocPage href="/docs/tools/workflow">
      <RefHeader id="run-workflow" name="Run Workflow" chip="Workflow" tone="violet">
        The agent calls this tool, which runs a workflow. The workflow does the multi-step
        work and talks to your connected apps.
      </RefHeader>

      <P>
        This is the single most useful tool type, because it lifts the ceiling on what an
        agent can do in one move. Instead of five tools the model must sequence correctly, you
        give it one tool backed by a graph you control.
      </P>

      <H2 id="parameters">Parameters</H2>
      <ParamTable
        params={[
          {
            name: 'workflow_id',
            type: 'workflow',
            required: true,
            description: (
              <>
                The workflow to run. Its declared{' '}
                <A href="/docs/nodes/trigger#inputs-as-tool-parameters">trigger inputs</A>{' '}
                automatically become this tool&rsquo;s parameters — you do not define them
                twice.
              </>
            ),
          },
          {
            name: 'filler_message',
            type: 'string',
            description: (
              <>
                A holding line spoken while the workflow runs, so the call does not fall
                silent. See <A href="#holding-line">below</A>.
              </>
            ),
          },
        ]}
      />

      <Callout kind="note" title="Parameters come from the workflow">
        Unlike every other tool type, you do not build a parameter list here. Change the
        workflow&rsquo;s trigger inputs and the tool&rsquo;s parameters change with them,
        which means the two can never drift apart.
      </Callout>

      <H2 id="the-chain">The agent → tool → workflow chain</H2>

      <Figure caption="Each link is configured once. The agent never touches your apps directly.">
        <Chain
          stages={[
            { label: 'Agent', caption: 'decides to act', tone: 'brand' },
            { label: 'Workflow tool', caption: 'collects inputs', tone: 'amber' },
            { label: 'Workflow', caption: 'branches, loops, calls', tone: 'violet' },
            { label: 'Your apps', caption: 'via integrations', tone: 'blue' },
          ]}
        />
      </Figure>

      <P>What happens on a call, in order:</P>
      <UL>
        <LI>The caller says something that matches the tool&rsquo;s description.</LI>
        <LI>The agent extracts the workflow&rsquo;s declared inputs from the conversation, asking for anything missing.</LI>
        <LI>The holding line is spoken.</LI>
        <LI>The workflow runs, with the collected values in <C>{'{{trigger.*}}'}</C>.</LI>
        <LI>Its result comes back, and the agent speaks the outcome.</LI>
      </UL>

      <Callout kind="tip" title="Run it synchronously">
        A workflow invoked mid-call should have <C>execution_mode</C> set to <C>sync</C>, so
        the agent waits for the result and can tell the caller what happened. An async run
        returns immediately and the agent has nothing to report.
      </Callout>

      <Callout kind="note" title="Retries are shortened while a caller waits">
        In a <C>sync</C> run a failing step gets one retry after two seconds, whatever the
        workflow&rsquo;s <C>max_retries</C> and <C>retry_delay</C> say — a minute of backoff
        would be a minute of silence. Plan for the failure in the graph instead; see{' '}
        <A href="/docs/workflows/execution#sync-retry-cap">Retries are capped during a call</A>.
      </Callout>

      <H2 id="holding-line">Avoiding dead air</H2>
      <P>
        A workflow that calls two APIs can take several seconds. On a phone line, silence that
        long reads as a dropped call — people say &ldquo;hello?&rdquo; and then hang up.
      </P>
      <P>
        The <Strong>holding line</Strong> is spoken the moment the tool is invoked. Make it
        specific enough to be reassuring:
      </P>
      <UL>
        <LI><C>&quot;One moment while I check that for you.&quot;</C></LI>
        <LI><C>&quot;Let me get that booked — this will take a few seconds.&quot;</C></LI>
        <LI><C>&quot;I&apos;m pulling up your account now.&quot;</C></LI>
      </UL>
      <Callout kind="warning" title="Keep mid-call workflows fast">
        A holding line buys you a few seconds, not a minute. If a workflow genuinely takes
        long, split it: do the fast part synchronously so the agent can respond, and trigger
        the slow remainder from a{' '}
        <A href="/docs/workflows/triggers#call-completed">call completed</A> workflow
        afterwards.
      </Callout>

      <H2 id="example">Example</H2>
      <P>
        An agent that books appointments. One tool on the agent; all the complexity in the
        workflow.
      </P>

      <CodeBlock
        language="The tool"
        code={`Name:          book_appointment
Description:   Books, moves, or cancels a clinic appointment.
               Use whenever the caller wants to arrange a visit.
Type:          Run Workflow
Workflow:      Appointment Booking
Holding line:  Let me check the diary for you — one moment.`}
      />

      <CodeBlock
        language="The workflow behind it"
        code={`Trigger (manual)
  inputs:  customer_name    string   required
           preferred_date   string   required
           appointment_type string   optional

  ↓
Integration — Google Calendar · list_events        (n_free01)
  checks availability on {{trigger.preferred_date}}

  ↓
Branch  —  steps.n_free01.slots_available  is not empty
  │
  ├─ true  → Integration: create_event
  │          → Integration: HubSpot · create_contact
  │          → Set Fields: outcome = "booked"
  │
  └─ false → Set Fields: outcome = "no availability"
             → alternatives = {{steps.n_free01.next_open}}`}
      />

      <P>
        From the agent&rsquo;s point of view this is one action. From the caller&rsquo;s point
        of view it is a short pause and then an answer. All the branching, the two API calls,
        and the fallback live in the workflow, where you can see and test them.
      </P>

      <Callout kind="tip" title="Design workflows around outcomes">
        Have the workflow finish by setting a small number of named outcome variables —{' '}
        <C>outcome</C>, <C>reference</C>, <C>alternatives</C>. That gives the agent something
        clean to speak, rather than leaving it to interpret a raw API response.
      </Callout>
    </DocPage>
  )
}
