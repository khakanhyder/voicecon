import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { CodeBlock } from '@/components/docs/CodeBlock'
import {
  A, C, Callout, H2, LI, P, ParamTable, RefHeader, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/tools/phone-call')

export default function PhoneCallToolsPage() {
  return (
    <DocPage href="/docs/tools/phone-call">
      <P>
        Phone call tools act on the call itself. All of them accept{' '}
        <A href="/docs/tools/parameters">parameters</A>, so their behaviour can depend on what
        the caller said.
      </P>

      <RefHeader id="transfer-call" name="Transfer Call" chip="Phone call" tone="emerald">
        Transfers the live call to another number or extension.
      </RefHeader>

      <ParamTable
        params={[
          {
            name: 'destination',
            type: 'string',
            required: true,
            description: (
              <>
                Phone number in E.164 (<C>+14155550123</C>) or a SIP URI. Use a parameter
                reference when the destination depends on the caller&rsquo;s need.
              </>
            ),
          },
          {
            name: 'message',
            type: 'string',
            description: (
              <>
                Spoken before transferring. Without it the line goes quiet at the exact moment
                the caller is most likely to think the call has failed.
              </>
            ),
          },
        ]}
      />

      <Callout kind="tip" title="One tool, many destinations">
        Rather than a tool per department, declare a <C>department</C> parameter with allowed
        values <C>sales, support, billing</C> and route on it. One tool, one description, and
        the model picks the destination from what the caller said.
      </Callout>

      <RefHeader id="hang-up" name="Hang Up" chip="Phone call" tone="emerald">
        Ends the call gracefully.
      </RefHeader>

      <ParamTable
        params={[
          {
            name: 'message',
            type: 'string',
            description: 'Farewell spoken before hanging up. This tool takes no parameters beyond it.',
          },
        ]}
      />

      <P>
        Give an agent this tool when you want it to end calls deliberately — after confirming
        a booking, or when a caller has clearly finished. Pair it with{' '}
        <C>end_call_phrases</C> on the agent so &ldquo;goodbye&rdquo; also works.
      </P>
      <Callout kind="warning" title="Describe when, not what">
        &ldquo;Ends the call&rdquo; invites the model to use it whenever a conversation lulls.
        &ldquo;Ends the call once the caller has confirmed they need nothing further&rdquo;
        does not.
      </Callout>

      <RefHeader id="leave-voicemail" name="Leave Voicemail" chip="Phone call" tone="emerald">
        Leaves a recorded message — used on outbound calls that reach an answering machine.
      </RefHeader>

      <ParamTable
        params={[
          {
            name: 'message',
            type: 'text',
            required: true,
            description: (
              <>
                What to say. Supports <C>{'{{parameter}}'}</C> references, so the message can
                name the recipient and the reason for calling.
              </>
            ),
          },
        ]}
      />

      <UL>
        <LI>Identify yourself and the business in the first sentence.</LI>
        <LI>Give one clear next step — a number to call, or that you will try again.</LI>
        <LI>Keep it under about twenty seconds; many systems cut off longer messages.</LI>
      </UL>

      <RefHeader id="dtmf" name="DTMF" chip="Phone call" tone="emerald">
        Sends touch-tone digits into the call — for navigating an IVR on a transferred or
        outbound leg.
      </RefHeader>

      <ParamTable
        params={[
          {
            name: 'digits',
            type: 'string',
            required: true,
            description: (
              <>
                The digits to send. Accepts <C>0-9</C>, <C>*</C>, and <C>#</C> — for example{' '}
                <C>1234#</C>.
              </>
            ),
          },
        ]}
      />

      <Callout kind="note" title="Sending, not receiving">
        This tool <em>sends</em> digits. To <em>capture</em> digits from a caller, use an{' '}
        <A href="/docs/nodes/conversation#ask">Ask Question</A> node with{' '}
        <C>input_type: dtmf</C>.
      </Callout>

      <RefHeader id="send-sms" name="Send Text" chip="Phone call" tone="emerald">
        Sends an SMS to the caller or any number, without interrupting the call.
      </RefHeader>

      <ParamTable
        params={[
          {
            name: 'to',
            type: 'string',
            required: true,
            description: (
              <>
                Recipient in E.164, or a reference such as <C>{'{{caller_number}}'}</C> to
                text the person on the line.
              </>
            ),
          },
          {
            name: 'message',
            type: 'text',
            required: true,
            description: (
              <>
                The message body. Use <C>{'{{parameter}}'}</C> tokens for anything the agent
                collected.
              </>
            ),
          },
        ]}
      />

      <CodeBlock
        language="A confirmation text"
        code={`Parameters
  name          string   "The caller's first name"                required
  date          string   "The confirmed appointment date"         required
  time          string   "The confirmed appointment time"         required

To               {{caller_number}}
Message          Hi {{name}}, your appointment is confirmed for
                 {{date}} at {{time}}. Reply CANCEL to cancel.`}
      />

      <Callout kind="tip" title="Texting beats spelling">
        Reference numbers, addresses, and links are painful to convey by voice and trivial to
        send by SMS. An agent that says &ldquo;I&rsquo;ve just texted you the details&rdquo;
        is faster and more accurate than one spelling out a postcode.
      </Callout>
      <Callout kind="warning" title="Requires SMS capability">
        The sending number must have SMS enabled at the carrier. Check the number&rsquo;s
        capabilities under <A href="/docs/phone-numbers#configuration">Phone Numbers</A>.
      </Callout>

      <RefHeader id="sip-request" name="SIP Request" chip="Phone call · Advanced" tone="emerald">
        Issues a raw SIP request. For telephony engineers integrating with existing SIP
        infrastructure.
      </RefHeader>

      <ParamTable
        params={[
          {
            name: 'sip_uri',
            type: 'string',
            required: true,
            description: <>The target, e.g. <C>sip:user@domain.com</C>.</>,
          },
          {
            name: 'method',
            type: 'enum',
            default: 'INVITE',
            description: (
              <>
                <C>INVITE</C> initiates a session, <C>BYE</C> terminates one, <C>REFER</C>{' '}
                transfers.
              </>
            ),
          },
        ]}
      />

      <Callout kind="note" title="Use the higher-level tools first">
        Transfer Call covers ordinary transfers, including to SIP addresses. Reach for SIP
        Request only when you need protocol-level control that Transfer Call does not expose.
      </Callout>

      <H2 id="summary">At a glance</H2>
      <Table
        dense
        headers={['Tool', 'Ends the call?', 'Needs']}
        widths={['w-[26%]', 'w-[20%]']}
        rows={[
          [<Strong>Transfer Call</Strong>, 'Yes — hands it over', 'A destination'],
          [<Strong>Hang Up</Strong>, 'Yes', 'Nothing'],
          [<Strong>Leave Voicemail</Strong>, 'Usually', 'A message'],
          [<Strong>DTMF</Strong>, 'No', 'Digits'],
          [<Strong>Send Text</Strong>, 'No', 'SMS-capable number'],
          [<Strong>SIP Request</Strong>, 'Depends on method', 'SIP infrastructure'],
        ]}
      />
    </DocPage>
  )
}
