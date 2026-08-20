'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { toast } from 'sonner'
import { AlertTriangle, Users } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { FieldError, errorInputClass, fieldErrorProps } from '@/components/ui/field-error'
import { useConfirm } from '@/hooks/use-confirm'
import { getErrorMessage } from '@/lib/api'
import { PERMISSIONS, workspaceService } from '@/lib/workspace'
import { useWorkspaceStore } from '@/store/workspaceStore'

const fieldClass =
  'w-full h-[45px] rounded-xl border border-slate-200 outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 bg-white text-[#000000] font-poppins px-3 text-[14px]'
const labelClass = 'text-[14px] font-bold text-[#000000] font-poppins block'

const TABS = [
  { value: 'general', label: 'General' },
  { value: 'danger', label: 'Danger Zone' },
] as const

const ROLE_LABELS: Record<string, string> = {
  owner: 'Owner',
  admin: 'Admin',
  member: 'Member',
  viewer: 'Viewer',
}

function ReadOnlyRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-b border-slate-100 py-3 last:border-0">
      <span className="text-sm text-slate-600">{label}</span>
      <span className="text-sm font-semibold text-slate-900">{value}</span>
    </div>
  )
}

/**
 * Settings → Workspace.
 *
 * The home for three endpoints that shipped without one: rename, leave and
 * delete. Every control is gated on the permission the server already
 * enforces, so what is on screen matches what the request would be allowed to
 * do rather than guessing from the role name.
 */
export default function WorkspaceSettingsPage() {
  const { confirm, ConfirmDialog } = useConfirm()
  const current = useWorkspaceStore((s) => s.current)
  const workspaces = useWorkspaceStore((s) => s.workspaces)
  const isLoading = useWorkspaceStore((s) => s.isLoading)
  const refresh = useWorkspaceStore((s) => s.refresh)
  const load = useWorkspaceStore((s) => s.load)
  const can = useWorkspaceStore((s) => s.can)

  const [tab, setTab] = useState<'general' | 'danger'>('general')
  const [name, setName] = useState('')
  const [nameError, setNameError] = useState<string>()
  const [saving, setSaving] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (current) setName(current.name)
  }, [current])

  const canRename = can(PERMISSIONS.workspaceManage)
  const canDelete = can(PERMISSIONS.workspaceDelete)
  // Leaving is for everyone *except* the owner — an owner would strand the
  // workspace, so the server makes them transfer ownership first.
  const canLeave = Boolean(current) && !current?.is_owner
  // The server refuses to delete or leave your last workspace; say so up front
  // rather than letting the user find out from an error.
  const isOnlyWorkspace = workspaces.length <= 1

  const handleRename = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) {
      setNameError('Enter a workspace name')
      return
    }
    if (trimmed.length < 2) {
      setNameError('Workspace name is too short')
      return
    }
    setNameError(undefined)
    setSaving(true)
    try {
      await workspaceService.rename(trimmed)
      // Refresh the store, not just this page: the name shows in the sidebar
      // switcher and the header, which would otherwise keep the old one until
      // a full reload.
      await refresh()
      await load()
      toast.success('Workspace renamed')
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const handleLeave = async () => {
    const ok = await confirm({
      title: `Leave ${current?.name}?`,
      description:
        'You will lose access to this workspace and everything in it. An owner or admin would have to invite you back.',
      confirmText: 'Leave workspace',
      isDestructive: true,
    })
    if (!ok) return

    setBusy(true)
    try {
      await workspaceService.leave()
      toast.success('You have left the workspace')
      // The stored id is gone; a full navigation re-resolves a live workspace.
      window.location.assign('/dashboard')
    } catch (err) {
      toast.error(getErrorMessage(err))
      setBusy(false)
    }
  }

  const handleDelete = async () => {
    const ok = await confirm({
      title: `Delete ${current?.name}?`,
      description:
        'Agents, workflows and phone numbers in this workspace stop working immediately. Call history and invoices are kept for your records. This cannot be undone from the dashboard.',
      confirmText: 'Delete workspace',
      isDestructive: true,
    })
    if (!ok) return

    setBusy(true)
    try {
      await workspaceService.remove()
      toast.success('Workspace deleted')
      window.location.assign('/dashboard')
    } catch (err) {
      toast.error(getErrorMessage(err))
      setBusy(false)
    }
  }

  if (isLoading && !current) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-muted" />
        <div className="h-64 animate-pulse rounded-2xl bg-muted" />
      </div>
    )
  }

  if (!current) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-6">
        <p className="text-sm text-slate-600">
          No workspace is selected. Pick one from the switcher in the sidebar.
        </p>
      </div>
    )
  }

  return (
    <>
      <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)} className="space-y-6">
        <TabsList className="h-auto gap-1 rounded-xl border border-slate-200 bg-slate-50 p-1">
          {TABS.map(({ value, label }) => (
            <TabsTrigger
              key={value}
              value={value}
              className={`rounded-lg px-4 py-2 text-[14px] font-semibold font-poppins transition-all ${
                tab === value
                  ? 'bg-white text-[#0F6A59] shadow-sm'
                  : 'text-slate-500 hover:bg-white/60 hover:text-slate-700'
              }`}
            >
              {label}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="general" className="mt-0 space-y-6">
          <form
            onSubmit={handleRename}
            noValidate
            className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4"
          >
            <div>
              <h2 className="text-xl font-semibold">Workspace Name</h2>
              <p className="mt-1 text-sm text-slate-500">
                {canRename
                  ? 'Shown in the workspace switcher and on invitations you send.'
                  : 'Only workspace owners and admins can rename this workspace.'}
              </p>
            </div>

            <div className="max-w-md space-y-2">
              <Label htmlFor="workspace_name" className={labelClass}>
                Name
              </Label>
              <Input
                id="workspace_name"
                value={name}
                onChange={(e) => {
                  setName(e.target.value)
                  if (nameError) setNameError(undefined)
                }}
                disabled={!canRename || saving}
                {...fieldErrorProps('workspace_name', nameError)}
                className={`${fieldClass} ${nameError ? errorInputClass : ''}`}
              />
              <FieldError id="workspace_name-error" message={nameError} />
            </div>

            {canRename && (
              <Button type="submit" disabled={saving || name.trim() === current.name}>
                {saving ? 'Saving…' : 'Save Changes'}
              </Button>
            )}
          </form>

          <div className="rounded-2xl border border-slate-200 bg-white p-6">
            <h2 className="mb-2 text-xl font-semibold">Details</h2>
            <ReadOnlyRow label="Workspace ID" value={current.slug} />
            <ReadOnlyRow label="Your role" value={ROLE_LABELS[current.role] ?? current.role} />
            <ReadOnlyRow
              label="Members"
              value={`${current.member_count} ${current.member_count === 1 ? 'member' : 'members'}`}
            />
            {current.owner_email && <ReadOnlyRow label="Owner" value={current.owner_email} />}
            <ReadOnlyRow
              label="Created"
              value={new Date(current.created_at).toLocaleDateString('en-GB', {
                day: 'numeric',
                month: 'short',
                year: 'numeric',
              })}
            />
          </div>

          <Link
            href="/dashboard/settings/team"
            className="group flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-6 transition-all hover:border-[#106959]"
          >
            <span className="flex h-12 w-12 items-center justify-center rounded-[10px] bg-[#0F6A59]/10 text-[#106959]">
              <Users className="h-6 w-6" />
            </span>
            <span>
              <span className="block text-[18px] font-bold font-poppins text-[#000000]">
                Members &amp; Roles
              </span>
              <span className="block text-[14px] text-black/60 font-poppins">
                Invite people, change roles, and transfer ownership.
              </span>
            </span>
          </Link>
        </TabsContent>

        <TabsContent value="danger" className="mt-0 space-y-6">
          {!canLeave && !canDelete && (
            <div className="rounded-2xl border border-slate-200 bg-white p-6">
              <p className="text-sm text-slate-600">
                There is nothing here for you. Owners can delete a workspace; everyone
                else can leave one.
              </p>
            </div>
          )}

          {canLeave && (
            <div className="rounded-2xl border border-slate-200 bg-white p-6">
              <h2 className="text-xl font-semibold">Leave Workspace</h2>
              <p className="mt-1 mb-4 text-sm text-slate-500">
                Remove yourself from {current.name}. You will need a new invitation to
                come back.
              </p>
              <Button variant="outline" onClick={handleLeave} disabled={busy}>
                {busy ? 'Working…' : 'Leave Workspace'}
              </Button>
            </div>
          )}

          {canDelete && (
            <div className="rounded-2xl border border-red-200 bg-red-50/40 p-6">
              <div className="flex items-start gap-3">
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-600" />
                <div className="flex-1">
                  <h2 className="text-xl font-semibold text-red-600">Delete Workspace</h2>
                  <p className="mt-1 mb-4 text-sm text-slate-600">
                    Agents, workflows and phone numbers stop working immediately. Call
                    history and invoices are kept so your records stay complete.
                  </p>

                  {isOnlyWorkspace ? (
                    <p className="text-sm font-medium text-slate-500">
                      This is your only workspace, so it cannot be deleted — you would
                      have nowhere to work. Create another one first.
                    </p>
                  ) : (
                    <Button variant="destructive" onClick={handleDelete} disabled={busy}>
                      {busy ? 'Deleting…' : 'Delete Workspace'}
                    </Button>
                  )}
                </div>
              </div>
            </div>
          )}
        </TabsContent>
      </Tabs>
      <ConfirmDialog />
    </>
  )
}
