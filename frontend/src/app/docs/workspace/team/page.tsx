import { DocPage, docMetadata } from '@/components/docs/DocPage'
import {
  A, C, Callout, H2, LI, P, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/workspace/team')

/** Tick or dash, so the permission matrix scans vertically. */
function Y() {
  return <span className="font-bold text-brand-600">✓</span>
}
function N() {
  return <span className="text-slate-300">—</span>
}

export default function TeamPage() {
  return (
    <DocPage href="/docs/workspace/team">
      <H2 id="workspaces">Workspaces</H2>
      <P>
        A workspace is the tenancy boundary. Every agent, workflow, tool, phone number,
        knowledge base, and call belongs to exactly one, and nothing crosses between them.
      </P>
      <UL>
        <LI>You can belong to several workspaces and switch between them from the switcher in the sidebar.</LI>
        <LI>Your role is per workspace — an admin in one may be a viewer in another.</LI>
        <LI>Billing is per workspace.</LI>
      </UL>
      <Callout kind="tip" title="A workspace per environment">
        Separate workspaces for production and staging is the cleanest way to keep test agents
        away from live phone numbers. The cost is duplicated setup; the benefit is never
        having a test call answered by a customer-facing number.
      </Callout>

      <H2 id="roles">The four roles</H2>
      <P>
        Roles form a strict hierarchy — <C>owner</C> &gt; <C>admin</C> &gt; <C>member</C> &gt;{' '}
        <C>viewer</C> — but permissions are not purely hierarchical. A few capabilities are
        withheld from admins deliberately.
      </P>
      <Table
        headers={['Role', 'In one line']}
        widths={['w-[16%]']}
        rows={[
          [<Strong>Owner</Strong>, 'Full control, including deleting the workspace and transferring ownership. Exactly one per workspace.'],
          [<Strong>Admin</Strong>, 'Everything an owner can do except transfer power or destroy the workspace.'],
          [<Strong>Member</Strong>, 'Builds and runs things — agents, workflows, tools, integrations. No team or billing access.'],
          [<Strong>Viewer</Strong>, 'Read-only. Can see everything, change nothing.'],
        ]}
      />
      <Callout kind="note" title="Why admins cannot do everything">
        Anything that changes who holds power — removing another admin, transferring ownership,
        deleting the workspace — belongs to the owner alone. An admin who could remove the
        owner would not really be an admin.
      </Callout>

      <H2 id="permission-matrix">Permission matrix</H2>
      <Table
        dense
        headers={['Capability', 'Owner', 'Admin', 'Member', 'Viewer']}
        widths={['w-[40%]', 'w-[12%]', 'w-[12%]', 'w-[12%]']}
        rows={[
          [<>View agents, calls, workflows, analytics</>, <Y />, <Y />, <Y />, <Y />],
          [<>Create and edit agents</>, <Y />, <Y />, <Y />, <N />],
          [<>Delete agents</>, <Y />, <Y />, <Y />, <N />],
          [<>Create and edit workflows</>, <Y />, <Y />, <Y />, <N />],
          [<>Execute workflows</>, <Y />, <Y />, <Y />, <N />],
          [<>Create and edit tools</>, <Y />, <Y />, <Y />, <N />],
          [<>Manage knowledge bases</>, <Y />, <Y />, <Y />, <N />],
          [<>Connect and manage integrations</>, <Y />, <Y />, <Y />, <N />],
          [<>Buy and configure phone numbers</>, <Y />, <Y />, <Y />, <N />],
          [<>View API keys</>, <Y />, <Y />, <Y />, <N />],
          [<>Create and revoke API keys</>, <Y />, <Y />, <N />, <N />],
          [<>Invite, remove, and re-role members</>, <Y />, <Y />, <N />, <N />],
          [<>Act on another admin or the owner</>, <Y />, <N />, <N />, <N />],
          [<>View billing and invoices</>, <Y />, <Y />, <N />, <N />],
          [<>Change the plan or payment method</>, <Y />, <N />, <N />, <N />],
          [<>Rename the workspace and change settings</>, <Y />, <Y />, <N />, <N />],
          [<>Transfer ownership</>, <Y />, <N />, <N />, <N />],
          [<>Delete the workspace</>, <Y />, <N />, <N />, <N />],
        ]}
      />

      <H2 id="inviting">Inviting people</H2>
      <P>
        <Strong>Settings</Strong> → <Strong>Team</Strong> → <Strong>Invite</Strong>. Enter an
        email address and choose a role. An invitation link is sent; accepting it adds them to
        the workspace.
      </P>
      <UL>
        <LI>
          Only <C>admin</C>, <C>member</C>, and <C>viewer</C> can be assigned. <C>owner</C> is
          never granted by invitation — it moves only by explicit transfer.
        </LI>
        <LI>Pending invitations are listed and can be revoked before they are accepted.</LI>
        <LI>Someone without an account is prompted to create one as part of accepting.</LI>
      </UL>
      <Callout kind="tip" title="Invite as viewer first">
        For anyone who mainly needs to read transcripts or check analytics — a manager, an
        analyst, a stakeholder — viewer is the right starting point. Promoting later is one
        click; recovering from an accidental deletion is not.
      </Callout>

      <H2 id="changing-roles">Changing roles and removing members</H2>
      <UL>
        <LI>Owners and admins may change a member&rsquo;s role.</LI>
        <LI>Only the owner may act on another admin, or on the owner.</LI>
        <LI>Removing someone revokes access immediately; everything they built stays.</LI>
        <LI>You may leave a workspace yourself — unless you are its owner.</LI>
      </UL>
      <Callout kind="warning" title="Check integrations before removing someone">
        A connection made with an individual&rsquo;s OAuth login can stop working when their
        access is revoked at the provider. Reconnect anything they owned as a service account
        first. See <A href="/docs/integrations#connecting-oauth">Integrations</A>.
      </Callout>

      <H2 id="ownership">Transferring ownership</H2>
      <P>
        The owner may transfer ownership to another member. The recipient becomes owner and
        the previous owner becomes an admin.
      </P>
      <UL>
        <LI>Do this before an owner leaves the organisation, not after.</LI>
        <LI>A workspace whose owner has departed with no transfer needs support intervention.</LI>
        <LI>Ownership cannot be shared — there is exactly one owner.</LI>
      </UL>
    </DocPage>
  )
}
