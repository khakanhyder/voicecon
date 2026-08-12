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
        <p className="text-black/60 mt-1 font-poppins text-[14px]">
          Step 1 of 2 — name it here, then you&apos;ll land on its page where you upload
          documents (PDF, Word, text) or paste content.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="rounded-2xl border border-slate-200 bg-white p-6 space-y-5">
        <div className="space-y-1.5">
          <Label htmlFor="kb-name" className="text-[14px] font-bold font-poppins text-[#000000] block mb-1">Name</Label>
          <Input
            id="kb-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Support FAQs"
            required
            className="w-full h-[45px] rounded-xl bg-white border border-slate-200 outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 px-3 font-poppins text-[14px] text-black"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="kb-desc" className="text-[14px] font-bold font-poppins text-[#000000] block mb-1">Description (optional)</Label>
          <Textarea
            id="kb-desc"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What kind of content lives in here?"
            rows={3}
            className="w-full rounded-xl bg-white border border-slate-200 p-3 font-poppins text-[14px] text-black"
          />
        </div>

        <div className="rounded-xl bg-slate-50 border border-slate-200 p-3 text-sm text-[#000000] font-poppins">
          Your documents are automatically split and indexed for fast, accurate
          retrieval — nothing else to configure.
        </div>

        <div className="flex gap-3 pt-2">
          <Button type="submit" disabled={isSaving} className="bg-[#106959] text-white hover:opacity-90 rounded-[8px] font-poppins font-medium">
            {isSaving ? 'Creating...' : 'Create & add documents'}
          </Button>
          <Link href="/dashboard/knowledge">
            <Button type="button" variant="outline" className="border border-slate-200 rounded-xl font-poppins font-medium text-black bg-white hover:bg-slate-50">Cancel</Button>
          </Link>
        </div>
      </form>
    </div>
  )
}
