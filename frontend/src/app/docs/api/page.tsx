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
          [<Strong key="c0">API key</Strong>, 'Servers, scripts, integrations', <C key="c1">Authorization: Bearer &lt;key&gt;</C>],
          [<Strong key="c0">JWT</Strong>, 'The web app, after signing in', <C key="c1">Authorization: Bearer &lt;access_token&gt;</C>],
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
          [<M key="c0">GET</M>, <C key="c1">/agents</C>, 'List agents.'],
          [<M key="c0">POST</M>, <C key="c1">/agents</C>, 'Create an agent.'],
          [<M key="c0">GET</M>, <C key="c1">/agents/stats</C>, 'Aggregate agent statistics.'],
          [<M key="c0">GET</M>, <C key="c1">/agents/{'{id}'}</C>, 'Fetch one agent.'],
          [<M key="c0">PATCH</M>, <C key="c1">/agents/{'{id}'}</C>, 'Update an agent.'],
          [<M key="c0">DELETE</M>, <C key="c1">/agents/{'{id}'}</C>, 'Delete an agent.'],
          [<M key="c0">POST</M>, <C key="c1">/agents/{'{id}'}/clone</C>, 'Clone an agent with its full configuration.'],
          [<M key="c0">POST</M>, <C key="c1">/agents/{'{id}'}/test</C>, 'Run a test interaction.'],
          [<M key="c0">POST</M>, <C key="c1">/agents/{'{id}'}/respond</C>, 'Get a single reply for a given input.'],
          [<M key="c0">POST</M>, <C key="c1">/agents/{'{id}'}/speak</C>, 'Synthesise speech in the agent’s voice.'],
          [<M key="c0">POST</M>, <C key="c1">/agents/{'{id}'}/transcribe</C>, 'Transcribe audio with the agent’s transcriber.'],
          [<M key="c0">GET</M>, <C key="c1">/agents/{'{id}'}/functions</C>, 'List the agent’s functions.'],
          [<M key="c0">POST</M>, <C key="c1">/agents/{'{id}'}/functions</C>, 'Add a function.'],
          [<M key="c0">GET</M>, <C key="c1">/agents/templates/list</C>, 'List available agent templates.'],
        ]}
      />

      <H2 id="calls-endpoints">Calls</H2>
      <Table
        headers={['Method', 'Path', 'Does']}
        widths={['w-[12%]', 'w-[40%]']}
        rows={[
          [<M key="c0">GET</M>, <C key="c1">/calls</C>, 'List calls, filterable by status, agent, and date.'],
          [<M key="c0">POST</M>, <C key="c1">/calls</C>, 'Place an outbound call.'],
          [<M key="c0">GET</M>, <C key="c1">/calls/stats</C>, 'Aggregate call statistics.'],
          [<M key="c0">GET</M>, <C key="c1">/calls/{'{id}'}</C>, 'Fetch a call with transcript, summary, and analysis.'],
          [<M key="c0">DELETE</M>, <C key="c1">/calls/{'{id}'}</C>, 'Delete a call record.'],
          [<M key="c0">GET</M>, <C key="c1">/calls/contacts</C>, 'List contacts derived from call history.'],
          [<M key="c0">GET</M>, <C key="c1">/calls/contacts/{'{number}'}/calls</C>, 'Every call with one number.'],
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
          [<M key="c0">GET</M>, <C key="c1">/workflows</C>, 'List workflows.'],
          [<M key="c0">POST</M>, <C key="c1">/workflows</C>, 'Create a workflow.'],
          [<M key="c0">GET</M>, <C key="c1">/workflows/{'{id}'}</C>, 'Fetch a workflow, including its graph.'],
          [<M key="c0">PATCH</M>, <C key="c1">/workflows/{'{id}'}</C>, 'Update a workflow.'],
          [<M key="c0">DELETE</M>, <C key="c1">/workflows/{'{id}'}</C>, 'Delete a workflow.'],
          [<M key="c0">POST</M>, <C key="c1">/workflows/{'{id}'}/execute</C>, 'Run a workflow with trigger data.'],
          [<M key="c0">POST</M>, <C key="c1">/workflows/{'{id}'}/validate</C>, 'Validate the graph without running it.'],
          [<M key="c0">GET</M>, <C key="c1">/workflows/{'{id}'}/executions</C>, 'List execution history.'],
          [<M key="c0">GET</M>, <C key="c1">/workflows/{'{id}'}/executions/{'{eid}'}</C>, 'Fetch one execution with per-node results.'],
          [<M key="c0">GET</M>, <C key="c1">/workflows/{'{id}'}/stats</C>, 'Execution statistics.'],
          [<M key="c0">POST</M>, <C key="c1">/workflows/{'{id}'}/test-trigger</C>, 'Fire the trigger with sample data.'],
          [<M key="c0">POST</M>, <C key="c1">/workflows/trigger/voice-event</C>, 'Dispatch a call event to matching workflows.'],
          [<M key="c0">POST</M>, <C key="c1">/workflows/trigger/integration-event</C>, 'Dispatch an integration event.'],
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
          [<M key="c0">GET</M>, <C key="c1">/tools</C>, 'List tools.'],
          [<M key="c0">POST</M>, <C key="c1">/tools</C>, 'Create a tool.'],
          [<M key="c0">GET</M>, <C key="c1">/tools/{'{id}'}</C>, 'Fetch a tool.'],
          [<M key="c0">PATCH</M>, <C key="c1">/tools/{'{id}'}</C>, 'Update a tool.'],
          [<M key="c0">DELETE</M>, <C key="c1">/tools/{'{id}'}</C>, 'Delete a tool.'],
          [<M key="c0">POST</M>, <C key="c1">/tools/{'{id}'}/test</C>, 'Run a tool with supplied parameters.'],
          [<M key="c0">GET</M>, <C key="c1">/tools/agents/{'{aid}'}/tools</C>, 'List an agent’s assigned tools.'],
          [<M key="c0">POST</M>, <C key="c1">/tools/agents/{'{aid}'}/tools/{'{tid}'}</C>, 'Assign a tool to an agent.'],
          [<M key="c0">DELETE</M>, <C key="c1">/tools/agents/{'{aid}'}/tools/{'{tid}'}</C>, 'Unassign a tool.'],
        ]}
      />

      <H2 id="knowledge-endpoints">Knowledge base</H2>
      <Table
        headers={['Method', 'Path', 'Does']}
        widths={['w-[12%]', 'w-[46%]']}
        rows={[
          [<M key="c0">GET</M>, <C key="c1">/knowledge/knowledge-bases</C>, 'List knowledge bases.'],
          [<M key="c0">POST</M>, <C key="c1">/knowledge/knowledge-bases</C>, 'Create one.'],
          [<M key="c0">GET</M>, <C key="c1">/knowledge/knowledge-bases/{'{id}'}</C>, 'Fetch one.'],
          [<M key="c0">DELETE</M>, <C key="c1">/knowledge/knowledge-bases/{'{id}'}</C>, 'Delete one.'],
          [<M key="c0">GET</M>, <C key="c1">/knowledge/knowledge-bases/{'{id}'}/documents</C>, 'List its documents.'],
          [<M key="c0">POST</M>, <C key="c1">/knowledge/documents</C>, 'Add a document from text or a URL.'],
          [<M key="c0">POST</M>, <C key="c1">/knowledge/documents/upload</C>, 'Upload a file.'],
          [<M key="c0">GET</M>, <C key="c1">/knowledge/documents/{'{id}'}/download</C>, 'Download the original.'],
          [<M key="c0">DELETE</M>, <C key="c1">/knowledge/documents/{'{id}'}</C>, 'Delete a document and its chunks.'],
          [<M key="c0">POST</M>, <C key="c1">/knowledge/search</C>, 'Semantic search, returning chunks and scores.'],
          [<M key="c0">POST</M>, <C key="c1">/knowledge/ask</C>, 'Search and answer in one call.'],
          [<M key="c0">GET</M>, <C key="c1">/knowledge/agents/{'{aid}'}/knowledge-bases</C>, 'List an agent’s links.'],
          [<M key="c0">PUT</M>, <C key="c1">/knowledge/agents/{'{aid}'}/knowledge-bases</C>, 'Replace an agent’s links.'],
        ]}
      />

      <H2 id="integrations-endpoints">Integrations</H2>
      <Table
        headers={['Method', 'Path', 'Does']}
        widths={['w-[12%]', 'w-[46%]']}
        rows={[
          [<M key="c0">GET</M>, <C key="c1">/integrations/connectors</C>, 'List available connectors.'],
          [<M key="c0">GET</M>, <C key="c1">/integrations/connections</C>, 'List your connections.'],
          [<M key="c0">POST</M>, <C key="c1">/integrations/connections</C>, 'Create a connection.'],
          [<M key="c0">PATCH</M>, <C key="c1">/integrations/connections/{'{id}'}</C>, 'Update a connection.'],
          [<M key="c0">DELETE</M>, <C key="c1">/integrations/connections/{'{id}'}</C>, 'Delete a connection.'],
          [<M key="c0">POST</M>, <C key="c1">/integrations/connections/{'{id}'}/test</C>, 'Test connectivity.'],
          [<M key="c0">GET</M>, <C key="c1">/integrations/connections/{'{id}'}/actions</C>, 'List actions with their schemas.'],
          [<M key="c0">GET</M>, <C key="c1">/integrations/connections/{'{id}'}/resources/{'{kind}'}</C>, 'List pickable resources.'],
          [<M key="c0">GET</M>, <C key="c1">/integrations/connections/{'{id}'}/defaults</C>, 'Read connection defaults.'],
          [<M key="c0">PUT</M>, <C key="c1">/integrations/connections/{'{id}'}/defaults</C>, 'Set connection defaults.'],
          [<M key="c0">POST</M>, <C key="c1">/integrations/oauth/authorize</C>, 'Begin an OAuth flow.'],
          [<M key="c0">POST</M>, <C key="c1">/integrations/oauth/callback</C>, 'Complete an OAuth flow.'],
          [<M key="c0">GET</M>, <C key="c1">/integrations/available-for-tools</C>, 'Connections usable as AI tools.'],
        ]}
      />

      <H2 id="phone-endpoints">Phone numbers</H2>
      <Table
        headers={['Method', 'Path', 'Does']}
        widths={['w-[12%]', 'w-[40%]']}
        rows={[
          [<M key="c0">GET</M>, <C key="c1">/phone-numbers</C>, 'List your numbers.'],
          [<M key="c0">GET</M>, <C key="c1">/phone-numbers/providers</C>, 'List connected carriers.'],
          [<M key="c0">GET</M>, <C key="c1">/phone-numbers/search</C>, 'Search carrier inventory.'],
          [<M key="c0">POST</M>, <C key="c1">/phone-numbers/provision</C>, 'Buy a number.'],
          [<M key="c0">GET</M>, <C key="c1">/phone-numbers/{'{id}'}</C>, 'Fetch one number.'],
          [<M key="c0">PATCH</M>, <C key="c1">/phone-numbers/{'{id}'}</C>, 'Update assignment and configuration.'],
          [<M key="c0">DELETE</M>, <C key="c1">/phone-numbers/{'{id}'}</C>, 'Release a number.'],
        ]}
      />

      <H2 id="errors">Errors</H2>
      <Table
        headers={['Status', 'Means', 'Do']}
        widths={['w-[12%]', 'w-[34%]']}
        rows={[
          [<C key="c0">400</C>, 'Malformed request.', 'Check the payload shape.'],
          [<C key="c0">401</C>, 'Missing or invalid credentials.', 'Check the Authorization header.'],
          [<C key="c0">403</C>, 'Authenticated, but not permitted.', 'Check the key’s scopes and the creator’s role.'],
          [<C key="c0">404</C>, 'Not found, or not in this workspace.', 'Check the id and the workspace.'],
          [<C key="c0">409</C>, 'Conflicts with current state.', 'E.g. executing an inactive workflow — change the state first.'],
          [<C key="c0">422</C>, 'Validation failed.', 'The body names the offending fields.'],
          [<C key="c0">429</C>, 'Rate limited.', 'Back off and retry.'],
          [<C key="c0">5xx</C>, 'Server error.', 'Retry with backoff; if it persists, contact support.'],
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
