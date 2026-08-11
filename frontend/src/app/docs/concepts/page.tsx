import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { Figure } from '@/components/docs/Diagram'
import {
  A, Callout, H2, LI, P, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/concepts')

export default function ConceptsPage() {
  return (
    <DocPage href="/docs/concepts">
      <H2 id="object-model">The object model</H2>
      <P>
        Voicecon has a small number of objects with clear ownership. Knowing which object owns
        a given setting is the difference between five minutes and an hour when something is
        not behaving.
      </P>

      <Figure caption="Ownership at a glance. An arrow means “points at” — a phone number points at one agent; an agent points at many tools.">
        <div className="space-y-2 font-mono text-[12.5px] leading-relaxed text-slate-700">
          <div>Workspace</div>
          <div className="pl-4">├── Agent ──────────── prompt, model, voice, turn-taking</div>
          <div className="pl-4">│&nbsp;&nbsp;&nbsp;├── Tools ──────── what it may do</div>
          <div className="pl-4">│&nbsp;&nbsp;&nbsp;├── Knowledge bases ─ what it may cite</div>
          <div className="pl-4">│&nbsp;&nbsp;&nbsp;└── Phone numbers ── where it is reachable</div>
          <div className="pl-4">├── Workflow ───────── nodes, edges, trigger</div>
          <div className="pl-4">├── Integration ────── one connected third-party account</div>
          <div className="pl-4">├── Knowledge base ─── documents, chunks, embeddings</div>
          <div className="pl-4">└── Call ───────────── transcript, recording, analysis, cost</div>
        </div>
      </Figure>

      <H2 id="agent">Agent</H2>
      <P>
        The conversational entity. An agent owns everything about <Strong>how it sounds and
        how it behaves</Strong>: the system prompt, the first message, the LLM provider and
        model, the speech-to-text engine, the text-to-speech voice, interruption sensitivity,
        silence timeouts, and the maximum call duration.
      </P>
      <P>
        An agent does <em>not</em> own the things it can do. Those are tools, assigned to the
        agent, and they can be shared across several agents.
      </P>
      <Callout kind="note" title="Agents are versioned and cloneable">
        Cloning an agent copies its full configuration. This is the safe way to try a
        prompt rewrite against a production agent without risking live calls.
      </Callout>

      <H2 id="tool">Tool</H2>
      <P>
        A single capability, defined once and reusable. A tool has a name, a description, a
        type, a type-specific configuration, and a set of <A href="/docs/tools/parameters">
        parameters</A>.
      </P>
      <P>
        The name and description are not cosmetic — they are what the model reads when it
        decides whether this is the tool for the current moment. The parameters are what it
        must collect from the caller before invoking it.
      </P>
      <P>
        Tools fall into four families: <Strong>workflow</Strong>, <Strong>phone call</Strong>,{' '}
        <Strong>assistant</Strong>, and <Strong>integration</Strong>. See{' '}
        <A href="/docs/tools">Tools</A>.
      </P>

      <H2 id="workflow">Workflow</H2>
      <P>
        A directed graph of nodes with a trigger. Workflows serve two distinct purposes, and
        the same builder handles both:
      </P>
      <UL>
        <LI>
          <Strong>Back-office automation</Strong> — triggered by a schedule, a webhook, or a
          completed call. No caller is on the line.
        </LI>
        <LI>
          <Strong>Call flow</Strong> — invoked mid-call by a workflow tool, using conversation
          nodes (Speak, Ask, Transfer) to drive the live call.
        </LI>
      </UL>
      <P>
        Every workflow keeps an execution history with per-node results, which is where you
        look when one fails. See <A href="/docs/workflows">Workflows</A>.
      </P>

      <H2 id="integration">Integration</H2>
      <P>
        Two words that get confused, so worth separating:
      </P>
      <Table
        headers={['Term', 'Meaning']}
        widths={['w-[24%]']}
        rows={[
          [
            <Strong>Connector</Strong>,
            'The platform-provided definition of an app — its base URL, auth type, rate limits, and the actions it supports. You do not create these.',
          ],
          [
            <Strong>Connection</Strong>,
            'Your authenticated account on that app. Credentials are encrypted at rest. This is what you create, and what a tool or workflow node points at.',
          ],
        ]}
      />
      <P>
        You may hold several connections to the same connector — two Slack workspaces, a
        sandbox and a production Salesforce. Each is selected independently.
      </P>

      <H2 id="knowledge-base">Knowledge base</H2>
      <P>
        A container of documents that have been split into chunks and embedded for semantic
        search. At call time, the caller&rsquo;s question is embedded, the closest chunks are
        retrieved, and they are injected into the model&rsquo;s context.
      </P>
      <P>
        A knowledge base is linked to an agent through a join that carries its own settings —
        priority, maximum results, minimum similarity, and whether to inject automatically.
        The same knowledge base can serve many agents with different settings for each. See{' '}
        <A href="/docs/knowledge-base">Knowledge Base</A>.
      </P>

      <H2 id="phone-number">Phone number</H2>
      <P>
        A real number provisioned through a carrier connection. It records which provider it
        was bought on, its capabilities (voice, SMS), its status, and its monthly cost.
      </P>
      <P>
        A number points at <Strong>at most one agent</Strong>. An agent may hold several
        numbers. Inbound calls to the number are answered by that agent.
      </P>

      <H2 id="call">Call</H2>
      <P>
        The record of a conversation. It carries direction, from and to numbers, status,
        timings, recording, transcript, an AI summary, analysis (sentiment, intent, topics),
        and a four-way cost split.
      </P>
      <P>
        Beneath each call sits an <Strong>event log</Strong> — timestamped entries for each
        transcription, model call, speech synthesis, and tool invocation, with durations. This
        is the forensic layer when a call misbehaved and the transcript alone does not explain
        why. See <A href="/docs/calls">Calls &amp; Call Logs</A>.
      </P>

      <H2 id="workspace">Workspace</H2>
      <P>
        The tenancy boundary. Every agent, workflow, tool, number, and call belongs to exactly
        one workspace, and nothing is visible across workspaces.
      </P>
      <P>
        People are added to a workspace with a role — owner, admin, member, or viewer — which
        determines what they may do. You can belong to several workspaces and switch between
        them. See <A href="/docs/workspace/team">Team &amp; Permissions</A>.
      </P>

      <H2 id="glossary">Glossary</H2>
      <Table
        headers={['Term', 'Definition']}
        widths={['w-[26%]']}
        rows={[
          ['Barge-in', 'The caller interrupting the agent mid-sentence. Controlled by interrupt settings on the agent.'],
          ['Chunk', 'A slice of a document, sized for embedding and retrieval. Set by chunk size and overlap.'],
          ['Connection', 'Your authenticated account on a third-party app.'],
          ['Connector', 'The platform-supplied definition of a third-party app.'],
          ['DTMF', 'Touch-tone keypad signalling. Used to capture digits instead of speech.'],
          ['E.164', 'The international phone number format, e.g. +14155550123.'],
          ['Edge', 'A connection between two workflow nodes, leaving a specific output handle.'],
          ['Embedding', 'A numeric vector representing text meaning, used for semantic search.'],
          ['Execution', 'One run of a workflow, with its own status, per-node results, and duration.'],
          ['Handle', 'A named output on a node. Branch has true and false; Switch has one per rule.'],
          ['LLM', 'The language model that decides what the agent says and which tools to call.'],
          ['Node', 'One step in a workflow.'],
          ['RAG', 'Retrieval-augmented generation — answering from retrieved documents rather than memory.'],
          ['Squad', 'Several agents orchestrated across one call, with transfer rules between them.'],
          ['STT', 'Speech-to-text. The transcriber that turns caller audio into words.'],
          ['Trigger', 'What starts a workflow.'],
          ['TTS', 'Text-to-speech. The voice engine that speaks the agent’s words.'],
          ['Turn', 'One exchange — the caller speaks, the agent replies.'],
        ]}
      />
    </DocPage>
  )
}
