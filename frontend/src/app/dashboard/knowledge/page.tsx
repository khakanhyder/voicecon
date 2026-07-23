'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { BookOpen, FileText, Plus, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'

interface KnowledgeBase {
  id: string
  name: string
  description: string | null
  embedding_model: string
  chunk_size: number
  document_count: number
  is_active: boolean
  created_at: string
}

export default function KnowledgeBasesPage() {
  const [items, setItems] = useState<KnowledgeBase[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  useEffect(() => {
    fetchAll()
  }, [])

  const fetchAll = async () => {
    try {
      const res = await apiClient.get<KnowledgeBase[]>(API_ENDPOINTS.KNOWLEDGE_BASES)
      setItems(res.data || [])
    } catch (error) {
      console.error('Failed to load knowledge bases:', error)
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
    }
  }

  const handleDelete = async (kb: KnowledgeBase) => {
    if (!confirm(`Delete "${kb.name}"? Its documents and embeddings are removed too.`)) return

    setDeletingId(kb.id)
    try {
      await apiClient.delete(API_ENDPOINTS.KNOWLEDGE_BASE(kb.id))
      setItems((prev) => prev.filter((i) => i.id !== kb.id))
      toast.success('Knowledge base deleted')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setDeletingId(null)
    }
  }

  if (isLoading) {
    return <div className="p-8 text-muted-foreground">Loading knowledge bases...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold">Knowledge Base</h1>
          <p className="text-muted-foreground mt-1">
            Upload documents your agents answer from. Content is split into chunks, embedded,
            and searched by meaning during calls and chats.
          </p>
        </div>
        <Link href="/dashboard/knowledge/new">
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            Create Knowledge Base
          </Button>
        </Link>
      </div>

      {items.length === 0 ? (
        <div className="rounded-lg border bg-card p-12 text-center">
          <BookOpen className="h-10 w-10 mx-auto text-muted-foreground mb-4" />
          <h2 className="text-lg font-semibold">No knowledge bases yet</h2>
          <p className="text-muted-foreground mt-1 mb-6">
            Create one, upload your FAQs or policies, then attach it to an agent.
          </p>
          <Link href="/dashboard/knowledge/new">
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              Create Knowledge Base
            </Button>
          </Link>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {items.map((kb) => (
            <div key={kb.id} className="rounded-lg border bg-card p-6 flex flex-col">
              <div className="flex items-start justify-between gap-2">
                <div className="rounded-md bg-primary/10 p-2">
                  <BookOpen className="h-5 w-5 text-primary" />
                </div>
                <button
                  onClick={() => handleDelete(kb)}
                  disabled={deletingId === kb.id}
                  className="text-muted-foreground hover:text-red-600 p-1"
                  aria-label="Delete knowledge base"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>

              <Link href={`/dashboard/knowledge/${kb.id}`} className="mt-4 flex-1">
                <h3 className="font-semibold text-lg hover:underline">{kb.name}</h3>
                {kb.description && (
                  <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                    {kb.description}
                  </p>
                )}
              </Link>

              <div className="flex items-center justify-between mt-4 pt-4 border-t text-sm">
                <span className="flex items-center gap-1.5 text-muted-foreground">
                  <FileText className="h-4 w-4" />
                  {kb.document_count} {kb.document_count === 1 ? 'document' : 'documents'}
                </span>
                <Link
                  href={`/dashboard/knowledge/${kb.id}`}
                  className="text-primary hover:underline"
                >
                  {kb.document_count === 0 ? 'Upload documents' : 'Manage documents'}
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
