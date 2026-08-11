import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { Chain, Figure } from '@/components/docs/Diagram'
import {
  A, C, Callout, H2, H3, LI, P, Step, Steps, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/agents')

export default function AgentsPage() {
  return (
    <DocPage href="/docs/agents">
      <H2 id="what-is-an-agent">What is an agent?</H2>
      <P>
        An agent is the entity that holds the conversation. It owns how it sounds, how it
        thinks, and how it takes turns — but not what it is allowed to do. Capabilities come
        from <A href="/docs/tools">tools</A> assigned to it, and facts come from{' '}
        <A href="/docs/knowledge-base">knowledge bases</A> linked to it.
      </P>
      <P>
        This separation is deliberate. It means you can build one carefully-tuned voice and
        personality, then reuse the same tools across a dozen agents, or swap an agent&rsquo;s
        model without touching anything else.
      </P>

      <H2 id="the-voice-loop">The voice loop</H2>
      <P>
        Understanding what happens on each turn explains most of the settings you will
        configure, and most of the latency you will feel.
      </P>

      <Figure caption="One conversational turn. Each stage adds latency; the settings on an agent mostly trade latency against quality at one of these stages.">
        <Chain
          stages={[
            { label: 'Caller speaks', tone: 'slate' },
            { label: 'Transcriber', caption: 'STT → text', tone: 'blue' },
            { label: 'LLM', caption: 'decides reply / tool', tone: 'brand' },
            { label: 'Voice', caption: 'TTS → audio', tone: 'violet' },
            { label: 'Caller hears', tone: 'slate' },
          ]}
        />
      </Figure>

      <P>Two things can interrupt that loop, and both matter:</P>
      <UL>
        <LI>
          <Strong>The caller interrupts</Strong> — barge-in. The agent stops speaking and
          listens. Governed by <C>interrupt_enabled</C> and <C>interrupt_sensitivity</C>.
        </LI>
        <LI>
          <Strong>The model calls a tool</Strong> — instead of replying, it invokes a tool,
          waits for the result, then speaks. A slow tool creates dead air, which is why
          workflow tools have a holding line.
        </LI>
      </UL>

      <H2 id="creating-an-agent">Creating an agent</H2>
      <Steps>
        <Step n={1} title="Start from blank or a template">
          <P>
            <Strong>Agents</Strong> → <Strong>New Agent</Strong>. Templates pre-fill a prompt
            and settings for common jobs; a blank agent gives you the defaults.
          </P>
        </Step>
        <Step n={2} title="Name and describe it">
          <P>
            The name appears on every call log and in tool pickers. Make it identify the
            agent&rsquo;s job, not its position in a list.
          </P>
        </Step>
        <Step n={3} title="Configure across the tabs">
          <P>
            Prompt, LLM, Transcriber, Voice, Tools, Conversation, Advanced, Knowledge, and
            Chat Widget. Every field is documented in{' '}
            <A href="/docs/agents/configuration">Agent Configuration</A>.
          </P>
        </Step>
        <Step n={4} title="Test before you attach a number">
          <P>
            Use the browser test to iterate for free. See{' '}
            <A href="/docs/agents/testing">Testing &amp; Channels</A>.
          </P>
        </Step>
      </Steps>

      <H2 id="agent-lifecycle">Activating, cloning, and deleting</H2>
      <Table
        headers={['Action', 'What happens']}
        widths={['w-[22%]']}
        rows={[
          [
            <Strong>Activate / deactivate</Strong>,
            'An inactive agent stops taking calls. Numbers stay assigned, so reactivating restores service without reconfiguration.',
          ],
          [
            <Strong>Clone</Strong>,
            'Copies the full configuration into a new agent. The clone starts with no phone numbers attached, so it cannot accidentally take live traffic.',
          ],
          [
            <Strong>Delete</Strong>,
            'Soft-deletes the agent. Its call history is retained for reporting. Detach phone numbers first, or those numbers will have no agent to answer.',
          ],
        ]}
      />

      <Callout kind="warning" title="Deleting an agent with a live number">
        A number whose agent has been deleted still rings — and nothing answers. Reassign the
        number before deleting, or release it.
      </Callout>

      <H2 id="agent-anatomy">Anatomy of a configured agent</H2>
      <P>
        A production-ready inbound agent usually has all of the following. If any are missing,
        it is worth asking whether that is a deliberate choice.
      </P>

      <H3>Always</H3>
      <UL>
        <LI>A first message that identifies the business and invites a response.</LI>
        <LI>A system prompt with an explicit scope and an explicit &ldquo;I don&rsquo;t know&rdquo; behaviour.</LI>
        <LI>A model chosen for latency, not just capability.</LI>
        <LI>A transcriber language matching your callers.</LI>
        <LI>A maximum call duration, so a stuck call cannot bill indefinitely.</LI>
      </UL>

      <H3>Usually</H3>
      <UL>
        <LI>An escape hatch — a transfer or handoff tool for when the agent is out of its depth.</LI>
        <LI>A knowledge base, so facts can be updated without editing prompts.</LI>
        <LI>End-call phrases, so &ldquo;goodbye&rdquo; reliably ends the call.</LI>
      </UL>

      <H3>When relevant</H3>
      <UL>
        <LI>Workflow tools for multi-step actions.</LI>
        <LI>Integration tools for direct CRM or calendar writes.</LI>
        <LI>Sentiment analysis, if you intend to report on it.</LI>
      </UL>
    </DocPage>
  )
}
