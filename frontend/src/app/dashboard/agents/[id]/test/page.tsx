'use client'

import { useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'

/**
 * This URL used to be a second, full-page test console. It did the same job as
 * the Test Call panel on the assistant page but was maintained separately, and
 * the two had drifted: this one named a transcriber model the assistant was not
 * using. The panel is the one test console now; old links and bookmarks land on
 * the assistant with the panel open.
 */
export default function AgentTestRedirect() {
  const router = useRouter()
  const { id } = useParams<{ id: string }>()

  useEffect(() => {
    router.replace(`/dashboard/agents/${id}?test=1`)
  }, [id, router])

  return (
    <div className="flex h-[400px] items-center justify-center text-sm text-slate-500">
      Opening the test call…
    </div>
  )
}
