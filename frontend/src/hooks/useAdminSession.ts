/**
 * The staff console's own session state.
 *
 * Deliberately not `useAuthStore` — that store holds the *customer app's*
 * session, and reading it here is what used to make a sign-in at one door
 * count as a sign-in at the other. This reads the admin scope's credentials
 * only (lib/session.ts), after mount so the server render and the client
 * render agree.
 */
'use client'

import { useCallback, useEffect, useState } from 'react'
import { authService } from '@/lib/auth'

export interface AdminSession {
  isAuthenticated: boolean
  /** True until localStorage has been read, which cannot happen on the server. */
  isLoading: boolean
  /** Re-read the stored session — call after signing in or out. */
  sync: () => void
}

export function useAdminSession(): AdminSession {
  const [state, setState] = useState({ isAuthenticated: false, isLoading: true })

  const sync = useCallback(() => {
    setState({ isAuthenticated: authService.isAuthenticated('admin'), isLoading: false })
  }, [])

  useEffect(() => {
    sync()
  }, [sync])

  return { ...state, sync }
}
