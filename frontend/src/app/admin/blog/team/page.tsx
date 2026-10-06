'use client'

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Copy, Eye, PenLine, ShieldCheck, Trash2, UserPlus, Wand2 } from 'lucide-react'
import { blogApi } from '@/lib/blog-admin'
import { ROLE_LABELS, type BlogTeamMember } from '@/lib/blog'
import {
  AdminButton,
  Badge,
  Callout,
  Dialog,
  Field,
  PageHeader,
  Table,
  TableState,
  Td,
  Th,
  Tr,
  errorText,
  formatDate,
  inputClass,
} from '@/components/admin/ui'
import { RelativeTime } from '@/components/ui/relative-time'
import { cn } from '@/lib/utils'

/**
 * Who can work on the blog (platform admins only). Blog editors and viewers
 * sign in at /admin/login like admins, but the console shows them only the
 * blog section and the API refuses everything else.
 */

const ROLES = [
  {
    value: 'editor' as const,
    label: 'Blog Editor',
    icon: PenLine,
    description: 'Create, edit, publish, unpublish and delete posts; manage categories.',
  },
  {
    value: 'viewer' as const,
    label: 'Blog Viewer',
    icon: Eye,
    description: 'Read posts, drafts and the blog dashboard. Cannot change anything.',
  },
]

function generatePassword(): string {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789'
  const bytes = new Uint32Array(14)
  crypto.getRandomValues(bytes)
  const body = Array.from(bytes, (b) => chars[b % chars.length]).join('')
  return `${body.slice(0, 7)}-${body.slice(7)}!`
}

function RoleBadge({ role }: { role: BlogTeamMember['role'] }) {
  const tone = role === 'admin' ? 'brand' : role === 'blog_editor' ? 'info' : 'neutral'
  return <Badge tone={tone}>{ROLE_LABELS[role]}</Badge>
}

export default function BlogTeamPage() {
  const qc = useQueryClient()
  const { data, isLoading, error } = useQuery({ queryKey: ['blog', 'team'], queryFn: blogApi.team })
  const [adding, setAdding] = useState(false)
  const [removing, setRemoving] = useState<BlogTeamMember | null>(null)
  const [form, setForm] = useState({ email: '', full_name: '', role: 'editor' as 'editor' | 'viewer', password: '' })
  const [created, setCreated] = useState<{ email: string; password: string | null } | null>(null)

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['blog', 'team'] })
    qc.invalidateQueries({ queryKey: ['blog', 'authors'] })
  }

  const add = useMutation({
    mutationFn: () =>
      blogApi.addTeamMember({
        email: form.email.trim(),
        full_name: form.full_name.trim() || undefined,
        role: form.role,
        password: form.password || undefined,
      }),
    onSuccess: (member) => {
      refresh()
      setAdding(false)
      setCreated({ email: member.email, password: member.created ? form.password : null })
      setForm({ email: '', full_name: '', role: 'editor', password: '' })
    },
    onError: (e) => toast.error(errorText(e)),
  })
  const changeRole = useMutation({
    mutationFn: ({ id, role }: { id: string; role: 'editor' | 'viewer' }) => blogApi.changeTeamRole(id, role),
    onSuccess: (m) => {
      toast.success(`${m.email} is now a ${ROLE_LABELS[m.role]}.`)
      refresh()
    },
    onError: (e) => toast.error(errorText(e)),
  })
  const remove = useMutation({
    mutationFn: (id: string) => blogApi.removeTeamMember(id),
    onSuccess: () => {
      toast.success('Blog access removed.')
      refresh()
      setRemoving(null)
    },
    onError: (e) => toast.error(errorText(e)),
  })

  const signInUrl = typeof window !== 'undefined' ? `${window.location.origin}/admin/login` : '/admin/login'

  return (
    <div>
      <PageHeader
        title="Blog team"
        description="People who can sign in to the console to work on the blog. They see only the blog section; every other page and API stays admin-only."
        actions={
          <AdminButton variant="primary" icon={UserPlus} onClick={() => setAdding(true)}>
            Add blog user
          </AdminButton>
        }
      />

      <div className="mb-6 grid gap-4 md:grid-cols-3">
        {[
          { icon: ShieldCheck, label: 'Admin', text: 'Platform admins have full blog access, plus this page.' },
          ...ROLES.map((r) => ({ icon: r.icon, label: r.label, text: r.description })),
        ].map((r) => (
          <div key={r.label} className="flex gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
              <r.icon className="h-4 w-4" />
            </span>
            <div>
              <p className="text-sm font-semibold text-slate-900">{r.label}</p>
              <p className="mt-0.5 text-xs leading-relaxed text-slate-500">{r.text}</p>
            </div>
          </div>
        ))}
      </div>

      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <Table>
          <thead>
            <tr>
              <Th>Person</Th>
              <Th>Role</Th>
              <Th className="text-right">Posts</Th>
              <Th>Last sign-in</Th>
              <Th>Added</Th>
              <Th className="w-56" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            <TableState colSpan={6} loading={isLoading} error={error} empty={!data?.length} />
            {data?.map((m) => (
              <Tr key={m.id}>
                <Td>
                  <p className="font-medium text-slate-900">{m.full_name || m.email.split('@')[0]}</p>
                  <p className="text-xs text-slate-500">
                    {m.email}
                    {!m.is_active && <span className="ml-1.5 text-rose-600">· disabled</span>}
                  </p>
                </Td>
                <Td>
                  <RoleBadge role={m.role} />
                </Td>
                <Td className="text-right tabular-nums">{m.posts}</Td>
                <Td className="text-xs text-slate-500">{m.last_login_at ? <RelativeTime value={m.last_login_at} /> : 'Never'}</Td>
                <Td className="text-xs text-slate-500">{formatDate(m.created_at)}</Td>
                <Td>
                  {m.role === 'admin' ? (
                    <span className="text-xs text-slate-400">Managed under Users</span>
                  ) : (
                    <div className="flex items-center justify-end gap-2">
                      <select
                        aria-label={`Role for ${m.email}`}
                        value={m.role === 'blog_editor' ? 'editor' : 'viewer'}
                        disabled={changeRole.isPending}
                        onChange={(e) => changeRole.mutate({ id: m.id, role: e.target.value as 'editor' | 'viewer' })}
                        className={cn(inputClass, 'h-8 w-36 pr-8 text-xs')}
                      >
                        <option value="editor">Blog Editor</option>
                        <option value="viewer">Blog Viewer</option>
                      </select>
                      <button
                        type="button"
                        aria-label={`Remove blog access for ${m.email}`}
                        onClick={() => setRemoving(m)}
                        className="rounded-md p-1.5 text-slate-400 hover:bg-rose-50 hover:text-rose-600"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  )}
                </Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      </section>

      <Dialog
        open={adding}
        onClose={() => !add.isPending && setAdding(false)}
        title="Add a blog user"
        description="Creates an account with the role you choose. If the email already has a Voicecon account, it gets the role and keeps its own password."
        footer={
          <>
            <AdminButton variant="ghost" onClick={() => setAdding(false)} disabled={add.isPending}>
              Cancel
            </AdminButton>
            <AdminButton variant="primary" icon={UserPlus} loading={add.isPending} disabled={!form.email.includes('@')} onClick={() => add.mutate()}>
              Add user
            </AdminButton>
          </>
        }
      >
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Email">
              <input
                autoFocus
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="writer@voicecon.ai"
                className={inputClass}
              />
            </Field>
            <Field label="Full name" hint="Shown as the byline on their posts.">
              <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} placeholder="Jane Doe" className={inputClass} />
            </Field>
          </div>

          <fieldset>
            <legend className="mb-1.5 text-xs font-medium text-slate-700">Role</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              {ROLES.map((r) => (
                <label
                  key={r.value}
                  className={cn(
                    'flex cursor-pointer gap-3 rounded-lg border p-3 transition-colors',
                    form.role === r.value ? 'border-brand-400 bg-brand-50/60 ring-1 ring-brand-200' : 'border-slate-200 hover:bg-slate-50'
                  )}
                >
                  <input
                    type="radio"
                    name="role"
                    value={r.value}
                    checked={form.role === r.value}
                    onChange={() => setForm({ ...form, role: r.value })}
                    className="mt-0.5 text-brand-600 focus:ring-brand-500"
                  />
                  <span>
                    <span className="block text-sm font-medium text-slate-900">{r.label}</span>
                    <span className="mt-0.5 block text-xs text-slate-500">{r.description}</span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          <Field label="Password" hint="Needed for a new account (at least 8 characters, not a common password). Ignored if the email already has an account.">
            <div className="flex gap-2">
              <input
                type="text"
                autoComplete="new-password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                className={cn(inputClass, 'font-mono')}
              />
              <AdminButton icon={Wand2} onClick={() => setForm({ ...form, password: generatePassword() })}>
                Generate
              </AdminButton>
            </div>
          </Field>
        </div>
      </Dialog>

      <Dialog
        open={!!created}
        onClose={() => setCreated(null)}
        title="Blog user added"
        footer={
          <AdminButton variant="primary" onClick={() => setCreated(null)}>
            Done
          </AdminButton>
        }
      >
        {created && (
          <div className="space-y-3 text-sm text-slate-600">
            <p>
              Share these sign-in details with <span className="font-medium text-slate-900">{created.email}</span>. No email is sent
              automatically.
            </p>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 font-mono text-xs leading-6 text-slate-800">
              <div>Sign in: {signInUrl}</div>
              <div>Email: {created.email}</div>
              <div>Password: {created.password ?? '(their existing password)'}</div>
            </div>
            <AdminButton
              icon={Copy}
              onClick={() =>
                navigator.clipboard
                  .writeText(`Sign in: ${signInUrl}\nEmail: ${created.email}\nPassword: ${created.password ?? '(your existing password)'}`)
                  .then(() => toast.success('Copied.'))
                  .catch(() => toast.error('Could not copy. Select the text instead.'))
              }
            >
              Copy details
            </AdminButton>
            {created.password && (
              <Callout tone="info">This password is shown once. They can change it later with &ldquo;Forgot password&rdquo; on the app sign-in page.</Callout>
            )}
          </div>
        )}
      </Dialog>

      <Dialog
        open={!!removing}
        onClose={() => !remove.isPending && setRemoving(null)}
        title={`Remove blog access for ${removing?.email}?`}
        description="They are locked out of the console on their next click. The account and the posts they wrote are kept."
        footer={
          <>
            <AdminButton variant="ghost" onClick={() => setRemoving(null)} disabled={remove.isPending}>
              Cancel
            </AdminButton>
            <AdminButton variant="danger" icon={Trash2} loading={remove.isPending} onClick={() => removing && remove.mutate(removing.id)}>
              Remove access
            </AdminButton>
          </>
        }
      />
    </div>
  )
}
