'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Bot } from 'lucide-react'
import { apiClient } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'

interface RailAgent {
  id: string
  name: string
  description: string | null
  is_active: boolean
}

/**
 * "All assistants" side rail shown next to the agent editor. Lists the
 * existing agents and hosts the page's primary action underneath.
 */
export function AssistantsRail({
  activeId,
  filter = '',
  children,
}: {
  activeId?: string
  /** Free-text filter driven by the search field in the page header. */
  filter?: string
  children?: React.ReactNode
}) {
  const [agents, setAgents] = useState<RailAgent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiClient
      .get<{ agents: RailAgent[] }>(API_ENDPOINTS.AGENTS)
      .then((r) => setAgents(r.data.agents || []))
      .catch(() => setAgents([]))
      .finally(() => setLoading(false))
  }, [])

  const q = filter.trim().toLowerCase()
  const visible = q
    ? agents.filter(a =>
        a.name?.toLowerCase().includes(q) || a.description?.toLowerCase().includes(q)
      )
    : agents

  return (
    <aside className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden">
        <div className="border-b border-slate-100 px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-900">All Assistants</h2>
        </div>

        <div className="max-h-[420px] overflow-y-auto p-2">
          {loading ? (
            <div className="space-y-2 p-1">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-14 animate-pulse rounded-xl bg-slate-100" />
              ))}
            </div>
          ) : visible.length === 0 ? (
            <p className="px-3 py-6 text-center text-sm text-slate-400">
              {q ? `No assistants match “${filter}”` : 'No assistants yet'}
            </p>
          ) : (
            visible.map((agent) => {
              const active = agent.id === activeId
              return (
                <Link
                  key={agent.id}
                  href={`/dashboard/agents/${agent.id}/edit`}
                  className={`flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors ${
                    active ? 'bg-[#0F6A59]/10' : 'hover:bg-slate-50'
                  }`}
                >
                  <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-[#0F6A59]/10 text-sm font-semibold text-[#0F6A59]">
                    {agent.name?.[0]?.toUpperCase() || <Bot className="h-4 w-4" />}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-slate-900">{agent.name}</span>
                    <span className="block truncate text-xs text-slate-400">
                      {agent.description || (agent.is_active ? 'Active' : 'Inactive')}
                    </span>
                  </span>
                </Link>
              )
            })
          )}
        </div>
      </div>

      {children}
    </aside>
  )
}
