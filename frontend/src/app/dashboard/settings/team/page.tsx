'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Mail } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { useAuthStore } from '@/store/authStore'

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

const ASSIGNABLE_ROLES = ['admin', 'member', 'viewer']
const ROLE_RANK: Record<string, number> = { viewer: 0, member: 1, admin: 2, owner: 3 }

function initials(member: TeamMember) {
  const base = member.name || member.email
  return base
    .split(/[\s@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((n) => n[0]?.toUpperCase())
    .join('')
}

export default function TeamSettingsPage() {
  const { user } = useAuthStore()
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('member')
  const [inviting, setInviting] = useState(false)
  const [loading, setLoading] = useState(true)
  const [members, setMembers] = useState<TeamMember[]>([])
  const [invitations, setInvitations] = useState<Invitation[]>([])
  const [busyId, setBusyId] = useState<string | null>(null)

  const load = async () => {
    // Invitations require admin+; tolerate a 403 for regular members.
    const [membersRes, invitesRes] = await Promise.allSettled([
      apiClient.get<TeamMember[]>(API_ENDPOINTS.TEAM_MEMBERS),
      apiClient.get<Invitation[]>(API_ENDPOINTS.TEAM_INVITATIONS),
    ])
    if (membersRes.status === 'fulfilled') setMembers(membersRes.value.data)
    else toast.error(getErrorMessage(membersRes.reason))
    setInvitations(invitesRes.status === 'fulfilled' ? invitesRes.value.data : [])
    setLoading(false)
  }

  useEffect(() => {
    load()
  }, [])

  // Current user's role in this org drives which actions are allowed.
  const myRole = members.find((m) => m.user_id === user?.id)?.role ?? 'member'
  const canManage = ROLE_RANK[myRole] >= ROLE_RANK.admin

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
    if (!confirm(`Cancel the invitation to ${invite.email}?`)) return
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
    if (!confirm(`Remove ${member.name || member.email} from the team?`)) return
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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Team Management</h1>
        <p className="text-muted-foreground">Invite team members and manage permissions</p>
      </div>

      {/* Invite Member */}
      {canManage && (
        <div className="rounded-lg border bg-card p-6 space-y-4">
          <h2 className="text-xl font-semibold">Invite Team Member</h2>
          <form onSubmit={handleInvite} className="flex flex-wrap items-end gap-4">
            <div className="flex-1 min-w-[220px] space-y-2">
              <Label htmlFor="email">Email Address</Label>
              <Input
                id="email"
                type="email"
                placeholder="colleague@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="role">Role</Label>
              <select
                id="role"
                className="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm capitalize focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                {ASSIGNABLE_ROLES.map((r) => (
                  <option key={r} value={r} className="capitalize">
                    {r}
                  </option>
                ))}
              </select>
            </div>
            <Button type="submit" disabled={inviting}>
              {inviting ? 'Sending…' : 'Send Invite'}
            </Button>
          </form>
          <p className="text-xs text-muted-foreground">
            We&apos;ll email them an invite with Accept/Decline links. If they already have an
            account, they&apos;ll also see it in their notifications.
          </p>
        </div>
      )}

      {/* Pending Invitations */}
      {canManage && invitations.length > 0 && (
        <div className="rounded-lg border bg-card p-6 space-y-4">
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
                className="flex items-center justify-between rounded-lg border border-dashed p-4"
              >
                <div className="flex items-center gap-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-amber-50 text-amber-600">
                    <Mail className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="font-medium">{invite.email}</p>
                    <p className="text-xs text-muted-foreground">
                      Invited as <span className="capitalize">{invite.role}</span>
                      {invite.invited_by_name ? ` by ${invite.invited_by_name}` : ''} · expires{' '}
                      {new Date(invite.expires_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700">
                    Pending
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
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
      <div className="rounded-lg border bg-card p-6 space-y-4">
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
              return (
                <div
                  key={member.id}
                  className="flex items-center justify-between rounded-lg border p-4"
                >
                  <div className="flex items-center gap-4">
                    <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center text-sm font-semibold text-primary">
                      {initials(member)}
                    </div>
                    <div>
                      <p className="font-medium">
                        {member.name || member.email}
                        {isSelf && <span className="text-xs text-muted-foreground"> (you)</span>}
                      </p>
                      <p className="text-sm text-muted-foreground">{member.email}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    {canManage && !isOwner ? (
                      <select
                        className="h-9 rounded-md border border-input bg-background px-2 text-sm capitalize focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                        value={member.role}
                        disabled={busyId === member.id}
                        onChange={(e) => handleRoleChange(member, e.target.value)}
                      >
                        {ASSIGNABLE_ROLES.map((r) => (
                          <option key={r} value={r} className="capitalize">
                            {r}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <div className="text-right">
                        <p className="text-sm font-medium capitalize">{member.role}</p>
                      </div>
                    )}
                    <span className="text-xs text-muted-foreground w-16 text-right">
                      {member.status}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={!canManage || isOwner || busyId === member.id}
                      onClick={() => handleRemove(member)}
                    >
                      {isOwner ? 'Owner' : 'Remove'}
                    </Button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Roles & Permissions */}
      <div className="rounded-lg border bg-card p-6 space-y-4">
        <h2 className="text-xl font-semibold">Roles &amp; Permissions</h2>
        <div className="space-y-3">
          {[
            ['Owner', 'Full access to all features and settings'],
            ['Admin', 'Can manage team members and most settings'],
            ['Member', 'Can create and manage agents and workflows'],
            ['Viewer', 'Read-only access to view agents and analytics'],
          ].map(([name, desc]) => (
            <div key={name} className="flex items-start gap-3">
              <div className="rounded bg-primary/10 px-2 py-1 text-xs font-medium text-primary w-16 text-center">
                {name}
              </div>
              <p className="flex-1 text-sm">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
