import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { CodeBlock } from '@/components/docs/CodeBlock'
import {
  A, C, Callout, H2, LI, Meta, P, ParamTable, RefHeader, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/nodes/conversation')

export default function ConversationNodesPage() {
  return (
    <DocPage href="/docs/nodes/conversation">
      <P>
        Conversation nodes drive a live call. They only work in a workflow invoked during a
        call — through a <A href="/docs/tools/workflow">workflow tool</A> — because they need
        somebody on the line.
      </P>

      <RefHeader id="speak" name="Speak" chip="Conversation" tone="blue">
        Says something to the caller and continues. The workflow&rsquo;s equivalent of a
        scripted line.
      </RefHeader>
      <Meta label="Outputs"><C>out</C></Meta>

      <ParamTable
        params={[
          {
            name: 'message',
            type: 'text',
            required: true,
            description: (
              <>
                What to say. Accepts <C>{'{{references}}'}</C> — <C>Thanks{' '}
                {'{{caller_name}}'}, your reference is {'{{ticket_id}}'}.</C>
              </>
            ),
          },
          {
            name: 'voice',
            type: 'string',
            default: 'the agent’s voice',
            description: (
              <>
                Override the voice for this line only. Leave empty unless you have a specific
                reason — switching voices mid-call is jarring.
              </>
            ),
          },
        ]}
      />

      <Callout kind="tip" title="Keep spoken lines short">
        A Speak node cannot be interrupted the way a conversational reply can. A long
        paragraph here is a long paragraph the caller must sit through. Split it across
        several nodes, or shorten it.
      </Callout>

      <RefHeader id="ask" name="Ask Question" chip="Conversation" tone="blue">
        Asks the caller something, waits for a reply, and stores it in a named variable.
      </RefHeader>
      <Meta label="Outputs"><C>out</C></Meta>

      <ParamTable
        params={[
          {
            name: 'question',
            type: 'text',
            required: true,
            description: 'What to ask. Supports references, so questions can be personalised.',
          },
          {
            name: 'variable',
            type: 'string',
            required: true,
            description: (
              <>
                Where the answer is stored. Later nodes read it as{' '}
                <C>{'{{<variable>}}'}</C> at the top level — no <C>steps.</C> prefix needed.
              </>
            ),
          },
          {
            name: 'input_type',
            type: 'enum',
            default: 'speech',
            description: (
              <>
                <C>speech</C> transcribes what the caller says. <C>dtmf</C> captures keypad
                presses instead.
              </>
            ),
          },
          {
            name: 'timeout',
            type: 'seconds',
            default: '10',
            description: (
              <>
                How long to wait for an answer. Raise it when the caller must look something
                up — an account number is rarely to hand.
              </>
            ),
          },
        ]}
      />

      <Table
        headers={['Use this input type', 'When']}
        widths={['w-[20%]']}
        rows={[
          [<C>speech</C>, 'Names, addresses, free-text reasons, yes/no. Natural, but transcription can misread.'],
          [<C>dtmf</C>, 'Account numbers, PINs, menu selections, card digits. Exact, and unaffected by accent or noise.'],
        ]}
      />

      <Callout kind="warning" title="Use DTMF for anything that must be exact">
        A misheard digit in an account number fails silently — the lookup returns nothing and
        the caller is told their account does not exist. If a value must be right, ask for it
        on the keypad.
      </Callout>

      <RefHeader id="transfer" name="Transfer Call" chip="Conversation · Terminal" tone="blue">
        Hands the call to a human or another number. The workflow ends here.
      </RefHeader>
      <Meta label="Outputs">None — this node is terminal</Meta>

      <ParamTable
        params={[
          {
            name: 'destination',
            type: 'string',
            required: true,
            description: (
              <>
                A phone number in E.164 (<C>+14155550123</C>) or a SIP URI. May be a reference,
                so the destination can be chosen by earlier logic.
              </>
            ),
          },
          {
            name: 'transfer_type',
            type: 'enum',
            default: 'blind',
            description: (
              <>
                <C>blind</C> connects the caller and drops out immediately. <C>warm</C>{' '}
                announces the caller to the recipient first, so they arrive with context.
              </>
            ),
          },
          {
            name: 'message',
            type: 'text',
            description: (
              <>
                Spoken to the caller before the transfer. Without it the line goes quiet and
                callers assume they have been cut off.
              </>
            ),
          },
        ]}
      />

      <UL>
        <LI>
          <Strong>Blind</Strong> — fast and cheap. Right for routing to a queue or a department
          that will re-ask for context anyway.
        </LI>
        <LI>
          <Strong>Warm</Strong> — slower and better. Right when a person is receiving a
          specific caller and repeating themselves would be annoying.
        </LI>
      </UL>

      <Callout kind="warning" title="Nothing runs after a transfer">
        The node is terminal. Anything you need recorded — a CRM note, a Slack alert — must
        happen <em>before</em> the Transfer node, not after it.
      </Callout>

      <RefHeader id="end" name="End Call" chip="Conversation · Terminal" tone="blue">
        Says a closing line and hangs up.
      </RefHeader>
      <Meta label="Outputs">None — this node is terminal</Meta>

      <ParamTable
        params={[
          {
            name: 'farewell',
            type: 'text',
            description: (
              <>
                Spoken before hanging up. Leave empty to end without a closing line, which is
                usually abrupt.
              </>
            ),
          },
        ]}
      />

      <Callout kind="note" title="End Call is not the only way a call ends">
        Calls also end when the caller hangs up, when <C>max_call_duration</C> is reached, or
        when the agent uses a Hang Up tool. This node is for ending a call deliberately, at a
        point your flow chose.
      </Callout>

      <H2 id="designing-conversation">Designing the conversation</H2>

      <P>Four habits separate a flow that sounds natural from one that sounds like a form.</P>

      <UL>
        <LI>
          <Strong>Confirm before acting.</Strong> Read the value back before doing anything
          irreversible. A Speak node with <C>{'{{appointment_date}}'}</C> followed by a
          yes/no Ask costs one turn and prevents a wrong booking.
        </LI>
        <LI>
          <Strong>Ask one thing at a time.</Strong> &ldquo;What&rsquo;s your name and account
          number?&rdquo; produces one answer containing both, and you cannot reliably split
          it. Two Ask nodes are shorter overall than untangling one.
        </LI>
        <LI>
          <Strong>Plan for no answer.</Strong> When a timeout produces an empty variable, a{' '}
          <A href="/docs/nodes/logic#filter">Filter</A> or{' '}
          <A href="/docs/nodes/logic#condition">Branch</A> on <C>is empty</C> lets you re-ask
          or route to a human, instead of carrying a blank forward.
        </LI>
        <LI>
          <Strong>Always leave an exit.</Strong> Every flow should have a path to a human. A
          caller trapped in a loop with no way out is worse than never having automated the
          call.
        </LI>
      </UL>

      <CodeBlock
        language="Ask → confirm → act"
        code={`Ask Question
  question:        What day works for you?
  variable:        preferred_date

Speak
  message:         Just to confirm — that's {{preferred_date}}?

Ask Question
  question:        Is that right?
  variable:        confirmed

Branch
  variable:        confirmed
  operator:        contains
  value:           yes

  ├─ true  → Integration: book the appointment
  └─ false → back to the first Ask Question`}
      />
    </DocPage>
  )
}
