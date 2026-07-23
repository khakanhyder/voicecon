'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'

export default function NewKnowledgeBasePage() {
  const router = useRouter()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      toast.error('Give the knowledge base a name')
      return
    }

    setIsSaving(true)
    try {
      // Chunk size/overlap are intentionally omitted — the backend picks sensible
      // defaults so users don't have to reason about embedding internals.
      const res = await apiClient.post<{ id: string }>(API_ENDPOINTS.KNOWLEDGE_BASES, {
        name: name.trim(),
        description: description.trim() || null,
      })
      toast.success('Knowledge base created')
      router.push(`/dashboard/knowledge/${res.data.id}`)
    } catch (error) {
      console.error('Failed to create knowledge base:', error)
      toast.error(getErrorMessage(error))
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <Link
        href="/dashboard/knowledge"
        className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4 mr-1.5" />
        Back to Knowledge Base
      </Link>

      <div>
        <h1 className="text-3xl font-bold">Create Knowledge Base</h1>
        <p className="text-muted-foreground mt-1">
          Step 1 of 2 — name it here, then you&apos;ll land on its page where you upload
          documents (PDF, Word, text) or paste content.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="rounded-lg border bg-card p-6 space-y-5">
        <div className="space-y-1.5">
          <Label htmlFor="kb-name">Name</Label>
          <Input
            id="kb-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Support FAQs"
            required
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="kb-desc">Description (optional)</Label>
          <Textarea
            id="kb-desc"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What kind of content lives in here?"
            rows={3}
          />
        </div>

        <div className="rounded-md bg-muted/50 p-3 text-sm text-muted-foreground">
          Your documents are automatically split and indexed for fast, accurate
          retrieval — nothing else to configure.
        </div>

        <div className="flex gap-3 pt-2">
          <Button type="submit" disabled={isSaving}>
            {isSaving ? 'Creating...' : 'Create & add documents'}
          </Button>
          <Link href="/dashboard/knowledge">
            <Button type="button" variant="outline">Cancel</Button>
          </Link>
        </div>
      </form>
    </div>
  )
}
