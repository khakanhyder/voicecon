import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { CodeBlock } from '@/components/docs/CodeBlock'
import {
  A, C, Callout, H2, H3, LI, Meta, P, ParamTable, RefHeader, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/nodes/actions')

export default function ActionNodesPage() {
  return (
    <DocPage href="/docs/nodes/actions">
      <P>
        Action nodes reach outside the workflow. All three are retryable, because failures
        against the outside world are often transient.
      </P>

      <RefHeader id="tool" name="Run Tool" chip="Actions" tone="violet">
        Executes a tool you have already configured under <Strong>Tools</Strong>.
      </RefHeader>
      <Meta label="Outputs"><C>out</C></Meta>

      <ParamTable
        params={[
          {
            name: 'tool_id',
            type: 'string',
            required: true,
            description: (
              <>
                The tool to run. Find ids in the <Strong>Tools</Strong> section — they look
                like <C>tool_xxxxxxxx</C>.
              </>
            ),
          },
          {
            name: 'parameters',
            type: 'JSON',
            default: '{}',
            description: (
              <>
                The arguments passed to the tool. Keys must match the tool&rsquo;s declared
                parameters. Values may be references.
              </>
            ),
          },
        ]}
      />

      <CodeBlock
        language="Parameters as JSON"
        code={`{
  "customer_name": "{{caller_name}}",
  "amount":        {{trigger.order_total}},
  "is_priority":   {{is_urgent}}
}

// "customer_name" is a mixed template → string.
// The other two are whole-value → they keep their real types.`}
      />

      <Callout kind="note" title="Same tool, two callers">
        A tool assigned to an agent is invoked by the model when it judges the moment right.
        The same tool run from this node is invoked because <em>you</em> put it in the graph.
        Configure it once; both paths use it.
      </Callout>

      <RefHeader id="webhook" name="Webhook" chip="Actions" tone="violet">
        Calls any HTTP endpoint and makes the response available to later steps.
      </RefHeader>
      <Meta label="Outputs"><C>out</C></Meta>

      <ParamTable
        params={[
          {
            name: 'url',
            type: 'string',
            required: true,
            description: (
              <>
                The endpoint. May contain references —{' '}
                <C>https://api.example.com/orders/{'{{order_id}}'}</C>.
              </>
            ),
          },
          {
            name: 'method',
            type: 'enum',
            default: 'POST',
            description: <><C>GET</C>, <C>POST</C>, <C>PUT</C>, <C>PATCH</C>, or <C>DELETE</C>.</>,
          },
          {
            name: 'headers',
            type: 'JSON',
            default: '{}',
            description: (
              <>
                Request headers. Authorization, content type, anything the endpoint requires.
              </>
            ),
          },
          {
            name: 'body',
            type: 'JSON',
            default: '{}',
            description: (
              <>
                The request body. Hidden when the method is <C>GET</C>, which has none.
                References inside keep their JSON types.
              </>
            ),
          },
        ]}
      />

      <H3>Reading the response</H3>
      <P>
        The response is stored under the node&rsquo;s id, so later steps can reach into it.
      </P>
      <CodeBlock
        language="Reaching into a response"
        code={`Node id: n_7fa21b30
Response: { "status": "ok", "results": [ { "id": 12, "email": "ada@example.com" } ] }

{{steps.n_7fa21b30.status}}              → "ok"
{{steps.n_7fa21b30.results[0].email}}    → "ada@example.com"
{{steps.n_7fa21b30.results[0].id}}       → 12   (a number, not "12")`}
      />

      <Callout kind="tip" title="Shorten it immediately">
        Those paths are brittle and unreadable. Follow a Webhook with a{' '}
        <A href="/docs/nodes/logic#transform">Set Fields</A> node that lifts the two or three
        values you actually need into short names, and use those from then on.
      </Callout>

      <Callout kind="warning" title="Secrets in headers">
        A token typed into the headers field is stored in the workflow definition and visible
        to anyone who can open the builder. Where the destination is a supported app, use an{' '}
        <A href="#action">Integration</A> node instead — its credentials are encrypted and
        held outside the graph.
      </Callout>

      <RefHeader id="action" name="Integration" chip="Actions" tone="violet">
        Runs a named action on one of your connected apps.
      </RefHeader>
      <Meta label="Outputs"><C>out</C></Meta>

      <ParamTable
        params={[
          {
            name: 'connection_id',
            type: 'connection',
            required: true,
            description: (
              <>
                Which connected account to act on. Connect apps under{' '}
                <A href="/docs/integrations">Integrations</A> first — the picker only lists
                connections that already exist.
              </>
            ),
          },
          {
            name: 'action',
            type: 'connection action',
            required: true,
            description: (
              <>
                What to do — <C>create_contact</C>, <C>send_message</C>,{' '}
                <C>create_event</C>. The list is populated from the chosen connection.
              </>
            ),
          },
          {
            name: 'parameters',
            type: 'action parameters',
            default: '{}',
            description: (
              <>
                Rendered from the action&rsquo;s own schema. Fields the connector marks as
                resources get a picker; everything else takes an expression.
              </>
            ),
          },
        ]}
      />

      <H3>Resource pickers</H3>
      <P>
        Some parameters point at something inside the connected account — a Slack channel, a
        Trello list, a Google calendar. Rather than making you find an opaque id, those fields
        render a picker that loads the real options from the connection.
      </P>
      <P>
        Most pickers also accept a pasted URL and extract the id from it, which is usually
        faster than scrolling a list. See{' '}
        <A href="/docs/integrations#resource-pickers">Resource pickers</A>.
      </P>

      <H3>Connection defaults</H3>
      <P>
        A connection can carry defaults — the channel to post to, the list to add cards to.
        Leave the corresponding field blank and the default applies, so you can change the
        destination in one place instead of editing every workflow. See{' '}
        <A href="/docs/integrations#connection-defaults">Connection defaults</A>.
      </P>

      <H2 id="choosing">Choosing between them</H2>
      <Table
        headers={['Use', 'When', 'Why']}
        widths={['w-[20%]', 'w-[40%]']}
        rows={[
          [
            <Strong>Integration</Strong>,
            'The destination is a supported app',
            'Credentials handled for you, parameters validated against a real schema, resource pickers, rate limiting, and logged calls.',
          ],
          [
            <Strong>Webhook</Strong>,
            'Your own API, or an app with no connector',
            'Total control over method, headers, and body — at the cost of managing auth yourself.',
          ],
          [
            <Strong>Run Tool</Strong>,
            'The logic already exists as a tool',
            'One definition serving both the agent and the workflow. Change it once.',
          ],
        ]}
      />

      <UL>
        <LI>
          Check the <A href="/docs/integrations/catalog">catalog</A> before reaching for
          Webhook — an Integration node is less work and considerably more robust.
        </LI>
        <LI>
          If you find yourself building the same Webhook in several workflows, promote it to a{' '}
          <A href="/docs/tools/integration#custom-tool">custom tool</A> and use Run Tool.
        </LI>
      </UL>
    </DocPage>
  )
}
