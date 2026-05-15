'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
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
  is_active: boolean
  created_at: string
}

export default function AgentsPage() {
  const router = useRouter()
  const [agents, setAgents] = useState<Agent[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    fetchAgents()
  }, [])

  const fetchAgents = async () => {
    try {
      const response = await apiClient.get<{ agents: Agent[]; total: number }>(API_ENDPOINTS.AGENTS)
      setAgents(response.data.agents || [])
    } catch (error) {
      console.error('Failed to fetch agents:', error)
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex h-[400px] items-center justify-center">
        <div className="text-lg text-muted-foreground">Loading agents...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Agents</h1>
          <p className="text-muted-foreground">
            Create and manage your AI voice agents
          </p>
        </div>
        <Link href="/dashboard/agents/new">
          <Button>Create Agent</Button>
        </Link>
      </div>

      {agents.length === 0 ? (
        <div className="rounded-lg border bg-card p-8 text-center">
          <div className="mx-auto max-w-md space-y-4">
            <div className="text-6xl">🎙️</div>
            <h2 className="text-2xl font-semibold">No agents yet</h2>
            <p className="text-muted-foreground">
              Get started by creating your first AI voice agent
            </p>
            <Link href="/dashboard/agents/new">
              <Button size="lg">Create Your First Agent</Button>
            </Link>
          </div>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {agents.map((agent) => (
            <div
              key={agent.id}
              className="rounded-lg border bg-card p-6 hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => router.push(`/dashboard/agents/${agent.id}`)}
            >
              <div className="flex items-start justify-between mb-4">
                <div className="h-12 w-12 rounded-lg bg-primary/10 flex items-center justify-center text-2xl">
                  🎙️
                </div>
                <div className={`px-2 py-1 rounded text-xs font-medium ${
                  agent.is_active
                    ? 'bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-400'
                    : 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400'
                }`}>
                  {agent.is_active ? 'Active' : 'Inactive'}
                </div>
              </div>

              <h3 className="font-semibold text-lg mb-2">{agent.name}</h3>
              <p className="text-sm text-muted-foreground mb-4 line-clamp-2">
                {agent.description || 'No description provided'}
              </p>

              <div className="space-y-2 text-xs text-muted-foreground">
                <div className="flex items-center justify-between">
                  <span>LLM:</span>
                  <span className="font-medium">{agent.llm_provider} / {agent.llm_model}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>TTS:</span>
                  <span className="font-medium capitalize">{agent.tts_provider}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>STT:</span>
                  <span className="font-medium capitalize">{agent.stt_provider}</span>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t">
                <p className="text-xs text-muted-foreground">
                  Created {new Date(agent.created_at).toLocaleDateString()}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
