'use client'

import { useEffect, useState } from 'react'
import { AlertCircle } from 'lucide-react'
import { takeSignedOutNotice } from '@/lib/session'

/**
 * Why the person was just signed out, shown once on the sign-in page.
 *
 * Set by the API client when the server ends a session for a reason worth
 * telling them — today, an account that was deactivated or deleted while they
 * were signed in (lib/api.ts). Renders nothing on an ordinary visit.
 */
export function SignedOutNotice({ className = '' }: { className?: string }) {
  const [message, setMessage] = useState<string | null>(null)

  // Read after mount: sessionStorage does not exist during server rendering,
  // and reading it in the initial state would make the two renders disagree.
  // Only ever set, never cleared: React's development double-invoke runs this
  // twice, and the second read finds the notice already taken.
  useEffect(() => {
    const notice = takeSignedOutNotice()
    if (notice) setMessage(notice)
  }, [])

  if (!message) return null

  return (
    <div
      role="alert"
      className={`flex items-start gap-2.5 rounded-lg border border-red-200 bg-red-50 px-3.5 py-3 text-sm text-red-800 ${className}`}
    >
      <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-600" aria-hidden="true" />
      <span>{message}</span>
    </div>
  )
}
