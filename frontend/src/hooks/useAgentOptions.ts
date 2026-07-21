import { useEffect, useState } from 'react'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'

export interface AgentOption {
  id: string
  name: string
}

/**
 * Load the organization's agents for use in a select.
 *
 * The workflow new/edit pages previously hardcoded placeholder options
 * ("agent1"/"agent2"), which were written into trigger_config and matched no
 * real agent at runtime.
 *
 * @param enabled Skip the request until the agent picker is actually shown.
 */
export function useAgentOptions(enabled: boolean = true) {
  const [agents, setAgents] = useState<AgentOption[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    if (!enabled || loaded) return

    let cancelled = false
    setIsLoading(true)

    apiClient
      .get<{ agents: AgentOption[] }>(API_ENDPOINTS.AGENTS)
      .then((res) => {
        if (cancelled) return
        setAgents(res.data.agents ?? [])
        setLoaded(true)
      })
      .catch((error) => {
        if (cancelled) return
        console.error('Failed to load agents:', error)
        toast.error(getErrorMessage(error))
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [enabled, loaded])

  return { agents, isLoading }
}
