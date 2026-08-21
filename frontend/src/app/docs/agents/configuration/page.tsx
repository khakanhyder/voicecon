import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { CodeBlock } from '@/components/docs/CodeBlock'
import {
  A, C, Callout, H2, H3, LI, P, ParamTable, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/agents/configuration')

export default function AgentConfigurationPage() {
  return (
    <DocPage href="/docs/agents/configuration">
      <P>
        The agent editor is organised into tabs. This page walks every field on every tab,
        what it changes, and how to choose a value.
      </P>

      <H2 id="prompt">Prompt</H2>
      <P>
        The two most consequential fields in the entire product. Almost every behavioural
        problem is a prompt problem before it is a model problem.
      </P>

      <ParamTable
        params={[
          {
            name: 'name',
            type: 'string',
            required: true,
            description: (
              <>
                Identifies the agent in lists, call logs, and pickers. Not spoken to callers —
                the agent&rsquo;s spoken name comes from the prompt.
              </>
            ),
          },
          {
            name: 'description',
            type: 'string',
            description: 'Internal note for your team. Never sent to the model.',
          },
          {
            name: 'first_message',
            type: 'string',
            description: (
              <>
                Spoken verbatim the instant the call connects, before the model is involved.
                Leave empty and the agent waits for the caller to speak first — which on a
                phone call usually produces an awkward silence.
              </>
            ),
          },
          {
            name: 'system_prompt',
            type: 'string',
            description: (
              <>
                The standing instruction sent with every model request. Defines role, scope,
                tone, and fallback behaviour.
              </>
            ),
          },
        ]}
      />

      <H3 id="writing-a-system-prompt">Writing a system prompt that works on the phone</H3>
      <P>
        A prompt tuned for chat will not perform well on a call. Four adjustments matter most:
      </P>
      <UL>
        <LI>
          <Strong>Demand brevity explicitly.</Strong> &ldquo;Keep replies to one or two
          sentences.&rdquo; Without this you get paragraphs, and callers interrupt.
        </LI>
        <LI>
          <Strong>Define the boundary.</Strong> State what the agent does <em>not</em> handle
          and what it should do instead — offer a transfer, take a message.
        </LI>
        <LI>
          <Strong>Give it an &ldquo;I don&rsquo;t know&rdquo;.</Strong> Models invent
          plausible answers when cornered. Tell it that admitting ignorance is the correct
          behaviour.
        </LI>
        <LI>
          <Strong>Describe when to use tools.</Strong> If a tool exists but the prompt never
          alludes to the situation it serves, the model will often talk its way around it.
        </LI>
      </UL>

      <CodeBlock
        language="A prompt skeleton that holds up"
        code={`You are {name}, a {role} for {company}.

WHAT YOU DO
- {task 1}
- {task 2}

WHAT YOU DO NOT DO
- {out of scope}. If asked, offer to {escape hatch}.

HOW YOU SPEAK
- One or two sentences per reply. This is a phone call.
- Confirm names, dates, and numbers back to the caller.
- Never guess. If you do not know, say so.

TOOLS
- Use {tool_name} when the caller {situation}.`}
      />

      <Callout kind="tip" title="Change one thing at a time">
        When a call goes wrong, resist rewriting the whole prompt. Find the exact turn in the
        transcript, change the one instruction that governs it, and re-test. Wholesale
        rewrites make it impossible to know what fixed anything.
      </Callout>

      <H2 id="llm">LLM selection</H2>
      <P>
        The model decides what the agent says and whether to call a tool. Voicecon supports
        fifteen providers, including a custom endpoint for a model you host yourself.
      </P>

      <ParamTable
        params={[
          {
            name: 'llm_provider',
            type: 'enum',
            default: 'openai',
            description: (
              <>
                OpenAI, Anthropic, Google Gemini, Groq, xAI, Mistral, Together AI, OpenRouter,
                Perplexity, Azure OpenAI, Cerebras, DeepInfra, Anyscale, Inflection, or
                Custom.
              </>
            ),
          },
          {
            name: 'llm_model',
            type: 'string',
            description: (
              <>
                The model within that provider. The picker annotates each with approximate
                latency — the number to optimise for on voice. A new agent created in the
                editor starts on the first model of the chosen provider (
                <C>gpt-5.4-nano</C> for OpenAI); one created through the API without naming a
                model falls back to <C>gpt-4</C>, so set it explicitly there.
              </>
            ),
          },
          {
            name: 'llm_temperature',
            type: 'number 0–2',
            default: '0.7',
            description: (
              <>
                Randomness. Below <C>0.4</C> the agent becomes consistent and slightly stiff —
                right for scripted and compliance work. Above <C>1.0</C> it becomes creative
                and unpredictable. Most production agents sit between <C>0.4</C> and{' '}
                <C>0.8</C>.
              </>
            ),
          },
          {
            name: 'llm_max_tokens',
            type: 'number 100–4000',
            default: '1000',
            description: (
              <>
                Ceiling on a single reply. This is a safety limit, not a brevity control — a
                low value truncates the agent mid-sentence rather than making it concise. Ask
                for brevity in the prompt instead.
              </>
            ),
          },
          {
            name: 'llm_custom_url',
            type: 'url',
            description: (
              <>
                Only for the Custom provider. Must expose an OpenAI-compatible{' '}
                <C>/v1/chat/completions</C> endpoint.
              </>
            ),
          },
          {
            name: 'llm_api_key',
            type: 'secret',
            description: (
              <>
                Bring your own key. Stored encrypted. Leave empty to use the platform&rsquo;s
                credentials where your plan permits.
              </>
            ),
          },
        ]}
      />

      <H3 id="choosing-a-model">Choosing a model</H3>
      <P>
        On a phone call, latency is a feature. A one-second pause that reads as thoughtful in
        chat reads as a dropped call on the phone.
      </P>
      <Table
        headers={['Situation', 'Reach for', 'Reasoning']}
        widths={['w-[30%]', 'w-[28%]']}
        rows={[
          [
            'Default starting point',
            <><C>gpt-5.4-nano</C> or <C>claude-haiku-4-5</C></>,
            'Sub-400ms, capable enough for most conversational work.',
          ],
          [
            'Fastest possible turn-taking',
            <><C>gpt-4.1-nano</C>, Groq, or Cerebras</>,
            'Around 100–200ms. Noticeably snappier; less capable on complex reasoning.',
          ],
          [
            'Complex multi-step reasoning',
            <><C>gpt-5.4</C> or <C>claude-sonnet-4-6</C></>,
            'Worth the extra latency when the agent must weigh several conditions.',
          ],
          [
            'Needs current web knowledge',
            'Perplexity Sonar Online',
            'Retrieves at inference time. Slower, but current.',
          ],
          [
            'Data residency or enterprise contract',
            'Azure OpenAI',
            'Same models under your own Azure tenancy.',
          ],
        ]}
      />
      <Callout kind="warning" title="Avoid reasoning models on voice">
        The <C>o1</C> and <C>o3</C> families think before answering — 3 to 15 seconds. That is
        unusable on a live call. They are listed for completeness, not for telephony.
      </Callout>

      <H2 id="transcriber">Transcriber (speech-to-text)</H2>
      <P>
        Converts caller audio into text. Its accuracy sets a ceiling on everything downstream:
        a misheard word cannot be recovered by a better model.
      </P>

      <ParamTable
        params={[
          {
            name: 'stt_provider',
            type: 'enum',
            default: 'deepgram',
            description: (
              <>
                Deepgram, AssemblyAI, ElevenLabs, Azure Speech, Gladia, Speechmatics, Soniox,
                or OpenAI Whisper.
              </>
            ),
          },
          {
            name: 'stt_model',
            type: 'string',
            description: (
              <>
                Provider-specific. Deepgram <C>nova-2</C> is the recommended default;{' '}
                <C>nova-3</C> trades a little latency for accuracy.
              </>
            ),
          },
          {
            name: 'stt_language',
            type: 'locale',
            default: 'en',
            description: (
              <>
                26 options, including regional variants. Set the specific variant when you
                know it — <C>en-GB</C> outperforms <C>en</C> on British callers, particularly
                for place names.
              </>
            ),
          },
        ]}
      />

      <Table
        headers={['Pick this provider', 'When']}
        widths={['w-[28%]']}
        rows={[
          ['Deepgram', 'Default. Tuned for telephone-bandwidth audio, low latency, strong English.'],
          ['AssemblyAI', 'You need speaker diarization — telling two voices apart on one line.'],
          ['Soniox', 'Broad multilingual coverage, with a phone-optimised English model.'],
          ['Speechmatics', 'You have domain vocabulary — drug names, SKUs, surnames — to bias toward.'],
          ['Gladia', 'Mixed-language calls where the caller may switch languages.'],
          ['Whisper', 'Accuracy matters more than latency, or you need an open-source path.'],
        ]}
      />

      <Callout kind="tip" title="Test with real telephone audio">
        A laptop microphone in a quiet room flatters every transcriber. Phone audio is 8kHz,
        compressed, and often noisy. Judge accuracy on an actual call.
      </Callout>

      <H2 id="voice">Voice (text-to-speech)</H2>
      <P>
        How the agent sounds. Fourteen providers, each with a voice catalogue, plus a field
        for a custom voice ID if you have cloned a voice with the provider directly.
      </P>

      <ParamTable
        params={[
          {
            name: 'tts_provider',
            type: 'enum',
            default: 'elevenlabs',
            description: (
              <>
                ElevenLabs, Cartesia, Deepgram Aura, OpenAI, Google, Azure, PlayHT, RimeAI,
                LMNT, Neuphonic, SmallestAI, Hume, MiniMax, or Inworld.
              </>
            ),
          },
          {
            name: 'tts_voice_id',
            type: 'string',
            description: (
              <>
                Chosen from the provider&rsquo;s catalogue, or entered directly via{' '}
                <Strong>Custom voice ID</Strong> — which is how you use a cloned voice.
              </>
            ),
          },
          {
            name: 'tts_speed',
            type: 'number 0.5–2.0',
            default: '1.0',
            description: (
              <>
                Playback rate. <C>1.05</C>–<C>1.15</C> often sounds more natural and
                purposeful than <C>1.0</C>. Past <C>1.3</C> comprehension drops sharply.
              </>
            ),
          },
          {
            name: 'tts_pitch',
            type: 'number 0.5–2.0',
            default: '1.0',
            description: (
              <>
                Pitch shift. Small adjustments only — large shifts produce obvious artefacts.
                Not honoured by every provider.
              </>
            ),
          },
        ]}
      />

      <Table
        headers={['Pick this provider', 'When']}
        widths={['w-[26%]']}
        rows={[
          ['ElevenLabs', 'Default. Best all-round naturalness, and voice cloning if you want a branded voice.'],
          ['Cartesia', 'Latency is the priority. Noticeably faster to first audio.'],
          ['Deepgram Aura', 'You are already on Deepgram for STT and want one vendor.'],
          ['Azure / Google', 'Wide language coverage or an existing enterprise agreement.'],
          ['Hume', 'You want the delivery to respond to emotional context.'],
          ['PlayHT', 'Voice cloning with a large stock catalogue.'],
        ]}
      />

      <H2 id="conversation">Conversation</H2>
      <P>
        Turn-taking and call limits. These settings decide whether the agent feels like a
        person or like a phone tree.
      </P>

      <ParamTable
        params={[
          {
            name: 'interrupt_enabled',
            type: 'boolean',
            default: 'true',
            description: (
              <>
                Whether the caller can interrupt the agent mid-sentence. Leave on for
                conversational agents. Turn off only when a passage must be heard in full —
                a legal disclosure, for instance.
              </>
            ),
          },
          {
            name: 'interrupt_sensitivity',
            type: 'number 0–1',
            default: '0.5',
            description: (
              <>
                How readily the agent yields. High values make it stop at a cough or a
                background voice; low values make it talk over a caller who is genuinely
                trying to speak. Raise it in quiet environments, lower it for callers on
                speakerphone or in cars.
              </>
            ),
          },
          {
            name: 'silence_timeout',
            type: 'ms 500–10000',
            default: '3000',
            description: (
              <>
                How long to wait after the caller stops before treating the turn as finished.
                Too low and the agent cuts off anyone who pauses to think; too high and every
                exchange feels sluggish. <C>2000</C>–<C>3000</C> suits most callers; raise it
                when callers read out long numbers.
              </>
            ),
          },
          {
            name: 'max_call_duration',
            type: 'seconds 60–7200',
            default: '1800',
            description: (
              <>
                Hard ceiling. The call ends when reached, regardless of state. This is your
                protection against a loop billing indefinitely — keep it set.
              </>
            ),
          },
          {
            name: 'end_call_phrases',
            type: 'string[]',
            default: '[]',
            description: (
              <>
                Phrases that end the call when the caller says them — &ldquo;goodbye&rdquo;,
                &ldquo;that&rsquo;s all&rdquo;, &ldquo;thanks, bye&rdquo;. Without these the
                agent may keep the line open after the conversation has plainly finished.
              </>
            ),
          },
        ]}
      />

      <Callout kind="note" title="These interact">
        High interrupt sensitivity with a short silence timeout produces an agent that
        constantly stops and restarts. If turn-taking feels chaotic, adjust one and re-test
        before touching the other.
      </Callout>

      <H2 id="advanced">Advanced</H2>
      <P>Signal processing and post-call analysis.</P>

      <ParamTable
        params={[
          {
            name: 'background_noise_reduction',
            type: 'boolean',
            default: 'true',
            description: (
              <>
                Filters ambient noise before transcription. Worth keeping on — most inbound
                calls come from cars, streets, and open-plan offices.
              </>
            ),
          },
          {
            name: 'sentiment_analysis_enabled',
            type: 'boolean',
            default: 'false',
            description: (
              <>
                Scores each call for sentiment and stores a score and label on the call
                record. Enable if you intend to report on it or trigger follow-up on negative
                calls; it adds post-call processing.
              </>
            ),
          },
          {
            name: 'emotion_detection_enabled',
            type: 'boolean',
            default: 'false',
            description: (
              <>
                Finer-grained emotional signals stored alongside sentiment. Useful for
                escalation rules — route angry calls to a supervisor.
              </>
            ),
          },
        ]}
      />

      <H2 id="knowledge">Knowledge</H2>
      <P>
        Links knowledge bases to this agent so it can answer from documents. Each link carries
        its own retrieval settings — priority, maximum results, minimum similarity, and
        automatic injection.
      </P>
      <P>
        The settings are documented in full under{' '}
        <A href="/docs/knowledge-base#link-settings">Knowledge Base → Link settings</A>.
      </P>
      <Callout kind="tip" title="Prompt or knowledge base?">
        Put <Strong>behaviour</Strong> in the prompt and <Strong>facts</Strong> in a knowledge
        base. Facts in a prompt have to be re-tested every time they change; facts in a
        knowledge base are updated by replacing a document.
      </Callout>

      <H2 id="tools-tab">Tools</H2>
      <P>
        Assigns existing tools to this agent. Tools are created once under{' '}
        <Strong>Tools</Strong> and assigned to as many agents as you like — the assignment is
        a link, not a copy, so editing the tool updates every agent using it.
      </P>
      <P>
        An agent with no tools can only talk. See <A href="/docs/tools">Tools</A> for what is
        available and how the model chooses between them.
      </P>
      <Callout kind="warning" title="More tools is not better">
        Every assigned tool goes into the model&rsquo;s context and competes for its
        attention. Beyond roughly eight to ten, selection accuracy degrades. If an agent needs
        many capabilities, group them behind a single workflow tool.
      </Callout>

      <H2 id="tuning-for-latency">Tuning for latency</H2>
      <P>
        Once behaviour is right, this is how you make it feel fast. Work down the list —
        the entries are ordered by impact per unit of effort.
      </P>

      <Table
        headers={['#', 'Change', 'Typical gain']}
        widths={['w-[6%]', 'w-[44%]']}
        rows={[
          ['1', <>Move to a faster model (<C>gpt-4.1-nano</C>, Groq, Cerebras)</>, '300–600ms per turn'],
          ['2', <>Lower <C>silence_timeout</C> from 3000ms toward 2000ms</>, 'Up to 1s of perceived wait'],
          ['3', 'Switch TTS to Cartesia or Deepgram Aura', '100–250ms to first audio'],
          ['4', <>Reduce assigned tools so the model has less to weigh</>, '50–150ms, plus better selection'],
          ['5', <>Lower <C>llm_max_tokens</C> so replies cannot run long</>, 'Caps the worst case'],
          ['6', 'Shorten the system prompt', 'Small but compounding across every turn'],
        ]}
      />

      <Callout kind="note" title="Measure, do not guess">
        Each call&rsquo;s event log records per-stage durations — transcription, model, speech.
        Open a slow call in <A href="/docs/calls#event-log">Calls</A> and read which stage
        actually cost the time before optimising the wrong one.
      </Callout>
    </DocPage>
  )
}
