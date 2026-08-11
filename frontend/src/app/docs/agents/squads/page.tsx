import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { Chain, Figure } from '@/components/docs/Diagram'
import {
  A, C, Callout, H2, LI, P, ParamTable, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/agents/squads')

export default function SquadsPage() {
  return (
    <DocPage href="/docs/agents/squads">
      <H2 id="what-is-a-squad">What is a squad?</H2>
      <P>
        A squad is several agents that share one call. The call starts with a designated
        agent, and transfer rules move the caller between specialists without dropping the
        line or losing context.
      </P>

      <Figure caption="A triage agent identifies intent, then hands to whichever specialist owns it.">
        <Chain
          stages={[
            { label: 'Call arrives', tone: 'slate' },
            { label: 'Triage agent', caption: 'initial agent', tone: 'brand' },
            { label: 'Billing agent', caption: 'or Support agent', tone: 'violet' },
          ]}
        />
      </Figure>

      <P>
        The value is focus. One agent trying to be a billing expert, a technical support
        engineer, and a scheduler holds a sprawling prompt and a long tool list, and does all
        three jobs worse than three tight agents would.
      </P>

      <H2 id="members-and-roles">Members and roles</H2>
      <ParamTable
        params={[
          {
            name: 'name',
            type: 'string',
            required: true,
            description: 'Identifies the squad in lists and on call records.',
          },
          {
            name: 'initial_agent_id',
            type: 'agent',
            description: (
              <>
                The agent that answers. Usually a lightweight triage agent whose only job is
                to work out what the caller needs.
              </>
            ),
          },
          {
            name: 'members',
            type: 'squad member[]',
            description: 'The agents available on this call, each with a role and conditions.',
          },
          {
            name: 'members[].role',
            type: 'string',
            description: (
              <>
                A label describing what this member handles — <C>billing</C>,{' '}
                <C>technical</C>, <C>scheduling</C>. Used in transfer rules.
              </>
            ),
          },
          {
            name: 'members[].transfer_conditions',
            type: 'object',
            description: 'When the call should move to this member.',
          },
          {
            name: 'members[].execution_order',
            type: 'number',
            default: '0',
            description: (
              <>
                Evaluation order when conditions overlap. Lower runs first — put your most
                specific member above your catch-all.
              </>
            ),
          },
        ]}
      />

      <H2 id="transfer-rules">Transfer rules</H2>
      <P>
        Transfer rules decide when the call moves. They are evaluated against the conversation
        as it develops, and the first matching rule wins — which makes ordering significant.
      </P>
      <UL>
        <LI>
          <Strong>Be specific.</Strong> A rule matching &ldquo;the caller mentions
          money&rdquo; will pull in far more than billing questions.
        </LI>
        <LI>
          <Strong>Order from narrow to broad.</Strong> A general rule placed first will
          swallow calls that a later, more precise rule should have taken.
        </LI>
        <LI>
          <Strong>Give the triage agent a fallback.</Strong> Decide explicitly what happens
          when nothing matches — usually staying with triage, or a human handoff.
        </LI>
      </UL>

      <Callout kind="warning" title="Transfers are not free">
        Each hop costs a moment of dead air and risks the caller repeating themselves. Two or
        three specialists is usually the practical ceiling; beyond that, callers notice the
        seams.
      </Callout>

      <H2 id="squad-vs-workflow">Squad or workflow?</H2>
      <P>
        Both route a call, and they solve genuinely different problems.
      </P>

      <Table
        headers={['', 'Squad', 'Workflow']}
        widths={['w-[22%]', 'w-[39%]']}
        rows={[
          ['Routes between', 'Whole agents, each with its own voice and prompt', 'Steps within one agent’s call'],
          ['Decides using', 'The model’s reading of intent', 'Explicit conditions you author'],
          ['Best for', 'Distinct domains needing different expertise or tone', 'A defined sequence with branches'],
          ['Caller experience', 'Feels like being put through to a department', 'Feels like one continuous conversation'],
          ['Predictability', 'Lower — the model chooses', 'Higher — you chose'],
        ]}
      />

      <Callout kind="tip" title="Start with one agent">
        Squads add coordination cost. Build a single agent first; split into a squad only when
        its prompt genuinely covers unrelated domains and you can feel the compromise in the
        transcripts. Also consider a{' '}
        <A href="/docs/tools/workflow">workflow tool</A> — often the sequence you wanted a
        second agent for is really a workflow.
      </Callout>
    </DocPage>
  )
}
