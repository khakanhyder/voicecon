import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { CodeBlock } from '@/components/docs/CodeBlock'
import {
  A, C, Callout, H2, LI, P, Step, Steps, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/quickstart')

export default function QuickstartPage() {
  return (
    <DocPage href="/docs/quickstart">
      <H2 id="before-you-start">Before you start</H2>
      <P>
        You need a Voicecon workspace and a plan or an active free trial. A trial requires no
        card and is enough to complete every step here, including buying a phone number.
      </P>
      <UL>
        <LI>Sign in and finish onboarding — company details and a plan or trial.</LI>
        <LI>
          If you want to hear the agent on a real phone, you will also need a connected
          carrier (Twilio or Telnyx) under <Strong>Integrations</Strong>. Steps 1&ndash;4 work
          without one.
        </LI>
      </UL>

      <Callout kind="note" title="Everything is reversible">
        Agents can be deleted, numbers released, and workflows switched off. Nothing in this
        guide commits you to ongoing cost except buying a phone number, which carries a small
        monthly fee from the carrier.
      </Callout>

      <H2 id="step-1-create-agent">Step 1 — Create an agent</H2>
      <Steps>
        <Step n={1} title="Open Agents and create">
          <P>
            Go to <Strong>Agents</Strong> in the sidebar and choose <Strong>New Agent</Strong>.
            Give it a name your team will recognise on a call log — <C>Riley — Inbound
            Support</C> beats <C>Agent 1</C>.
          </P>
        </Step>
        <Step n={2} title="Add a description">
          <P>
            Optional, but it is what other people in the workspace will read six months from
            now when they wonder what this agent is for.
          </P>
        </Step>
      </Steps>

      <H2 id="step-2-write-prompt">Step 2 — Write the prompt</H2>
      <P>
        Two fields do most of the work. On the <Strong>Prompt</Strong> tab, set the first
        message and the system prompt.
      </P>
      <P>
        The <Strong>first message</Strong> is spoken verbatim the moment the call connects.
        It sets expectations and gives the caller something to respond to:
      </P>
      <CodeBlock
        compact
        language="First message"
        code={`Thanks for calling Wellness Partners, this is Riley. How can I help you today?`}
      />
      <P>
        The <Strong>system prompt</Strong> is the agent&rsquo;s standing instruction. Be
        specific about role, scope, tone, and what to do when it does not know something:
      </P>
      <CodeBlock
        language="System prompt"
        code={`You are Riley, a scheduling assistant for Wellness Partners, a physiotherapy clinic.

Your job:
- Help callers book, move, or cancel appointments.
- Answer questions about opening hours, location, and pricing.

Rules:
- Keep replies to one or two sentences. This is a phone call, not an email.
- Always confirm the date and time back to the caller before booking.
- If you do not know something, say so and offer to take a message.
- Never give medical advice. If asked, offer to book a consultation instead.`}
      />

      <Callout kind="tip" title="Write for the ear">
        Long, well-structured paragraphs read beautifully and sound terrible. Ask for short
        replies explicitly — models default to prose length that works on screen, not on a
        phone line.
      </Callout>

      <H2 id="step-3-pick-voice">Step 3 — Pick a model and voice</H2>
      <P>
        Move through the <Strong>LLM Selection</Strong>, <Strong>Transcriber</Strong>, and{' '}
        <Strong>Voice Selection</Strong> tabs. The defaults are sensible; these are the
        choices worth making deliberately on your first agent:
      </P>
      <Table
        headers={['Setting', 'Start with', 'Why']}
        widths={['w-[26%]', 'w-[28%]']}
        rows={[
          [
            'LLM model',
            <C>gpt-4.1-mini</C>,
            'Fast enough for natural turn-taking. Move up only if the agent reasons poorly.',
          ],
          [
            'Temperature',
            <C>0.7</C>,
            'Lower for scripted accuracy, higher for warmth. 0.3–0.8 is the usable band.',
          ],
          [
            'Transcriber',
            <>Deepgram <C>nova-2</C></>,
            'Strong accuracy on telephone-quality audio with low latency.',
          ],
          [
            'Voice',
            'Any ElevenLabs voice',
            'Preview a few. Voice choice affects trust more than most people expect.',
          ],
          [
            'Language',
            'Match your callers',
            'Set on the transcriber. A mismatch here degrades everything downstream.',
          ],
        ]}
      />
      <P>
        Save the agent. Full detail on every field is in{' '}
        <A href="/docs/agents/configuration">Agent Configuration</A>.
      </P>

      <H2 id="step-4-test">Step 4 — Test it in the browser</H2>
      <P>
        Open the agent and choose <Strong>Test</Strong>. This opens a browser-based call using
        your microphone — no phone number required, and no telephony cost.
      </P>
      <UL>
        <LI>Allow microphone access when prompted.</LI>
        <LI>Speak naturally, including interrupting the agent mid-sentence.</LI>
        <LI>Deliberately ask something out of scope, and check the refusal is graceful.</LI>
      </UL>
      <P>
        Test calls are recorded in <Strong>Calls</Strong> with direction <C>test</C>, so you
        can read the transcript afterwards rather than trying to remember what went wrong.
      </P>

      <H2 id="step-5-phone-number">Step 5 — Attach a phone number</H2>
      <Steps>
        <Step n={1} title="Connect a carrier">
          <P>
            Under <Strong>Integrations</Strong>, connect Twilio or Telnyx with your account
            credentials. This is the account the number is purchased on and billed to.
          </P>
        </Step>
        <Step n={2} title="Search for a number">
          <P>
            Go to <Strong>Phone Numbers</Strong> → <Strong>Purchase Number</Strong>. Filter by
            country and area code, and pick one with voice capability.
          </P>
        </Step>
        <Step n={3} title="Assign the agent">
          <P>
            Once provisioned, open the number and set its agent to the one you just built.
            Voicecon points the carrier&rsquo;s voice webhook at the platform automatically —
            you do not configure webhooks by hand.
          </P>
        </Step>
        <Step n={4} title="Call it">
          <P>Dial the number from your own phone. The agent answers.</P>
        </Step>
      </Steps>

      <H2 id="step-6-review">Step 6 — Review the call</H2>
      <P>
        Open <Strong>Calls</Strong> and select the call you just made. You get the transcript,
        the recording, an AI-written summary, and a cost breakdown split across transcription,
        model, speech, and telephony.
      </P>
      <P>
        This is the loop you will run hundreds of times: place a call, read the transcript,
        find the sentence where it went wrong, adjust the prompt, call again.
      </P>

      <H2 id="next-steps">Next steps</H2>
      <P>Your agent can talk. Now give it the ability to act.</P>
      <UL>
        <LI>
          <A href="/docs/tools">Add a tool</A> so it can send an SMS, transfer to a human, or
          write to your CRM.
        </LI>
        <LI>
          <A href="/docs/knowledge-base">Attach a knowledge base</A> so it answers from your
          documents instead of from the prompt.
        </LI>
        <LI>
          <A href="/docs/workflows">Build a workflow</A> when a single tool is not enough and
          the sequence needs branching.
        </LI>
        <LI>
          <A href="/docs/agents/configuration#tuning-for-latency">Tune for latency</A> once the
          behaviour is right and you want it to feel faster.
        </LI>
      </UL>
    </DocPage>
  )
}
