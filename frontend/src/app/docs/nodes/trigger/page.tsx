import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { CodeBlock } from '@/components/docs/CodeBlock'
import {
  A, C, Callout, H2, LI, Meta, P, ParamTable, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/nodes/trigger')

export default function TriggerNodePage() {
  return (
    <DocPage href="/docs/nodes/trigger">
      <H2 id="purpose">Purpose</H2>
      <P>
        Every workflow has exactly one Trigger node, and it is placed for you when the
        workflow is created. It marks the entry point and declares the workflow&rsquo;s
        inputs.
      </P>
      <Meta label="Category">Trigger</Meta>
      <Meta label="Outputs"><C>out</C></Meta>
      <Meta label="Inputs">None — nothing can precede it</Meta>

      <P>
        The <em>type</em> of trigger — manual, schedule, webhook, call event, integration
        event — is a property of the workflow, set alongside its name, not a field on this
        node. See <A href="/docs/workflows/triggers">Triggers</A>.
      </P>

      <H2 id="parameters">Parameters</H2>
      <ParamTable
        params={[
          {
            name: 'inputs',
            type: 'input[]',
            default: '[]',
            description: (
              <>
                The parameters this workflow accepts. Each becomes available everywhere as{' '}
                <C>{'{{trigger.<name>}}'}</C>.
              </>
            ),
          },
        ]}
      />

      <P>Each declared input carries:</P>
      <Table
        headers={['Field', 'Purpose']}
        widths={['w-[22%]']}
        rows={[
          [<Strong>Name</Strong>, <>The reference key. Use <C>snake_case</C> — it is what you will type in every downstream field.</>],
          [<Strong>Type</Strong>, 'String, number, or boolean. Governs how the value is interpreted when supplied.'],
          [<Strong>Description</Strong>, 'What the value is. Read by the model when this workflow is used as a tool.'],
          [<Strong>Required</Strong>, 'Whether the workflow can run without it.'],
        ]}
      />

      <H2 id="inputs-as-tool-parameters">Inputs become tool parameters</H2>
      <P>
        This is the most important thing about the Trigger node, and the easiest to miss.
      </P>
      <P>
        When a workflow is wired to an agent through a{' '}
        <A href="/docs/tools/workflow">workflow tool</A>, its declared inputs become the
        parameters the agent must extract from the conversation before it can run the
        workflow. The agent reads the names and descriptions to work out what to listen for.
      </P>

      <CodeBlock
        language="One declaration, two consumers"
        code={`Trigger inputs
  customer_email   string   "The caller's email address"        required
  appointment_day  string   "The day they want, e.g. Tuesday"   required
  notes            string   "Anything else they mentioned"      optional

↓ inside the workflow            ↓ as a tool parameter
{{trigger.customer_email}}       The agent asks for, and extracts,
{{trigger.appointment_day}}      the caller's email and preferred day
{{trigger.notes}}                before invoking the workflow.`}
      />

      <Callout kind="tip" title="Write descriptions for the model">
        &ldquo;The caller&rsquo;s email address&rdquo; gets extracted reliably.
        &ldquo;email&rdquo; gets confused with the business&rsquo;s email, a colleague&rsquo;s
        email, or nothing at all. The guidance in{' '}
        <A href="/docs/tools/parameters#writing-descriptions">Tool Parameters</A> applies
        here verbatim.
      </Callout>

      <UL>
        <LI>
          <Strong>Mark inputs required only when they truly are.</Strong> A required parameter
          the caller cannot supply leaves the agent stuck asking for something that does not
          exist.
        </LI>
        <LI>
          <Strong>Keep the list short.</Strong> Each input is another thing the agent must
          extract correctly before anything happens. Three or four is comfortable; ten is not.
        </LI>
      </UL>

      <H2 id="example">Example</H2>
      <CodeBlock
        language="An appointment-booking workflow"
        code={`Trigger  (manual — invoked by a workflow tool)
  inputs:
    customer_name   string   required
    customer_phone  string   required
    preferred_date  string   required

  ↓ out

Integration — Google Calendar · create_event
  summary:  Appointment with {{trigger.customer_name}}
  start:    {{trigger.preferred_date}}

  ↓ out

Branch
  variable:  steps.n_cal01.status
  operator:  equals
  value:     confirmed

  ├─ true  → Speak: "You're booked for {{trigger.preferred_date}}."
  └─ false → Speak: "I couldn't confirm that. Let me take a message."`}
      />
    </DocPage>
  )
}
