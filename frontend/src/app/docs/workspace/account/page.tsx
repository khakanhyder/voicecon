import { DocPage, docMetadata } from '@/components/docs/DocPage'
import {
  A, Callout, H2, LI, P, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/workspace/account')

export default function AccountPage() {
  return (
    <DocPage href="/docs/workspace/account">
      <H2 id="profile">Profile</H2>
      <P>
        <Strong>Settings</Strong> → <Strong>Profile</Strong> holds your name, email, and
        avatar. Your name appears wherever activity is attributed, so make it recognisable to
        colleagues.
      </P>
      <P>
        Profile details are per person, not per workspace — changing your name updates it
        everywhere you are a member.
      </P>

      <H2 id="password">Password and sign-in</H2>
      <UL>
        <LI>Change your password under <Strong>Profile</Strong>; the current one is required.</LI>
        <LI>Social sign-in is available where configured, letting you use an existing identity provider.</LI>
        <LI>Password reset is available from the sign-in page via a link sent to your email.</LI>
      </UL>
      <Callout kind="tip" title="Use SSO where you can">
        An account tied to your organisation&rsquo;s identity provider is deactivated
        automatically when someone leaves. A standalone password is one more thing to remember
        to revoke.
      </Callout>

      <H2 id="notifications">Notifications</H2>
      <P>
        The bell in the header carries workspace notifications — invitations, integration
        failures, billing events, and workflow errors.
      </P>
      <Table
        headers={['Action', 'Effect']}
        widths={['w-[26%]']}
        rows={[
          [<Strong>Mark as read</Strong>, 'Clears one notification from the unread count.'],
          [<Strong>Mark all as read</Strong>, 'Clears everything.'],
        ]}
      />
      <Callout kind="note" title="Integration failure notices matter most">
        A failed integration is the failure mode most likely to go unnoticed, because calls
        keep working and only the downstream record is missing. Treat those notifications as
        actionable rather than informational.
      </Callout>

      <H2 id="onboarding">Onboarding</H2>
      <P>
        New accounts pass through a short onboarding: company details, then a plan or a free
        trial. Company details inform how the workspace is set up; the plan step decides your
        entitlements.
      </P>
      <UL>
        <LI>Onboarding can be resumed if you leave partway.</LI>
        <LI>Company details are editable later under workspace settings.</LI>
        <LI>
          Starting a trial here is the same trial described in{' '}
          <A href="/docs/workspace/billing#free-trial">Billing</A> — once per account.
        </LI>
      </UL>
    </DocPage>
  )
}
