import { DocPage, docMetadata } from '@/components/docs/DocPage'
import {
  A, C, Callout, H2, H3, LI, P, Strong, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/troubleshooting')

export default function TroubleshootingPage() {
  return (
    <DocPage href="/docs/troubleshooting">
      <P>
        Symptoms people actually report, and what fixes them. Each section is ordered by how
        often the cause turns out to be the culprit.
      </P>

      <Callout kind="tip" title="Start with the transcript, always">
        Almost every diagnosis begins by finding the exact turn where the call diverged. Open
        the call in <A href="/docs/calls">Calls</A> before changing anything.
      </Callout>

      <H2 id="agent-issues">The agent sounds wrong</H2>

      <H3>It talks too much</H3>
      <P>
        The system prompt does not demand brevity. Add &ldquo;Keep replies to one or two
        sentences. This is a phone call.&rdquo; Lowering <C>llm_max_tokens</C> is not the fix —
        that truncates mid-sentence rather than producing shorter replies.
      </P>

      <H3>It answers a question the caller did not ask</H3>
      <P>
        The transcriber misheard. Check the transcript: if the words are wrong there, no prompt
        change will help. Try a different{' '}
        <A href="/docs/agents/configuration#transcriber">STT model</A>, or set a more specific
        language variant — <C>en-GB</C> rather than <C>en</C>.
      </P>

      <H3>It interrupts the caller</H3>
      <P>
        <C>silence_timeout</C> is too short — the agent treats a thinking pause as the end of a
        turn. Raise it toward <C>3000</C>ms, higher if callers read out long numbers.
      </P>

      <H3>It talks over the caller and will not stop</H3>
      <P>
        <C>interrupt_sensitivity</C> is too low, or <C>interrupt_enabled</C> is off. Raise
        sensitivity. If it now stops at every background noise, you have gone too far — the
        usable band is narrow, so move in small steps.
      </P>

      <H3>It invents answers</H3>
      <P>
        The prompt has no explicit &ldquo;I don&rsquo;t know&rdquo; behaviour. Add one, and put
        the facts in a <A href="/docs/knowledge-base">knowledge base</A> rather than relying on
        the model to have them.
      </P>

      <H3>It feels slow</H3>
      <P>
        Read the <A href="/docs/calls#event-log">event log</A> and find which stage costs the
        time before changing anything. Then work down{' '}
        <A href="/docs/agents/configuration#tuning-for-latency">the latency list</A>.
      </P>

      <H2 id="tool-issues">A tool never fires</H2>

      <H3>The description is too vague</H3>
      <P>
        By far the most common cause. The model chooses using the name and description alone.
        Rewrite the description to name the <em>situation</em>: &ldquo;Use when the caller
        wants to schedule, move, or cancel a visit&rdquo; rather than &ldquo;calendar
        tool&rdquo;.
      </P>

      <H3>Two tools overlap</H3>
      <P>
        If two descriptions could both plausibly match, selection becomes a coin flip. Make the
        boundary explicit in both, or merge them into one tool with a parameter that
        distinguishes the cases.
      </P>

      <H3>Too many tools are assigned</H3>
      <P>
        Past roughly eight to ten, accuracy degrades. Group related capabilities behind one{' '}
        <A href="/docs/tools/workflow">workflow tool</A>.
      </P>

      <H3>The prompt never mentions the situation</H3>
      <P>
        Assigning a tool makes it available; the prompt makes it likely. Add a line describing
        when the agent should reach for it.
      </P>

      <H3>It fires but fails</H3>
      <P>
        Different problem. Run the tool&rsquo;s <Strong>Test</Strong> action with sample
        values — for the HTTP tool types that sends the same request a live call would, so a
        failure there is reproducible in front of you. The messages below name what to change.
      </P>

      <H3>&ldquo;Headers is not valid JSON&rdquo; / &ldquo;Body Template is not valid JSON&rdquo;</H3>
      <P>
        The field holds text that does not parse, and the message gives the line and column.
        Nearly always a trailing comma after the last entry, a missing closing brace, or
        single quotes where JSON needs double ones.
      </P>

      <H3>&ldquo;… url rejected&rdquo;</H3>
      <P>
        The destination is not a public address. Loopback, private ranges and the cloud
        metadata address are refused, and redirects are not followed. See{' '}
        <A href="/docs/tools/integration#api-request-limits">Where it may connect</A>.
      </P>

      <H3>The endpoint returns 401, and the credentials look right</H3>
      <P>
        Check that the auth mode is actually selected — the credential fields only appear once
        you choose one, and a mode with a blank credential now fails the tool outright rather
        than sending an unauthenticated request. If you are hand-assembling an{' '}
        <C>Authorization</C> header in an{' '}
        <A href="/docs/tools/integration#api-request">API Request</A> tool, consider a{' '}
        <A href="/docs/tools/integration#custom-tool">Custom Tool</A> instead, where auth is a
        structured field.
      </P>

      <H3>The receiving API stored a literal {'{{placeholder}}'}</H3>
      <P>
        The reference did not resolve, which means the parameter was not collected under that
        name. Check the spelling against the tool&rsquo;s{' '}
        <A href="/docs/tools/parameters">declared parameters</A> — an unresolved reference is
        sent as <C>null</C>, so a literal placeholder arriving means the template names
        something that does not exist.
      </P>

      <H3>&ldquo;… tools run through a connected integration&rdquo;</H3>
      <P>
        The tool was created as a Google Sheets, Google Calendar, or GoHighLevel type. Those
        predate the connector system and have no credentials of their own. Connect the app
        under <A href="/docs/integrations">Integrations</A> and rebuild the tool as a{' '}
        <A href="/docs/tools/integration#connected-integration">Connected Integration</A>.
      </P>

      <H3>The agent said it worked, and nothing happened</H3>
      <P>
        If this is an older tool of one of the three types just above, that is exactly what it
        did — those reported success without acting. They now fail with the message above
        instead. Rebuild the tool as a Connected Integration and the agent will report the real
        outcome.
      </P>

      <H2 id="workflow-issues">A workflow fails</H2>

      <H3>A value arrives empty</H3>
      <P>
        Nearly always a mistyped reference. Missing references resolve to <C>null</C> or an
        empty string rather than raising, so a typo produces a silent blank. Check the spelling
        against <A href="/docs/workflows/variables">Variables &amp; Expressions</A>.
      </P>

      <H3>An API rejects the payload</H3>
      <P>
        Usually a type problem. A stray space or character around <C>{'{{ }}'}</C> turns a
        whole-value reference into a mixed template, and the number <C>42</C> becomes the
        string <C>&quot;42 &quot;</C>. See{' '}
        <A href="/docs/workflows/variables#type-preservation">Type preservation</A>.
      </P>

      <H3>A branch always takes the same path</H3>
      <UL>
        <LI>The variable path is wrong, so it is always empty and never matches.</LI>
        <LI>
          You used <C>equals</C> on speech. Callers say &ldquo;yeah&rdquo;, not
          &ldquo;yes&rdquo;. Use <C>contains</C>, or ask via{' '}
          <A href="/docs/nodes/conversation#ask">DTMF</A>.
        </LI>
        <LI>On a Switch, an earlier broad rule is catching everything. Reorder narrowest first.</LI>
      </UL>

      <H3>Later steps fail in confusing ways</H3>
      <P>
        With <C>error_handling</C> set to <C>continue</C>, one early failure cascades. Find the{' '}
        <em>first</em> failed node, not the last. See{' '}
        <A href="/docs/workflows/execution#reading-a-run">Reading a failed run</A>.
      </P>

      <H3>Nothing runs at all</H3>
      <P>
        The workflow is inactive. Executing an inactive workflow is refused with{' '}
        <C>409 Conflict</C> rather than silently ignored.
      </P>

      <H3>A step runs several times</H3>
      <P>
        Parallel branches converged on it directly. Put a{' '}
        <A href="/docs/nodes/logic#merge">Merge</A> node in front of it.
      </P>

      <H3>&ldquo;This step type is no longer available&rdquo;</H3>
      <P>
        The workflow contains a node this build has retired — the Code node, in almost every
        case. It shows as <Strong>Unsupported step</Strong> and blocks the run. Rebuild what it
        did with <A href="/docs/nodes/logic#calculate">Calculate</A> or{' '}
        <A href="/docs/nodes/logic#transform">Set Fields</A>, or call your own endpoint with a{' '}
        <A href="/docs/nodes/actions#webhook">Webhook</A>, then delete the old node. See{' '}
        <A href="/docs/workflows#retired-steps">Steps that are no longer supported</A>.
      </P>

      <H3>&ldquo;Webhook url rejected&rdquo;</H3>
      <P>
        The address is not publicly routable. <C>localhost</C>, <C>10.x</C>, <C>192.168.x</C>,{' '}
        <C>169.254.x</C> and the like are refused, and redirects are not followed — so a public
        URL that <C>302</C>s to an internal one fails here too. Point the node at the final
        public address. See{' '}
        <A href="/docs/nodes/actions#webhook">Which destinations are allowed</A>.
      </P>

      <H3>&ldquo;Tool … not found&rdquo; or &ldquo;Connection … not found&rdquo;</H3>
      <P>
        The id names something outside this workspace — usually because the workflow was
        copied from another one. The message is identical whether the record is missing or
        belongs to someone else, so recreate the tool or connection here rather than hunting
        for the difference.
      </P>

      <H3>&ldquo;Action &lsquo;x&rsquo; is not available on …&rdquo;</H3>
      <P>
        The action name is not one the connector publishes. Pick it from the dropdown rather
        than typing it, and check the{' '}
        <A href="/docs/integrations/catalog">catalog</A> for the exact spelling.
      </P>

      <H3>Set Fields says a field &ldquo;has no value to work on&rdquo;</H3>
      <P>
        The row&rsquo;s source resolved to nothing, and its transform cannot run on an absent
        value. Either the step that was meant to produce it did not run, or the reference is
        mistyped. The message names the field and the transform — start there.
      </P>

      <H3>A date comes out as 2026-08-28T14:30:00</H3>
      <P>
        <Strong>Add days</Strong> and <Strong>Add hours</Strong> return a date, not a phrase.
        Chain <Strong>Format as date</Strong> after them to choose how it reads. See{' '}
        <A href="/docs/nodes/logic#transform-chains">Chaining transforms</A>.
      </P>

      <H3>A mid-call workflow gives up too quickly</H3>
      <P>
        It is not ignoring your settings. A <C>sync</C> run caps retries at one attempt after
        two seconds, because the alternative is dead air on the line. Handle the failure in the
        graph instead of waiting it out — see{' '}
        <A href="/docs/workflows/execution#sync-retry-cap">Retries are capped during a call</A>.
      </P>

      <H3>A webhook-triggered workflow never fires</H3>
      <P>
        Check it has a <C>webhook_key</C>. A webhook workflow without one refuses every
        request rather than accepting them, so it looks identical to nothing arriving. See{' '}
        <A href="/docs/workflows/triggers#webhook">Webhook triggers</A>.
      </P>

      <H3>A scheduled workflow runs at the wrong hour</H3>
      <P>
        Cron expressions are evaluated in UTC and there is no timezone setting, so a local
        schedule shifts when daylight saving does. Convert to UTC yourself. See{' '}
        <A href="/docs/workflows/triggers#schedule">Schedule triggers</A>.
      </P>

      <H2 id="integration-issues">An integration breaks</H2>

      <H3>It worked yesterday and does not today</H3>
      <P>
        Test the connection first — it takes seconds and is the most likely cause. A{' '}
        <C>401</C> or <C>403</C> means the credential was revoked, expired beyond refresh, or
        lost a scope. Reconnect.
      </P>

      <H3>It broke when someone left</H3>
      <P>
        The connection was made with their personal OAuth login. Reconnect as a service
        account, and audit your other connections for the same exposure.
      </P>

      <H3>Requests are slow or intermittently failing</H3>
      <P>
        You are hitting rate limits. Requests are paced to stay inside the provider&rsquo;s
        declared limits, so a large <A href="/docs/nodes/logic#loop">loop</A> runs slower than
        the raw API would. Use a bulk action where the connector offers one.
      </P>

      <H3>Records stopped appearing, but nothing reports an error</H3>
      <P>
        The classic silent failure: <C>error_handling</C> is <C>continue</C>, so the workflow
        succeeds while the write fails. Check{' '}
        <A href="/docs/analytics#integration-metrics">integration metrics</A> for a success
        rate that has quietly dropped.
      </P>

      <H2 id="phone-issues">Calls do not connect</H2>

      <H3>The number rings but nothing answers</H3>
      <UL>
        <LI>No agent is assigned to it.</LI>
        <LI>The assigned agent was deleted.</LI>
        <LI>The agent is deactivated.</LI>
        <LI>The number&rsquo;s status is <C>inactive</C>.</LI>
      </UL>

      <H3>Outbound calls fail immediately</H3>
      <UL>
        <LI>The destination is not in E.164 — it needs the leading <C>+</C> and country code.</LI>
        <LI>The from-number is not one you own, or lacks voice capability.</LI>
        <LI>The carrier connection has expired. Test it.</LI>
        <LI>The carrier is blocking the destination — some regions require prior authorisation.</LI>
      </UL>

      <H3>SMS does not send</H3>
      <P>
        The sending number lacks SMS capability. That is set at purchase and cannot be added
        afterwards — check the number&rsquo;s{' '}
        <A href="/docs/phone-numbers#configuration">capabilities</A>. You will need a
        different number.
      </P>

      <H3>Calls stop connecting mid-campaign</H3>
      <P>
        You have hit a plan limit, most likely call minutes. Check{' '}
        <A href="/docs/workspace/billing#usage">Usage</A>.
      </P>

      <H2 id="knowledge-issues">The agent ignores the knowledge base</H2>

      <H3>It says it does not know things that are documented</H3>
      <UL>
        <LI>
          <C>min_similarity</C> is too high — nothing clears the floor. Lower it in steps of{' '}
          <C>0.05</C>.
        </LI>
        <LI>
          The document reports <C>completed</C> but produced <C>0</C> chunks. Extraction
          failed — a scanned PDF with no text layer is the usual reason.
        </LI>
        <LI>
          The knowledge base is linked but <C>is_active</C> is off, or <C>auto_inject</C> is
          off and there is no query tool.
        </LI>
        <LI>
          The document uses internal vocabulary and the caller uses ordinary words. Add both
          phrasings.
        </LI>
      </UL>

      <H3>It answers with irrelevant passages</H3>
      <P>
        <C>min_similarity</C> is too low, or <C>max_results</C> too high, so weak matches are
        being included. Raise the floor toward <C>0.8</C> and reduce results to three.
      </P>

      <H3>It quotes something out of date</H3>
      <P>
        The old document is still indexed. Delete it rather than uploading a correction
        alongside — both will be retrieved, and the model has no way to know which is current.
      </P>

      <H3>Answers are cut off or missing context</H3>
      <P>
        Chunks are too small, or overlap too low, so the answer is split across a boundary.
        Raise <C>chunk_size</C> and <C>chunk_overlap</C>, then re-upload — existing documents
        keep the chunks they were created with.
      </P>

      <Callout kind="note" title="Still stuck?">
        Isolate the layer. Search the knowledge base directly to test retrieval without the
        model. Run a tool&rsquo;s test action to check it without the agent. Execute a workflow
        manually to check it without a call. Whichever step fails alone is the one to fix.
      </Callout>
    </DocPage>
  )
}
