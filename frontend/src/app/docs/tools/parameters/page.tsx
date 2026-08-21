import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { CodeBlock } from '@/components/docs/CodeBlock'
import {
  A, C, Callout, H2, LI, P, ParamTable, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/tools/parameters')

export default function ToolParametersPage() {
  return (
    <DocPage href="/docs/tools/parameters">
      <H2 id="why-parameters">Why parameters matter</H2>
      <P>
        A parameter is a value the agent must extract from the conversation before it can run
        the tool. Together they form the contract between a spoken sentence and a structured
        API call.
      </P>
      <P>
        The agent reads your parameter definitions to decide what to listen for and, if
        something is missing, what to ask. A well-defined parameter produces a natural
        follow-up question. A vague one produces an agent that either invents a value or asks
        something baffling.
      </P>

      <CodeBlock
        language="What the model actually does"
        code={`Caller:  "Hi, I'd like to book a check-up for Tuesday morning."

Model:   book_appointment matches this. Its parameters are:
           customer_name    required   ← not stated yet
           preferred_date   required   ← "Tuesday"
           time_of_day      optional   ← "morning"

Agent:   "Happy to help. Can I take your name?"     ← asks for the gap
Caller:  "Ada Lovelace."

Model:   invokes book_appointment({
           customer_name:  "Ada Lovelace",
           preferred_date: "Tuesday",
           time_of_day:    "morning"
         })`}
      />

      <H2 id="the-fields">The four fields</H2>
      <P>Every parameter in the builder has the same four fields.</P>

      <ParamTable
        params={[
          {
            name: 'Name',
            type: 'string',
            required: true,
            description: (
              <>
                The key sent to your endpoint, and the token used in templates as{' '}
                <C>{'{{name}}'}</C>. Use <C>snake_case</C>. The model reads this too — a
                descriptive name is a free hint.
              </>
            ),
          },
          {
            name: 'Type',
            type: 'enum',
            default: 'string',
            description: (
              <>
                <C>string</C>, <C>number</C>, <C>boolean</C>, <C>object</C>, or{' '}
                <C>array</C>. Tells the model what shape of value to produce.
              </>
            ),
          },
          {
            name: 'Description',
            type: 'string',
            description: (
              <>
                The single most important field. What the value is, in the words a caller
                would use. See <A href="#writing-descriptions">below</A>.
              </>
            ),
          },
          {
            name: 'Required',
            type: 'boolean',
            default: 'false',
            description: (
              <>
                Whether the agent must have this before invoking the tool. Required parameters
                turn into follow-up questions; optional ones are filled if mentioned and
                skipped otherwise.
              </>
            ),
          },
        ]}
      />

      <P>
        String parameters gain a fifth field, <Strong>Allowed values</Strong>, covered under{' '}
        <A href="#allowed-values">enums</A>.
      </P>

      <H2 id="types">Parameter types</H2>
      <Table
        headers={['Type', 'Use for', 'Example value']}
        widths={['w-[16%]', 'w-[44%]']}
        rows={[
          [<C>string</C>, 'Names, emails, dates as spoken, free text, IDs', <C>&quot;Ada Lovelace&quot;</C>],
          [<C>number</C>, 'Quantities, amounts, scores, durations', <C>3</C>],
          [<C>boolean</C>, 'Yes/no facts the caller confirms', <C>true</C>],
          [<C>object</C>, 'Structured data with named fields', <C>{'{ "street": "…", "city": "…" }'}</C>],
          [<C>array</C>, 'Lists — several items, several dates', <C>{'["Tue", "Wed"]'}</C>],
        ]}
      />

      <Callout kind="tip" title="Prefer strings for spoken values">
        Callers say &ldquo;next Tuesday&rdquo;, &ldquo;the twelfth&rdquo;, &ldquo;tomorrow
        afternoon&rdquo;. Declaring a date as a <C>string</C> and normalising it downstream —
        in a <A href="/docs/nodes/logic#transform">Set Fields</A> node or on your own server —
        works far better than hoping the model produces a clean ISO date from speech.
      </Callout>

      <Callout kind="warning" title="Objects and arrays are hard to speak">
        Extracting a nested object from a phone conversation is unreliable. Where you need
        structure, ask for the pieces as separate flat parameters and assemble them yourself.
      </Callout>

      <H2 id="writing-descriptions">Writing descriptions the model can use</H2>
      <P>
        Descriptions are read by the model at selection time. Treat them as instructions, not
        labels.
      </P>

      <Table
        headers={['Instead of', 'Write']}
        widths={['w-[30%]']}
        rows={[
          [<C>&quot;name&quot;</C>, <C>&quot;The caller&rsquo;s full name, as they say it&quot;</C>],
          [<C>&quot;date&quot;</C>, <C>&quot;The date the caller wants, in their own words, e.g. &lsquo;next Tuesday&rsquo;&quot;</C>],
          [<C>&quot;amount&quot;</C>, <C>&quot;The refund amount in pounds, numbers only&quot;</C>],
          [<C>&quot;id&quot;</C>, <C>&quot;The 8-digit account number the caller reads out&quot;</C>],
          [<C>&quot;urgent&quot;</C>, <C>&quot;True only if the caller explicitly says it is urgent&quot;</C>],
        ]}
      />

      <P>Three rules cover most of it:</P>
      <UL>
        <LI>
          <Strong>Say whose value it is.</Strong> &ldquo;email&rdquo; is ambiguous on a
          support call. &ldquo;The caller&rsquo;s email address&rdquo; is not.
        </LI>
        <LI>
          <Strong>Give the expected shape.</Strong> Format, units, length. &ldquo;in pounds,
          numbers only&rdquo; prevents <C>&quot;about fifty quid&quot;</C>.
        </LI>
        <LI>
          <Strong>State the condition for booleans.</Strong> &ldquo;True only if the caller
          explicitly says&hellip;&rdquo; stops the model inferring urgency from tone.
        </LI>
      </UL>

      <H2 id="required-vs-optional">Required vs optional</H2>
      <P>
        Required parameters are blocking: the agent will not invoke the tool until it has
        them, so each one becomes a question the caller must answer.
      </P>

      <Table
        headers={['Mark required when', 'Mark optional when']}
        rows={[
          ['The tool cannot function without it', 'The tool has a sensible default'],
          ['The caller always knows it', 'Only some callers will have it'],
          ['A wrong value would be harmful', 'It merely enriches the result'],
        ]}
      />

      <Callout kind="warning" title="Required parameters cost turns">
        Five required parameters is five questions before anything happens. Callers lose
        patience. Ask for the minimum, act, and gather the rest afterwards if you still need
        it.
      </Callout>

      <H2 id="allowed-values">Allowed values (enums)</H2>
      <P>
        On a string parameter, <Strong>Allowed values</Strong> takes a comma-separated list.
        The model is then constrained to those values, which turns messy speech into a clean
        token.
      </P>

      <CodeBlock
        language="Constraining free speech"
        code={`Parameter:       urgency
Type:            string
Description:     How urgent the caller says the issue is
Allowed values:  low, medium, high

Caller says:     "It's not desperate but I'd like it sorted this week."
Model produces:  "medium"        ← one of your three, never prose`}
      />

      <UL>
        <LI>Use enums wherever a downstream system expects a fixed set — statuses, priorities, categories, departments.</LI>
        <LI>Keep the list short. Three to six values is comfortable; twenty is a lookup, not an enum.</LI>
        <LI>Use the exact tokens your API expects, so no translation step is needed.</LI>
      </UL>

      <H2 id="using-in-templates">Using parameters in templates</H2>
      <P>
        Collected values are available in the tool&rsquo;s own configuration fields as{' '}
        <C>{'{{parameter_name}}'}</C>.
      </P>

      <CodeBlock
        language="An API Request tool using its parameters"
        code={`Parameters
  customer_name   string   "The caller's full name"          required
  email           string   "The caller's email address"      required
  callback_time   string   "When they want to be called back" optional

Body template
{
  "name":     "{{customer_name}}",
  "email":    "{{email}}",
  "callback": "{{callback_time}}",
  "source":   "voice"
}`}
      />

      <P>
        The same tokens work in an SMS message template, a Slack message, a Google Sheets row,
        or a calendar event title.
      </P>

      <H2 id="generated-schema">The generated schema</H2>
      <P>
        Behind the builder, your parameters compile to a JSON Schema — the standard format the
        model consumes. You never edit this directly, but seeing it clarifies what the model
        receives.
      </P>

      <CodeBlock
        language="json"
        code={`{
  "type": "object",
  "properties": {
    "customer_name": {
      "type": "string",
      "description": "The caller's full name"
    },
    "urgency": {
      "type": "string",
      "description": "How urgent the caller says the issue is",
      "enum": ["low", "medium", "high"]
    },
    "callback_time": {
      "type": "string",
      "description": "When they want to be called back"
    }
  },
  "required": ["customer_name", "urgency"]
}`}
      />

      <Callout kind="note" title="Connected Integration tools skip all of this">
        When a tool points at a connected integration action, its parameters are generated
        from that action&rsquo;s published schema — correct names, types, and required flags,
        with no typing. See{' '}
        <A href="/docs/tools/integration#connected-integration">Connected Integration</A>.
      </Callout>
    </DocPage>
  )
}
