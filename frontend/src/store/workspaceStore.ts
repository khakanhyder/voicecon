/**
 * Active-workspace Zustand store.
 *
 * Holds which workspace the user is working inside, their role in it, and the
 * permission set the backend granted. Components read `can(...)` to decide what
 * to render — the server enforces the same permissions independently, so this
 * is presentation only, never the security boundary.
 */
import { create } from 'zustand'
import {
  WorkspaceDetail,
  WorkspaceSummary,
  getActiveWorkspaceId,
  setActiveWorkspaceId,
  workspaceService,
} from '@/lib/workspace'

interface WorkspaceState {
  current: WorkspaceDetail | null
  workspaces: WorkspaceSummary[]
  isLoading: boolean
  isSwitching: boolean
  error: string | null

  /** Load the current workspace and the switcher list. Safe to call repeatedly. */
  load: () => Promise<void>
  switchTo: (organizationId: string) => Promise<WorkspaceDetail | null>
  refresh: () => Promise<void>
  reset: () => void
  can: (permission: string) => boolean
}

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  current: null,
  workspaces: [],
  isLoading: true,
  isSwitching: false,
  error: null,

  load: async () => {
    set({ isLoading: true, error: null })
    try {
      const [current, workspaces] = await Promise.all([
        workspaceService.current(),
        workspaceService.list(),
      ])
      set({ current, workspaces, isLoading: false })
    } catch (e: any) {
      // A brand-new account can briefly have no workspace; surface it rather
      // than spinning forever.
      set({
        isLoading: false,
        error: e?.response?.data?.detail ?? 'Could not load your workspace',
      })
    }
  },

  switchTo: async (organizationId: string) => {
    if (get().current?.id === organizationId) return get().current
    set({ isSwitching: true })
    try {
      const current = await workspaceService.switch(organizationId)
      const workspaces = await workspaceService.list()
      set({ current, workspaces, isSwitching: false, error: null })
      return current
    } catch (e: any) {
      set({ isSwitching: false, error: e?.response?.data?.detail ?? 'Could not switch workspace' })
      return null
    }
  },

  refresh: async () => {
    try {
      const [current, workspaces] = await Promise.all([
        workspaceService.current(),
        workspaceService.list(),
      ])
      set({ current, workspaces })
    } catch {
      /* keep the last known good state */
    }
  },

  reset: () => {
    setActiveWorkspaceId(null)
    set({ current: null, workspaces: [], isLoading: true, error: null })
  },

  can: (permission: string) => get().current?.permissions.includes(permission) ?? false,
}))

/** Convenience hook: `const canInvite = usePermission('team:manage')`. */
export function usePermission(permission: string): boolean {
  return useWorkspaceStore((s) => s.current?.permissions.includes(permission) ?? false)
}

export { getActiveWorkspaceId }
