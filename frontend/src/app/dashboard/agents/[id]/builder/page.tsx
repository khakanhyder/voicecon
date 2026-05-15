'use client'

import { useParams } from 'next/navigation'
import { FlowBuilder } from '@/components/agents/FlowBuilder'

export default function AgentBuilderPage() {
  const params = useParams()
  const agentId = params.id as string

  return (
    <div className="h-[calc(100vh-8rem)]">
      <FlowBuilder agentId={agentId} />
    </div>
  )
}
