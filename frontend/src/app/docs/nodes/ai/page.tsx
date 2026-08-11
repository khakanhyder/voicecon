import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { CodeBlock } from '@/components/docs/CodeBlock'
import {
  A, C, Callout, H2, LI, Meta, P, ParamTable, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/nodes/ai')

export default function AiNodePage() {
  return (
    <DocPage href="/docs/nodes/ai">
      <H2 id="purpose">Purpose</H2>
      <P>
        The AI Response node hands one step of the workflow back to the language model. You
        supply context; it produces a reply, which is spoken to the caller and optionally
        stored in a variable.
      </P>
      <Meta label="Category">AI</Meta>
      <Meta label="Outputs"><C>out</C></Meta>

      <P>
        This is how you get flexibility inside an otherwise deterministic flow. A scripted
        intake can still handle &ldquo;actually, can I ask something first?&rdquo; if you give
        it an AI node at the right moment.
      </P>

      <H2 id="parameters">Parameters</H2>
      <ParamTable
        params={[
          {
            name: 'context',
            type: 'text',
            required: true,
            description: (
              <>
                What the model should know and do at this point. Supports references, so you
                can feed it data the workflow has already gathered.
              </>
            ),
          },
          {
            name: 'constraints',
            type: 'text',
            description: (
              <>
                Boundaries on the reply — length, tone, what not to say. Technically optional;
                in practice this is what keeps the node predictable.
              </>
            ),
          },
          {
            name: 'variable',
            type: 'string',
            description: (
              <>
                Stores the generated reply for later steps as <C>{'{{<variable>}}'}</C>. Leave
                empty if the reply only needs to be spoken.
              </>
            ),
          },
        ]}
      />

      <H2 id="writing-context">Writing good context</H2>
      <P>
        The context field is a prompt for one turn, not a system prompt. Three things make the
        difference between a useful node and an unpredictable one.
      </P>

      <UL>
        <LI>
          <Strong>State the situation and the goal.</Strong> &ldquo;The caller has just
          described a fault with their router. Suggest one thing to try.&rdquo; beats
          &ldquo;Help the caller.&rdquo;
        </LI>
        <LI>
          <Strong>Feed in what the flow already knows.</Strong> References make the reply
          specific rather than generic — the model should not ask for something the workflow
          collected two nodes ago.
        </LI>
        <LI>
          <Strong>Constrain the output.</Strong> Without constraints you get a paragraph. On a
          phone call you want a sentence.
        </LI>
      </UL>

      <CodeBlock
        language="A context that behaves"
        code={`Context:
  The caller is {{caller_name}}. They reported: {{issue_description}}.
  Their account status is {{steps.n_crm01.status}}.
  Acknowledge the problem and suggest exactly one next step.

Constraints:
  Two sentences maximum. Warm but not effusive.
  Do not promise a refund, a timeline, or an engineer visit.
  If the account status is "suspended", say only that billing must be
  resolved first, and do not troubleshoot.`}
      />

      <Callout kind="warning" title="Constraints are load-bearing">
        The AI node is the least predictable thing in a workflow. Anything the model must
        never say — pricing, legal commitments, medical or financial advice — belongs in
        constraints, explicitly. Omitting them is how a deterministic flow acquires a
        surprise.
      </Callout>

      <H2 id="example">Example</H2>
      <P>
        A support flow that looks up the account, generates a tailored reply, then routes on
        whether the caller is satisfied.
      </P>

      <CodeBlock
        language="Lookup → AI → route"
        code={`Ask Question
  question:     What seems to be the problem?
  variable:     issue_description

Integration — HubSpot · search_contacts        (node id n_crm01)
  query:        {{caller_phone}}

AI Response
  context:      The caller is {{steps.n_crm01.results[0].firstname}}.
                They reported: {{issue_description}}.
                Suggest one troubleshooting step.
  constraints:  Two sentences. No promises about timelines.
  variable:     suggestion

Ask Question
  question:     Did that help?
  variable:     resolved

Branch
  variable:     resolved
  operator:     contains
  value:        yes

  ├─ true  → End Call:   "Glad that sorted it. Thanks for calling."
  └─ false → Transfer Call: +14155550100  (warm)`}
      />

      <Table
        headers={['Reach for', 'When']}
        widths={['w-[26%]']}
        rows={[
          [
            <Strong>AI Response</Strong>,
            'The reply depends on gathered data and cannot be written in advance.',
          ],
          [
            <A href="/docs/nodes/conversation#speak">Speak</A>,
            'You know exactly what should be said. Cheaper, faster, and never surprising.',
          ],
          [
            <A href="/docs/tools/assistant#query-knowledge-base">Query Knowledge Base</A>,
            'The answer exists in your documents. Retrieval beats generation for facts.',
          ],
        ]}
      />

      <Callout kind="tip" title="Prefer Speak where you can">
        Every AI node adds latency and variance. If the line is the same on every call, write
        it once in a Speak node. Save the AI node for the turns that genuinely cannot be
        scripted.
      </Callout>
    </DocPage>
  )
}
