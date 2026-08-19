import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { CodeBlock } from '@/components/docs/CodeBlock'
import {
  A, C, Callout, H2, H3, LI, Meta, P, ParamTable, RefHeader, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/nodes/logic')

export default function LogicNodesPage() {
  return (
    <DocPage href="/docs/nodes/logic">
      <P>
        Logic nodes shape the path a run takes and the data it carries. None of them need a
        caller, so they work in every workflow.
      </P>

      <RefHeader id="condition" name="Branch" chip="Logic" tone="amber">
        Splits the flow in two on a single condition. Exactly one side runs.
      </RefHeader>
      <Meta label="Outputs"><C>true</C>, <C>false</C></Meta>

      <ParamTable
        params={[
          {
            name: 'variable',
            type: 'string',
            required: true,
            description: (
              <>
                What to test. A bare path — <C>account_number</C>,{' '}
                <C>steps.n_abc123.status</C>, <C>trigger.amount</C>. The braced form is also
                accepted.
              </>
            ),
          },
          {
            name: 'operator',
            type: 'enum',
            default: 'equals',
            description: <>How to compare. See the <A href="#operators">operator reference</A>.</>,
          },
          {
            name: 'value',
            type: 'string',
            description: (
              <>
                What to compare against. Hidden when the operator is <C>is empty</C> or{' '}
                <C>is not empty</C>, since those take no operand.
              </>
            ),
          },
        ]}
      />

      <Callout kind="tip" title="Both handles need somewhere to go">
        An unconnected <C>false</C> handle means half your callers hit a dead end. If one side
        genuinely has nothing to do, point it at a Merge so the intent is visible.
      </Callout>

      <RefHeader id="switch" name="Switch" chip="Logic" tone="amber">
        Routes to one of several branches. The first matching rule wins; anything unmatched
        takes <C>else</C>.
      </RefHeader>
      <Meta label="Outputs">One handle per rule, plus <C>else</C></Meta>

      <ParamTable
        params={[
          {
            name: 'rules',
            type: 'rule[]',
            default: '[]',
            description: (
              <>
                An ordered list. Each rule has a label (which names its output handle), a
                variable, an operator, and a value. Adding a rule grows a new handle on the
                node.
              </>
            ),
          },
        ]}
      />

      <P>
        <Strong>Order is the logic.</Strong> Rules are evaluated top to bottom and the first
        match wins, so a broad rule placed above a narrow one will swallow cases the narrow
        rule was written for.
      </P>

      <CodeBlock
        language="Order matters"
        code={`WRONG — the first rule catches everything
  1. intent contains  "support"     → General support
  2. intent contains  "support billing" → Billing support   ← never reached

RIGHT — narrowest first
  1. intent contains  "support billing" → Billing support
  2. intent contains  "support"     → General support
  else                              → Triage`}
      />

      <Callout kind="note" title="Switch or several Branches?">
        Use Switch for three or more mutually exclusive routes on the same variable — it is
        one node instead of a chain, and the rule list reads as a table. Use Branch when there
        are exactly two outcomes, or when each test looks at a different variable.
      </Callout>

      <RefHeader id="filter" name="Filter" chip="Logic" tone="amber">
        Continues only when a condition holds. When it does not, this path of the run stops
        cleanly.
      </RefHeader>
      <Meta label="Outputs"><C>out</C></Meta>

      <ParamTable
        params={[
          {
            name: 'variable',
            type: 'string',
            required: true,
            description: <>What to test, e.g. <C>trigger.score</C>.</>,
          },
          {
            name: 'operator',
            type: 'enum',
            default: 'equals',
            description: (
              <>
                A slightly reduced set: <C>equals</C>, <C>does not equal</C>,{' '}
                <C>contains</C>, <C>is greater than</C>, <C>is less than</C>,{' '}
                <C>is empty</C>, <C>is not empty</C>.
              </>
            ),
          },
          {
            name: 'value',
            type: 'string',
            description: <>Hidden for <C>is empty</C> and <C>is not empty</C>.</>,
          },
        ]}
      />

      <P>
        Filter is a guard, not a fork. Where Branch says &ldquo;do this or that&rdquo;, Filter
        says &ldquo;only carry on if&rdquo;. It is the right node for gating a{' '}
        <A href="/docs/workflows/triggers#call-completed">call completed</A> workflow so it
        acts only on calls that matter, and for stopping a run before a destructive step when a
        required value came back empty.
      </P>

      <RefHeader id="merge" name="Merge" chip="Logic" tone="amber">
        Joins parallel branches back into one path.
      </RefHeader>
      <Meta label="Outputs"><C>out</C></Meta>
      <Meta label="Parameters">None</Meta>

      <P>
        Merge waits for its incoming branches, then continues once. Use it whenever several
        paths converge and the next step should run a single time rather than once per
        incoming edge.
      </P>

      <CodeBlock
        language="Three writes in parallel, then one confirmation"
        code={`Ask Question
  └─ out ──┬──→ Integration: create CRM contact ──┐
           ├──→ Integration: post to Slack ───────┼──→ Merge ──→ Speak: "All done."
           └──→ Webhook: notify internal API ─────┘

# Without Merge, the Speak node would fire three times.`}
      />

      <RefHeader id="loop" name="Loop Over Items" chip="Logic" tone="amber">
        Runs a body of steps once per item in a list.
      </RefHeader>
      <Meta label="Outputs"><C>loop</C> (the body, once per item), <C>done</C> (after the last)</Meta>

      <ParamTable
        params={[
          {
            name: 'items',
            type: 'string',
            description: (
              <>
                A reference to a list — <C>trigger.customers</C>,{' '}
                <C>steps.n_abc123.results</C>. If it does not resolve to a list, the loop runs
                zero times.
              </>
            ),
          },
          {
            name: 'max_iterations',
            type: 'number',
            default: '100',
            description: (
              <>
                Hard ceiling, regardless of list length. This is a runaway guard — an API that
                unexpectedly returns fifty thousand rows will not take your workflow with it.
              </>
            ),
          },
        ]}
      />

      <P>Inside the body, three references are available and change each iteration:</P>
      <Table
        headers={['Reference', 'Value']}
        widths={['w-[28%]']}
        rows={[
          [<C>{'{{loop.item}}'}</C>, 'The current item. Reach into it with dots when items are objects.'],
          [<C>{'{{loop.index}}'}</C>, 'Zero-based position.'],
          [<C>{'{{loop.length}}'}</C>, 'Total number of items.'],
        ]}
      />

      <Callout kind="warning" title="Loops multiply cost and time">
        A body containing an API call with 200 items makes 200 API calls, sequentially. That
        is fine in a scheduled workflow and disastrous in one running mid-call. Keep{' '}
        <C>max_iterations</C> honest, and prefer a single bulk API call over a loop of
        individual ones where the connector offers one.
      </Callout>

      <RefHeader id="transform" name="Set Fields" chip="Logic" tone="amber">
        Builds or reshapes named values for later steps.
      </RefHeader>
      <Meta label="Outputs"><C>out</C></Meta>

      <ParamTable
        params={[
          {
            name: 'transformations',
            type: 'key/value map',
            default: '{}',
            description: (
              <>
                Each row is a name and an expression. Every name becomes a top-level variable
                available to later steps as <C>{'{{name}}'}</C>.
              </>
            ),
          },
        ]}
      />

      <P>Three jobs this node does well:</P>
      <UL>
        <LI>
          <Strong>Shorten a reference.</Strong> Turn{' '}
          <C>steps.n_a1b2c3d4.body.results[0].email</C> into <C>{'{{lead_email}}'}</C> once,
          then use the short name everywhere.
        </LI>
        <LI>
          <Strong>Compose a value.</Strong> Join first and last names, build a message, format
          a reference number.
        </LI>
        <LI>
          <Strong>Mark a checkpoint.</Strong> Capture what mattered at a point in a long
          workflow, so a failed run shows you the state at that moment.
        </LI>
      </UL>

      <Callout kind="tip" title="Watch the type rule">
        A row whose value is <em>only</em> a reference keeps that value&rsquo;s type. A row
        that combines references with text produces a string. See{' '}
        <A href="/docs/workflows/variables#type-preservation">Type preservation</A>.
      </Callout>

      <RefHeader id="calculate" name="Calculate" chip="Logic" tone="amber">
        Works out numbers from other values, one row at a time.
      </RefHeader>
      <Meta label="Outputs"><C>out</C></Meta>

      <ParamTable
        params={[
          {
            name: 'calculations',
            type: 'array',
            required: true,
            description: (
              <>
                Rows of <C>{'{ name, left, operator, right }'}</C>. Operands may be literals
                or <C>{'{{references}}'}</C>.
              </>
            ),
          },
          {
            name: 'decimals',
            type: 'number',
            description: <>Round every result to this many decimal places. Optional.</>,
          },
        ]}
      />

      <H3>Rows build on each other</H3>
      <P>
        Rows run top to bottom and each result is published as soon as it is worked out, so a
        later row can use an earlier one by name. Three related figures live in one node
        rather than three.
      </P>
      <CodeBlock
        language="text"
        code={`subtotal  =  {{trigger.price}}  ×   {{trigger.quantity}}
tax       =  15                 % of {{subtotal}}
total     =  {{subtotal}}       +   {{tax}}

# Later steps can then say: "That comes to {{total}}."`}
      />

      <P>
        Operators are <C>+</C>, <C>−</C>, <C>×</C>, <C>÷</C>, remainder, and <C>% of</C>.
      </P>

      <Callout kind="note" title="Totalling a list belongs in Set Fields">
        Calculate works on individual numbers. To add up a field across a list — an order
        total, an average call length — use <A href="#transform">Set Fields</A> with the
        <C>Sum of</C> transform, which takes the list and the field name to add up.
      </Callout>

      <Callout kind="warning" title="A missing value stops the step">
        If an operand is empty or is not a number, the step fails with a message naming the
        row, rather than quietly producing nothing. That is deliberate: a blank total is far
        worse when the next step reads it out to a caller.
      </Callout>

      <RefHeader id="delay" name="Wait" chip="Logic" tone="amber">
        Pauses before continuing.
      </RefHeader>
      <Meta label="Outputs"><C>out</C></Meta>

      <ParamTable
        params={[
          {
            name: 'delay_seconds',
            type: 'number',
            required: true,
            default: '5',
            description: 'How long to pause.',
          },
        ]}
      />

      <P>Legitimate uses are narrower than people expect:</P>
      <UL>
        <LI>Giving an external system time to finish processing something you just sent it.</LI>
        <LI>Spacing out requests to a rate-limited API inside a loop.</LI>
        <LI>Deliberately delaying a follow-up message after a call ends.</LI>
      </UL>

      <Callout kind="danger" title="Never wait during a live call">
        A Wait node in a mid-call workflow is silence on the line. The caller will assume the
        call has dropped. If you need to fill time while something completes, use a{' '}
        <A href="/docs/tools/workflow#holding-line">holding line</A> on the workflow tool
        instead.
      </Callout>

      <H2 id="operators">Operator reference</H2>
      <P>
        Branch and Filter share an operator vocabulary. Branch offers the full set; Filter
        offers a reduced one.
      </P>

      <Table
        headers={['Operator', 'True when', 'Branch', 'Filter']}
        widths={['w-[22%]', 'w-[44%]', 'w-[10%]']}
        rows={[
          [<C>equals</C>, 'The values match', 'Yes', 'Yes'],
          [<C>does not equal</C>, 'The values differ', 'Yes', 'Yes'],
          [<C>contains</C>, 'The value appears inside the variable', 'Yes', 'Yes'],
          [<C>does not contain</C>, 'The value does not appear inside it', 'Yes', '—'],
          [<C>starts with</C>, 'The variable begins with the value', 'Yes', '—'],
          [<C>ends with</C>, 'The variable ends with the value', 'Yes', '—'],
          [<C>is greater than</C>, 'Numerically larger', 'Yes', 'Yes'],
          [<C>is less than</C>, 'Numerically smaller', 'Yes', 'Yes'],
          [<C>is empty</C>, 'Null, missing, or an empty string', 'Yes', 'Yes'],
          [<C>is not empty</C>, 'Has any value', 'Yes', 'Yes'],
        ]}
      />

      <H3>Practical notes</H3>
      <UL>
        <LI>
          <Strong><C>contains</C> is the right operator for speech.</Strong> A caller who
          means yes says &ldquo;yeah&rdquo;, &ldquo;yes please&rdquo;, &ldquo;that&rsquo;s
          right&rdquo;. <C>equals yes</C> matches none of them; <C>contains yes</C> matches
          two. For genuinely reliable yes/no, use a{' '}
          <A href="/docs/nodes/conversation#ask">DTMF question</A>.
        </LI>
        <LI>
          <Strong>Comparisons on missing values.</Strong> A reference that resolves to nothing
          is empty, so <C>is empty</C> is true and <C>equals anything</C> is false. Test for
          emptiness explicitly rather than relying on a comparison to fail.
        </LI>
        <LI>
          <Strong>Numeric comparisons need numbers.</Strong>{' '}
          <C>is greater than</C> against a value that arrived as text may not behave as you
          expect. If a value crosses a boundary as a string, convert it in a Set
          Fields node first.
        </LI>
      </UL>
    </DocPage>
  )
}
