'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import Link from 'next/link'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'

interface Workflow {
  id: string
  name: string
  description: string
  trigger_type: string
  is_active: boolean
  created_at: string
}

export default function WorkflowsPage() {
  const router = useRouter()
  const [workflows, setWorkflows] = useState<Workflow[]>([])
  const [isLoading, setIsLoading] = useState(true)

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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Workflows</h1>
          <p className="text-muted-foreground">
            Create and manage automation workflows
          </p>
        </div>
        <Link href="/dashboard/workflows/new">
          <Button>Create Workflow</Button>
        </Link>
      </div>

      {workflows.length === 0 ? (
        <div className="rounded-lg border bg-card p-8 text-center">
          <div className="mx-auto max-w-md space-y-4">
            <div className="flex h-16 w-16 mx-auto items-center justify-center rounded-2xl bg-blue-50"><svg className="h-8 w-8 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg></div>
            <h2 className="text-2xl font-semibold">No workflows yet</h2>
            <p className="text-muted-foreground">
              Build your first automation workflow to connect your agents with apps
            </p>
            <Link href="/dashboard/workflows/new">
              <Button size="lg">Create Your First Workflow</Button>
            </Link>
          </div>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {workflows.map((workflow) => (
            <div
              key={workflow.id}
              className="rounded-lg border bg-card p-6 hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => router.push(`/dashboard/workflows/${workflow.id}`)}
            >
              <div className="flex items-start justify-between mb-4">
                <div className="h-10 w-10 rounded-xl bg-blue-50 flex items-center justify-center">
                  <svg className="h-5 w-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                </div>
                <div className={`px-2 py-1 rounded text-xs font-medium ${
                  workflow.is_active
                    ? 'bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-400'
                    : 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400'
                }`}>
                  {workflow.is_active ? 'Active' : 'Inactive'}
                </div>
              </div>

              <h3 className="font-semibold text-lg mb-2">{workflow.name}</h3>
              <p className="text-sm text-muted-foreground mb-4 line-clamp-2">
                {workflow.description || 'No description provided'}
              </p>

              <div className="space-y-2 text-xs text-muted-foreground">
                <div className="flex items-center justify-between">
                  <span>Trigger:</span>
                  <span className="font-medium capitalize">{workflow.trigger_type.replace('_', ' ')}</span>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t">
                <p className="text-xs text-muted-foreground">
                  Created {new Date(workflow.created_at).toLocaleDateString()}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
