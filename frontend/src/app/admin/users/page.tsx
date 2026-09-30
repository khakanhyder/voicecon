'use client'

import { useState } from 'react'
import Link from 'next/link'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { BadgeCheck, Ban, Unlock, LogOut, PlayCircle, ShieldCheck, ShieldOff, Trash2 } from 'lucide-react'
import { adminApi, type UserDetail, type UserRow } from '@/lib/admin'
import {
  AdminButton,
  Badge,
  Detail,
  Dialog,
  Drawer,
  FilterSelect,
  PageHeader,
  Pagination,
  SearchInput,
  StatusBadge,
  Table,
  TableState,
  Td,
  Th,
  Tr,
  errorText,
  formatDate,
  humanize,
  initialParam,
} from '@/components/admin/ui'
import { RelativeTime } from '@/components/ui/relative-time'

type Confirm = { title: string; description: string; confirm: string; danger?: boolean; run: () => Promise<unknown> } | null

/** Confirmation step for deleting an account — nothing is deleted until "Delete user" is pressed. */
function DeleteUserDialog({ user, onClose, onDeleted }: { user: UserRow | null; onClose: () => void; onDeleted?: () => void }) {
  const qc = useQueryClient()
  const remove = useMutation({
    mutationFn: (id: string) => adminApi.deleteUser(id),
    onSuccess: (res) => {
      toast.success(
        res.workspaces_deactivated
          ? `User deleted. ${res.workspaces_deactivated} workspace${res.workspaces_deactivated === 1 ? '' : 's'} they owned ${res.workspaces_deactivated === 1 ? 'was' : 'were'} deactivated.`
          : 'User deleted.'
      )
      qc.invalidateQueries({ queryKey: ['admin', 'users'] })
      qc.invalidateQueries({ queryKey: ['admin', 'organizations'] })
      onClose()
      onDeleted?.()
    },
    onError: (e) => toast.error(errorText(e)),
  })

  return (
    <Dialog
      open={!!user}
      onClose={() => !remove.isPending && onClose()}
      title="Delete this user?"
      description={
        <>
          <span className="font-medium text-slate-700">{user?.full_name || user?.email}</span>
          {user?.full_name && <> ({user.email})</>} will be deleted.
        </>
      }
      footer={
        <>
          <AdminButton variant="ghost" onClick={onClose} disabled={remove.isPending}>Cancel</AdminButton>
          <AdminButton variant="danger" icon={Trash2} loading={remove.isPending} onClick={() => user && remove.mutate(user.id)}>
            Delete user
          </AdminButton>
        </>
      }
    >
      <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
        <li>They are signed out everywhere and can no longer sign in.</li>
        <li>Every workspace they own is deactivated and its subscription cancelled.</li>
        <li>They are removed from workspaces they were only a member of.</li>
        <li>Their email is freed, so they could sign up again as a new account.</li>
      </ul>
      <p className="mt-3 text-sm text-slate-500">Calls and invoices are kept for records. This cannot be undone from the console.</p>
    </Dialog>
  )
}

function UserDrawer({ userId, onClose }: { userId: string; onClose: () => void }) {
  const qc = useQueryClient()
  const { data: user, isLoading } = useQuery({ queryKey: ['admin', 'user', userId], queryFn: () => adminApi.user(userId) })
  const [confirm, setConfirm] = useState<Confirm>(null)
  const [deleting, setDeleting] = useState<UserRow | null>(null)

  const act = useMutation({
    mutationFn: (fn: () => Promise<unknown>) => fn(),
    onSuccess: () => {
      toast.success('Done')
      setConfirm(null)
      qc.invalidateQueries({ queryKey: ['admin', 'user', userId] })
      qc.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
    onError: (e) => toast.error(errorText(e)),
  })

  const ask = (c: NonNullable<Confirm>) => setConfirm(c)

  const actions = (u: UserDetail) => (
    <>
      {u.locked_for_seconds > 0 && (
        <AdminButton icon={Unlock} onClick={() => act.mutate(() => adminApi.unlockUser(u.id))}>Unlock sign-in</AdminButton>
      )}
      {!u.is_verified && (
        <AdminButton icon={BadgeCheck} onClick={() => act.mutate(() => adminApi.updateUser(u.id, { is_verified: true }))}>Mark verified</AdminButton>
      )}
      <AdminButton
        icon={LogOut}
        onClick={() => ask({
          title: `Sign ${u.email} out everywhere?`,
          description: 'Every session and refresh token this user holds stops working. They can sign in again.',
          confirm: 'Sign out',
          run: () => adminApi.signOutUser(u.id),
        })}
      >
        Sign out everywhere
      </AdminButton>
      {u.is_platform_admin ? (
        <AdminButton
          icon={ShieldOff}
          onClick={() => ask({
            title: 'Revoke platform admin?',
            description: `${u.email} loses access to this admin console.`,
            confirm: 'Revoke',
            danger: true,
            run: () => adminApi.updateUser(u.id, { is_platform_admin: false }),
          })}
        >
          Revoke admin
        </AdminButton>
      ) : (
        <AdminButton
          icon={ShieldCheck}
          onClick={() => ask({
            title: 'Make this user a platform admin?',
            description: `${u.email} will be able to change provider keys, plans and every customer account. Only grant this to Voicecon staff.`,
            confirm: 'Grant admin',
            danger: true,
            run: () => adminApi.updateUser(u.id, { is_platform_admin: true }),
          })}
        >
          Make admin
        </AdminButton>
      )}
      {u.is_active ? (
        <AdminButton
          variant="danger"
          icon={Ban}
          onClick={() => ask({
            title: `Disable ${u.email}?`,
            description: 'They are signed out immediately and cannot sign in until re-enabled. Their workspaces are unaffected.',
            confirm: 'Disable',
            danger: true,
            run: () => adminApi.updateUser(u.id, { is_active: false }),
          })}
        >
          Disable
        </AdminButton>
      ) : (
        <AdminButton variant="primary" icon={PlayCircle} onClick={() => act.mutate(() => adminApi.updateUser(u.id, { is_active: true }))}>
          Enable
        </AdminButton>
      )}
      {!u.is_platform_admin && (
        <AdminButton variant="danger" icon={Trash2} onClick={() => setDeleting(u)}>Delete</AdminButton>
      )}
    </>
  )

  return (
    <Drawer
      open
      onClose={onClose}
      title={user?.full_name || user?.email || 'User'}
      subtitle={user?.email}
      footer={user ? actions(user) : undefined}
    >
      {isLoading || !user ? (
        <div className="h-40 animate-pulse rounded-lg bg-slate-50" />
      ) : (
        <div className="space-y-6">
          <div className="flex flex-wrap gap-2">
            {user.is_active ? <StatusBadge status="active" /> : <StatusBadge status="failed" label="Disabled" />}
            {user.is_verified ? <Badge tone="success">Email verified</Badge> : <Badge tone="warning">Unverified</Badge>}
            {user.is_platform_admin && <Badge tone="brand">Platform admin</Badge>}
            {user.locked_for_seconds > 0 && <Badge tone="danger">Locked {Math.ceil(user.locked_for_seconds / 60)} min</Badge>}
          </div>
          <dl className="grid grid-cols-2 gap-4">
            <Detail label="Sign-in method">{humanize(user.auth_provider)}</Detail>
            <Detail label="Company">{user.company_name || '—'}</Detail>
            <Detail label="Phone">{user.phone_number || '—'}</Detail>
            <Detail label="Timezone">{user.timezone}</Detail>
            <Detail label="Joined">{formatDate(user.created_at, true)}</Detail>
            <Detail label="Last sign-in">{formatDate(user.last_login_at, true)}</Detail>
          </dl>
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Workspaces</p>
            <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
              {user.memberships.map((m) => (
                <li key={m.organization_id} className="flex items-center justify-between px-3 py-2.5 text-sm">
                  <Link href={`/admin/organizations/${m.organization_id}`} className="font-medium text-slate-800 hover:underline">
                    {m.organization_name}
                    {!m.organization_active && <span className="ml-1 text-xs font-normal text-rose-600">(suspended)</span>}
                  </Link>
                  <Badge>{humanize(m.role)}</Badge>
                </li>
              ))}
              {user.memberships.length === 0 && <li className="px-3 py-3 text-sm text-slate-500">Not a member of any workspace.</li>}
            </ul>
          </div>
        </div>
      )}

      <Dialog
        open={!!confirm}
        onClose={() => setConfirm(null)}
        title={confirm?.title}
        description={confirm?.description}
        footer={
          <>
            <AdminButton variant="ghost" onClick={() => setConfirm(null)}>Cancel</AdminButton>
            <AdminButton variant={confirm?.danger ? 'danger' : 'primary'} loading={act.isPending} onClick={() => confirm && act.mutate(confirm.run)}>
              {confirm?.confirm}
            </AdminButton>
          </>
        }
      />
      <DeleteUserDialog user={deleting} onClose={() => setDeleting(null)} onDeleted={onClose} />
    </Drawer>
  )
}

export default function UsersPage() {
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('')
  const [page, setPage] = useState(1)
  const [open, setOpen] = useState<string>(() => initialParam('focus'))
  const [deleting, setDeleting] = useState<UserRow | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin', 'users', { search, filter, page }],
    queryFn: () => adminApi.users({ search, filter, page, page_size: 25 }),
    placeholderData: keepPreviousData,
  })

  return (
    <>
      <PageHeader title="Users" description="Every account on the platform. Open a user to verify, disable, sign out, delete or grant admin access." />

      <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row">
          <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1) }} placeholder="Search by email, name or company" className="flex-1" />
          <FilterSelect
            label="Filter"
            value={filter}
            onChange={(v) => { setFilter(v); setPage(1) }}
            options={[
              { value: '', label: 'All users' },
              { value: 'active', label: 'Active' },
              { value: 'disabled', label: 'Disabled' },
              { value: 'unverified', label: 'Unverified email' },
              { value: 'admins', label: 'Platform admins' },
            ]}
          />
        </div>
        <Table>
          <thead>
            <tr><Th>User</Th><Th>Status</Th><Th>Sign-in</Th><Th className="text-right">Workspaces</Th><Th>Joined</Th><Th>Last sign-in</Th><Th><span className="sr-only">Actions</span></Th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            <TableState colSpan={7} loading={isLoading} error={error} empty={data?.items.length === 0} emptyText="No users match." />
            {data?.items.map((u) => (
              <Tr key={u.id} onClick={() => setOpen(u.id)}>
                <Td>
                  <p className="font-medium text-slate-900">
                    {u.full_name || '—'}
                    {u.is_platform_admin && <ShieldCheck className="ml-1.5 inline h-3.5 w-3.5 text-brand-600" aria-label="Platform admin" />}
                  </p>
                  <p className="text-xs text-slate-400">{u.email}</p>
                </Td>
                <Td>
                  <div className="flex flex-wrap gap-1">
                    {u.is_active ? <StatusBadge status="active" /> : <StatusBadge status="failed" label="Disabled" />}
                    {!u.is_verified && <Badge tone="warning">Unverified</Badge>}
                    {u.locked_for_seconds > 0 && <Badge tone="danger">Locked</Badge>}
                  </div>
                </Td>
                <Td className="text-slate-500">{humanize(u.auth_provider)}</Td>
                <Td className="text-right tabular-nums">{u.organizations}</Td>
                <Td className="text-slate-500">{formatDate(u.created_at)}</Td>
                <Td className="text-slate-500"><RelativeTime value={u.last_login_at} /></Td>
                <Td className="w-12 text-right">
                  {!u.is_platform_admin && (
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); setDeleting(u) }}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-600"
                      aria-label={`Delete ${u.email}`}
                      title="Delete user"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </Td>
              </Tr>
            ))}
          </tbody>
        </Table>
        {data && data.total > 0 && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />}
      </div>

      {open && <UserDrawer userId={open} onClose={() => setOpen('')} />}
      <DeleteUserDialog user={deleting} onClose={() => setDeleting(null)} />
    </>
  )
}
