import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { CodeBlock } from '@/components/docs/CodeBlock'
import {
  A, C, Callout, H2, LI, P, ParamTable, RefHeader, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/tools/assistant')

export default function AssistantToolsPage() {
  return (
    <DocPage href="/docs/tools/assistant">
      <P>
        Assistant tools change who or what is answering — a person instead of the agent, or
        your documents instead of the model&rsquo;s memory.
      </P>

      <RefHeader id="handoff" name="Handoff" chip="Assistant" tone="brand">
        Hands the conversation to a human agent or a queue.
      </RefHeader>

      <ParamTable
        params={[
          {
            name: 'destination',
            type: 'string',
            required: true,
            description: (
              <>
                The queue or agent identifier in your contact-centre system —{' '}
                <C>support-queue</C>, <C>billing-tier-2</C>. Not a phone number.
              </>
            ),
          },
          {
            name: 'message',
            type: 'string',
            description: (
              <>
                Spoken to the caller before the handoff — &ldquo;Let me put you through to a
                specialist.&rdquo;
              </>
            ),
          },
        ]}
      />

      <P>Every agent that takes real calls should have an escape hatch. Handoff is it.</P>
      <UL>
        <LI>The caller explicitly asks for a person.</LI>
        <LI>The agent has failed twice at the same request.</LI>
        <LI>The caller is upset, and sentiment or your own judgement says escalate.</LI>
        <LI>The request is outside the agent&rsquo;s scope entirely.</LI>
      </UL>

      <CodeBlock
        language="A handoff tool that fires when it should"
        code={`Name:         transfer_to_human
Description:  Hands the caller to a human support agent. Use when the caller
              asks for a person, when you have already failed to help twice,
              or when the caller is clearly frustrated.
Destination:  support-queue
Message:      Of course — let me put you through to a colleague now.

Parameters
  reason      string   "Brief summary of why the caller needs a human"   required`}
      />

      <Callout kind="tip" title="Collect a reason">
        A <C>reason</C> parameter costs nothing and gives the receiving human context. It also
        makes escalations reportable — you can see what your agent keeps failing at.
      </Callout>

      <RefHeader id="query-knowledge-base" name="Query Knowledge Base" chip="Assistant" tone="brand">
        Searches a specific knowledge base and returns matching passages for the agent to
        answer from.
      </RefHeader>

      <ParamTable
        params={[
          {
            name: 'knowledge_base_id',
            type: 'string',
            required: true,
            description: (
              <>
                Which knowledge base to search. Find ids under{' '}
                <A href="/docs/knowledge-base">Knowledge Base</A>.
              </>
            ),
          },
        ]}
      />

      <P>
        Declare a <C>query</C> parameter so the agent can pass what the caller actually asked:
      </P>
      <CodeBlock
        language="A targeted lookup tool"
        code={`Name:         check_return_policy
Description:  Looks up the returns and refunds policy. Use whenever the caller
              asks about returning an item, refunds, or exchange windows.
KB id:        kb_7f3a91c2

Parameters
  query       string   "The caller's question, in their own words"   required`}
      />

      <H2 id="linked-vs-tool">Linked knowledge base or query tool?</H2>
      <P>
        There are two ways to give an agent access to documents, and they behave differently.
      </P>

      <Table
        headers={['', 'Linked to the agent', 'Query Knowledge Base tool']}
        widths={['w-[22%]', 'w-[38%]']}
        rows={[
          [
            'How it fires',
            'Automatically — relevant passages are injected into context',
            'The model decides to call it',
          ],
          [
            'Best for',
            'A single body of knowledge the agent draws on constantly',
            'Several distinct bodies, searched only when relevant',
          ],
          [
            'Cost',
            'Retrieval on every turn',
            'Retrieval only when invoked',
          ],
          [
            'Control',
            'Priority, similarity, and result count per link',
            'Explicit — you name the situation in the description',
          ],
        ]}
      />

      <Callout kind="note" title="A useful pattern">
        Link the general product knowledge base to the agent so it is always available, and
        add query tools for narrow, high-stakes bodies — pricing, legal terms, policy — where
        you want retrieval to be deliberate and traceable rather than ambient.
      </Callout>

      <H2 id="handoff-vs-transfer">Handoff or Transfer Call?</H2>
      <Table
        headers={['', 'Handoff', 'Transfer Call']}
        widths={['w-[22%]', 'w-[38%]']}
        rows={[
          ['Sends to', 'A queue or agent in your contact centre', 'A phone number or SIP address'],
          ['Context', 'Can carry a reason and conversation context', 'Whatever the receiving system reads'],
          ['Use when', 'You run a contact-centre platform with queues', 'You are routing to a plain phone line'],
        ]}
      />
      <P>
        If your team is reached on an ordinary number, use{' '}
        <A href="/docs/tools/phone-call#transfer-call">Transfer Call</A>. Handoff is for
        contact-centre platforms where a queue is the destination.
      </P>
    </DocPage>
  )
}
