import { DocPage, docMetadata } from '@/components/docs/DocPage'
import {
  A, C, Callout, H2, H3, LI, P, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/analytics')

export default function AnalyticsPage() {
  return (
    <DocPage href="/docs/analytics">
      <H2 id="dashboard">The dashboard</H2>
      <P>
        <Strong>Analytics</Strong> aggregates what your agents have been doing — volume,
        outcomes, performance, and spend — across whatever date range you choose.
      </P>
      <P>
        Individual calls live in <A href="/docs/calls">Calls</A>. Analytics is for the
        patterns: is volume growing, is one agent underperforming, is an integration quietly
        failing.
      </P>

      <H2 id="call-metrics">Call metrics</H2>
      <Table
        headers={['Metric', 'What it tells you']}
        widths={['w-[26%]']}
        rows={[
          ['Total calls', 'Volume over the range, split by inbound and outbound.'],
          ['Completed / missed / failed', 'Outcome mix. A rising failed share is an infrastructure signal, not a quality one.'],
          ['Average duration', 'Longer is not automatically worse — but a sharp change means something shifted.'],
          ['Total and average cost', 'Spend, and cost per call.'],
          ['Sentiment distribution', 'Requires sentiment analysis enabled on the agent.'],
          ['Top intents and topics', 'What people actually call about — often not what you expected.'],
        ]}
      />
      <Callout kind="tip" title="Topics are a roadmap">
        The topic list is the most under-used view here. A subject appearing in a fifth of your
        calls with no tool or knowledge base behind it is the highest-value thing you could
        build next.
      </Callout>

      <H2 id="agent-metrics">Agent metrics</H2>
      <P>
        The same measures, per agent. This is where you compare a prompt change against the
        version it replaced.
      </P>
      <UL>
        <LI><Strong>Calls handled</Strong> and how they ended.</LI>
        <LI><Strong>Average duration</Strong> — a jump often means callers are struggling to be understood.</LI>
        <LI><Strong>Transfer and escalation rate</Strong> — how often the agent gave up.</LI>
        <LI><Strong>Cost per call</Strong> — the practical measure of whether a bigger model was worth it.</LI>
      </UL>
      <Callout kind="note" title="Clone before you experiment">
        To compare two prompts fairly, clone the agent, change one thing, and run both. Editing
        a live agent mid-week leaves you comparing two halves of a week rather than two
        versions.
      </Callout>

      <H2 id="integration-metrics">Integration metrics</H2>
      <P>
        Per-connection request volume, success rate, and latency. Integrations tend to fail
        silently — a workflow keeps running with <C>error_handling</C> set to <C>continue</C>,
        and nobody notices the CRM stopped receiving records.
      </P>
      <UL>
        <LI><Strong>Falling success rate</Strong> — expiring credentials or a changed API.</LI>
        <LI><Strong>Rising latency</Strong> — provider trouble, or you are being throttled.</LI>
        <LI><Strong>Volume dropping to zero</Strong> — something upstream stopped calling it at all.</LI>
      </UL>

      <H2 id="realtime">Real-time view</H2>
      <P>
        Live activity — calls in progress, workflows currently executing, and errors as they
        happen. Useful during a launch, a campaign, or when you have just deployed a change
        and want to watch the first calls land.
      </P>

      <H2 id="interpreting">Interpreting the numbers</H2>

      <H3>Averages hide the problem</H3>
      <P>
        An average duration of four minutes could be every call taking four minutes, or half
        taking one and half taking seven. The second is a much more interesting business. Look
        at distribution before drawing conclusions.
      </P>

      <H3>A short call is not automatically a good call</H3>
      <P>
        Calls get short when the agent resolves things quickly, and also when callers give up.
        Read a sample of short calls before celebrating the number.
      </P>

      <H3>Failed calls are the most actionable metric</H3>
      <P>
        Every other number reflects quality, which is subjective. A failed call is
        unambiguous: someone tried to reach you and could not. Investigate those first.
      </P>

      <H3>Cost per resolved call beats cost per call</H3>
      <P>
        A cheaper model that raises the transfer rate has not saved money — it has moved the
        cost to a person. Measure spend against outcomes, not against volume.
      </P>

      <Callout kind="tip" title="Pick three numbers and watch them weekly">
        Dashboards reward regular attention, not exhaustive analysis. Failed call rate,
        escalation rate, and cost per call cover most of what matters. Everything else is
        there for when one of those three moves.
      </Callout>
    </DocPage>
  )
}
