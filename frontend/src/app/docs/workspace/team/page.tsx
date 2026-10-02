import { DocPage, docMetadata } from '@/components/docs/DocPage'
import {
  A, C, Callout, H2, H3, LI, P, Strong, Table, UL,
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
          [<Strong key="c0">Owner</Strong>, 'The person who created the workspace. Full control, including billing and deleting the workspace. Exactly one per workspace, and it never changes.'],
          [<Strong key="c0">Admin</Strong>, 'Runs the team day to day, but cannot touch the owner or other admins, change the plan, or delete the workspace.'],
          [<Strong key="c0">Member</Strong>, 'Builds and runs things — agents, workflows, tools, integrations. No team or billing access.'],
          [<Strong key="c0">Viewer</Strong>, 'Read-only. Can see everything, change nothing.'],
        ]}
      />
      <Callout kind="note" title="Why admins cannot do everything">
        Anything that changes who holds power — removing another admin, promoting someone to
        admin, deleting the workspace — belongs to the owner alone. An admin who could remove the
        owner would not really be an admin.
      </Callout>

      <H2 id="permission-matrix">Permission matrix</H2>
      <Table
        dense
        headers={['Capability', 'Owner', 'Admin', 'Member', 'Viewer']}
        widths={['w-[40%]', 'w-[12%]', 'w-[12%]', 'w-[12%]']}
        rows={[
          [<>View agents, calls, workflows, analytics</>, <Y key="c0" />, <Y key="c1" />, <Y key="c2" />, <Y key="c3" />],
          [<>Create and edit agents</>, <Y key="c0" />, <Y key="c1" />, <Y key="c2" />, <N key="c3" />],
          [<>Delete agents</>, <Y key="c0" />, <Y key="c1" />, <Y key="c2" />, <N key="c3" />],
          [<>Create and edit workflows</>, <Y key="c0" />, <Y key="c1" />, <Y key="c2" />, <N key="c3" />],
          [<>Execute workflows</>, <Y key="c0" />, <Y key="c1" />, <Y key="c2" />, <N key="c3" />],
          [<>Create and edit tools</>, <Y key="c0" />, <Y key="c1" />, <Y key="c2" />, <N key="c3" />],
          [<>Manage knowledge bases</>, <Y key="c0" />, <Y key="c1" />, <Y key="c2" />, <N key="c3" />],
          [<>Connect and manage integrations</>, <Y key="c0" />, <Y key="c1" />, <Y key="c2" />, <N key="c3" />],
          [<>Buy and configure phone numbers</>, <Y key="c0" />, <Y key="c1" />, <Y key="c2" />, <N key="c3" />],
          [<>View API keys</>, <Y key="c0" />, <Y key="c1" />, <Y key="c2" />, <N key="c3" />],
          [<>Create and revoke API keys</>, <Y key="c0" />, <Y key="c1" />, <N key="c2" />, <N key="c3" />],
          [<>Invite, remove, and re-role members</>, <Y key="c0" />, <Y key="c1" />, <N key="c2" />, <N key="c3" />],
          [<>Act on another admin or the owner</>, <Y key="c0" />, <N key="c1" />, <N key="c2" />, <N key="c3" />],
          [<>View billing and invoices</>, <Y key="c0" />, <Y key="c1" />, <N key="c2" />, <N key="c3" />],
          [<>Change the plan or payment method</>, <Y key="c0" />, <N key="c1" />, <N key="c2" />, <N key="c3" />],
          [<>Rename the workspace and change settings</>, <Y key="c0" />, <Y key="c1" />, <N key="c2" />, <N key="c3" />],
          [<>Delete the workspace</>, <Y key="c0" />, <N key="c1" />, <N key="c2" />, <N key="c3" />],
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

      <H2 id="workspace-settings">Workspace settings</H2>
      <P>
        <Strong>Settings</Strong> → <Strong>Workspace</Strong> is where the workspace itself
        is administered, as opposed to the people in it. Everyone can open it, because it is
        also where you leave a workspace — but what you can do there depends on your role.
      </P>

      <H3>General</H3>
      <Table
        headers={['Setting', 'What it is', 'Who can change it']}
        widths={['w-[22%]', 'w-[46%]']}
        rows={[
          [
            <Strong key="c0">Name</Strong>,
            <>
              Shown in the workspace switcher and on the invitations you send. Renaming takes
              effect everywhere immediately — no reload needed. Minimum two characters.
            </>,
            'Owner, admin',
          ],
          [
            <Strong key="c0">Workspace ID</Strong>,
            <>
              The workspace&rsquo;s slug. Stable — it does not change when you rename the
              workspace. Quote it when contacting support.
            </>,
            <em key="c1">Read-only</em>,
          ],
          [<Strong key="c0">Your role</Strong>, 'Your role in this workspace, not your role elsewhere.', <em key="c1">Read-only</em>],
          [<Strong key="c0">Members</Strong>, <>How many people are in it. The list itself lives under <Strong>Team</Strong>.</>, <em key="c1">Read-only</em>],
          [<Strong key="c0">Owner</Strong>, 'The owner’s email — who to ask when you need something only an owner can do.', <em key="c1">Read-only</em>],
          [<Strong key="c0">Created</Strong>, 'When the workspace was created.', <em key="c1">Read-only</em>],
        ]}
      />
      <Callout kind="note" title="Renaming is cosmetic; the ID is not">
        The name is a label and can change as often as you like. The workspace ID is what
        identifies the workspace underneath, so anything that referenced it keeps working
        across a rename.
      </Callout>

      <H3>Danger zone</H3>
      <Table
        headers={['Action', 'What happens', 'Who']}
        widths={['w-[20%]', 'w-[50%]']}
        rows={[
          [
            <Strong key="c0">Leave workspace</Strong>,
            <>
              Removes you from it. You lose access to everything inside, and need a fresh
              invitation to return. What you built stays behind.
            </>,
            'Everyone except the owner',
          ],
          [
            <Strong key="c0">Delete workspace</Strong>,
            <>
              Agents, workflows and phone numbers stop working immediately. Call history and
              invoices are kept so your records stay complete. Not undoable from the
              dashboard.
            </>,
            'Owner only',
          ],
        ]}
      />
      <UL>
        <LI>
          <Strong>The owner cannot leave.</Strong> Ownership can&apos;t be handed on, so leaving
          would strand the workspace with nobody able to administer it. The owner&apos;s way
          out is deleting the workspace.
        </LI>
        <LI>
          <Strong>You cannot leave or delete your last workspace.</Strong> You would have
          nowhere to work. Create or join another one first; the page says so rather than
          letting you discover it from an error.
        </LI>
        <LI>
          Both actions ask for confirmation, and both take effect at once — there is no grace
          period and no undo button.
        </LI>
      </UL>
      <Callout kind="danger" title="Deleting takes the phone numbers with it">
        Numbers attached to a deleted workspace stop routing calls. If the number matters,
        release it deliberately or move the work to another workspace before deleting — a
        caller dialling a dead number is the part of this nobody notices until it is too late.
      </Callout>

      <H2 id="ownership">Ownership</H2>
      <P>
        The user who creates a workspace is its owner, permanently. Ownership cannot be
        transferred, shared or assigned.
      </P>
      <UL>
        <LI>There is exactly one owner. Invited people can only be admins, members or viewers.</LI>
        <LI>
          No one — not an admin, and not the owner through the team page — can change the
          owner&apos;s role or remove the owner. The API refuses it however the request is made.
        </LI>
        <LI>
          The owner can change the role of, or remove, anyone else in the workspace, including
          admins.
        </LI>
      </UL>
    </DocPage>
  )
}
