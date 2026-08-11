import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { SectionGrid, StartHere } from '@/components/docs/SectionGrid'
import { Chain, Figure } from '@/components/docs/Diagram'
import {
  A, Callout, H2, H3, InfoCard, LI, P, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs')

export default function IntroductionPage() {
  return (
    <DocPage href="/docs">
      <P>
        Voicecon is a platform for building AI agents that hold real phone conversations —
        and, crucially, that <Strong>do things</Strong> during those conversations. An agent
        can look up an order in your CRM, book a slot on a calendar, text a confirmation, or
        escalate to a human, all mid-sentence.
      </P>
      <P>
        Most voice AI platforms stop at the conversation. Voicecon pairs the conversation
        layer with an automation layer: a visual workflow builder and a library of connected
        apps, so the agent is not just talking about your business — it is operating it.
      </P>

      <H2 id="start-here">Start here</H2>
      <P>
        Three routes in, depending on what you already know. If you are new, take the first.
      </P>
      <StartHere />

      <H2 id="the-building-blocks">The building blocks</H2>
      <P>
        Everything in Voicecon is assembled from seven objects. You will meet all of them in
        the first hour, so it is worth knowing what each one is responsible for.
      </P>

      <div className="grid gap-3 sm:grid-cols-2">
        <InfoCard title="Agent">
          The voice on the call. Owns the prompt, the model, the voice, and the turn-taking
          behaviour.
        </InfoCard>
        <InfoCard title="Tool">
          A single capability the agent may invoke — transfer a call, write to a CRM, run a
          workflow. The agent decides when.
        </InfoCard>
        <InfoCard title="Workflow">
          A visual, multi-step automation. Branches, loops, code, and calls out to apps.
        </InfoCard>
        <InfoCard title="Integration">
          A connected third-party account — HubSpot, Slack, Google Calendar — with its
          credentials stored once and reused everywhere.
        </InfoCard>
        <InfoCard title="Knowledge base">
          Documents the agent can search and answer from, so facts live outside the prompt.
        </InfoCard>
        <InfoCard title="Phone number">
          A real number, bought through a carrier, pointed at one agent.
        </InfoCard>
      </div>

      <P>
        The seventh is the <Strong>call</Strong> itself — the record of what happened, with
        transcript, recording, summary, analysis, and cost. Every other object exists to shape
        the calls, and every call is the evidence of whether that shaping worked.
      </P>

      <H2 id="how-they-fit-together">How they fit together</H2>
      <P>
        The relationships matter more than the definitions. Here is the whole platform in one
        line:
      </P>

      <Figure caption="A phone number routes to an agent; the agent uses tools; a tool can run a workflow; the workflow acts on connected apps.">
        <Chain
          stages={[
            { label: 'Phone number', caption: 'carrier', tone: 'slate' },
            { label: 'Agent', caption: 'prompt + voice', tone: 'brand' },
            { label: 'Tool', caption: 'a capability', tone: 'amber' },
            { label: 'Workflow', caption: 'multi-step logic', tone: 'violet' },
            { label: 'Your apps', caption: 'via integrations', tone: 'blue' },
          ]}
        />
      </Figure>

      <P>
        Not every call travels the whole chain. A simple FAQ agent stops at the second box. An
        agent that only needs to send one SMS stops at the third. The chain extends as far as
        the job requires, and each link is optional.
      </P>

      <Table
        headers={['If you need to…', 'Reach for']}
        widths={['w-[46%]']}
        rows={[
          ['Answer questions from documents', <>A <A href="/docs/knowledge-base">knowledge base</A> attached to the agent</>],
          ['Do one specific thing (send an SMS, transfer)', <>A single <A href="/docs/tools">tool</A></>],
          ['Do several things in order, with branching', <>A <A href="/docs/workflows">workflow</A>, invoked by a workflow tool</>],
          ['Read or write data in another product', <>An <A href="/docs/integrations">integration</A>, used from a tool or workflow</>],
          ['Hand the caller to a person', <>A transfer or handoff <A href="/docs/tools/phone-call">tool</A></>],
        ]}
      />

      <H2 id="two-ways-to-build">Two ways to build a call</H2>
      <P>
        Voicecon supports two distinct styles of call design, and choosing the right one for
        the job saves a great deal of rework.
      </P>

      <H3>Prompt-driven (an agent with tools)</H3>
      <P>
        You write a system prompt describing the agent&rsquo;s job, attach a handful of tools,
        and let the model decide what to say and when to act. The conversation is open-ended;
        the model handles unexpected turns.
      </P>
      <UL>
        <LI><Strong>Best for</Strong> support, qualification, FAQ, anything conversational.</LI>
        <LI><Strong>Trade-off</Strong> less deterministic — the model may phrase things differently each call.</LI>
      </UL>

      <H3>Flow-driven (a workflow with conversation nodes)</H3>
      <P>
        You lay out the call as a graph: speak this, ask that, branch on the answer, call this
        API, end. The path is explicit and repeatable.
      </P>
      <UL>
        <LI><Strong>Best for</Strong> scripted intake, compliance-sensitive calls, surveys, IVR replacement.</LI>
        <LI><Strong>Trade-off</Strong> less adaptable — a caller who goes off-script has to be handled by a branch you wrote.</LI>
      </UL>

      <Callout kind="note" title="They combine">
        The strongest designs use both. A prompt-driven agent handles the conversation, and
        when it needs to execute a precise sequence — verify identity, check three systems,
        book the slot — it calls a workflow tool that runs the deterministic part. See{' '}
        <A href="/docs/tools/workflow">Workflow Tools</A>.
      </Callout>

      <H2 id="browse">Browse the documentation</H2>
      <P>
        Ten sections, thirty-five pages, covering every feature in the platform — from a first
        agent to the REST API behind it.
      </P>
      <SectionGrid />
    </DocPage>
  )
}
