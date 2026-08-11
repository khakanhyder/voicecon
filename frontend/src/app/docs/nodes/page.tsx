import { DocPage, docMetadata } from '@/components/docs/DocPage'
import {
  A, Badge, C, Callout, H2, H3, LI, P, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/nodes')

export default function NodesPage() {
  return (
    <DocPage href="/docs/nodes">
      <H2 id="categories">The four categories</H2>
      <P>
        The palette groups nodes by what they do. The grouping is not cosmetic — it tells you
        whether a node needs a caller on the line.
      </P>

      <Table
        headers={['Category', 'Nodes', 'Needs a live call?']}
        widths={['w-[20%]', 'w-[46%]']}
        rows={[
          [
            <Badge tone="blue">Conversation</Badge>,
            'Speak, Ask Question, Transfer Call, End Call',
            'Yes',
          ],
          [
            <Badge tone="amber">Logic</Badge>,
            'Branch, Switch, Filter, Merge, Loop Over Items, Set Fields, Code, Wait',
            'No',
          ],
          [
            <Badge tone="violet">Actions</Badge>,
            'Run Tool, Webhook, Integration',
            'No',
          ],
          [
            <Badge tone="brand">AI</Badge>,
            'AI Response',
            'No',
          ],
        ]}
      />

      <Callout kind="warning" title="Conversation nodes need somebody listening">
        Speak, Ask, Transfer, and End Call only make sense in a workflow invoked during a live
        call — that is, through a <A href="/docs/tools/workflow">workflow tool</A>. Put them
        in a scheduled workflow and there is nobody on the other end.
      </Callout>

      <H2 id="quick-reference">Quick reference table</H2>
      <P>Every node type, its outputs, and where its full documentation lives.</P>

      <Table
        headers={['Node', 'Does', 'Outputs']}
        widths={['w-[20%]', 'w-[48%]']}
        rows={[
          [<A href="/docs/nodes/trigger">Trigger</A>, 'Starts the workflow; declares its inputs', <C>out</C>],
          [<A href="/docs/nodes/conversation#speak">Speak</A>, 'Says something to the caller', <C>out</C>],
          [<A href="/docs/nodes/conversation#ask">Ask Question</A>, 'Asks, and captures the answer into a variable', <C>out</C>],
          [<A href="/docs/nodes/conversation#transfer">Transfer Call</A>, 'Hands the call to a number or SIP address', <em>none — terminal</em>],
          [<A href="/docs/nodes/conversation#end">End Call</A>, 'Says goodbye and hangs up', <em>none — terminal</em>],
          [<A href="/docs/nodes/logic#condition">Branch</A>, 'Splits on one condition', <><C>true</C>, <C>false</C></>],
          [<A href="/docs/nodes/logic#switch">Switch</A>, 'Routes to the first matching rule', <>one per rule, plus <C>else</C></>],
          [<A href="/docs/nodes/logic#filter">Filter</A>, 'Continues only when a condition holds', <C>out</C>],
          [<A href="/docs/nodes/logic#merge">Merge</A>, 'Joins parallel branches back together', <C>out</C>],
          [<A href="/docs/nodes/logic#loop">Loop Over Items</A>, 'Runs a body once per item in a list', <><C>loop</C>, <C>done</C></>],
          [<A href="/docs/nodes/logic#transform">Set Fields</A>, 'Builds named values for later steps', <C>out</C>],
          [<A href="/docs/nodes/logic#code">Code</A>, 'Runs a Python or JavaScript snippet', <C>out</C>],
          [<A href="/docs/nodes/logic#delay">Wait</A>, 'Pauses before continuing', <C>out</C>],
          [<A href="/docs/nodes/actions#tool">Run Tool</A>, 'Executes a configured tool', <C>out</C>],
          [<A href="/docs/nodes/actions#webhook">Webhook</A>, 'Calls an external HTTP endpoint', <C>out</C>],
          [<A href="/docs/nodes/actions#action">Integration</A>, 'Runs an action on a connected app', <C>out</C>],
          [<A href="/docs/nodes/ai">AI Response</A>, 'Generates a reply from context', <C>out</C>],
        ]}
      />

      <H2 id="anatomy">Anatomy of a node</H2>
      <P>Every node on the canvas shows the same four things.</P>
      <UL>
        <LI><Strong>Icon and accent colour</Strong> — its category, readable at a glance.</LI>
        <LI><Strong>Title</Strong> — the node type, or a name you gave it.</LI>
        <LI>
          <Strong>Summary line</Strong> — a one-line rendering of its configuration. A Speak
          node shows its message; a Branch shows <C>account_number equals 12345</C>. This is
          how you read a graph without opening every node.
        </LI>
        <LI>
          <Strong>Handles</Strong> — an input on the left, outputs on the right. Terminal nodes
          have no outputs; Switch grows one handle per rule as you add them.
        </LI>
      </UL>
      <Callout kind="tip" title="An unconfigured node says so">
        A node with nothing set summarises as &ldquo;No message set&rdquo;, &ldquo;No condition
        set&rdquo;, and so on. Scanning a graph for those phrases is the quickest way to find
        what you left half-finished.
      </Callout>

      <H2 id="common-fields">Field types you will meet</H2>
      <P>
        The inspector renders each field according to its type. Knowing the types explains why
        some fields behave differently from a plain text box.
      </P>

      <Table
        headers={['Field type', 'Behaviour']}
        widths={['w-[24%]']}
        rows={[
          [<Strong>Text / Textarea</Strong>, <>Free text. Accepts <C>{'{{references}}'}</C>.</>],
          [<Strong>Number</Strong>, 'Numeric input, usually with a sensible default already filled.'],
          [<Strong>Select</Strong>, 'A fixed list of options.'],
          [<Strong>JSON</Strong>, <>A JSON object. References inside are resolved with types preserved — see <A href="/docs/workflows/variables#type-preservation">Type preservation</A>.</>],
          [<Strong>Code</Strong>, 'A syntax-highlighted editor, highlighting by the sibling language field.'],
          [<Strong>Connection</Strong>, 'Picks one of your connected integrations.'],
          [<Strong>Connection action</Strong>, 'Picks an action on the chosen connection. Populated after a connection is selected.'],
          [<Strong>Action parameters</Strong>, 'Rendered from the action’s own schema — resource pickers where the connector offers one, expression inputs elsewhere.'],
          [<Strong>Key / value</Strong>, 'An editable list of name-to-value assignments.'],
          [<Strong>Rules</Strong>, 'The ordered rule list that grows a Switch node’s output handles.'],
          [<Strong>Inputs</Strong>, 'Declares the workflow’s parameters. Only on the Trigger node.'],
        ]}
      />

      <H3>Fields that appear and disappear</H3>
      <P>
        Some fields are conditional. Choose <C>is empty</C> as a Branch operator and the value
        field vanishes, because there is nothing to compare against. Choose <C>GET</C> on a
        Webhook and the body field vanishes for the same reason. This is intentional — the
        inspector only shows fields that can affect the outcome.
      </P>
    </DocPage>
  )
}
