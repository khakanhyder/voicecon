import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { CodeBlock } from '@/components/docs/CodeBlock'
import {
  A, C, Callout, H2, H3, P, Strong, Table,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/workflows/variables')

export default function VariablesPage() {
  return (
    <DocPage href="/docs/workflows/variables">
      <H2 id="the-context-object">The context object</H2>
      <P>
        Every workflow run carries one context object. Nodes read from it and write to it, and
        that is the only way data moves between steps.
      </P>

      <CodeBlock
        language="The shape of the context"
        code={`{
  "trigger": { …whatever started the run… },
  "steps": {
    "n_a1b2c3d4": { …that node's result… },
    "n_e5f6g7h8": { … }
  },
  …top-level variables published by Ask, Set Fields, Code, and AI nodes…
}`}
      />

      <Table
        headers={['Namespace', 'Written by', 'Read as']}
        widths={['w-[20%]', 'w-[34%]']}
        rows={[
          [<C>trigger</C>, 'The trigger, once, at the start', <C>{'{{trigger.field}}'}</C>],
          [<C>steps</C>, 'Every node, keyed by node id', <C>{'{{steps.n_abc123.field}}'}</C>],
          ['top level', 'Ask, Set Fields, Code, AI nodes', <C>{'{{variable_name}}'}</C>],
        ]}
      />

      <Callout kind="tip" title="Prefer top-level names">
        <C>{'{{steps.n_a1b2c3d4.answer}}'}</C> is correct but unreadable, and it breaks if you
        rebuild the node. An Ask node&rsquo;s <Strong>Save answer as</Strong> field publishes
        the answer at the top level, so you can write <C>{'{{account_number}}'}</C> instead.
        Use it.
      </Callout>

      <H2 id="reference-syntax">Reference syntax</H2>
      <P>
        References use double braces and dot paths. Whitespace inside the braces is tolerated.
      </P>

      <Table
        headers={['Reference', 'Resolves to']}
        widths={['w-[46%]']}
        rows={[
          [<C>{'{{trigger.email}}'}</C>, 'A field on the trigger data'],
          [<C>{'{{account_number}}'}</C>, 'A top-level variable published by an earlier node'],
          [<C>{'{{steps.n_abc123.status}}'}</C>, 'A field on a specific node’s result'],
          [<C>{'{{trigger.items[0].sku}}'}</C>, 'The first item in an array, then a field on it'],
          [<C>{'{{results.0.latitude}}'}</C>, 'Array index without brackets — also valid'],
          [<C>{'{{trigger.items[-1].sku}}'}</C>, 'Negative index — counts from the end'],
        ]}
      />

      <P>
        Array indexing matters more than it first appears: real APIs return lists constantly,
        and without indexing most of a response would be unreachable.
      </P>

      <H2 id="type-preservation">Type preservation</H2>
      <P>
        This is the rule that most often surprises people, and getting it wrong produces bugs
        that a run will happily report as successful.
      </P>

      <H3>Whole-value references keep their type</H3>
      <P>
        When a field contains <em>nothing but</em> one reference, the resolved value is
        returned with its own type intact.
      </P>
      <CodeBlock
        language="Whole-value — types survive"
        code={`Field value:  {{trigger.amount}}
Context:      { "trigger": { "amount": 42 } }
Result:       42            ← the number, not "42"

Field value:  {{trigger.paid}}
Context:      { "trigger": { "paid": true } }
Result:       true          ← JSON boolean, not "True"

Field value:  {{trigger.customer}}
Context:      { "trigger": { "customer": { "id": 7, "name": "Ada" } } }
Result:       { "id": 7, "name": "Ada" }   ← the object itself`}
      />

      <H3>Mixed templates always produce text</H3>
      <P>
        The moment a reference has anything around it, the result can only be a string, so
        every reference in it is converted to text.
      </P>
      <CodeBlock
        language="Mixed — everything becomes a string"
        code={`Field value:  Hello {{name}}, you owe {{amount}}
Context:      { "name": "Ada", "amount": 42 }
Result:       "Hello Ada, you owe 42"

Field value:  Amount: {{trigger.paid}}
Result:       "Amount: true"       ← lowercase JSON spelling, not Python's True`}
      />

      <Callout kind="warning" title="Why this matters">
        A webhook body of <C>{'{"amount": "{{trigger.amount}} "}'}</C> — note the stray space —
        posts the <em>string</em> <C>&quot;42 &quot;</C> where the receiving API expected the
        number <C>42</C>. Many APIs reject that; some accept it and store nonsense. If an
        integration is receiving the right values in the wrong types, look for stray
        characters around the braces first.
      </Callout>

      <H2 id="missing-references">Missing references</H2>
      <P>
        A reference that resolves to nothing does not stay on the page as literal text.
      </P>
      <Table
        headers={['Case', 'Result']}
        widths={['w-[38%]']}
        rows={[
          [<>Whole-value, e.g. <C>{'{{trigger.missing}}'}</C></>, <>Becomes <C>null</C></>],
          [<>Mixed, e.g. <C>{'Hi {{missing}}'}</C></>, <>Becomes <C>&quot;Hi &quot;</C> — an empty substitution</>],
        ]}
      />
      <P>
        Leaving the literal <C>{'{{trigger.missing}}'}</C> in an outbound payload would be
        indistinguishable downstream from a real value, so it is resolved away instead. The
        practical consequence: a typo in a reference produces a silently empty field, not an
        error. If a value is arriving empty, check the spelling of the reference before
        anything else.
      </P>
      <Callout kind="tip" title="Guard against empty">
        Where a missing value would be harmful, add a <A href="/docs/nodes/logic#filter">
        Filter</A> with <C>is not empty</C> before the step that depends on it. The run stops
        cleanly rather than writing a blank record.
      </Callout>

      <H2 id="publishing-variables">Publishing your own variables</H2>
      <P>Four node types write top-level variables you can name yourself.</P>

      <Table
        headers={['Node', 'Publishes', 'Named by']}
        widths={['w-[22%]', 'w-[34%]']}
        rows={[
          [
            <A href="/docs/nodes/conversation#ask">Ask Question</A>,
            'The caller’s answer',
            <>The <Strong>Save answer as</Strong> field</>,
          ],
          [
            <A href="/docs/nodes/logic#transform">Set Fields</A>,
            'One variable per row',
            'The key of each row',
          ],
          [
            <A href="/docs/nodes/logic#code">Code</A>,
            'Each key of the returned object',
            'The object’s keys',
          ],
          [
            <A href="/docs/nodes/ai">AI Response</A>,
            'The generated reply',
            <>The <Strong>Save reply as</Strong> field</>,
          ],
        ]}
      />

      <CodeBlock
        language="Set Fields publishing two variables"
        code={`full_name  =  {{first_name}} {{last_name}}
is_urgent  =  {{trigger.priority}}

# Later nodes can now use {{full_name}} and {{is_urgent}} directly.
# Note: full_name is a mixed template → a string.
#       is_urgent is whole-value      → keeps its original type.`}
      />

      <H2 id="loop-variables">Loop variables</H2>
      <P>
        Inside a <A href="/docs/nodes/logic#loop">Loop Over Items</A> body, three extra
        references exist and change on each iteration.
      </P>
      <Table
        headers={['Reference', 'Meaning']}
        widths={['w-[30%]']}
        rows={[
          [<C>{'{{loop.item}}'}</C>, 'The current item.'],
          [<C>{'{{loop.index}}'}</C>, 'Zero-based position in the list.'],
          [<C>{'{{loop.length}}'}</C>, 'Total number of items.'],
        ]}
      />
      <P>
        When items are objects, reach into them the usual way:{' '}
        <C>{'{{loop.item.email}}'}</C>.
      </P>
      <Callout kind="note" title="Loop variables are scoped to the body">
        They exist only inside the loop. After the <C>done</C> handle they are gone — carry
        anything you need forward with a Set Fields node inside the body.
      </Callout>

      <H2 id="examples">Worked examples</H2>

      <H3>Passing a caller&rsquo;s answer to an API</H3>
      <CodeBlock
        language="Ask → Webhook"
        code={`Ask Question
  Question:        What is your account number?
  Save answer as:  account_number

Webhook
  URL:     https://api.example.com/accounts/lookup
  Method:  POST
  Body:    { "account": "{{account_number}}" }

# account_number is a string here — the caller spoke it, so a string is right.`}
      />

      <H3>Branching on an API response</H3>
      <CodeBlock
        language="Webhook → Branch"
        code={`Webhook          (node id n_7fa21b30)
  Returns:  { "status": "active", "balance": 240.5 }

Branch
  Variable:  steps.n_7fa21b30.status
  Operator:  equals
  Value:     active

# The Branch operand is a bare path, not a {{reference}} — both spellings are
# accepted, but the bare form is what the field expects.`}
      />

      <H3>Sending a typed payload</H3>
      <CodeBlock
        language="Preserving numbers and booleans"
        code={`Webhook body:
{
  "customer_id": {{trigger.customer_id}},
  "amount":      {{steps.n_7fa21b30.balance}},
  "is_priority": {{is_urgent}},
  "note":        "Call from {{caller_name}} on {{call_date}}"
}

# The first three are whole-value → number, number, boolean.
# "note" is mixed → a string. That is exactly what each field wants.`}
      />
    </DocPage>
  )
}
