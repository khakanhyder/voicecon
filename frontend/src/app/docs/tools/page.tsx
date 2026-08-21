import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { Chain, Figure } from '@/components/docs/Diagram'
import {
  A, Badge, C, Callout, H2, H3, LI, P, Step, Steps, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/tools')

export default function ToolsPage() {
  return (
    <DocPage href="/docs/tools">
      <H2 id="what-is-a-tool">What is a tool?</H2>
      <P>
        A tool is one thing an agent can do. Without tools an agent can only talk; with them
        it can transfer a call, text a confirmation, write to your CRM, look something up, or
        run an entire workflow.
      </P>
      <P>
        Tools are defined once under <Strong>Tools</Strong> and assigned to as many agents as
        you like. The assignment is a link, not a copy — fix a tool once and every agent using
        it is fixed.
      </P>

      <H2 id="how-the-agent-chooses">How the agent chooses a tool</H2>
      <P>
        This is worth understanding properly, because almost every &ldquo;my tool never
        fires&rdquo; problem lives here.
      </P>

      <Figure caption="The model sees names, descriptions, and parameter schemas — never your configuration.">
        <Chain
          stages={[
            { label: 'Caller speaks', tone: 'slate' },
            { label: 'Model reads tool names + descriptions', tone: 'brand' },
            { label: 'Picks one, extracts parameters', tone: 'amber' },
            { label: 'Tool runs', tone: 'violet' },
            { label: 'Result spoken', tone: 'slate' },
          ]}
        />
      </Figure>

      <P>Three consequences follow directly:</P>
      <UL>
        <LI>
          <Strong>The description is the interface.</Strong> The model decides using the name
          and description alone. &ldquo;Books an appointment in the clinic calendar. Use when
          the caller wants to schedule, move, or cancel a visit.&rdquo; fires reliably;
          &ldquo;calendar tool&rdquo; does not.
        </LI>
        <LI>
          <Strong>Parameters are what it must collect.</Strong> Each declared parameter is a
          value the agent has to extract from speech before it can act. See{' '}
          <A href="/docs/tools/parameters">Tool Parameters</A>.
        </LI>
        <LI>
          <Strong>Tools compete.</Strong> Every assigned tool sits in the model&rsquo;s
          context. Two tools with overlapping descriptions produce coin-flip selection.
        </LI>
      </UL>

      <Callout kind="warning" title="Keep the list short">
        Beyond roughly eight to ten tools per agent, selection accuracy visibly degrades. If
        an agent needs many capabilities, put them behind one{' '}
        <A href="/docs/tools/workflow">workflow tool</A> and let the workflow do the routing.
      </Callout>

      <H2 id="the-four-families">The four families</H2>
      <Table
        headers={['Family', 'Tools', 'Reference']}
        widths={['w-[20%]', 'w-[48%]']}
        rows={[
          [
            <Badge tone="violet">Workflow</Badge>,
            'Run Workflow',
            <A href="/docs/tools/workflow">Workflow tools</A>,
          ],
          [
            <Badge tone="emerald">Phone call</Badge>,
            'Transfer Call, Hang Up, Leave Voicemail, DTMF, Send Text, SIP Request',
            <A href="/docs/tools/phone-call">Phone call tools</A>,
          ],
          [
            <Badge tone="brand">Assistant</Badge>,
            'Handoff, Query Knowledge Base',
            <A href="/docs/tools/assistant">Assistant tools</A>,
          ],
          [
            <Badge tone="blue">Integration</Badge>,
            'Connected Integration, API Request, MCP, Slack, Google Sheets, Google Calendar, GoHighLevel, Custom Tool',
            <A href="/docs/tools/integration">Integration tools</A>,
          ],
        ]}
      />

      <H2 id="creating-a-tool">Creating a tool</H2>
      <Steps>
        <Step n={1} title="Pick a type">
          <P>
            <Strong>Tools</Strong> → <Strong>New Tool</Strong>, then choose from the four
            families. The type decides which configuration fields you get and cannot be
            changed afterwards.
          </P>
        </Step>
        <Step n={2} title="Name and describe it">
          <P>
            Both are read by the model. Name it after the action —{' '}
            <C>book_appointment</C>, not <C>tool_2</C>. Write the description as an
            instruction about <em>when</em> to use it.
          </P>
        </Step>
        <Step n={3} title="Configure the type-specific fields">
          <P>
            A URL and headers for an API request, a destination for a transfer, a workflow for
            a workflow tool. Each type is documented on its own page.
          </P>
        </Step>
        <Step n={4} title="Define parameters">
          <P>
            What the agent must collect. Connected Integration tools fill these in
            automatically from the action&rsquo;s schema; everything else you declare
            yourself.
          </P>
        </Step>
        <Step n={5} title="Test it">
          <P>Run it with sample values before assigning it to a live agent.</P>
        </Step>
        <Step n={6} title="Assign it">
          <P>Attach it to the agents that should have it.</P>
        </Step>
      </Steps>

      <H2 id="assigning-to-agents">Assigning a tool to an agent</H2>
      <P>
        Open the agent, go to the <Strong>Tools</Strong> tab, and select the tools it should
        have. Assignment is many-to-many: one tool serves many agents, one agent holds many
        tools.
      </P>
      <UL>
        <LI>Editing a tool changes behaviour for every agent using it, immediately.</LI>
        <LI>Deactivating a tool removes it from every agent without deleting the definition.</LI>
        <LI>Unassigning removes it from one agent only.</LI>
      </UL>

      <H3>Do not forget the prompt</H3>
      <P>
        Assigning a tool makes it <em>available</em>. Mentioning the situation in the system
        prompt makes it <em>likely</em>. Agents often talk their way around a perfectly good
        tool because nothing in the prompt suggested the situation calls for one.
      </P>

      <H2 id="testing-a-tool">Testing a tool</H2>
      <P>
        Each tool has a <Strong>Test</Strong> action. Supply parameter values and it reports
        success or failure, the response, and elapsed time.
      </P>

      <P>
        What Test actually does depends on the family, because some tools have nothing to act
        on outside a live call.
      </P>
      <Table
        headers={['Tool types', 'What Test does']}
        widths={['w-[34%]']}
        rows={[
          [
            <>
              <A href="/docs/tools/integration#api-request">API Request</A>,{' '}
              <A href="/docs/tools/integration#custom-tool">Custom Tool</A>,{' '}
              <A href="/docs/tools/integration#mcp">MCP</A>,{' '}
              <A href="/docs/tools/integration#slack">Slack</A>
            </>,
            <>
              <Strong>Sends the real request</Strong>, through exactly the same code a live
              call uses — same headers, same authentication, same body template, same
              destination checks. A tool that passes here behaves the same way on the phone.
            </>,
          ],
          [
            <><A href="/docs/tools/phone-call">Phone call tools</A>, Handoff</>,
            'Reports that there is no live call to act on. Nothing is dialled, transferred, or texted.',
          ],
          [
            <A href="/docs/tools/workflow">Run Workflow</A>,
            <>
              Declines, because running it would run the whole workflow with its side effects.
              Use the builder&rsquo;s <Strong>Run</Strong> button, which shows every step.
            </>,
          ],
          [
            <A href="/docs/tools/assistant#query-knowledge-base">Query Knowledge Base</A>,
            <>
              Declines, and points at the knowledge base&rsquo;s own{' '}
              <A href="/docs/knowledge-base#testing-retrieval">Test retrieval</A> panel, which
              shows the matched passages and their scores.
            </>,
          ],
          [
            <A href="/docs/tools/integration#connected-integration">Connected Integration</A>,
            <>
              Declines, and points at <A href="/docs/integrations#testing-a-connection">
              Integrations</A>, where the connection itself can be checked.
            </>,
          ],
        ]}
      />

      <Callout kind="warning" title="A passing test is a real request">
        For the four HTTP types above, Test hits your endpoint for real. If that endpoint
        creates a record, charges a card, or posts to a channel people read, it will do so.
        Point them at a sandbox while you are still building.
      </Callout>

      <H3 id="reading-a-test-result">Reading the result</H3>
      <P>
        The four HTTP types return the same shape, and it is the same shape later workflow
        steps read.
      </P>
      <Table
        headers={['Field', 'Is']}
        widths={['w-[22%]']}
        rows={[
          [<C>status_code</C>, <>The HTTP status — <C>200</C>, <C>404</C>, <C>500</C>.</>],
          [<C>ok</C>, <>Whether the status was a success. This is what to branch on.</>],
          [<C>json</C>, <>The parsed response, when the endpoint returned JSON. Reach into it with dots.</>],
          [<C>body</C>, <>The raw response text, capped at 2,000 characters. Present either way, so a non-JSON error page is still visible.</>],
        ]}
      />
      <Callout kind="tip" title="A 500 is not a failed tool">
        <C>success</C> means the request was made and answered. If your endpoint replied{' '}
        <C>500</C>, the tool succeeded and <C>ok</C> is <C>false</C> — check{' '}
        <C>status_code</C> and <C>body</C> to see what your server said.
      </Callout>

      <H3>When a test fails</H3>
      <P>
        The message names what to change, rather than reporting an internal error:
      </P>
      <Table
        headers={['Message', 'Means']}
        widths={['w-[42%]']}
        rows={[
          [
            <C>Headers is not valid JSON: …</C>,
            'The field names the line and column. Usually a trailing comma or a missing quote.',
          ],
          [
            <C>… url rejected: …</C>,
            <>
              The destination is not a public address. See{' '}
              <A href="/docs/tools/integration#api-request-limits">Where it may connect</A>.
            </>,
          ],
          [
            <C>Bearer authentication is selected but no token is set</C>,
            'An auth mode was chosen and its credential left blank.',
          ],
          [
            <C>The request timed out</C>,
            'Your endpoint did not answer in time. Raise the timeout, or check it is reachable.',
          ],
        ]}
      />

      <P>
        A tool that passes its test but never fires on a call is not a configuration problem —
        it is a naming and description problem. Rewrite the description to name the situation.
      </P>
    </DocPage>
  )
}
