'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, FileText, Search, Trash2, Upload, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'
import { useConfirm } from '@/hooks/use-confirm'

interface KnowledgeBase {
  id: string
  name: string
  description: string | null
  embedding_model: string
  chunk_size: number
  chunk_overlap: number
  document_count: number
}

interface KBDocument {
  id: string
  title: string
  source_type: string
  file_type: string | null
  file_size: number | null
  processing_status: string
  processing_error: string | null
  total_chunks: number
  created_at: string
}

interface AskSource {
  document_title: string
  content: string
  similarity: number
}

interface AskResult {
  answer: string
  sources: AskSource[]
}

const ACCEPTED = '.txt,.md,.pdf,.docx,.xlsx,.xls,.json,.csv'

function statusStyle(status: string) {
  if (status === 'completed') return 'bg-green-100 text-green-700'
  if (status === 'failed') return 'bg-red-100 text-red-700'
  return 'bg-blue-100 text-blue-700'
}

export default function KnowledgeBaseDetailPage() {
  const params = useParams()
  const router = useRouter()
  const kbId = params.id as string

  const [kb, setKb] = useState<KnowledgeBase | null>(null)
  const [docs, setDocs] = useState<KBDocument[]>([])
  const [isLoading, setIsLoading] = useState(true)
  
  const { confirm, ConfirmDialog } = useConfirm()

  const [isUploading, setIsUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const [pasteTitle, setPasteTitle] = useState('')
  const [pasteBody, setPasteBody] = useState('')
  const [isPasting, setIsPasting] = useState(false)

  const [query, setQuery] = useState('')
  const [answer, setAnswer] = useState<AskResult | null>(null)
  const [isSearching, setIsSearching] = useState(false)
  const [showSources, setShowSources] = useState(false)

  const fetchDocs = useCallback(async () => {
    try {
      const res = await apiClient.get<KBDocument[]>(API_ENDPOINTS.KNOWLEDGE_BASE_DOCUMENTS(kbId))
      setDocs(res.data || [])
      return res.data || []
    } catch (error) {
      console.error('Failed to load documents:', error)
      return []
    }
  }, [kbId])

  useEffect(() => {
    const load = async () => {
      try {
        const res = await apiClient.get<KnowledgeBase>(API_ENDPOINTS.KNOWLEDGE_BASE(kbId))
        setKb(res.data)
        await fetchDocs()
      } catch (error) {
        toast.error(getErrorMessage(error))
        router.push('/dashboard/knowledge')
      } finally {
        setIsLoading(false)
      }
    }
    if (kbId) load()
  }, [kbId, fetchDocs, router])

  // Documents embed in the background, so poll while any are still working.
  useEffect(() => {
    const pending = docs.some((d) => d.processing_status !== 'completed' && d.processing_status !== 'failed')
    if (!pending) return
    const t = setTimeout(fetchDocs, 3000)
    return () => clearTimeout(t)
  }, [docs, fetchDocs])

  const handleUpload = async (file: File) => {
    setIsUploading(true)
    try {
      const form = new FormData()
      form.append('knowledge_base_id', kbId)
      form.append('file', file)
      await apiClient.post(API_ENDPOINTS.KNOWLEDGE_UPLOAD, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      toast.success(`"${file.name}" uploaded — processing now`)
      await fetchDocs()
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const handlePaste = async () => {
    if (!pasteTitle.trim() || !pasteBody.trim()) {
      toast.error('Add a title and some content')
      return
    }
    setIsPasting(true)
    try {
      await apiClient.post(API_ENDPOINTS.KNOWLEDGE_DOCUMENTS, {
        knowledge_base_id: kbId,
        title: pasteTitle.trim(),
        content: pasteBody.trim(),
        source_type: 'text',
      })
      toast.success('Text added — processing now')
      setPasteTitle('')
      setPasteBody('')
      await fetchDocs()
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsPasting(false)
    }
  }


  const handleDownload = async (docId: string, title: string) => {
    try {
      const url = API_ENDPOINTS.KNOWLEDGE_DOCUMENT_DOWNLOAD(docId);
      const token = localStorage.getItem('access_token');
      const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) throw new Error('Download failed');
      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      const dlName = title.toLowerCase().endsWith('.txt') ? title : `${title}.txt`;
      a.download = dlName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);
    } catch (error) {
      toast.error('Failed to download document');
    }
  }

  const getFileMeta = (title: string, mime?: string | null) => {
    const ext = title.split('.').pop()?.toLowerCase() || '';
    if (['pdf'].includes(ext) || (mime && mime.includes('pdf'))) {
      return { label: 'PDF', bg: 'bg-red-500', name: 'PDF Document' };
    } else if (['doc', 'docx'].includes(ext) || (mime && mime.includes('word'))) {
      return { label: 'DOC', bg: 'bg-blue-500', name: 'Word Document' };
    } else if (['xls', 'xlsx'].includes(ext) || (mime && (mime.includes('excel') || mime.includes('spreadsheet')))) {
      return { label: 'XLS', bg: 'bg-green-500', name: 'Excel Spreadsheet' };
    } else if (['csv'].includes(ext)) {
      return { label: 'CSV', bg: 'bg-green-500', name: 'CSV File' };
    } else if (['ppt', 'pptx'].includes(ext) || (mime && mime.includes('powerpoint'))) {
      return { label: 'PPT', bg: 'bg-orange-500', name: 'PowerPoint' };
    } else if (['txt', 'md', 'json'].includes(ext)) {
      return { label: ext.toUpperCase(), bg: 'bg-slate-500', name: 'Text Document' };
    }
    return { label: ext ? ext.substring(0,3).toUpperCase() : 'DOC', bg: 'bg-slate-500', name: mime || 'Document' };
  }

  const handleDeleteDoc = async (doc: KBDocument) => {
    const ok = await confirm({
      title: 'Delete Document',
      description: `Are you sure you want to delete "${doc.title}"? This cannot be undone.`,
      isDestructive: true
    })
    if (!ok) return
    try {
      await apiClient.delete(API_ENDPOINTS.KNOWLEDGE_DOCUMENT(doc.id))
      setDocs((prev) => prev.filter((d) => d.id !== doc.id))
      toast.success('Document deleted')
    } catch (error) {
      toast.error(getErrorMessage(error))
    }
  }

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    setIsSearching(true)
    setShowSources(false)
    try {
      const res = await apiClient.post<AskResult>(API_ENDPOINTS.KNOWLEDGE_ASK, {
        knowledge_base_id: kbId,
        query: query.trim(),
        top_k: 5,
      })
      setAnswer(res.data)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsSearching(false)
    }
  }

  if (isLoading) return <div className="p-8 text-muted-foreground">Loading...</div>
  if (!kb) return null

  const ready = docs.filter((d) => d.processing_status === 'completed').length

  return (
    <div className="space-y-6">
      <Link
        href="/dashboard/knowledge"
        className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4 mr-1.5" />
        Back to Knowledge Base
      </Link>

      <div>
        {kb.description && <p className="text-black/60 font-poppins text-[14px]">{kb.description}</p>}
        <p className="text-[13px] font-poppins text-black/50 mt-1">
          {ready} of {docs.length} document(s) ready · embeddings via {kb.embedding_model} ·
          chunk size {kb.chunk_size}
        </p>
      </div>

      {/* Add content */}
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
          <h2 className="text-xl font-bold font-poppins text-[#000000]">Upload a file</h2>
          <p className="text-sm text-muted-foreground">
            PDF, Word (.docx), Excel (.xlsx), text, Markdown, JSON or CSV. Scanned/image-only PDFs can&apos;t be
            read — they need OCR.
          </p>
          <input
            ref={fileRef}
            type="file"
            accept={ACCEPTED}
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) handleUpload(f)
            }}
          />
          <Button onClick={() => fileRef.current?.click()} disabled={isUploading} className="bg-[#106959] text-white hover:opacity-90 rounded-[8px] font-poppins font-medium h-[45px]">
            <Upload className="h-4 w-4 mr-2" />
            {isUploading ? 'Uploading...' : 'Choose file'}
          </Button>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
          <h2 className="text-xl font-bold font-poppins text-[#000000]">Or paste text</h2>
          <div className="space-y-1.5">
            <Label htmlFor="pt" className="text-[14px] font-bold font-poppins text-[#000000] block mb-1">Title</Label>
            <Input
              id="pt"
              className="w-full h-[45px] rounded-xl bg-white border border-slate-200 outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 px-3 font-poppins text-[14px] text-black"
              value={pasteTitle}
              onChange={(e) => setPasteTitle(e.target.value)}
              placeholder="e.g. Refund policy"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="pb" className="text-[14px] font-bold font-poppins text-[#000000] block mb-1">Content</Label>
            <Textarea
              id="pb"
              className="w-full rounded-xl bg-white border border-slate-200 p-3 font-poppins text-[14px] text-black"
              rows={4}
              value={pasteBody}
              onChange={(e) => setPasteBody(e.target.value)}
              placeholder="Paste the policy, FAQ, or script here..."
            />
          </div>
          <Button onClick={handlePaste} disabled={isPasting} variant="outline" className="border border-slate-200 rounded-xl font-poppins font-medium text-black bg-white hover:bg-slate-50 h-[45px]">
            {isPasting ? 'Adding...' : 'Add text'}
          </Button>
        </div>
      </div>

      {/* Documents */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold font-poppins text-[#000000]">Documents</h2>
          <Button variant="outline" size="sm" onClick={fetchDocs} className="border border-slate-200 rounded-xl font-poppins font-medium text-black bg-white hover:bg-slate-50 h-[40px]">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>

        {docs.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nothing added yet. Upload a file or paste text above.
          </p>
        ) : (
          <div className="space-y-2">
            {docs.map((d) => (
              <div key={d.id} className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-4">
                <div className="flex items-center gap-4 min-w-0 w-full sm:w-auto">
                  {(() => {
                    const meta = getFileMeta(d.title, d.file_type);
                    return (
                      <>
                        <div className={`flex items-center justify-center h-10 w-10 ${meta.bg} rounded text-white shrink-0 font-bold text-xs uppercase`}>
                          {meta.label}
                        </div>
                        <div className="min-w-0">
                          <p className="text-[18px] font-poppins text-[#000000] truncate">{d.title}</p>
                          <p className="text-[12px] font-poppins text-black mt-0.5">
                            {meta.name} • {d.file_size ? `${(d.file_size / 1024).toFixed(2)} KB` : 'Unknown size'}
                          </p>
                          {d.processing_error && (
                            <p className="text-xs text-red-600 mt-1 break-words">{d.processing_error}</p>
                          )}
                        </div>
                      </>
                    );
                  })()}
                </div>
                <div className="flex flex-wrap sm:flex-nowrap items-center gap-3 shrink-0 w-full sm:w-auto">
                  <Button onClick={() => handleDownload(d.id, d.title)} className="flex-1 sm:flex-none bg-[#106959] hover:opacity-90 text-white rounded-[8px] font-poppins font-medium h-[40px] px-6">
                    Download
                  </Button>
                  <Button onClick={() => handleDeleteDoc(d)} className="flex-1 sm:flex-none bg-[#FF0000] hover:bg-red-700 text-white rounded-[8px] font-poppins font-medium h-[40px] px-6">
                    Delete
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Ask tester */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
        <div>
          <h2 className="text-xl font-bold font-poppins text-[#000000]">Ask your knowledge base</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Ask a question the way a caller would. You get the answer your agent would give —
            retrieved from your documents, then written up by the LLM.
          </p>
        </div>

        <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-2">
          <Input
            value={query}
            className="w-full h-[45px] rounded-xl bg-white border border-slate-200 outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 px-3 font-poppins text-[14px] text-black"
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. ask anything that's in the attached documents"
          />
          <Button type="submit" disabled={isSearching} className="w-full sm:w-auto bg-[#106959] text-white hover:opacity-90 rounded-[8px] font-poppins font-medium h-[45px]">
            <Search className="h-4 w-4 mr-2" />
            {isSearching ? 'Thinking...' : 'Ask'}
          </Button>
        </form>

        {answer !== null && (
          <div className="space-y-3">
            {/* The answer the caller would actually hear */}
            <div className="rounded-md border bg-muted/40 p-4">
              <p className="text-xs font-medium text-muted-foreground mb-1.5">Answer</p>
              <p className="text-sm whitespace-pre-wrap">{answer.answer}</p>
            </div>

            {/* The raw passages behind it, on demand */}
            {answer.sources.length > 0 && (
              <div>
                <button
                  onClick={() => setShowSources((s) => !s)}
                  className="text-sm text-primary hover:underline"
                >
                  {showSources ? 'Hide' : 'Show'} sources ({answer.sources.length})
                </button>
                {showSources && (
                  <div className="space-y-2 mt-2">
                    {answer.sources.map((s, i) => (
                      <div key={i} className="rounded-md border p-3">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-medium text-muted-foreground">
                            {s.document_title}
                          </span>
                          <span className="text-xs font-medium">
                            {(s.similarity * 100).toFixed(0)}% match
                          </span>
                        </div>
                        <p className="text-sm">{s.content}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
      <ConfirmDialog />
    </div>
  )
}
