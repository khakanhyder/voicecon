import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { CodeBlock } from '@/components/docs/CodeBlock'
import {
  A, C, Callout, H2, LI, P, ParamTable, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/workspace/api-keys')

export default function ApiKeysPage() {
  return (
    <DocPage href="/docs/workspace/api-keys">
      <H2 id="creating-a-key">Creating a key</H2>
      <P>
        <Strong>Settings</Strong> → <Strong>API Keys</Strong> → <Strong>New Key</Strong>. Keys
        are scoped to the workspace you are in and let external systems drive the platform
        without a user session.
      </P>
      <ParamTable
        params={[
          {
            name: 'name',
            type: 'string',
            required: true,
            description: (
              <>
                What this key is for — <C>Website booking form</C>, <C>Nightly sync</C>. When
                the time comes to revoke one, this is all you will have to go on.
              </>
            ),
          },
          {
            name: 'scopes',
            type: 'string[]',
            description: (
              <>
                What the key may do. Grant the narrowest set that works. See{' '}
                <A href="#scopes">Scopes</A>.
              </>
            ),
          },
          {
            name: 'expires_at',
            type: 'datetime',
            description: (
              <>
                Optional expiry. Set one on anything given to a contractor or used for a
                time-boxed project.
              </>
            ),
          },
        ]}
      />
      <Callout kind="danger" title="The secret is shown once">
        The full key is displayed at creation and never again. Copy it into your secret store
        immediately. If you lose it, regenerate — there is no way to retrieve it.
      </Callout>

      <H2 id="using-a-key">Using a key</H2>
      <P>Send it as a bearer token.</P>
      <CodeBlock
        language="bash"
        code={`curl https://api.your-voicecon-host.com/api/v1/agents \\
  -H "Authorization: Bearer $VOICECON_API_KEY"`}
      />
      <UL>
        <LI>Keep keys in environment variables or a secret manager, never in source control.</LI>
        <LI>Never expose a key in browser JavaScript — anything a browser can read, a visitor can take.</LI>
        <LI>Use a separate key per integration, so revoking one does not break the others.</LI>
      </UL>

      <H2 id="scopes">Scopes</H2>
      <P>
        Scopes follow a <C>resource:action</C> shape. <C>:read</C> is view-only,{' '}
        <C>:write</C> covers create and update, and <C>:delete</C> is split out where
        destroying data deserves its own gate.
      </P>
      <Table
        headers={['Scope', 'Allows']}
        widths={['w-[30%]']}
        rows={[
          [<C>agents:read</C>, 'List and view agents.'],
          [<C>agents:write</C>, 'Create and update agents.'],
          [<C>agents:delete</C>, 'Delete agents.'],
          [<C>calls:read</C>, 'List calls, read transcripts and analysis.'],
          [<C>calls:write</C>, 'Place outbound calls.'],
          [<C>phone_numbers:read</C>, 'List numbers and their configuration.'],
          [<C>phone_numbers:write</C>, 'Buy, configure, and release numbers.'],
          [<C>workflows:read</C>, 'List workflows and their execution history.'],
          [<C>workflows:write</C>, 'Create and update workflows.'],
          [<C>workflows:execute</C>, 'Run workflows.'],
          [<C>tools:read</C>, 'List tools.'],
          [<C>tools:write</C>, 'Create and update tools.'],
          [<C>knowledge:read</C>, 'Search knowledge bases and list documents.'],
          [<C>knowledge:write</C>, 'Create knowledge bases and upload documents.'],
          [<C>integrations:read</C>, 'List connections and their status.'],
          [<C>integrations:write</C>, 'Create and update connections.'],
          [<C>analytics:read</C>, 'Read aggregated metrics.'],
          [<C>team:read</C>, 'List workspace members.'],
          [<C>workspace:read</C>, 'Read workspace details.'],
        ]}
      />
      <Callout kind="note" title="Some scopes cannot be granted to a key at all">
        Anything that changes who holds power or spends money — managing team roles, changing
        the plan, transferring ownership, deleting the workspace — is not assignable to an API
        key under any circumstances. Attempting it is rejected at creation rather than
        accepted and silently ignored.
      </Callout>

      <H2 id="the-ceiling">The permission ceiling</H2>
      <P>
        A key never grants more than the person who created it has. Scopes are the maximum a
        key may do; the creator&rsquo;s own role is the ceiling.
      </P>
      <CodeBlock
        language="How the two combine"
        code={`Key scopes:        agents:read, agents:write, agents:delete
Creator's role:    member    → may write and delete agents
Effective:         agents:read, agents:write, agents:delete   ✓

Same key, creator later demoted to viewer:
Creator's role:    viewer    → read-only
Effective:         agents:read                                 ← write and delete stop working`}
      />
      <P>
        This means a key cannot be used to escalate privileges, and demoting someone
        immediately narrows every key they created. It also means a key can stop working
        without anything about the key changing — check the creator&rsquo;s role before
        debugging further.
      </P>

      <H2 id="rotating">Rotating and revoking</H2>
      <Table
        headers={['Action', 'Effect']}
        widths={['w-[22%]']}
        rows={[
          [<Strong>Regenerate</Strong>, 'Issues a new secret for the same key. The old secret stops working immediately — update the consumer first, or expect downtime.'],
          [<Strong>Disable</Strong>, 'Stops the key working without deleting it. The reversible option when you suspect a leak but are not sure.'],
          [<Strong>Delete</Strong>, 'Removes it permanently.'],
        ]}
      />
      <UL>
        <LI>Rotate on a schedule, and immediately whenever someone with access leaves.</LI>
        <LI>Disable first if you are unsure what a key is used for — the breakage tells you.</LI>
        <LI>Set expiry dates on anything temporary, so forgotten keys expire themselves.</LI>
      </UL>
      <Callout kind="warning" title="If a key leaks">
        Disable it immediately, then review <A href="/docs/calls">Calls</A> and workflow
        execution history for activity you do not recognise. Regenerating without disabling
        first leaves a window where the old secret still works.
      </Callout>
    </DocPage>
  )
}
