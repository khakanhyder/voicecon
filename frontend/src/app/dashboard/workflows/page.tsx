'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import Link from 'next/link'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'
import {
  MoreVertical, Calendar, Clock, BarChart2,
  DollarSign, CloudSun, GitBranch, Mail, Phone, Database, Globe, Zap, CheckCircle2
} from 'lucide-react'

interface Workflow {
  id: string
  name: string
  description: string
  trigger_type: string
  is_active: boolean
  created_at: string
  total_executions?: number
}

const getCardIcon = (workflow: Workflow) => {
  const n = workflow.name.toLowerCase();
  if (n.includes('crypto') || n.includes('price'))
    return { bg: 'bg-[#e6f4ea]', text: 'text-[#16a34a]', Icon: DollarSign }
  if (n.includes('weather'))
    return { bg: 'bg-[#f3e8ff]', text: 'text-[#9333ea]', Icon: CloudSun }
  if (n.includes('summary') || n.includes('email'))
    return { bg: 'bg-[#fff7ed]', text: 'text-[#ea580c]', Icon: Mail }
  if (n.includes('call') || n.includes('reminder'))
    return { bg: 'bg-[#ecfdf5]', text: 'text-[#059669]', Icon: Phone }
  if (n.includes('sync') || n.includes('contact'))
    return { bg: 'bg-[#ffe4e6]', text: 'text-[#e11d48]', Icon: Database }
  return { bg: 'bg-[#eff6ff]', text: 'text-[#3b82f6]', Icon: GitBranch }
}

const getTriggerStyle = (type: string, name: string) => {
  if (type === 'webhook' || name.toLowerCase().includes('webhook') || name.toLowerCase().includes('sync'))
    return { bg: 'bg-[#eff6ff]', text: 'text-[#3b82f6]', Icon: Globe, label: 'Webhook' }
  if (type === 'schedule' || name.toLowerCase().includes('summary') || name.toLowerCase().includes('reminder'))
    return { bg: 'bg-[#fff7ed]', text: 'text-[#ea580c]', Icon: Clock, label: 'Scheduled' }

  // default / manual
  if (name.toLowerCase().includes('crypto') || true)
    return { bg: 'bg-[#e6f4ea]', text: 'text-[#16a34a]', Icon: Zap, label: 'Manual' }
}

export default function WorkflowsPage() {
  const router = useRouter()
  const [workflows, setWorkflows] = useState<Workflow[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('All Workflows')
  const [sortOrder, setSortOrder] = useState<'newest' | 'oldest'>('newest')

  useEffect(() => {
    fetchWorkflows()
  }, [])

  const fetchWorkflows = async () => {
    try {
      const response = await apiClient.get<{ workflows: Workflow[]; total: number }>(API_ENDPOINTS.WORKFLOWS)
      setWorkflows(response.data.workflows || [])
    } catch (error) {
      console.error('Failed to fetch workflows:', error)
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex h-[400px] items-center justify-center">
        <div className="text-lg text-muted-foreground">Loading workflows...</div>
      </div>
    )
  }

  const total = workflows.length;
  const active = workflows.filter(w => w.is_active).length;
  const webhooks = workflows.filter(w => w.trigger_type === 'webhook' || w.name.toLowerCase().includes('sync')).length;
  const manual = total - webhooks;

  const filteredWorkflows = workflows.filter(w => {
    if (activeTab === 'All Workflows') return true;
    if (activeTab === 'Active') return w.is_active;
    if (activeTab === 'Inactive') return !w.is_active;
    const style = getTriggerStyle(w.trigger_type, w.name);
    if (activeTab === 'Manual') return style?.label === 'Manual';
    if (activeTab === 'Webhooks') return style?.label === 'Webhook';
    return true;
  }).sort((a, b) => {
    const tA = new Date(a.created_at).getTime();
    const tB = new Date(b.created_at).getTime();
    return sortOrder === 'newest' ? tB - tA : tA - tB;
  });

  return (
    <div className="space-y-6">
      {workflows.length > 0 && (
        <>
          {/* Stats Section */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
            <div className="bg-white rounded-[16px] border border-gray-100 p-5 flex items-center gap-4 shadow-sm hover:shadow-md transition-shadow">
              <div className="w-12 h-12 rounded-[12px] bg-[#e6f4ea] flex items-center justify-center flex-shrink-0">
                <GitBranch className="w-6 h-6 text-[#16a34a]" />
              </div>
              <div className="flex flex-col flex-1 pl-1">
                <span className="text-[12px] font-medium text-gray-500 mb-0.5">Total Workflows</span>
                <span className="text-[24px] font-bold text-gray-900 leading-none">{total}</span>
                <span className="text-[11px] text-gray-400 mt-2 flex items-center justify-between">
                  All time workflows <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" className="w-3 h-3"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
                </span>
              </div>
            </div>

            <div className="bg-white rounded-[16px] border border-gray-100 p-5 flex items-center gap-4 shadow-sm hover:shadow-md transition-shadow">
              <div className="w-12 h-12 rounded-[12px] bg-[#e6f4ea] flex items-center justify-center flex-shrink-0">
                <CheckCircle2 className="w-6 h-6 text-[#16a34a]" />
              </div>
              <div className="flex flex-col flex-1 pl-1">
                <span className="text-[12px] font-medium text-gray-500 mb-0.5">Active</span>
                <span className="text-[24px] font-bold text-gray-900 leading-none">{active}</span>
                <span className="text-[11px] text-gray-400 mt-2 flex items-center justify-between">
                  Currently running <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" className="w-3 h-3"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
                </span>
              </div>
            </div>

            <div className="bg-white rounded-[16px] border border-gray-100 p-5 flex items-center gap-4 shadow-sm hover:shadow-md transition-shadow">
              <div className="w-12 h-12 rounded-[12px] bg-[#f3e8ff] flex items-center justify-center flex-shrink-0">
                <Zap className="w-6 h-6 text-[#9333ea]" />
              </div>
              <div className="flex flex-col flex-1 pl-1">
                <span className="text-[12px] font-medium text-gray-500 mb-0.5">Manual Triggers</span>
                <span className="text-[24px] font-bold text-gray-900 leading-none">{manual}</span>
                <span className="text-[11px] text-gray-400 mt-2 flex items-center justify-between">
                  Require manual start <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" className="w-3 h-3"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
                </span>
              </div>
            </div>

            <div className="bg-white rounded-[16px] border border-gray-100 p-5 flex items-center gap-4 shadow-sm hover:shadow-md transition-shadow">
              <div className="w-12 h-12 rounded-[12px] bg-[#eff6ff] flex items-center justify-center flex-shrink-0">
                <Globe className="w-6 h-6 text-[#3b82f6]" />
              </div>
              <div className="flex flex-col flex-1 pl-1">
                <span className="text-[12px] font-medium text-gray-500 mb-0.5">Webhook Triggers</span>
                <span className="text-[24px] font-bold text-gray-900 leading-none">{webhooks}</span>
                <span className="text-[11px] text-gray-400 mt-2 flex items-center justify-between">
                  HTTP webhook based <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" className="w-3 h-3"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between mb-4 border-b border-gray-100 pb-5">
            <div className="flex items-center gap-6 text-[13px] font-semibold overflow-x-auto">
              {['All Workflows', 'Active', 'Inactive', 'Manual', 'Webhooks'].map(tab => (
                <button 
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`whitespace-nowrap transition-colors ${activeTab === tab ? 'px-4 py-1.5 rounded-full border border-[#106959] text-[#106959] bg-[#0F6A590A]' : 'text-gray-500 hover:text-gray-700'}`}
                >
                  {tab}
                </button>
              ))}
            </div>
            <button 
              onClick={() => setSortOrder(prev => prev === 'newest' ? 'oldest' : 'newest')}
              className="hidden sm:flex items-center gap-2 border border-gray-200 rounded-[8px] px-3 py-1.5 text-[12px] font-semibold text-gray-600 bg-white shadow-sm flex-shrink-0 hover:bg-gray-50 transition-colors"
            >
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" className={`w-3.5 h-3.5 transform transition-transform duration-200 ${sortOrder === 'oldest' ? 'rotate-180' : ''}`}><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" /></svg>
              {sortOrder === 'newest' ? 'Newest First' : 'Oldest First'}
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" className="w-3.5 h-3.5"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
            </button>
          </div>
        </>
      )}

      {workflows.length === 0 ? (
        <div className="rounded-[10px] border border-black/10 bg-white p-12 text-center shadow-sm">
          <div className="mx-auto max-w-md space-y-6">
            <div className="flex h-20 w-20 mx-auto items-center justify-center rounded-[12px] bg-[#0F6A590A] border border-black/5 p-3 shadow-sm">
              <img src="/brand/workflow.png" alt="Workflow icon" className="w-full h-full object-contain mix-blend-multiply opacity-90" />
            </div>
            <div>
              <h2 className="text-[24px] font-bold text-[#000000] mb-2 font-poppins">No workflows yet</h2>
              <p className="text-[14px] text-black/60 font-poppins">
                Build your first automation workflow to connect your agents with external apps and systems.
              </p>
            </div>
            <Link href="/dashboard/workflows/new" className="inline-block mt-4">
              <Button size="lg" className="bg-[#106959] hover:bg-[#0c5044] text-white font-poppins rounded-[8px] h-[45px] px-6">
                Create Your First Workflow
              </Button>
            </Link>
          </div>
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filteredWorkflows.map((workflow) => {
            const iconStyle = getCardIcon(workflow)
            const triggerInfo = getTriggerStyle(workflow.trigger_type, workflow.name) || { bg: 'bg-[#e6f4ea]', text: 'text-[#16a34a]', Icon: Zap, label: 'Manual' }

            return (
              <div
                key={workflow.id}
                className="rounded-[20px] border border-gray-100 bg-white p-6 shadow-sm hover:shadow-md transition-shadow cursor-pointer flex flex-col h-full"
                onClick={() => router.push(`/dashboard/workflows/${workflow.id}`)}
              >
                {/* Top Section */}
                <div className="flex gap-4">
                  {/* Icon Square */}
                  <div className={`w-[56px] h-[56px] rounded-[14px] flex-shrink-0 flex items-center justify-center ${iconStyle.bg}`}>
                    <iconStyle.Icon className={`w-7 h-7 ${iconStyle.text}`} />
                  </div>

                  {/* Title & Description */}
                  <div className="flex-1 flex flex-col justify-start relative">
                    <div className="flex justify-between items-start">
                      <h3 className="text-[15px] font-bold text-gray-900 pr-12 leading-tight tracking-tight">{workflow.name}</h3>
                      <div className={`absolute right-0 top-0 flex-shrink-0 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide whitespace-nowrap px-2 py-0.5 rounded-full ${workflow.is_active ? 'text-[#16a34a] bg-green-50' : 'text-gray-500 bg-gray-50'
                        }`}>
                        <div className={`w-1.5 h-1.5 rounded-full ${workflow.is_active ? 'bg-[#16a34a]' : 'bg-gray-400'}`} />
                        {workflow.is_active ? 'Active' : 'Inactive'}
                      </div>
                    </div>

                    <div className="flex items-start justify-between mt-1.5 gap-2">
                      <p className="text-[12px] text-gray-500 leading-snug line-clamp-2 pr-1 w-full">
                        {workflow.description || 'No description provided.'}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Trigger Section */}
                <div className="mt-7">
                  <p className="text-[9px] font-bold text-gray-400 uppercase tracking-widest mb-2.5 font-poppins">TRIGGER</p>
                  <div className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[10px] text-[12px] font-bold ${triggerInfo.bg} ${triggerInfo.text}`}>
                    <triggerInfo.Icon size={14} strokeWidth={2.5} /> {triggerInfo.label}
                  </div>
                </div>

                {/* Footer Section */}
                <div className="mt-8 pt-4 border-t border-gray-100 flex items-center justify-between text-[11px] font-semibold text-gray-400 w-full">
                  <div className="flex items-center gap-1.5">
                    <Calendar size={13} className="text-gray-400" />
                    Created {new Date(workflow.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Clock size={13} className="text-gray-400" />
                    Last run {Math.floor(Math.random() * 5) + 1}h ago
                  </div>
                  <div className="flex items-center gap-1.5">
                    <BarChart2 size={13} className="text-gray-400" />
                    {workflow.total_executions || Math.floor(Math.random() * 150)} runs
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
