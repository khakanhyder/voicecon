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
        <Strong>Settings</Strong> → <Strong>Profile</Strong> holds everything about you as a
        person. These details are per account, not per workspace — changing your name updates
        it everywhere you are a member.
      </P>

      <Table
        headers={['Field', 'Notes']}
        widths={['w-[24%]']}
        rows={[
          [
            <Strong>Profile picture</Strong>,
            <>
              Click the circle or drag an image onto it. JPEG, PNG, WebP or GIF, up to 5MB.
              If your picture is already hosted somewhere — a Google account photo, say —
              open <em>Or paste an image URL</em> beneath it instead.
            </>,
          ],
          [
            <Strong>Full name</Strong>,
            'Appears wherever activity is attributed, so make it recognisable to colleagues.',
          ],
          [
            <Strong>Email</Strong>,
            <>
              Read-only. It is your sign-in identity, so changing it needs support.
            </>,
          ],
          [<Strong>Phone number</Strong>, 'Your own contact number. Unrelated to the numbers your agents answer on.'],
          [<Strong>Company</Strong>, 'Free text on your profile.'],
          [<Strong>Bio</Strong>, 'A short description of yourself.'],
          [
            <Strong>Timezone</Strong>,
            <>
              Chosen from a list. Worth setting before you read call logs or schedule
              anything — it is the timezone timestamps are shown in.
            </>,
          ],
        ]}
      />
      <Callout kind="note" title="Two save buttons, two forms">
        The profile fields save together with <Strong>Save Changes</Strong>. The password
        section below is a separate form with its own button — changing your password does not
        save the fields above it, and vice versa.
      </Callout>

      <H2 id="password">Password and sign-in</H2>
      <UL>
        <LI>
          Change your password under <Strong>Profile</Strong> → <Strong>Change Password</Strong>:
          current password, new password, and confirmation.
        </LI>
        <LI>
          If you signed up through a social provider and have never set a password, leave{' '}
          <Strong>Current Password</Strong> blank — setting one this way gives you a second way
          in.
        </LI>
        <LI>Password reset is available from the sign-in page via a link sent to your email.</LI>
      </UL>
      <Callout kind="tip" title="Use SSO where you can">
        An account tied to your organisation&rsquo;s identity provider is deactivated
        automatically when someone leaves. A standalone password is one more thing to remember
        to revoke.
      </Callout>

      <H2 id="deactivating">Deactivating your account</H2>
      <P>
        The danger zone at the bottom of <Strong>Profile</Strong> deactivates your account. It
        signs you out and disables access; support can restore it.
      </P>
      <Callout kind="warning" title="This is about you, not your workspace">
        Deactivating your account does not delete any workspace, and it does not hand your
        workspaces to anyone else. If you own one, transfer ownership first — otherwise you
        leave a workspace nobody can administer. See{' '}
        <A href="/docs/workspace/team#ownership">Transferring ownership</A>. To step out of a
        single workspace while keeping your account, leave it from{' '}
        <A href="/docs/workspace/team#workspace-settings">Workspace settings</A> instead.
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
        <LI>
          The workspace name can be changed afterwards under{' '}
          <A href="/docs/workspace/team#workspace-settings">Workspace settings</A>, and your
          own company field under <Strong>Profile</Strong>. The remaining onboarding answers —
          industry, company size, preferred language — are used to set the workspace up and
          are not editable afterwards from the dashboard.
        </LI>
        <LI>
          Starting a trial here is the same trial described in{' '}
          <A href="/docs/workspace/billing#free-trial">Billing</A> — once per account.
        </LI>
      </UL>
    </DocPage>
  )
}
