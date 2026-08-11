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
        values. If it fails there, it is a configuration problem — check the URL,
        authentication, and whether required parameters are actually being collected.
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
