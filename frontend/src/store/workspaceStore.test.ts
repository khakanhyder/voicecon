/**
 * Unit tests for the active-workspace store.
 *
 * `can()` decides which controls render. It is presentation only — the server
 * enforces the same strings on every request — but a bug here either hides
 * controls a user is entitled to, or shows them controls that will 403. Both
 * are worth pinning, so the tests below cover the deny path as carefully as the
 * allow path.
 *
 * The HTTP layer is mocked at `@/lib/workspace`, so no request is made.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { WorkspaceDetail, WorkspaceSummary } from '@/lib/workspace'

vi.mock('@/lib/workspace', async () => {
  const actual = await vi.importActual<typeof import('@/lib/workspace')>('@/lib/workspace')
  return {
    ...actual,
    setActiveWorkspaceId: vi.fn(),
    getActiveWorkspaceId: vi.fn(() => null),
    workspaceService: {
      list: vi.fn(),
      current: vi.fn(),
      switch: vi.fn(),
    },
  }
})

const { workspaceService, setActiveWorkspaceId } = await import('@/lib/workspace')
const { useWorkspaceStore } = await import('./workspaceStore')

function detail(overrides: Partial<WorkspaceDetail> = {}): WorkspaceDetail {
  return {
    id: 'ws-1',
    name: 'Acme',
    slug: 'acme',
    plan_type: 'starter',
    role: 'owner',
    is_owner: true,
    permissions: ['agents:read', 'agents:write', 'team:read'],
    member_count: 3,
    owner_email: 'owner@example.com',
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function summary(overrides: Partial<WorkspaceSummary> = {}): WorkspaceSummary {
  return {
    id: 'ws-1',
    name: 'Acme',
    slug: 'acme',
    role: 'owner',
    is_owner: true,
    is_current: true,
    member_count: 3,
    joined_at: '2026-01-01T00:00:00Z',
    plan_type: 'starter',
    ...overrides,
  }
}

/** The store is a module singleton; reset it or state leaks between tests. */
beforeEach(() => {
  useWorkspaceStore.setState({
    current: null,
    workspaces: [],
    isLoading: true,
    isSwitching: false,
    error: null,
  })
  vi.clearAllMocks()
})

describe('load', () => {
  it('stores the workspace and the switcher list', async () => {
    vi.mocked(workspaceService.current).mockResolvedValue(detail())
    vi.mocked(workspaceService.list).mockResolvedValue([summary()])

    await useWorkspaceStore.getState().load()

    const state = useWorkspaceStore.getState()
    expect(state.current?.id).toBe('ws-1')
    expect(state.workspaces).toHaveLength(1)
    expect(state.isLoading).toBe(false)
  })

  it('clears a previous error on a successful reload', async () => {
    useWorkspaceStore.setState({ error: 'stale failure' })
    vi.mocked(workspaceService.current).mockResolvedValue(detail())
    vi.mocked(workspaceService.list).mockResolvedValue([])

    await useWorkspaceStore.getState().load()

    expect(useWorkspaceStore.getState().error).toBeNull()
  })

  it('surfaces a failure instead of spinning forever', async () => {
    // A brand-new account can briefly have no workspace. Leaving isLoading true
    // would leave the dashboard on a spinner with nothing to say.
    vi.mocked(workspaceService.current).mockRejectedValue({
      response: { data: { detail: 'No workspace yet' } },
    })
    vi.mocked(workspaceService.list).mockResolvedValue([])

    await useWorkspaceStore.getState().load()

    const state = useWorkspaceStore.getState()
    expect(state.isLoading).toBe(false)
    expect(state.error).toBe('No workspace yet')
  })

  it('falls back to a readable message when the server sends no detail', async () => {
    vi.mocked(workspaceService.current).mockRejectedValue(new Error('network'))
    vi.mocked(workspaceService.list).mockResolvedValue([])

    await useWorkspaceStore.getState().load()

    expect(useWorkspaceStore.getState().error).toMatch(/could not load/i)
  })
})

describe('switchTo', () => {
  it('replaces the current workspace and refreshes the list', async () => {
    useWorkspaceStore.setState({ current: detail({ id: 'ws-1' }) })
    vi.mocked(workspaceService.switch).mockResolvedValue(
      detail({ id: 'ws-2', name: 'Other' })
    )
    vi.mocked(workspaceService.list).mockResolvedValue([summary({ id: 'ws-2' })])

    const result = await useWorkspaceStore.getState().switchTo('ws-2')

    expect(result?.id).toBe('ws-2')
    expect(useWorkspaceStore.getState().current?.id).toBe('ws-2')
    expect(useWorkspaceStore.getState().isSwitching).toBe(false)
  })

  it('is a no-op when already in that workspace', async () => {
    // Re-selecting the current workspace in the switcher must not cost a round
    // trip or flash the switching state.
    useWorkspaceStore.setState({ current: detail({ id: 'ws-1' }) })

    const result = await useWorkspaceStore.getState().switchTo('ws-1')

    expect(result?.id).toBe('ws-1')
    expect(workspaceService.switch).not.toHaveBeenCalled()
  })

  it('reports a failed switch and stays where it was', async () => {
    // Being removed from a workspace mid-session lands here; the user must keep
    // a usable workspace rather than end up with none.
    useWorkspaceStore.setState({ current: detail({ id: 'ws-1' }) })
    vi.mocked(workspaceService.switch).mockRejectedValue({
      response: { data: { detail: 'You are not a member' } },
    })

    const result = await useWorkspaceStore.getState().switchTo('ws-2')

    const state = useWorkspaceStore.getState()
    expect(result).toBeNull()
    expect(state.current?.id).toBe('ws-1')
    expect(state.error).toBe('You are not a member')
    expect(state.isSwitching).toBe(false)
  })
})

describe('refresh', () => {
  it('updates the workspace in place', async () => {
    useWorkspaceStore.setState({ current: detail({ member_count: 3 }) })
    vi.mocked(workspaceService.current).mockResolvedValue(detail({ member_count: 4 }))
    vi.mocked(workspaceService.list).mockResolvedValue([summary()])

    await useWorkspaceStore.getState().refresh()

    expect(useWorkspaceStore.getState().current?.member_count).toBe(4)
  })

  it('keeps the last known good state when the refresh fails', async () => {
    // A background refresh must never blank the UI the user is looking at.
    useWorkspaceStore.setState({ current: detail({ name: 'Acme' }) })
    vi.mocked(workspaceService.current).mockRejectedValue(new Error('offline'))
    vi.mocked(workspaceService.list).mockRejectedValue(new Error('offline'))

    await useWorkspaceStore.getState().refresh()

    expect(useWorkspaceStore.getState().current?.name).toBe('Acme')
  })
})

describe('reset', () => {
  it('clears the workspace and the stored id on sign-out', async () => {
    // The stored id is sent as a header on every request; leaving it behind
    // would point the next user at the previous user's workspace.
    useWorkspaceStore.setState({ current: detail(), workspaces: [summary()] })

    useWorkspaceStore.getState().reset()

    const state = useWorkspaceStore.getState()
    expect(state.current).toBeNull()
    expect(state.workspaces).toEqual([])
    expect(setActiveWorkspaceId).toHaveBeenCalledWith(null)
  })
})

describe('can', () => {
  it('allows a permission the server granted', () => {
    useWorkspaceStore.setState({ current: detail({ permissions: ['agents:write'] }) })

    expect(useWorkspaceStore.getState().can('agents:write')).toBe(true)
  })

  it('denies a permission that was not granted', () => {
    useWorkspaceStore.setState({ current: detail({ permissions: ['agents:read'] }) })

    expect(useWorkspaceStore.getState().can('agents:write')).toBe(false)
  })

  it('denies everything before a workspace has loaded', () => {
    // Rendering write controls during the initial load would let a viewer click
    // straight into a 403.
    useWorkspaceStore.setState({ current: null })

    expect(useWorkspaceStore.getState().can('agents:read')).toBe(false)
  })

  it('denies everything for a workspace with no permissions', () => {
    useWorkspaceStore.setState({ current: detail({ permissions: [] }) })

    expect(useWorkspaceStore.getState().can('agents:read')).toBe(false)
  })

  it('matches permission strings exactly, never by prefix', () => {
    // `agents:read` must not satisfy `agents:read_write`, and a substring match
    // would quietly widen every permission in the app.
    useWorkspaceStore.setState({ current: detail({ permissions: ['agents:read'] }) })

    expect(useWorkspaceStore.getState().can('agents')).toBe(false)
    expect(useWorkspaceStore.getState().can('agents:read:extra')).toBe(false)
  })
})
