import { DocPage, docMetadata } from '@/components/docs/DocPage'
import {
  A, C, Callout, H2, LI, P, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/workspace/billing')

export default function BillingPage() {
  return (
    <DocPage href="/docs/workspace/billing">
      <H2 id="free-trial">The free trial</H2>
      <P>
        A trial starts without a card and gives you a working workspace — build agents, run
        workflows, connect integrations, and place calls.
      </P>
      <UL>
        <LI>No payment details required to start.</LI>
        <LI>Attached to a plan, so you experience that plan&rsquo;s limits.</LI>
        <LI>
          <Strong>Once per account.</Strong> The restriction is checked against more than one
          signal, so a second workspace or a new email will not reset it.
        </LI>
        <LI>Converting to a paid plan carries your work over — nothing is rebuilt.</LI>
      </UL>
      <Callout kind="tip" title="Use the trial to reach one real call">
        The trial is most valuable if you get all the way to a phone call rather than stopping
        at a configured agent. Buying a number is the one step that costs money separately —
        do it early so the rest of the trial is spent on the thing that matters.
      </Callout>

      <H2 id="plans">Plans and entitlements</H2>
      <P>
        Plans differ across the dimensions that actually constrain a voice platform:
      </P>
      <Table
        headers={['Dimension', 'What it limits']}
        widths={['w-[26%]']}
        rows={[
          ['Call minutes', 'How much talking your agents can do in a period.'],
          ['Agents', 'How many you may have configured at once.'],
          ['Phone numbers', 'How many numbers the workspace may hold.'],
          ['Workflow executions', 'How many runs per period.'],
          ['Knowledge base storage', 'Total documents or volume indexed.'],
          ['Team seats', 'How many people may be members.'],
          ['Integrations', 'Whether premium connectors are available.'],
        ]}
      />
      <P>
        Your current entitlements are shown under <Strong>Settings</Strong> →{' '}
        <Strong>Billing</Strong>, alongside what you have used.
      </P>

      <H2 id="usage">Usage and limits</H2>
      <P>
        Usage accrues through the billing period and resets at its start. The billing page
        shows consumption against each entitlement.
      </P>
      <UL>
        <LI>Approaching a limit is surfaced before you hit it.</LI>
        <LI>Exceeding one restricts the relevant capability — calls stop connecting, or workflows stop running.</LI>
        <LI>Upgrading takes effect immediately and lifts the restriction.</LI>
      </UL>
      <Callout kind="warning" title="Call minutes run out mid-conversation">
        The most disruptive limit to hit is minutes, because it affects live callers rather
        than a background job. Watch it during a campaign, and set{' '}
        <C>max_call_duration</C> on your agents so a single stuck call cannot consume an
        unreasonable share.
      </Callout>

      <H2 id="changing-plan">Changing or cancelling a plan</H2>
      <Table
        headers={['Action', 'What happens']}
        widths={['w-[22%]']}
        rows={[
          [<Strong>Upgrade</Strong>, 'Effective immediately, with the period prorated.'],
          [<Strong>Downgrade</Strong>, 'Effective at the next period, so you keep what you have paid for. Check you are within the lower plan’s limits first.'],
          [<Strong>Cancel</Strong>, 'Access continues to the end of the paid period, then stops.'],
          [<Strong>Reactivate</Strong>, 'Available after cancelling, restoring the subscription.'],
        ]}
      />
      <Callout kind="warning" title="Downgrade below your usage and something has to give">
        If you hold five phone numbers and move to a plan allowing two, the excess must be
        released. Sort that out before the change takes effect rather than discovering it when
        calls stop arriving.
      </Callout>

      <H2 id="pay-as-you-go">Pay As You Go</H2>
      <P>
        Pay As You Go has no monthly fee. You add credit to a balance, and each call minute is
        paid for from it at the rate shown on the plan card. Nothing renews, and credit you
        have not used does not expire.
      </P>
      <UL>
        <LI>
          <Strong>Starting.</Strong> Choose it under <Strong>Settings</Strong> →{' '}
          <Strong>Billing</Strong> and add credit. The first top-up is what starts the plan,
          whether you are on a free trial, a lapsed plan or a new workspace.
        </LI>
        <LI>
          <Strong>What a call costs.</Strong> Calls are charged per started minute when they
          end. The balance, every top-up and every call charge are listed under{' '}
          <Strong>Balance</Strong> → <Strong>History</Strong>.
        </LI>
        <LI>
          <Strong>Phone numbers.</Strong> A Voicecon number is charged monthly from the same
          balance. If the balance cannot cover it the number is put on hold, and later
          released, exactly as it is when a subscription lapses.
        </LI>
        <LI>
          <Strong>Running out.</Strong> When the balance cannot pay for another minute, new
          calls are not connected, and a call in progress is ended politely when the credit
          set aside for it is used up. You are emailed when the balance runs low and again
          when it runs out.
        </LI>
        <LI>
          <Strong>Auto-recharge.</Strong> Where card payments are taken in the app, you can
          save your card when adding credit and have the balance topped up automatically
          below a level you choose.
        </LI>
      </UL>
      <Table
        headers={['Moving', 'What happens']}
        widths={['w-[34%]']}
        rows={[
          [<Strong>Trial → Pay As You Go</Strong>, 'Takes effect with your first top-up.'],
          [<Strong>Subscription → Pay As You Go</Strong>, 'Takes effect when the period you have paid for ends. Add credit before then so calls keep running. You can change your mind until that date.'],
          [<Strong>Pay As You Go → subscription</Strong>, 'Takes effect at checkout. Your remaining credit is kept.'],
        ]}
      />
      <Callout kind="warning" title="A low balance stops calls, including the one in progress">
        Unlike a subscription, there is no allowance to go over and be billed for later. If
        your agents answer calls you cannot afford to miss, turn on auto-recharge or keep the
        balance comfortably above what a busy day uses.
      </Callout>

      <H2 id="invoices">Invoices</H2>
      <P>
        Invoices are listed under <Strong>Settings</Strong> → <Strong>Billing</Strong> with
        their status and downloadable copies. Payment is handled by Stripe; card details are
        never stored by Voicecon.
      </P>
      <P>
        Subscription events — upgrades, downgrades, renewals, failed payments — are recorded,
        which is what to consult when a charge is not what you expected.
      </P>

      <H2 id="what-costs-money">What a call costs</H2>
      <P>
        Two separate bills are involved, and conflating them causes confusion.
      </P>
      <Table
        headers={['Billed by', 'For']}
        widths={['w-[24%]']}
        rows={[
          [<Strong>Voicecon</Strong>, 'Your plan — the platform, and the minutes it includes.'],
          [<Strong>Your carrier</Strong>, 'Phone numbers (monthly) and call minutes (per minute), directly on your Twilio or Telnyx account.'],
          [<Strong>Your AI providers</Strong>, 'Model, transcription, and speech usage — when you bring your own API keys.'],
        ]}
      />
      <P>
        Per-call cost, split across transcription, model, speech, and telephony, is shown on
        every call record. See <A href="/docs/calls#costs">Cost breakdown</A>. Aggregates are
        in <A href="/docs/analytics">Analytics</A>.
      </P>
      <Callout kind="tip" title="The cheapest optimisation is a shorter reply">
        Model and speech costs both scale with how much the agent says, and callers prefer
        brevity anyway. Asking for shorter replies in the system prompt reduces spend and
        improves the experience at the same time — which is rare.
      </Callout>
    </DocPage>
  )
}
