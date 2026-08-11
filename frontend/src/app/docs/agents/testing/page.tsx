import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { CodeBlock } from '@/components/docs/CodeBlock'
import {
  A, C, Callout, H2, H3, LI, P, ParamTable, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/agents/testing')

export default function AgentTestingPage() {
  return (
    <DocPage href="/docs/agents/testing">
      <H2 id="browser-test">Testing in the browser</H2>
      <P>
        Open an agent and choose <Strong>Test</Strong>. This starts a live conversation over
        your computer&rsquo;s microphone and speakers — the same pipeline as a phone call,
        without the phone or the telephony charge.
      </P>
      <UL>
        <LI>Allow microphone access when the browser asks.</LI>
        <LI>
          The session is recorded as a call with direction <C>test</C>, so the transcript and
          event log are waiting for you afterwards in <Strong>Calls</Strong>.
        </LI>
        <LI>
          Every configuration change takes effect on the next test immediately — no deploy
          step.
        </LI>
      </UL>
      <Callout kind="note" title="What the browser test does not reproduce">
        Your laptop microphone is far better than a phone line. Transcription accuracy,
        background noise handling, and barge-in behaviour all look better in the browser than
        they will on a real call. Validate those on an actual phone before going live.
      </Callout>

      <H2 id="what-to-check">What to check on a test call</H2>
      <P>
        Working through this list catches most problems before a customer finds them.
      </P>

      <Table
        headers={['Check', 'What good looks like']}
        widths={['w-[32%]']}
        rows={[
          ['Opening', 'The first message plays immediately, with no leading silence.'],
          ['Reply length', 'One or two sentences. If you are getting paragraphs, the prompt needs to say so.'],
          ['Interruption', 'Talk over the agent. It should stop within roughly a second and listen.'],
          ['Thinking pause', 'Pause mid-sentence yourself. The agent should wait, not jump in.'],
          ['Out of scope', 'Ask something unrelated. It should decline gracefully and redirect.'],
          ['Unknown facts', 'Ask something it cannot know. It should admit that, not invent an answer.'],
          ['Tool firing', 'Create the situation a tool exists for. Confirm it actually fires.'],
          ['Numbers and names', 'Read out a phone number or spell a surname. Check the transcript got it.'],
          ['Ending', 'Say “goodbye”. The call should end, not hang open.'],
        ]}
      />

      <H2 id="outbound-calls">Placing an outbound call</H2>
      <P>
        Outbound calls are initiated through the API or by a workflow, using one of your
        provisioned numbers as the caller ID.
      </P>
      <CodeBlock
        language="bash"
        code={`curl -X POST https://api.your-voicecon-host.com/api/v1/calls \\
  -H "Authorization: Bearer $VOICECON_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "agent_id": "b6f1…",
    "direction": "outbound",
    "from_number": "+14155550123",
    "to_number": "+14155559876"
  }'`}
      />
      <P>
        The response carries the call id; poll it or watch <Strong>Calls</Strong> for the
        transcript once the call completes.
      </P>
      <Callout kind="warning" title="Outbound calling is regulated">
        Consent requirements, calling-hour restrictions, and disclosure rules vary by
        jurisdiction and are your responsibility. Many regions require an automated caller to
        identify itself as such at the start of the call — put that in the first message.
      </Callout>

      <H2 id="chat-widget">The chat widget</H2>
      <P>
        The same agent can serve text conversations on your website. The{' '}
        <Strong>Chat Widget</Strong> tab generates a public key and an embed snippet.
      </P>

      <ParamTable
        params={[
          {
            name: 'enabled',
            type: 'boolean',
            default: 'true',
            description: 'Turns the widget on or off without changing the embed on your site.',
          },
          {
            name: 'public_key',
            type: 'string',
            description: (
              <>
                Generated for you. Safe to publish — it identifies the widget and grants no
                access to your workspace.
              </>
            ),
          },
          {
            name: 'config',
            type: 'object',
            description: (
              <>
                Branding: colours, position, greeting, and title. Updates merge with what is
                already stored, so changing one field will not reset the others.
              </>
            ),
          },
        ]}
      />

      <P>Paste the snippet before the closing body tag on any page:</P>
      <CodeBlock
        language="html"
        code={`<script
  src="https://your-voicecon-host.com/widget.js"
  data-public-key="pk_live_…"
  defer
></script>`}
      />

      <P>
        Widget sessions and their messages are listed under the agent, so text conversations
        can be reviewed like calls.
      </P>
      <Callout kind="tip" title="One agent, two channels">
        The widget uses the same prompt, model, tools, and knowledge base as the voice agent.
        That is usually what you want — but remember a prompt demanding one-sentence replies
        for the phone will also shorten your chat replies. If the two channels need different
        behaviour, clone the agent.
      </Callout>

      <H2 id="debugging">Debugging a bad call</H2>
      <P>
        When a call goes wrong, work in this order. It moves from the cheapest check to the
        most involved.
      </P>

      <H3>1. Read the transcript</H3>
      <P>
        Find the exact turn where it derailed. Most problems are visible here: the agent
        misheard a word, answered a question it should have deflected, or never attempted the
        tool.
      </P>

      <H3>2. Check the transcription, not the agent</H3>
      <P>
        If the transcript shows the agent answering a question the caller did not ask, the
        transcriber misheard. That is an STT problem — change provider, model, or language
        variant. No amount of prompt work fixes a misheard word.
      </P>

      <H3>3. Open the event log</H3>
      <P>
        The call&rsquo;s event log shows each transcription, model call, speech synthesis, and
        tool invocation with durations and errors. A tool that failed shows up here even when
        the agent covered for it smoothly in the transcript.
      </P>

      <H3>4. Test the tool in isolation</H3>
      <P>
        Every tool has a <Strong>Test</Strong> action that runs it with parameters you supply.
        If it fails there, the problem is the tool&rsquo;s configuration, not the agent&rsquo;s
        judgement.
      </P>

      <H3>5. Reproduce in the browser</H3>
      <P>
        Recreate the situation in a browser test, where iteration costs nothing. Once fixed,
        confirm on a real call — some problems only appear at telephone audio quality.
      </P>

      <Callout kind="note" title="Common causes, ranked">
        In rough order of frequency: prompt too vague about scope; tool description too vague
        for the model to match it to the situation; wrong transcriber language; silence
        timeout too short; too many tools assigned; model too small for the reasoning
        required.
      </Callout>

      <P>
        More failure modes and their fixes are collected in{' '}
        <A href="/docs/troubleshooting">Troubleshooting</A>.
      </P>
    </DocPage>
  )
}
