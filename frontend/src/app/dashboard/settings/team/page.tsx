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


      {/* Invite Member */}
      {canManage && (
        <div className="rounded-[10px] border border-[#000000] bg-white p-6 space-y-4">
          <h2 className="text-xl font-semibold">Invite Team Member</h2>
          <form onSubmit={handleInvite} className="flex flex-col sm:flex-row sm:items-end gap-4">
            <div className="flex-1 space-y-2">
              <Label htmlFor="email" className="text-[14px] font-bold text-[#000000] font-poppins block">Email Address</Label>
              <Input
                id="email"
                type="email"
                placeholder="colleague@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
               className="w-full h-[45px] rounded-[8px] border border-[#000000] bg-[#0F6A590A] text-[#000000] font-poppins px-3 text-[14px]" />
            </div>
            <div className="space-y-2 w-full sm:w-auto">
              <Label htmlFor="role" className="text-[14px] font-bold text-[#000000] font-poppins block">Role</Label>
              <select
                id="role" className="w-full h-[45px] rounded-[8px] border border-[#000000] bg-[#0F6A590A] text-[#000000] font-poppins px-3 text-[14px]"
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
            <Button type="submit" disabled={inviting} className="w-full sm:w-auto h-[45px]">
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
        <div className="rounded-[10px] border border-[#000000] bg-white p-6 space-y-4">
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
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-[10px] border border-dashed border-[#000000] p-4 bg-white"
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
      <div className="rounded-[10px] border border-[#000000] bg-white p-6 space-y-4">
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
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-[10px] border border-[#000000] p-4 bg-white"
                >
                  <div className="flex items-center gap-4">
                    <div className="h-10 w-10 shrink-0 rounded-full bg-primary/10 flex items-center justify-center text-sm font-semibold text-primary">
                      {initials(member)}
                    </div>
                    <div>
                      <p className="font-medium break-all">
                        {member.name || member.email}
                        {isSelf && <span className="text-xs text-muted-foreground"> (you)</span>}
                      </p>
                      <p className="text-sm text-muted-foreground break-all mt-0.5">{member.email}</p>
                    </div>
                  </div>
                  <div className="flex flex-wrap sm:flex-nowrap items-center gap-3 sm:gap-4 w-full sm:w-auto">
                    {canManage && !isOwner ? (
                      <select className="flex-1 sm:w-auto h-[40px] rounded-[8px] border border-[#000000] bg-[#0F6A590A] text-[#000000] font-poppins px-3 text-[14px]"
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
                      <div className="flex-1 sm:flex-none sm:text-right">
                        <p className="text-sm font-medium capitalize">{member.role}</p>
                      </div>
                    )}
                    <span className="text-xs text-muted-foreground sm:w-16 sm:text-right">
                      {member.status}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="flex-1 sm:flex-none justify-center"
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
      <div className="rounded-[10px] border border-[#000000] bg-white p-6 space-y-4">
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
