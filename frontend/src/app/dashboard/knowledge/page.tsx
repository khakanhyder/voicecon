'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { BookOpen, FileText, Plus, Trash2, LayoutGrid, List, Clock, Database, Eye, Upload, MoreHorizontal } from 'lucide-react'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'
import { ConfirmModal } from '@/components/ui/confirm-modal'

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
  const router = useRouter()
  const [items, setItems] = useState<KnowledgeBase[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [sortBy, setSortBy] = useState('Recently Updated')
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

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

  const handleDelete = async () => {
    if (!deletingId) return
    setIsDeleting(true)
    try {
      await apiClient.delete(API_ENDPOINTS.KNOWLEDGE_BASE(deletingId))
      setItems((prev) => prev.filter((i) => i.id !== deletingId))
      toast.success('Knowledge base deleted')
      setDeletingId(null)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsDeleting(false)
    }
  }

  const getTimeAgo = (dateStr: string) => {
    const diff = Math.max(0, Date.now() - new Date(dateStr).getTime())
    const mins = Math.floor(diff / 60000)
    if (mins < 60) return `${Math.max(1, mins)}m ago`
    const hours = Math.floor(mins / 60)
    if (hours < 24) return `${hours}h ago`
    return `${Math.floor(hours / 24)}d ago`
  }

  const filtered = items
    .filter(i => i.name.toLowerCase().includes(search.toLowerCase()) || i.description?.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      if (sortBy === 'Name') return a.name.localeCompare(b.name)
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    })

  const totalDocs = items.reduce((sum, item) => sum + item.document_count, 0)
  const activeKbs = items.filter(i => i.is_active).length

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex h-20 bg-white rounded-xl border border-slate-200 animate-pulse mb-6"></div>
        <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-white rounded-xl border border-slate-200 p-5 h-[280px] animate-pulse"></div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Stats Header */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-5 flex items-center justify-between shadow-sm">
          <div className="flex items-start gap-4">
            <div className="bg-emerald-50 text-emerald-600 rounded-lg p-3 shrink-0">
              <BookOpen className="w-6 h-6" />
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-500 mb-0.5">Total Libraries</div>
              <div className="text-2xl font-bold text-slate-900 leading-none">{items.length}</div>
              <div className="text-xs text-slate-400 mt-1 flex items-center gap-1.5 hover:text-emerald-500 cursor-pointer transition-colors">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>
                {activeKbs} Active knowledge bases
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5 flex items-center justify-between shadow-sm">
          <div className="flex items-start gap-4">
            <div className="bg-blue-50 text-blue-600 rounded-lg p-3 shrink-0">
              <FileText className="w-6 h-6" />
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-500 mb-0.5">Total Documents</div>
              <div className="text-2xl font-bold text-slate-900 leading-none">{totalDocs}</div>
              <div className="text-xs text-slate-400 mt-1 line-clamp-1">Across all libraries</div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5 flex items-center justify-between shadow-sm">
          <div className="flex items-start gap-4">
            <div className="bg-orange-50 text-orange-600 rounded-lg p-3 shrink-0">
              <Clock className="w-6 h-6" />
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-500 mb-0.5">Last Updated</div>
              <div className="text-xl font-bold text-slate-900 leading-none mt-1">
                {items.length > 0 ? 'Just now' : 'Never'}
              </div>
              <div className="text-xs text-slate-400 mt-1">Recently active libraries</div>
            </div>
          </div>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 py-2">
         {/* We omit tags since we don't have categories */}
         <div className="flex items-center">
            {/* Keeping it empty to push right actions */}
         </div>
         <div className="flex items-center gap-3 shrink-0">
           <select 
             value={sortBy}
             onChange={(e) => setSortBy(e.target.value)}
             className="border border-slate-200 rounded-lg text-sm font-medium text-slate-600 py-2 pl-3 pr-8 outline-none bg-white hover:bg-slate-50 appearance-none cursor-pointer shadow-sm"
           >
             <option value="Recently Updated">Sort by: Recently Updated</option>
             <option value="Name">Sort by: Name</option>
           </select>
           <div className="hidden sm:flex bg-slate-50 rounded-lg p-1 border border-slate-200 items-center">
             <button onClick={() => setViewMode('grid')} className={`rounded p-1.5 transition-colors ${viewMode === 'grid' ? 'bg-white shadow-sm' : 'hover:bg-slate-100'}`}>
                <LayoutGrid className={`w-4 h-4 ${viewMode === 'grid' ? 'text-emerald-600' : 'text-slate-400'}`} />
             </button>
             <button onClick={() => setViewMode('list')} className={`rounded p-1.5 transition-colors ${viewMode === 'list' ? 'bg-white shadow-sm' : 'hover:bg-slate-100'}`}>
                <List className={`w-4 h-4 ${viewMode === 'list' ? 'text-emerald-600' : 'text-slate-400'}`} />
             </button>
           </div>
        </div>
      </div>

      <div className={`grid gap-6 ${viewMode === 'grid' ? 'md:grid-cols-2 xl:grid-cols-3' : 'grid-cols-1'}`}>
        {filtered.map((kb, index) => {
          const colors = [
            'text-emerald-600 bg-emerald-50 border-emerald-100',
            'text-blue-600 bg-blue-50 border-blue-100',
            'text-purple-600 bg-purple-50 border-purple-100',
            'text-orange-600 bg-orange-50 border-orange-100'
          ]
          const colorClass = colors[index % colors.length]
          
          return (
            <div key={kb.id} className={`group bg-white rounded-xl border border-slate-200 flex flex-col justify-between shadow-sm hover:shadow-[0_8px_30px_rgb(0,0,0,0.04)] transition-all overflow-hidden p-5 ${viewMode === 'grid' ? 'min-h-[250px]' : ''}`}>
              <div className="flex flex-col flex-1">
                {/* Header Row */}
                <div className={`flex items-start gap-4 mb-4 ${viewMode === 'list' ? 'items-center gap-6' : ''}`}>
                  <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border ${colorClass} cursor-pointer`} onClick={() => router.push(`/dashboard/knowledge/${kb.id}`)}>
                     <BookOpen className="h-6 w-6" />
                  </div>
                  
                  <div className="flex-1 min-w-0 cursor-pointer" onClick={() => router.push(`/dashboard/knowledge/${kb.id}`)}>
                    <div className="flex items-start justify-between">
                      <h3 className="font-bold text-slate-900 text-lg leading-tight group-hover:text-[#106959] transition-colors truncate">{kb.name}</h3>
                      <div className="shrink-0 flex items-center justify-end pl-2">
                        <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-bold ${kb.is_active ? 'text-emerald-700 bg-emerald-50' : 'text-slate-500 bg-slate-100'}`}>
                          <span className={`h-1.5 w-1.5 rounded-full ${kb.is_active ? 'bg-emerald-500' : 'bg-slate-400'}`}></span>
                          {kb.is_active ? 'Active' : 'Draft'}
                        </span>
                      </div>
                    </div>
                    
                    <p className={`text-sm text-slate-500 mt-1.5 ${viewMode === 'list' ? 'line-clamp-1' : 'line-clamp-2 min-h-[40px]'}`}>
                      {kb.description || 'No description provided.'}
                    </p>
                  </div>
                </div>

                {/* Metadata Row */}
                <div className="flex items-center flex-wrap gap-x-3 gap-y-2 text-xs font-medium text-slate-500 mt-auto">
                  <div className="flex items-center gap-1.5 whitespace-nowrap">
                    <FileText className="w-3.5 h-3.5" />
                    {kb.document_count} doc{kb.document_count !== 1 ? 's' : ''}
                  </div>
                  <div className="w-px h-3 bg-slate-300"></div>
                  <div className="flex items-center gap-1.5 line-clamp-1 break-all w-24 sm:w-auto">
                    <Database className="w-3.5 h-3.5 flex-shrink-0" />
                    <span className="truncate">{kb.embedding_model}</span>
                  </div>
                  <div className="w-px h-3 bg-slate-300"></div>
                  <div className="flex items-center gap-1.5 whitespace-nowrap">
                     <Clock className="w-3.5 h-3.5" />
                     {getTimeAgo(kb.created_at)}
                  </div>
                </div>
              </div>

              {/* Action Buttons Footer */}
              <div className="mt-5 flex flex-wrap items-center gap-2">
                 <button onClick={() => router.push(`/dashboard/knowledge/${kb.id}`)} className="flex-1 flex items-center justify-center gap-1.5 rounded-lg border border-emerald-200 py-1.5 text-xs font-semibold text-emerald-600 hover:bg-emerald-50 transition-colors">
                   <Eye className="w-3.5 h-3.5" /> View
                 </button>
                 <button onClick={() => router.push(`/dashboard/knowledge/${kb.id}`)} className="flex-1 flex items-center justify-center gap-1.5 rounded-lg border border-slate-200 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-colors">
                   <FileText className="w-3.5 h-3.5 shrink-0" /> <span className="truncate">Manage Docs</span>
                 </button>
                 <button onClick={() => router.push(`/dashboard/knowledge/${kb.id}`)} className="flex-1 hidden min-[400px]:flex items-center justify-center gap-1.5 rounded-lg border border-slate-200 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-colors">
                   <Upload className="w-3.5 h-3.5 shrink-0" /> Upload
                 </button>
                 <button onClick={() => setDeletingId(kb.id)} className="flex items-center justify-center rounded-lg border border-slate-200 p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 hover:border-red-200 transition-colors cursor-pointer relative w-8 h-8 group/btn" title="Delete">
                   <MoreHorizontal className="w-4 h-4 absolute group-hover/btn:opacity-0 transition-opacity" />
                   <Trash2 className="w-4 h-4 absolute opacity-0 group-hover/btn:opacity-100 transition-opacity" />
                 </button>
              </div>
            </div>
          )
        })}

        {/* Add another knowledge base card */}
        <Link href="/dashboard/knowledge/new">
          <div className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 bg-slate-50/50 p-8 hover:border-[#0F6A59]/40 hover:bg-[#0F6A59]/5 transition-all group cursor-pointer ${
            viewMode === 'list' ? 'h-[100px] flex-row gap-4' : 'h-full min-h-[250px]'
          }`}>
            <div className={`flex items-center justify-center rounded-full bg-[#0F6A59]/10 transition-colors ${
              viewMode === 'list' ? 'h-10 w-10' : 'h-16 w-16 mb-4'
            }`}>
              <Plus className={`${viewMode === 'list' ? 'h-5 w-5' : 'h-6 w-6'} text-[#0F6A59] transition-colors`} />
            </div>
            {viewMode === 'grid' && (
              <>
                <h3 className="text-lg font-bold text-slate-900 mb-1">Add New Knowledge Base</h3>
                <p className="text-xs font-medium text-slate-500 text-center mb-6 px-4">
                  Create a new library to organize your knowledge sources.
                </p>
              </>
            )}
            <button className={`bg-[#0F6A59] hover:bg-[#0c5044] text-white rounded-[8px] py-2 text-sm font-bold flex items-center gap-2 transition-colors ${
              viewMode === 'list' ? 'px-4 ml-auto' : 'px-5'
            }`}>
               <Plus className="w-4 h-4" /> Create New Library
            </button>
          </div>
        </Link>
      </div>

      <ConfirmModal
        isOpen={!!deletingId}
        title="Delete Knowledge Base"
        description="Are you sure you want to delete this knowledge base? Its documents and embeddings will be removed too."
        confirmText="Delete Knowledge Base"
        cancelText="Cancel"
        isDestructive={true}
        isLoading={isDeleting}
        onConfirm={handleDelete}
        onCancel={() => setDeletingId(null)}
      />
    </div>
  )
}
