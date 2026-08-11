import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { CodeBlock } from '@/components/docs/CodeBlock'
import {
  A, C, Callout, H2, LI, P, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/api')

/** Method chip, so endpoint tables scan by verb. */
function M({ children }: { children: string }) {
  const tone =
    children === 'GET'
      ? 'bg-blue-50 text-blue-700 border-blue-200'
      : children === 'DELETE'
        ? 'bg-rose-50 text-rose-700 border-rose-200'
        : children === 'POST'
          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
          : 'bg-amber-50 text-amber-700 border-amber-200'
  return (
    <span className={`inline-block rounded border px-1.5 py-0.5 font-mono text-[11px] font-semibold ${tone}`}>
      {children}
    </span>
  )
}

export default function ApiPage() {
  return (
    <DocPage href="/docs/api">
      <H2 id="base-url">Base URL and versioning</H2>
      <P>
        All endpoints live under <C>/api/v1</C> on your Voicecon host.
      </P>
      <CodeBlock compact language="Base URL" code={`https://api.your-voicecon-host.com/api/v1`} />
      <P>
        Interactive OpenAPI documentation is served by the backend at <C>/docs</C>, and is the
        authoritative reference for request and response shapes.
      </P>

      <H2 id="authentication">Authentication</H2>
      <P>Two mechanisms, for two different callers.</P>
      <Table
        headers={['Method', 'For', 'Header']}
        widths={['w-[20%]', 'w-[34%]']}
        rows={[
          [<Strong>API key</Strong>, 'Servers, scripts, integrations', <C>Authorization: Bearer &lt;key&gt;</C>],
          [<Strong>JWT</Strong>, 'The web app, after signing in', <C>Authorization: Bearer &lt;access_token&gt;</C>],
        ]}
      />
      <CodeBlock
        language="bash"
        code={`curl https://api.your-voicecon-host.com/api/v1/agents \\
  -H "Authorization: Bearer $VOICECON_API_KEY"`}
      />
      <P>
        API key scopes and their ceiling are covered in{' '}
        <A href="/docs/workspace/api-keys">API Keys</A>.
      </P>

      <H2 id="conventions">Conventions</H2>
      <UL>
        <LI>Requests and responses are JSON. Send <C>Content-Type: application/json</C> on writes.</LI>
        <LI>Identifiers are UUIDs.</LI>
        <LI>Timestamps are ISO 8601 in UTC.</LI>
        <LI>Partial updates use <C>PATCH</C>; only the fields you send are changed.</LI>
        <LI>List endpoints accept <C>skip</C> and <C>limit</C>, and return a total alongside the items.</LI>
        <LI>Successful deletes return <C>204 No Content</C>.</LI>
        <LI>Everything is scoped to the workspace the credential belongs to.</LI>
      </UL>

      <H2 id="agents-endpoints">Agents</H2>
      <Table
        headers={['Method', 'Path', 'Does']}
        widths={['w-[12%]', 'w-[40%]']}
        rows={[
          [<M>GET</M>, <C>/agents</C>, 'List agents.'],
          [<M>POST</M>, <C>/agents</C>, 'Create an agent.'],
          [<M>GET</M>, <C>/agents/stats</C>, 'Aggregate agent statistics.'],
          [<M>GET</M>, <C>/agents/{'{id}'}</C>, 'Fetch one agent.'],
          [<M>PATCH</M>, <C>/agents/{'{id}'}</C>, 'Update an agent.'],
          [<M>DELETE</M>, <C>/agents/{'{id}'}</C>, 'Delete an agent.'],
          [<M>POST</M>, <C>/agents/{'{id}'}/clone</C>, 'Clone an agent with its full configuration.'],
          [<M>POST</M>, <C>/agents/{'{id}'}/test</C>, 'Run a test interaction.'],
          [<M>POST</M>, <C>/agents/{'{id}'}/respond</C>, 'Get a single reply for a given input.'],
          [<M>POST</M>, <C>/agents/{'{id}'}/speak</C>, 'Synthesise speech in the agent’s voice.'],
          [<M>POST</M>, <C>/agents/{'{id}'}/transcribe</C>, 'Transcribe audio with the agent’s transcriber.'],
          [<M>GET</M>, <C>/agents/{'{id}'}/functions</C>, 'List the agent’s functions.'],
          [<M>POST</M>, <C>/agents/{'{id}'}/functions</C>, 'Add a function.'],
          [<M>GET</M>, <C>/agents/templates/list</C>, 'List available agent templates.'],
        ]}
      />

      <H2 id="calls-endpoints">Calls</H2>
      <Table
        headers={['Method', 'Path', 'Does']}
        widths={['w-[12%]', 'w-[40%]']}
        rows={[
          [<M>GET</M>, <C>/calls</C>, 'List calls, filterable by status, agent, and date.'],
          [<M>POST</M>, <C>/calls</C>, 'Place an outbound call.'],
          [<M>GET</M>, <C>/calls/stats</C>, 'Aggregate call statistics.'],
          [<M>GET</M>, <C>/calls/{'{id}'}</C>, 'Fetch a call with transcript, summary, and analysis.'],
          [<M>DELETE</M>, <C>/calls/{'{id}'}</C>, 'Delete a call record.'],
          [<M>GET</M>, <C>/calls/contacts</C>, 'List contacts derived from call history.'],
          [<M>GET</M>, <C>/calls/contacts/{'{number}'}/calls</C>, 'Every call with one number.'],
        ]}
      />
      <CodeBlock
        language="Placing an outbound call"
        code={`curl -X POST https://api.your-voicecon-host.com/api/v1/calls \\
  -H "Authorization: Bearer $VOICECON_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "agent_id":    "b6f1c2d3-…",
    "direction":   "outbound",
    "from_number": "+14155550123",
    "to_number":   "+14155559876"
  }'`}
      />

      <H2 id="workflows-endpoints">Workflows</H2>
      <Table
        headers={['Method', 'Path', 'Does']}
        widths={['w-[12%]', 'w-[44%]']}
        rows={[
          [<M>GET</M>, <C>/workflows</C>, 'List workflows.'],
          [<M>POST</M>, <C>/workflows</C>, 'Create a workflow.'],
          [<M>GET</M>, <C>/workflows/{'{id}'}</C>, 'Fetch a workflow, including its graph.'],
          [<M>PATCH</M>, <C>/workflows/{'{id}'}</C>, 'Update a workflow.'],
          [<M>DELETE</M>, <C>/workflows/{'{id}'}</C>, 'Delete a workflow.'],
          [<M>POST</M>, <C>/workflows/{'{id}'}/execute</C>, 'Run a workflow with trigger data.'],
          [<M>POST</M>, <C>/workflows/{'{id}'}/validate</C>, 'Validate the graph without running it.'],
          [<M>GET</M>, <C>/workflows/{'{id}'}/executions</C>, 'List execution history.'],
          [<M>GET</M>, <C>/workflows/{'{id}'}/executions/{'{eid}'}</C>, 'Fetch one execution with per-node results.'],
          [<M>GET</M>, <C>/workflows/{'{id}'}/stats</C>, 'Execution statistics.'],
          [<M>POST</M>, <C>/workflows/{'{id}'}/test-trigger</C>, 'Fire the trigger with sample data.'],
          [<M>POST</M>, <C>/workflows/trigger/voice-event</C>, 'Dispatch a call event to matching workflows.'],
          [<M>POST</M>, <C>/workflows/trigger/integration-event</C>, 'Dispatch an integration event.'],
        ]}
      />
      <Callout kind="note" title="Executing an inactive workflow is refused">
        A workflow that is switched off returns <C>409 Conflict</C> rather than a generic
        error — nothing is broken, and retrying without activating it will never succeed.
      </Callout>

      <H2 id="tools-endpoints">Tools</H2>
      <Table
        headers={['Method', 'Path', 'Does']}
        widths={['w-[12%]', 'w-[44%]']}
        rows={[
          [<M>GET</M>, <C>/tools</C>, 'List tools.'],
          [<M>POST</M>, <C>/tools</C>, 'Create a tool.'],
          [<M>GET</M>, <C>/tools/{'{id}'}</C>, 'Fetch a tool.'],
          [<M>PATCH</M>, <C>/tools/{'{id}'}</C>, 'Update a tool.'],
          [<M>DELETE</M>, <C>/tools/{'{id}'}</C>, 'Delete a tool.'],
          [<M>POST</M>, <C>/tools/{'{id}'}/test</C>, 'Run a tool with supplied parameters.'],
          [<M>GET</M>, <C>/tools/agents/{'{aid}'}/tools</C>, 'List an agent’s assigned tools.'],
          [<M>POST</M>, <C>/tools/agents/{'{aid}'}/tools/{'{tid}'}</C>, 'Assign a tool to an agent.'],
          [<M>DELETE</M>, <C>/tools/agents/{'{aid}'}/tools/{'{tid}'}</C>, 'Unassign a tool.'],
        ]}
      />

      <H2 id="knowledge-endpoints">Knowledge base</H2>
      <Table
        headers={['Method', 'Path', 'Does']}
        widths={['w-[12%]', 'w-[46%]']}
        rows={[
          [<M>GET</M>, <C>/knowledge/knowledge-bases</C>, 'List knowledge bases.'],
          [<M>POST</M>, <C>/knowledge/knowledge-bases</C>, 'Create one.'],
          [<M>GET</M>, <C>/knowledge/knowledge-bases/{'{id}'}</C>, 'Fetch one.'],
          [<M>DELETE</M>, <C>/knowledge/knowledge-bases/{'{id}'}</C>, 'Delete one.'],
          [<M>GET</M>, <C>/knowledge/knowledge-bases/{'{id}'}/documents</C>, 'List its documents.'],
          [<M>POST</M>, <C>/knowledge/documents</C>, 'Add a document from text or a URL.'],
          [<M>POST</M>, <C>/knowledge/documents/upload</C>, 'Upload a file.'],
          [<M>GET</M>, <C>/knowledge/documents/{'{id}'}/download</C>, 'Download the original.'],
          [<M>DELETE</M>, <C>/knowledge/documents/{'{id}'}</C>, 'Delete a document and its chunks.'],
          [<M>POST</M>, <C>/knowledge/search</C>, 'Semantic search, returning chunks and scores.'],
          [<M>POST</M>, <C>/knowledge/ask</C>, 'Search and answer in one call.'],
          [<M>GET</M>, <C>/knowledge/agents/{'{aid}'}/knowledge-bases</C>, 'List an agent’s links.'],
          [<M>PUT</M>, <C>/knowledge/agents/{'{aid}'}/knowledge-bases</C>, 'Replace an agent’s links.'],
        ]}
      />

      <H2 id="integrations-endpoints">Integrations</H2>
      <Table
        headers={['Method', 'Path', 'Does']}
        widths={['w-[12%]', 'w-[46%]']}
        rows={[
          [<M>GET</M>, <C>/integrations/connectors</C>, 'List available connectors.'],
          [<M>GET</M>, <C>/integrations/connections</C>, 'List your connections.'],
          [<M>POST</M>, <C>/integrations/connections</C>, 'Create a connection.'],
          [<M>PATCH</M>, <C>/integrations/connections/{'{id}'}</C>, 'Update a connection.'],
          [<M>DELETE</M>, <C>/integrations/connections/{'{id}'}</C>, 'Delete a connection.'],
          [<M>POST</M>, <C>/integrations/connections/{'{id}'}/test</C>, 'Test connectivity.'],
          [<M>GET</M>, <C>/integrations/connections/{'{id}'}/actions</C>, 'List actions with their schemas.'],
          [<M>GET</M>, <C>/integrations/connections/{'{id}'}/resources/{'{kind}'}</C>, 'List pickable resources.'],
          [<M>GET</M>, <C>/integrations/connections/{'{id}'}/defaults</C>, 'Read connection defaults.'],
          [<M>PUT</M>, <C>/integrations/connections/{'{id}'}/defaults</C>, 'Set connection defaults.'],
          [<M>POST</M>, <C>/integrations/oauth/authorize</C>, 'Begin an OAuth flow.'],
          [<M>POST</M>, <C>/integrations/oauth/callback</C>, 'Complete an OAuth flow.'],
          [<M>GET</M>, <C>/integrations/available-for-tools</C>, 'Connections usable as AI tools.'],
        ]}
      />

      <H2 id="phone-endpoints">Phone numbers</H2>
      <Table
        headers={['Method', 'Path', 'Does']}
        widths={['w-[12%]', 'w-[40%]']}
        rows={[
          [<M>GET</M>, <C>/phone-numbers</C>, 'List your numbers.'],
          [<M>GET</M>, <C>/phone-numbers/providers</C>, 'List connected carriers.'],
          [<M>GET</M>, <C>/phone-numbers/search</C>, 'Search carrier inventory.'],
          [<M>POST</M>, <C>/phone-numbers/provision</C>, 'Buy a number.'],
          [<M>GET</M>, <C>/phone-numbers/{'{id}'}</C>, 'Fetch one number.'],
          [<M>PATCH</M>, <C>/phone-numbers/{'{id}'}</C>, 'Update assignment and configuration.'],
          [<M>DELETE</M>, <C>/phone-numbers/{'{id}'}</C>, 'Release a number.'],
        ]}
      />

      <H2 id="errors">Errors</H2>
      <Table
        headers={['Status', 'Means', 'Do']}
        widths={['w-[12%]', 'w-[34%]']}
        rows={[
          [<C>400</C>, 'Malformed request.', 'Check the payload shape.'],
          [<C>401</C>, 'Missing or invalid credentials.', 'Check the Authorization header.'],
          [<C>403</C>, 'Authenticated, but not permitted.', 'Check the key’s scopes and the creator’s role.'],
          [<C>404</C>, 'Not found, or not in this workspace.', 'Check the id and the workspace.'],
          [<C>409</C>, 'Conflicts with current state.', 'E.g. executing an inactive workflow — change the state first.'],
          [<C>422</C>, 'Validation failed.', 'The body names the offending fields.'],
          [<C>429</C>, 'Rate limited.', 'Back off and retry.'],
          [<C>5xx</C>, 'Server error.', 'Retry with backoff; if it persists, contact support.'],
        ]}
      />
      <CodeBlock
        language="Error shape"
        code={`{
  "detail": "Workflow is not active and cannot be executed."
}`}
      />
      <Callout kind="tip" title="Distinguish 403 from 404">
        A <C>404</C> on an id you know exists usually means it belongs to a different
        workspace — every credential is scoped to one. A <C>403</C> means you found it but may
        not touch it.
      </Callout>
    </DocPage>
  )
}
