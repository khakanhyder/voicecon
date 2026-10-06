'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { blogApi } from '@/lib/blog-admin'
import type { BlogCategory } from '@/lib/blog'
import {
  AdminButton,
  Dialog,
  Field,
  PageHeader,
  Table,
  TableState,
  Td,
  Th,
  Tr,
  errorText,
  inputClass,
} from '@/components/admin/ui'
import { useCanWriteBlog } from '@/components/admin/blog/shared'
import { cn } from '@/lib/utils'

type Editing = { id?: string; name: string; slug: string; description: string } | null

export default function BlogCategoriesPage() {
  const qc = useQueryClient()
  const canWrite = useCanWriteBlog()
  const { data, isLoading, error } = useQuery({ queryKey: ['blog', 'categories'], queryFn: blogApi.categories })
  const [editing, setEditing] = useState<Editing>(null)
  const [deleting, setDeleting] = useState<BlogCategory | null>(null)

  const save = useMutation({
    mutationFn: (c: NonNullable<Editing>) => {
      const body = { name: c.name.trim(), slug: c.slug.trim() || undefined, description: c.description.trim() || undefined }
      return c.id ? blogApi.updateCategory(c.id, body) : blogApi.createCategory(body)
    },
    onSuccess: (c) => {
      toast.success(editing?.id ? 'Category updated.' : `Category "${c.name}" created.`)
      qc.invalidateQueries({ queryKey: ['blog'] })
      setEditing(null)
    },
    onError: (e) => toast.error(errorText(e)),
  })
  const remove = useMutation({
    mutationFn: (id: string) => blogApi.deleteCategory(id),
    onSuccess: () => {
      toast.success('Category deleted. Its posts are now uncategorised.')
      qc.invalidateQueries({ queryKey: ['blog'] })
      setDeleting(null)
    },
    onError: (e) => toast.error(errorText(e)),
  })

  return (
    <div>
      <PageHeader
        title="Categories"
        description="Group posts by topic. Readers can filter the blog page by category, and each article links to its category."
        actions={
          canWrite && (
            <AdminButton variant="primary" icon={Plus} onClick={() => setEditing({ name: '', slug: '', description: '' })}>
              Add category
            </AdminButton>
          )
        }
      />

      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <Table>
          <thead>
            <tr>
              <Th>Name</Th>
              <Th>URL</Th>
              <Th>Description</Th>
              <Th className="text-right">Posts</Th>
              {canWrite && <Th className="w-24" />}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            <TableState colSpan={canWrite ? 5 : 4} loading={isLoading} error={error} empty={!data?.length} emptyText="No categories yet." />
            {data?.map((c) => (
              <Tr key={c.id}>
                <Td className="font-medium text-slate-900">{c.name}</Td>
                <Td className="text-xs text-slate-500">/blog?category={c.slug}</Td>
                <Td className="max-w-md truncate text-slate-600">{c.description || <span className="text-slate-400">—</span>}</Td>
                <Td className="text-right tabular-nums">
                  {c.posts > 0 ? (
                    <Link href={`/admin/blog/posts?category_id=${c.id}`} className="font-medium text-brand-700 hover:underline">
                      {c.posts}
                    </Link>
                  ) : (
                    <span className="text-slate-400">0</span>
                  )}
                </Td>
                {canWrite && (
                  <Td>
                    <div className="flex justify-end gap-1">
                      <button
                        type="button"
                        aria-label={`Edit ${c.name}`}
                        onClick={() => setEditing({ id: c.id, name: c.name, slug: c.slug, description: c.description ?? '' })}
                        className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        aria-label={`Delete ${c.name}`}
                        onClick={() => setDeleting(c)}
                        className="rounded-md p-1.5 text-slate-400 hover:bg-rose-50 hover:text-rose-600"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </Td>
                )}
              </Tr>
            ))}
          </tbody>
        </Table>
      </section>

      <Dialog
        open={!!editing}
        onClose={() => !save.isPending && setEditing(null)}
        title={editing?.id ? 'Edit category' : 'Add category'}
        footer={
          <>
            <AdminButton variant="ghost" onClick={() => setEditing(null)} disabled={save.isPending}>
              Cancel
            </AdminButton>
            <AdminButton variant="primary" loading={save.isPending} disabled={!editing?.name.trim()} onClick={() => editing && save.mutate(editing)}>
              {editing?.id ? 'Save' : 'Add category'}
            </AdminButton>
          </>
        }
      >
        {editing && (
          <div className="space-y-4">
            <Field label="Name">
              <input
                autoFocus
                value={editing.name}
                maxLength={80}
                onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                placeholder="e.g. Guides"
                className={inputClass}
              />
            </Field>
            <Field label="URL slug" hint="Optional. Made from the name when empty.">
              <input
                value={editing.slug}
                maxLength={100}
                onChange={(e) => setEditing({ ...editing, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-') })}
                placeholder="guides"
                className={inputClass}
              />
            </Field>
            <Field label="Description" hint="Optional. For your team; not shown on the site yet.">
              <textarea
                value={editing.description}
                maxLength={500}
                rows={3}
                onChange={(e) => setEditing({ ...editing, description: e.target.value })}
                className={cn(inputClass, 'h-auto py-2')}
              />
            </Field>
          </div>
        )}
      </Dialog>

      <Dialog
        open={!!deleting}
        onClose={() => !remove.isPending && setDeleting(null)}
        title={`Delete "${deleting?.name}"?`}
        description={
          deleting?.posts
            ? `Its ${deleting.posts} post${deleting.posts === 1 ? '' : 's'} will stay, without a category.`
            : 'No posts use this category.'
        }
        footer={
          <>
            <AdminButton variant="ghost" onClick={() => setDeleting(null)} disabled={remove.isPending}>
              Cancel
            </AdminButton>
            <AdminButton variant="danger" icon={Trash2} loading={remove.isPending} onClick={() => deleting && remove.mutate(deleting.id)}>
              Delete category
            </AdminButton>
          </>
        }
      />
    </div>
  )
}
