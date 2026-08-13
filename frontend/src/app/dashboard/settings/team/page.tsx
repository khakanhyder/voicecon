'use client'

/**
 * Settings → Team.
 *
 * Renders the current workspace's members and pending invites, and gates every
 * control on the permission set the backend handed back in
 * `GET /workspaces/current`. The gating mirrors the server's rules rather than
 * inventing its own: you can only act on someone strictly below you, only the
 * owner can touch an admin, and ownership moves only through an explicit
 * transfer. The API enforces all of it independently — this just avoids showing
 * buttons that would 403.
 */

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Crown, Mail, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { useAuthStore } from '@/store/authStore'
import { useWorkspaceStore } from '@/store/workspaceStore'
import { PERMISSIONS, workspaceService } from '@/lib/workspace'

import { useConfirm } from '@/hooks/use-confirm'

interface TeamMember {
  id: string
  user_id: string
  name: string | null
  email: string
  role: string
  status: string
  joined_at: string
}

interface Invitation {
  id: string
  email: string
  role: string
  status: string
  invited_by_name: string | null
  expires_at: string
  created_at: string
}

const ROLE_RANK: Record<string, number> = { viewer: 0, member: 1, admin: 2, owner: 3 }

/** Roles that can be handed out. "owner" is never among them — see the transfer flow. */
const ASSIGNABLE_ROLES = ['admin', 'member', 'viewer']

function initials(member: { name: string | null; email: string }) {
  const base = member.name || member.email
  return base
    .split(/[\s@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((n) => n[0]?.toUpperCase())
    .join('')
}

export default function TeamSettingsPage() {
  const { confirm, ConfirmDialog } = useConfirm()
  const { user } = useAuthStore()
  const workspace = useWorkspaceStore((s) => s.current)
  const refreshWorkspace = useWorkspaceStore((s) => s.refresh)

  const [email, setEmail] = useState('')
  const [role, setRole] = useState('member')
  const [inviting, setInviting] = useState(false)
  const [loading, setLoading] = useState(true)
  const [members, setMembers] = useState<TeamMember[]>([])
  const [invitations, setInvitations] = useState<Invitation[]>([])
  const [busyId, setBusyId] = useState<string | null>(null)

  const permissions = workspace?.permissions ?? []
  const canManage = permissions.includes(PERMISSIONS.teamManage)
  const canManageAdmins = permissions.includes(PERMISSIONS.teamManageAdmins)
  const canTransferOwnership = permissions.includes(PERMISSIONS.workspaceTransferOwnership)
  const myRole = workspace?.role ?? 'member'

  const load = async () => {
    // Pending invites are admin-only; a plain member gets a 403 and simply
    // sees the roster without them.
    const [membersRes, invitesRes] = await Promise.allSettled([
      apiClient.get<TeamMember[]>(API_ENDPOINTS.TEAM_MEMBERS),
      apiClient.get<Invitation[]>(API_ENDPOINTS.TEAM_INVITATIONS),
    ])
    if (membersRes.status === 'fulfilled') setMembers(membersRes.value.data)
    else toast.error(getErrorMessage(membersRes.reason))
    setInvitations(invitesRes.status === 'fulfilled' ? invitesRes.value.data : [])
    setLoading(false)
  }

  // Re-read the roster whenever the active workspace changes.
  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspace?.id])

  /** Whether the signed-in user may change or remove `member`. Mirrors `can_act_on`. */
  const canActOn = (member: TeamMember) => {
    if (!canManage) return false
    if (member.user_id === user?.id) return false
    if (ROLE_RANK[member.role] >= ROLE_RANK.admin) return canManageAdmins
    return ROLE_RANK[myRole] > ROLE_RANK[member.role]
  }

  /** Roles this user may hand out. Only an owner can create another admin. */
  const assignableRoles = canManageAdmins
    ? ASSIGNABLE_ROLES
    : ASSIGNABLE_ROLES.filter((r) => ROLE_RANK[r] < ROLE_RANK.admin)

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim()) return
    setInviting(true)
    try {
      await apiClient.post(API_ENDPOINTS.TEAM_INVITE, { email: email.trim(), role })
      toast.success(`Invitation sent to ${email.trim()}`)
      setEmail('')
      setRole('member')
      await load()
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setInviting(false)
    }
  }

  const handleCancelInvite = async (invite: Invitation) => {
    const ok = await confirm({
      title: 'Cancel Invitation',
      description: `Cancel the invitation to ${invite.email}? They will no longer be able to join with this invite.`,
      confirmText: 'Cancel Invitation',
      cancelText: 'Keep Invitation',
      isDestructive: true,
    })
    if (!ok) return
    setBusyId(invite.id)
    try {
      await apiClient.delete(API_ENDPOINTS.TEAM_INVITATION(invite.id))
      toast.success('Invitation canceled')
      await load()
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  const handleRoleChange = async (member: TeamMember, newRole: string) => {
    setBusyId(member.id)
    try {
      await apiClient.patch(API_ENDPOINTS.TEAM_MEMBER(member.id), { role: newRole })
      toast.success('Role updated')
      await load()
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  const handleRemove = async (member: TeamMember) => {
    const ok = await confirm({
      title: 'Remove Member',
      description: `Remove ${member.name || member.email} from the team? They will immediately lose access to this workspace.`,
      confirmText: 'Remove',
      isDestructive: true,
    })
    if (!ok) return
    setBusyId(member.id)
    try {
      await apiClient.delete(API_ENDPOINTS.TEAM_MEMBER(member.id))
      toast.success('Member removed')
      await load()
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  const handleTransferOwnership = async (member: TeamMember) => {
    const confirmed = await confirm({
      title: 'Transfer Ownership',
      description:
        `Make ${member.name || member.email} the owner of ${workspace?.name}? ` +
        `You will become an admin and will no longer be able to manage billing, ` +
        `transfer ownership, or delete the workspace.`,
      confirmText: 'Transfer Ownership',
      isDestructive: true,
    })
    if (!confirmed) return
    setBusyId(member.id)
    try {
      await workspaceService.transferOwnership(member.user_id)
      toast.success(`${member.name || member.email} is now the owner`)
      await Promise.all([load(), refreshWorkspace()])
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="space-y-6">
      {/* Which workspace these members belong to — a user in several needs this */}
      {workspace && (
        <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
          <span>
            Managing <span className="font-semibold text-slate-900">{workspace.name}</span>
          </span>
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium capitalize text-primary">
            You are {workspace.role}
          </span>
        </div>
      )}

      {/* Invite Member */}
      {canManage && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
          <h2 className="text-xl font-semibold">Invite Team Member</h2>
          <form onSubmit={handleInvite} className="flex flex-col sm:flex-row sm:items-end gap-4">
            <div className="flex-1 space-y-2">
              <Label htmlFor="email" className="text-base font-bold text-[#000000] font-poppins block">Email Address</Label>
              <Input
                id="email"
                type="email"
                placeholder="user@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full h-[45px] rounded-xl border border-slate-200 outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 bg-white text-[#000000] font-poppins px-3 text-[14px]" />
            </div>
            <div className="space-y-2 w-full sm:w-auto">
              <Label htmlFor="role" className="text-[14px] font-bold text-[#000000] font-poppins block">Role</Label>
              <select
                id="role" className="w-full h-[45px] rounded-xl border border-slate-200 outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 bg-white text-[#000000] font-poppins px-3 text-[14px]"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                {assignableRoles.map((r) => (
                  <option key={r} value={r} className="capitalize">
                    {r}
                  </option>
                ))}
              </select>
            </div>
            <Button type="submit" disabled={inviting} className="w-full sm:w-auto h-[45px]">
              {inviting ? 'Sending…' : 'Send Invite'}
            </Button>
          </form>
          <p className="text-sm text-muted-foreground">
            We&apos;ll email them an invite with Accept/Decline links. If they already have an
            account, they&apos;ll also see it in their notifications.
            {!canManageAdmins && ' Only the workspace owner can invite an admin.'}
          </p>
        </div>
      )}

      {/* Pending Invitations */}
      {canManage && invitations.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
          <h2 className="text-xl font-semibold">
            Pending Invitations
            <span className="ml-2 rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
              {invitations.length}
            </span>
          </h2>
          <div className="space-y-3">
            {invitations.map((invite) => (
              <div
                key={invite.id}
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-2xl border border-dashed border-slate-200 p-4 bg-white"
              >
                <div className="flex items-center gap-4">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-50 text-amber-600">
                    <Mail className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="font-medium break-all">{invite.email}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Invited as <span className="capitalize">{invite.role}</span>
                      {invite.invited_by_name ? ` by ${invite.invited_by_name}` : ''} · expires{' '}
                      {new Date(invite.expires_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <div className="flex flex-row items-center gap-3">
                  <span className="rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700">
                    Pending
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="flex-1 sm:flex-none justify-center"
                    disabled={busyId === invite.id}
                    onClick={() => handleCancelInvite(invite)}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Team Members */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
        <h2 className="text-xl font-semibold">Team Members</h2>

        {loading ? (
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <div key={i} className="h-16 animate-pulse rounded-lg bg-muted" />
            ))}
          </div>
        ) : (
          <div className="space-y-4">
            {members.map((member) => {
              const isOwner = member.role === 'owner'
              const isSelf = member.user_id === user?.id
              const editable = canActOn(member)
              // Only the owner can hand the workspace over, and only to someone
              // who isn't already the owner.
              const showTransfer = canTransferOwnership && !isOwner && !isSelf
              return (
                <div
                  key={member.id}
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-2xl border border-slate-200 p-4 bg-white"
                >
                  <div className="flex items-center gap-4">
                    <div className="h-10 w-10 shrink-0 rounded-full bg-primary/10 flex items-center justify-center text-sm font-semibold text-primary">
                      {initials(member)}
                    </div>
                    <div>
                      <p className="font-semibold break-all flex items-center gap-1.5">
                        {member.name || member.email}
                        {isOwner && <Crown className="h-3.5 w-3.5 text-amber-500" />}
                        {isSelf && <span className="text-sm text-muted-foreground">(you)</span>}
                      </p>
                      <p className="text-base text-muted-foreground break-all mt-0.5">{member.email}</p>
                    </div>
                  </div>
                  <div className="flex flex-wrap sm:flex-nowrap items-center gap-3 sm:gap-4 w-full sm:w-auto">
                    {editable ? (
                      <select className="flex-1 sm:w-auto h-[40px] rounded-xl border border-slate-200 bg-white text-[#000000] font-poppins px-3 text-[14px]"
                        value={member.role}
                        disabled={busyId === member.id}
                        onChange={(e) => handleRoleChange(member, e.target.value)}
                      >
                        {/* Keep the member's current role in the list even if we
                            couldn't have assigned it ourselves. */}
                        {Array.from(new Set([...assignableRoles, member.role])).map((r) => (
                          <option
                            key={r}
                            value={r}
                            className="capitalize"
                            disabled={!assignableRoles.includes(r)}
                          >
                            {r}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <div className="flex-1 sm:flex-none sm:text-right">
                        <p className="text-sm font-medium capitalize">{member.role}</p>
                      </div>
                    )}
                    <span className="text-xs text-muted-foreground sm:w-16 sm:text-right">
                      {member.status}
                    </span>
                    {showTransfer && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="flex-1 sm:flex-none justify-center gap-1.5"
                        disabled={busyId === member.id}
                        onClick={() => handleTransferOwnership(member)}
                        title="Make this person the workspace owner"
                      >
                        <ShieldCheck className="h-4 w-4" />
                        Make owner
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="flex-1 sm:flex-none justify-center"
                      disabled={!editable || busyId === member.id}
                      onClick={() => handleRemove(member)}
                      title={
                        isOwner
                          ? 'The workspace owner cannot be removed — transfer ownership first'
                          : undefined
                      }
                    >
                      {isOwner ? 'Owner' : isSelf ? 'You' : 'Remove'}
                    </Button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Roles & Permissions */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
        <h2 className="text-xl font-semibold">Roles &amp; Permissions</h2>
        <div className="space-y-3">
          {[
            ['Owner', 'Full access. Only the owner can transfer ownership, manage billing, or delete the workspace.'],
            ['Admin', 'Manages members, invites, and API keys, but cannot remove the owner, promote admins, or take ownership.'],
            ['Member', 'Can create and manage agents, workflows, tools, and knowledge bases.'],
            ['Viewer', 'Read-only access to agents, calls, and analytics.'],
          ].map(([name, desc]) => (
            <div key={name} className="flex items-start gap-3">
              <div className="rounded bg-primary/10 px-2 py-1 text-sm font-medium text-primary w-16 text-center">
                {name}
              </div>
              <p className="flex-1 text-base mt-1">{desc}</p>
            </div>
          ))}
        </div>
      </div>
      <ConfirmDialog />
    </div>
  )
}
