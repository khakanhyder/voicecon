'use client'

import { useState, useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { Button } from '@/components/ui/button'
import Link from 'next/link'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'

interface Agent {
  id: string
  name: string
  description: string
  llm_provider: string
  llm_model: string
  tts_provider: string
  stt_provider: string
  system_prompt: string
  first_message: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export default function AgentDetailPage() {
  const router = useRouter()
  const params = useParams()
  const agentId = params.id as string

  const [agent, setAgent] = useState<Agent | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isToggling, setIsToggling] = useState(false)

  useEffect(() => {
    if (agentId) {
      fetchAgent()
    }
  }, [agentId])

  const fetchAgent = async () => {
    try {
      const response = await apiClient.get<Agent>(`${API_ENDPOINTS.AGENTS}${agentId}`)
      setAgent(response.data)
    } catch (error) {
      console.error('Failed to fetch agent:', error)
      toast.error(getErrorMessage(error))
      router.push('/dashboard/agents')
    } finally {
      setIsLoading(false)
    }
  }

  const handleToggleActive = async () => {
    if (!agent) return

    setIsToggling(true)
    try {
      const response = await apiClient.patch<Agent>(
        `${API_ENDPOINTS.AGENTS}${agentId}`,
        { is_active: !agent.is_active }
      )
      setAgent(response.data)
      toast.success(`Agent ${response.data.is_active ? 'activated' : 'deactivated'} successfully`)
    } catch (error) {
      console.error('Failed to toggle agent status:', error)
      toast.error(getErrorMessage(error))
    } finally {
      setIsToggling(false)
    }
  }

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this agent? This action cannot be undone.')) {
      return
    }

    setIsDeleting(true)
    try {
      await apiClient.delete(`${API_ENDPOINTS.AGENTS}${agentId}`)
      toast.success('Agent deleted successfully')
      router.push('/dashboard/agents')
    } catch (error) {
      console.error('Failed to delete agent:', error)
      toast.error(getErrorMessage(error))
      setIsDeleting(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex h-[400px] items-center justify-center">
        <div className="text-lg text-muted-foreground">Loading agent...</div>
      </div>
    )
  }

  if (!agent) {
    return (
      <div className="flex h-[400px] items-center justify-center">
        <div className="text-lg text-muted-foreground">Agent not found</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight">{agent.name}</h1>
            <div className={`px-3 py-1 rounded-full text-xs font-medium ${
              agent.is_active
                ? 'bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-400'
                : 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400'
            }`}>
              {agent.is_active ? 'Active' : 'Inactive'}
            </div>
          </div>
          <p className="text-muted-foreground">
            {agent.description || 'No description provided'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={handleToggleActive}
            disabled={isToggling}
          >
            {isToggling ? 'Updating...' : agent.is_active ? 'Deactivate' : 'Activate'}
          </Button>
          <Link href={`/dashboard/agents/${agentId}/edit`}>
            <Button variant="outline">Edit</Button>
          </Link>
          <Button
            variant="destructive"
            onClick={handleDelete}
            disabled={isDeleting}
          >
            {isDeleting ? 'Deleting...' : 'Delete'}
          </Button>
        </div>
      </div>

      {/* Agent Configuration */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* AI Configuration */}
        <div className="rounded-lg border bg-card p-6 space-y-4">
          <h2 className="text-xl font-semibold">AI Configuration</h2>

          <div className="space-y-3">
            <div className="flex justify-between items-center pb-2 border-b">
              <span className="text-sm text-muted-foreground">LLM Provider</span>
              <span className="font-medium capitalize">{agent.llm_provider}</span>
            </div>

            <div className="flex justify-between items-center pb-2 border-b">
              <span className="text-sm text-muted-foreground">LLM Model</span>
              <span className="font-medium">{agent.llm_model}</span>
            </div>

            <div className="flex justify-between items-center pb-2 border-b">
              <span className="text-sm text-muted-foreground">Text-to-Speech</span>
              <span className="font-medium capitalize">{agent.tts_provider}</span>
            </div>

            <div className="flex justify-between items-center pb-2 border-b">
              <span className="text-sm text-muted-foreground">Speech-to-Text</span>
              <span className="font-medium capitalize">{agent.stt_provider}</span>
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="rounded-lg border bg-card p-6 space-y-4">
          <h2 className="text-xl font-semibold">Quick Actions</h2>

          <div className="space-y-2">
            <Link href={`/dashboard/agents/${agentId}/test`} className="block">
              <Button variant="outline" className="w-full justify-start">
                Test Agent
              </Button>
            </Link>

            <Link href={`/dashboard/agents/${agentId}/builder`} className="block">
              <Button variant="outline" className="w-full justify-start">
                Flow Builder
              </Button>
            </Link>

            <Link href={`/dashboard/calls?agent=${agentId}`} className="block">
              <Button variant="outline" className="w-full justify-start">
                View Call History
              </Button>
            </Link>

            <Link href={`/dashboard/analytics?agent=${agentId}`} className="block">
              <Button variant="outline" className="w-full justify-start">
                View Analytics
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* Prompts */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* System Prompt */}
        <div className="rounded-lg border bg-card p-6 space-y-4">
          <div>
            <h2 className="text-xl font-semibold">System Prompt</h2>
            <p className="text-sm text-muted-foreground">Instructions for the AI agent</p>
          </div>

          <div className="rounded-lg bg-muted p-4 font-mono text-sm whitespace-pre-wrap">
            {agent.system_prompt || 'No system prompt configured'}
          </div>
        </div>

        {/* First Message */}
        <div className="rounded-lg border bg-card p-6 space-y-4">
          <div>
            <h2 className="text-xl font-semibold">First Message</h2>
            <p className="text-sm text-muted-foreground">Initial greeting when a call starts</p>
          </div>

          <div className="rounded-lg bg-muted p-4 font-mono text-sm whitespace-pre-wrap">
            {agent.first_message || 'No first message configured'}
          </div>
        </div>
      </div>

      {/* Metadata */}
      <div className="rounded-lg border bg-card p-6 space-y-4">
        <h2 className="text-xl font-semibold">Information</h2>

        <div className="grid gap-4 md:grid-cols-3">
          <div>
            <p className="text-sm text-muted-foreground">Agent ID</p>
            <p className="font-mono text-sm mt-1">{agent.id}</p>
          </div>

          <div>
            <p className="text-sm text-muted-foreground">Created</p>
            <p className="text-sm mt-1">{new Date(agent.created_at).toLocaleString()}</p>
          </div>

          <div>
            <p className="text-sm text-muted-foreground">Last Updated</p>
            <p className="text-sm mt-1">{new Date(agent.updated_at).toLocaleString()}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
