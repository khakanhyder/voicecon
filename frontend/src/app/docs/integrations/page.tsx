import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { CodeBlock } from '@/components/docs/CodeBlock'
import {
  A, C, Callout, H2, H3, LI, P, Step, Steps, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/integrations')

export default function IntegrationsPage() {
  return (
    <DocPage href="/docs/integrations">
      <H2 id="connectors-and-connections">Connectors and connections</H2>
      <P>
        Two words that look interchangeable and are not. Getting them straight makes the rest
        of this page obvious.
      </P>
      <Table
        headers={['', 'Connector', 'Connection']}
        widths={['w-[18%]', 'w-[38%]']}
        rows={[
          ['Is', 'The platform’s definition of an app', 'Your authenticated account on that app'],
          ['Carries', 'Base URL, auth type, rate limits, supported actions', 'Encrypted credentials, config, status'],
          ['Created by', 'Voicecon', 'You'],
          ['Example', '“HubSpot”', '“HubSpot — Production” and “HubSpot — Sandbox”'],
        ]}
      />
      <P>
        Tools and workflow nodes point at a <Strong>connection</Strong>, never a connector.
        That is what lets you keep a sandbox and a production account side by side and choose
        between them per node.
      </P>

      <H2 id="connecting-oauth">Connecting with OAuth</H2>
      <P>
        Most apps use OAuth. You are redirected to the provider, you approve access, and you
        come back with a connection already made.
      </P>
      <Steps>
        <Step n={1} title="Choose the app">
          <P>
            <Strong>Integrations</Strong> → browse or search the catalog → <Strong>Connect</Strong>.
          </P>
        </Step>
        <Step n={2} title="Approve on the provider">
          <P>
            Sign in and review the scopes being requested. Approve as the account that should
            own the data your agents create.
          </P>
        </Step>
        <Step n={3} title="Name the connection">
          <P>
            Give it a name that says which account it is — <C>HubSpot — Production</C>. You
            will be picking from this list inside every tool and workflow node.
          </P>
        </Step>
      </Steps>
      <Callout kind="note" title="Token refresh is automatic">
        OAuth access tokens expire. Voicecon stores the refresh token encrypted and renews the
        access token before use, so a connection keeps working without intervention. A
        connection that does stop working has usually had access revoked on the provider side.
      </Callout>
      <Callout kind="warning" title="Connect as a service account where you can">
        A connection made with an individual&rsquo;s login breaks when that person leaves.
        Where the provider supports it, connect as a shared service account.
      </Callout>

      <H2 id="connecting-api-key">Connecting with an API key</H2>
      <P>
        Some apps authenticate with a key or token instead. You paste the credential and it is
        encrypted at rest.
      </P>
      <UL>
        <LI>Create the key in the provider&rsquo;s own settings.</LI>
        <LI>Grant the narrowest scope that covers what your agents need to do.</LI>
        <LI>Paste it into the connection form and save.</LI>
      </UL>
      <P>
        A few connectors need extra fields alongside the key — an account or location
        identifier, a region, a base URL for self-hosted instances. The form asks for whatever
        that connector requires.
      </P>

      <H2 id="testing-a-connection">Testing a connection</H2>
      <P>
        Every connection has a <Strong>Test</Strong> action that makes a real, harmless call
        to the provider and reports back. Run it after connecting, and again first whenever a
        tool or workflow starts failing.
      </P>
      <Table
        headers={['Result', 'Means']}
        widths={['w-[24%]']}
        rows={[
          ['Success', 'Credentials valid and the API reachable.'],
          ['401 / 403', 'Key revoked, token expired beyond refresh, or missing scopes. Reconnect.'],
          ['429', 'Rate limited. The credentials are fine; you are calling too often.'],
          ['5xx', 'The provider is having trouble. Not something you can fix here.'],
        ]}
      />
      <P>
        Connections track consecutive errors and the last error message, so a failing
        connection is visible in the list before someone reports a broken workflow.
      </P>

      <H2 id="actions">Actions and their parameters</H2>
      <P>
        Each connector publishes a set of actions with typed parameter schemas. That schema is
        what makes the rest of the platform work without you writing API glue:
      </P>
      <UL>
        <LI>
          In a <A href="/docs/nodes/actions#action">workflow Integration node</A>, the
          parameter fields are rendered from it.
        </LI>
        <LI>
          In a <A href="/docs/tools/integration#connected-integration">Connected Integration
          tool</A>, the tool&rsquo;s parameters are generated from it — correct names, types,
          and required flags, with no typing.
        </LI>
      </UL>
      <P>
        The full list of actions per app is in the{' '}
        <A href="/docs/integrations/catalog">catalog</A>.
      </P>

      <H2 id="resource-pickers">Resource pickers</H2>
      <P>
        Some parameters refer to something <em>inside</em> the connected account — a Slack
        channel, a Trello board and list, a Google calendar, a ClickUp list, a Monday board, a
        GoHighLevel pipeline. Those fields render a picker that loads the real options from
        your connection rather than making you hunt for an opaque id.
      </P>

      <H3>Pasting a URL</H3>
      <P>
        Most pickers also accept a URL. Paste the link to the board, channel, sheet, or page
        and the id is extracted for you — usually faster than scrolling a long list.
      </P>
      <CodeBlock
        language="URLs that resolve to ids"
        code={`Trello board     https://trello.com/b/AbC12dEf/my-board
Trello card      https://trello.com/c/XyZ98wVu/42-task
Slack channel    https://acme.slack.com/archives/C01ABCDEFGH
Google Sheet     https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMd…/edit
Google Drive     https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQr…/view
Notion page      https://notion.so/Workspace-1a2b3c4d5e6f7890abcdef1234567890
Airtable base    https://airtable.com/appAbCdEfGhIjKlMn/tblXyZ123456789
Monday board     https://acme.monday.com/boards/1234567890
ClickUp list     https://app.clickup.com/v/li/901234567`}
      />

      <H2 id="connection-defaults">Connection defaults</H2>
      <P>
        A connection can carry default destinations — the Slack channel to post to, the Trello
        list to add cards to, the calendar to book on. Leave the matching field blank on a
        node or tool and the default is used.
      </P>
      <UL>
        <LI>
          <Strong>One place to change.</Strong> Move your alerts to a different Slack channel
          by editing the connection, not by opening every workflow that posts there.
        </LI>
        <LI>
          <Strong>Explicit wins.</Strong> A value set on the node always overrides the
          default, so exceptions stay possible.
        </LI>
      </UL>

      <H2 id="health">Rate limits, errors, and health</H2>

      <H3>Rate limiting</H3>
      <P>
        Each connector declares the limits its provider enforces — per minute, per hour, per
        day — and requests are paced to stay inside them. That is why a{' '}
        <A href="/docs/nodes/logic#loop">loop</A> over a large list may run slower than the
        raw API would allow: it is being kept below the ceiling deliberately, rather than
        being throttled and failing.
      </P>

      <H3>Retries</H3>
      <P>
        Failed requests are retried with backoff. Combined with the workflow&rsquo;s own{' '}
        <A href="/docs/workflows/execution#error-handling">retry settings</A>, transient
        provider problems usually resolve without a failed run.
      </P>

      <H3>Logging</H3>
      <P>
        Every call through a connection is logged with method, endpoint, status code,
        duration, and any error. When a workflow reports that an integration failed, the log
        tells you whether the provider rejected the request, and why.
      </P>

      <Callout kind="tip" title="Check the connection before the workflow">
        Most integration failures are credential or permission problems, not graph problems.
        Test the connection first — it takes five seconds and rules out the most likely cause.
      </Callout>
    </DocPage>
  )
}
