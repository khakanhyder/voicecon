import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { Chain, Figure } from '@/components/docs/Diagram'
import {
  A, Badge, C, Callout, H2, H3, LI, P, Step, Steps, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/workflows')

export default function WorkflowsPage() {
  return (
    <DocPage href="/docs/workflows">
      <H2 id="what-is-a-workflow">What is a workflow?</H2>
      <P>
        A workflow is a graph of steps you draw on a canvas. Each node does one thing — ask a
        question, branch on a value, call an API, run some code — and edges decide what
        happens next.
      </P>
      <P>
        Where an agent is probabilistic (the model chooses), a workflow is deterministic (you
        chose). That makes workflows the right tool whenever the sequence matters, the branch
        conditions are known, or an auditor might one day ask what happened.
      </P>

      <H2 id="when-to-use">When to use a workflow</H2>
      <Table
        headers={['Situation', 'Workflow?']}
        widths={['w-[52%]']}
        rows={[
          ['One action, no branching — send an SMS', <>No. Use a single <A href="/docs/tools">tool</A>.</>],
          ['Several actions in a fixed order', <>Yes.</>],
          ['The next step depends on an earlier answer', <>Yes — that is what Branch and Switch are for.</>],
          ['Something must happen after every call ends', <>Yes, with a <A href="/docs/workflows/triggers#call-completed">call completed</A> trigger.</>],
          ['Something must happen on a schedule', <>Yes, with a <A href="/docs/workflows/triggers#schedule">schedule</A> trigger.</>],
          ['An open-ended conversation', <>No. That is an agent&rsquo;s job.</>],
          ['A scripted intake or survey', <>Yes — conversation nodes give you an exact script.</>],
        ]}
      />

      <H2 id="the-builder">The builder</H2>
      <P>The canvas has three regions, and you will move between them constantly.</P>

      <Figure caption="Palette on the left, canvas in the middle, inspector on the right.">
        <Chain
          stages={[
            { label: 'Palette', caption: 'nodes to add', tone: 'slate' },
            { label: 'Canvas', caption: 'the graph', tone: 'brand' },
            { label: 'Inspector', caption: 'selected node’s fields', tone: 'violet' },
          ]}
        />
      </Figure>

      <UL>
        <LI>
          <Strong>Palette</Strong> — every node type, grouped into Conversation, Logic,
          Actions, and AI. Drag onto the canvas or click to place.
        </LI>
        <LI>
          <Strong>Canvas</Strong> — nodes and edges. Each node shows its title and a one-line
          summary of its configuration, so a glance tells you what the graph does without
          opening anything.
        </LI>
        <LI>
          <Strong>Inspector</Strong> — the selected node&rsquo;s parameters. Fields appear and
          disappear based on other fields; a Branch node with <C>is empty</C> selected hides
          its value field, because there is nothing to compare against.
        </LI>
      </UL>

      <P>
        The toolbar carries <Strong>Save</Strong> and <Strong>Run</Strong>. Running saves
        first, so a test always executes the graph in front of you rather than the last saved
        version.
      </P>

      <H2 id="creating-a-workflow">Creating a workflow</H2>
      <Steps>
        <Step n={1} title="Create and name it">
          <P>
            <Strong>Workflows</Strong> → <Strong>New Workflow</Strong>. Every workflow begins
            with a Trigger node already on the canvas.
          </P>
        </Step>
        <Step n={2} title="Choose the trigger">
          <P>
            What starts it — manual, schedule, webhook, a call event, or an integration
            event. See <A href="/docs/workflows/triggers">Triggers</A>.
          </P>
        </Step>
        <Step n={3} title="Declare inputs">
          <P>
            On the Trigger node, declare the values the workflow needs. These become
            references like <C>{'{{trigger.customer_email}}'}</C>, and — when the workflow is
            invoked by a workflow tool — they become the parameters the agent collects.
          </P>
        </Step>
        <Step n={4} title="Add nodes and connect them">
          <P>
            Drag from a node&rsquo;s output handle to the next node&rsquo;s input. Full
            reference in <A href="/docs/nodes">All Nodes</A>.
          </P>
        </Step>
        <Step n={5} title="Run a test">
          <P>
            <Strong>Run</Strong> executes the graph and lights up each node as it completes.
            See <A href="/docs/workflows/execution">Running &amp; History</A>.
          </P>
        </Step>
        <Step n={6} title="Activate it">
          <P>
            A workflow that is not active will not run — an execute request against an
            inactive workflow is refused rather than silently ignored.
          </P>
        </Step>
      </Steps>

      <H2 id="connecting-nodes">Connecting nodes</H2>
      <P>
        Edges leave a specific <Strong>output handle</Strong>. Most nodes have one, called{' '}
        <C>out</C>. Some have several, and which handle you drag from decides the meaning of
        the edge.
      </P>

      <Table
        headers={['Node', 'Handles', 'Meaning']}
        widths={['w-[22%]', 'w-[30%]']}
        rows={[
          ['Branch', <><C>true</C>, <C>false</C></>, 'Two paths, one taken per run.'],
          ['Switch', <>one per rule, plus <C>else</C></>, 'First matching rule wins; unmatched runs take else.'],
          ['Loop Over Items', <><C>loop</C>, <C>done</C></>, <><C>loop</C> is the body, run once per item; <C>done</C> continues after the last iteration.</>],
          ['Transfer Call, End Call', 'none', 'Terminal. The call is gone; nothing can follow.'],
          ['Everything else', <><C>out</C></>, 'Continue.'],
        ]}
      />

      <Callout kind="tip" title="Branches can rejoin">
        Two paths that need to converge should meet at a <A href="/docs/nodes/logic#merge">
        Merge</A> node. Pointing two edges straight at the same downstream node works, but
        Merge makes the intent explicit and is far easier to read six months later.
      </Callout>

      <H3>Parallel branches</H3>
      <P>
        Several edges may leave one handle. Those paths run concurrently, which is the fast
        way to do three independent things — write to the CRM, post to Slack, send an email —
        without waiting for each in turn. Bring them back together with Merge if a later step
        needs all three finished.
      </P>

      <H2 id="validation">Validation</H2>
      <P>
        The builder checks the graph continuously and lists what it finds. Problems come in
        two weights: <Strong>errors</Strong>, which will stop the run, and{' '}
        <Strong>warnings</Strong>, which are usually a mistake but will not by themselves
        prevent execution.
      </P>

      <Table
        headers={['Reported', 'Weight', 'Means']}
        widths={['w-[26%]', 'w-[14%]']}
        rows={[
          [
            <Strong>Required field missing</Strong>,
            <Badge tone="rose">Error</Badge>,
            'A Webhook with no URL, an Ask with no variable to save into.',
          ],
          [
            <Strong>Field is not valid JSON</Strong>,
            <Badge tone="rose">Error</Badge>,
            <>A headers or body field that does not parse — usually a trailing comma or a missing quote.</>,
          ],
          [
            <Strong>Step no longer supported</Strong>,
            <Badge tone="rose">Error</Badge>,
            <>
              A node type this build has retired, kept from an older version of the flow. See{' '}
              <A href="#retired-steps">below</A>.
            </>,
          ],
          [
            <Strong>Workflow contains a loop</Strong>,
            <Badge tone="rose">Error</Badge>,
            <>
              Edges form a cycle, so the run would never finish. To repeat work, use the{' '}
              <A href="/docs/nodes/logic#loop">Loop Over Items</A> node rather than wiring a
              step back to an earlier one.
            </>,
          ],
          [
            <Strong>Not connected to the flow</Strong>,
            <Badge tone="amber">Warning</Badge>,
            'Nothing reaches the node from the trigger, so it never runs.',
          ],
          [
            <Strong>Output not connected</Strong>,
            <Badge tone="amber">Warning</Badge>,
            <>
              A node with more than one output — Branch, Switch, Loop — has a handle going
              nowhere. That path of the run stops there.
            </>,
          ],
          [
            <Strong>Workflow has no steps yet</Strong>,
            <Badge tone="amber">Warning</Badge>,
            'Only a trigger on the canvas.',
          ],
        ]}
      />

      <H3 id="retired-steps">Steps that are no longer supported</H3>
      <P>
        A workflow saved against an older build can contain a node type this one has removed —
        the Code node, which ran a Python or JavaScript snippet, is the one you are most likely
        to meet. Those nodes render as <Strong>Unsupported step</Strong> and are flagged as an
        error, because the run would fail at that step anyway.
      </P>
      <P>
        Opening one shows no fields, deliberately: reading its stored configuration against a
        different node&rsquo;s fields would discard it the moment you saved. Replace it
        instead — most Code nodes were doing arithmetic or reshaping a value, which{' '}
        <A href="/docs/nodes/logic#calculate">Calculate</A> and{' '}
        <A href="/docs/nodes/logic#transform">Set Fields</A> now do between them — then delete
        the old node. For anything genuinely requiring code, call your own endpoint with a{' '}
        <A href="/docs/nodes/actions#webhook">Webhook</A>.
      </P>

      <Callout kind="warning" title="Validation checks shape, not correctness">
        It confirms the graph can run. It cannot tell you that <C>{'{{trigger.emial}}'}</C> is
        a typo, or that your Branch compares against the wrong value. Only a test run reveals
        those.
      </Callout>
    </DocPage>
  )
}
