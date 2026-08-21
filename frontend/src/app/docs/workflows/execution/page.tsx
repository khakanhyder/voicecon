import { DocPage, docMetadata } from '@/components/docs/DocPage'
import {
  A, C, Callout, H2, H3, LI, P, ParamTable, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/workflows/execution')

export default function ExecutionPage() {
  return (
    <DocPage href="/docs/workflows/execution">
      <H2 id="test-run">Running a test</H2>
      <P>
        <Strong>Run</Strong> in the builder saves the graph and then executes it, streaming
        results back node by node. Each node lights up as it starts, then settles into success
        or failure, so you watch the path the run actually took.
      </P>
      <UL>
        <LI>Nodes that ran show their output in the execution panel.</LI>
        <LI>Nodes that were skipped — the untaken side of a branch — stay dim.</LI>
        <LI>A failed node shows its error, and you can jump straight to it on the canvas.</LI>
      </UL>
      <Callout kind="warning" title="A test run is a real run">
        Integration nodes genuinely write to your connected apps, and webhook nodes genuinely
        call your endpoints. Point tests at sandbox connections, or add a{' '}
        <A href="/docs/nodes/logic#filter">Filter</A> that stops the run before the
        destructive step while you are still iterating.
      </Callout>

      <H2 id="execution-model">The execution model</H2>
      <P>
        The engine walks the graph from the trigger, following whichever handles each node
        activates.
      </P>
      <UL>
        <LI>
          <Strong>Branching</Strong> — a Branch activates exactly one of <C>true</C> or{' '}
          <C>false</C>. Everything downstream of the other handle is skipped.
        </LI>
        <LI>
          <Strong>Parallelism</Strong> — several edges leaving one handle run concurrently, up
          to a concurrency limit. Independent work does not queue behind unrelated work.
        </LI>
        <LI>
          <Strong>Joining</Strong> — a <A href="/docs/nodes/logic#merge">Merge</A> waits for
          its incoming branches before continuing.
        </LI>
        <LI>
          <Strong>Results</Strong> — each node&rsquo;s output is stored under{' '}
          <C>steps.&lt;node_id&gt;</C> as soon as it finishes, so later nodes can read it.
        </LI>
        <LI>
          <Strong>Termination</Strong> — the run ends when no node has an unfollowed active
          handle, or when a terminal node (Transfer, End Call) is reached.
        </LI>
      </UL>

      <H2 id="error-handling">Error handling and retries</H2>
      <P>Workflow-level settings decide what a failing node does to the run.</P>

      <ParamTable
        params={[
          {
            name: 'error_handling',
            type: 'enum',
            default: 'continue',
            description: (
              <>
                <C>continue</C> marks the node failed and carries on down the graph;{' '}
                <C>stop</C> aborts the whole run. Use <C>stop</C> when later steps would act
                on data the failed step was supposed to produce.
              </>
            ),
          },
          {
            name: 'max_retries',
            type: 'number',
            default: '3',
            description: (
              <>
                How many times a retryable node is re-attempted before being marked failed.
              </>
            ),
          },
          {
            name: 'retry_delay',
            type: 'seconds',
            default: '60',
            description: 'Wait between attempts, giving a rate-limited or briefly-down service time to recover.',
          },
          {
            name: 'execution_mode',
            type: 'enum',
            default: 'async',
            description: (
              <>
                <C>async</C> returns immediately and runs in the background — right for
                scheduled and webhook work. <C>sync</C> holds the request until the run
                finishes, which is what a mid-call tool needs so the agent can speak the
                result.
              </>
            ),
          },
        ]}
      />

      <Callout kind="note" title="Only some nodes retry">
        Retries apply to nodes that call the outside world — Integration, Run Tool, and
        Webhook — where failure is often transient. Logic and conversation nodes are not
        retried: re-running a Branch would produce the identical result, and re-asking a
        caller a question they already answered is worse than failing.
      </Callout>

      <H3 id="sync-retry-cap">Retries are capped during a call</H3>
      <P>
        A <C>sync</C> run has somebody waiting on it — usually a caller, silent on the line —
        so the workflow&rsquo;s configured backoff is overridden while it runs that way.
      </P>
      <Table
        headers={['Setting', 'Async run', 'Sync run']}
        widths={['w-[28%]', 'w-[24%]']}
        rows={[
          [<C>max_retries</C>, 'As configured, up to 10', <>At most <Strong>1</Strong> retry</>],
          [<C>retry_delay</C>, 'As configured', <>At most <Strong>2 seconds</Strong></>],
        ]}
      />
      <P>
        This is why a mid-call workflow with <C>max_retries: 3</C> and <C>retry_delay: 60</C>{' '}
        does not pause for three minutes — it makes one extra attempt after two seconds and
        then reports the failure. Three minutes of dead air would end the call long before the
        third attempt.
      </P>
      <Callout kind="tip" title="Design the failure, do not wait it out">
        If a mid-call step can fail, give the graph somewhere to go: follow it with a{' '}
        <A href="/docs/nodes/logic#condition">Branch</A> on the result and a{' '}
        <A href="/docs/nodes/conversation#speak">Speak</A> node that says so honestly, or a{' '}
        <A href="/docs/nodes/conversation#transfer">Transfer</A> to a human. A caller told
        &ldquo;I can&rsquo;t reach that system right now, let me put you through&rdquo; has a
        far better call than one held in silence.
      </Callout>

      <H3 id="per-node-settings">Per-node overrides</H3>
      <P>
        The settings above are workflow-wide. A single node can override them through its{' '}
        <C>settings</C> object in the workflow definition — useful when one step talks to a
        service with different characteristics from the rest.
      </P>
      <Table
        headers={['Setting', 'Effect']}
        widths={['w-[32%]']}
        rows={[
          [
            <C>{'settings.on_error'}</C>,
            <>
              <C>continue</C> or <C>stop</C> for this node alone, overriding the
              workflow&rsquo;s <C>error_handling</C>.
            </>,
          ],
          [
            <C>{'settings.retry.enabled'}</C>,
            <>
              Turns retrying on for a node that would not normally retry, or off for one that
              would.
            </>,
          ],
          [<C>{'settings.retry.max_tries'}</C>, <>Retry count for this node.</>],
          [<C>{'settings.retry.delay_seconds'}</C>, <>Wait between this node&rsquo;s attempts.</>],
          [
            <C>{'settings.retry.backoff'}</C>,
            <>
              <C>fixed</C> (the default) waits the same each time; <C>exponential</C> doubles
              the wait on every attempt, which is kinder to a service that is already
              struggling.
            </>,
          ],
          [
            <C>{'settings.timeout_seconds'}</C>,
            <>
              Abandon this step if it has not finished in time. The step is marked failed —
              a timeout is not retried.
            </>,
          ],
        ]}
      />
      <Callout kind="note" title="These are definition-level, not builder fields">
        The inspector does not show them; set them on the node in the workflow definition
        through the <A href="/docs/api#workflows-endpoints">API</A>. The sync caps above still
        apply on top of whatever a node asks for.
      </Callout>

      <H2 id="execution-history">Execution history</H2>
      <P>
        Every run is recorded, whether it came from a test, a schedule, a webhook, or an
        agent&rsquo;s tool call. Open a workflow&rsquo;s <Strong>History</Strong> tab.
      </P>

      <Table
        headers={['Field', 'What it tells you']}
        widths={['w-[26%]']}
        rows={[
          [<C>status</C>, <>One of <C>pending</C>, <C>running</C>, <C>completed</C>, <C>failed</C>, <C>cancelled</C>.</>],
          [<C>trigger_data</C>, 'Exactly what the run started with — the first thing to check when output looks wrong.'],
          [<C>steps_executed</C>, 'How far it got. A low number on a long workflow means it stopped early.'],
          [<C>steps_successful</C> , 'How many succeeded.'],
          [<C>steps_failed</C>, 'How many failed. Non-zero with status completed means error handling was set to continue.'],
          [<C>duration_ms</C>, 'Wall-clock time. Watch this on mid-call workflows — slow runs mean dead air.'],
          [<C>result_data</C>, 'Per-node outputs.'],
          [<C>error_message</C>, 'Why it failed, when it did.'],
        ]}
      />

      <P>
        The workflow list also carries running totals — total, successful, and failed
        executions, plus when it last ran. A workflow whose failure count is climbing is
        usually a broken integration connection rather than a broken graph.
      </P>

      <H2 id="reading-a-run">Reading a failed run</H2>

      <H3>1. Check the trigger data first</H3>
      <P>
        Most &ldquo;the workflow is wrong&rdquo; reports are really &ldquo;the workflow
        received something unexpected&rdquo;. Look at <C>trigger_data</C> before reading the
        graph.
      </P>

      <H3>2. Find the first failure, not the last</H3>
      <P>
        With <C>error_handling</C> set to <C>continue</C>, one early failure cascades — later
        nodes read empty values and fail in confusing ways. Fix the first one and the rest
        often disappear.
      </P>

      <H3>3. Distinguish empty from failed</H3>
      <P>
        A node that succeeded but produced nothing usually means a mistyped reference: a
        missing reference resolves to <C>null</C> or an empty string rather than raising. See{' '}
        <A href="/docs/workflows/variables#missing-references">Missing references</A>.
      </P>

      <H3>4. Check the connection, not the node</H3>
      <P>
        Integration nodes fail when the underlying connection has expired, been revoked, or
        hit a rate limit. Test the connection under <Strong>Integrations</Strong> before
        rebuilding the node.
      </P>

      <H3>5. Re-run with the same input</H3>
      <P>
        Copy <C>trigger_data</C> from the failed run into a manual execute. That reproduces
        the failure exactly, instead of testing against data that happens to work.
      </P>

      <Callout kind="tip" title="Instrument long workflows">
        On a workflow with many steps, a <A href="/docs/nodes/logic#transform">Set Fields</A>{' '}
        node placed at each phase boundary — capturing what mattered at that point — turns an
        opaque failure into an obvious one. It costs nothing to run and pays for itself the
        first time something breaks at 3am.
      </Callout>
    </DocPage>
  )
}
