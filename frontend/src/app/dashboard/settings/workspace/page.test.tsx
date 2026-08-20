/**
 * Settings → Workspace.
 *
 * What matters here is that the controls track the *permissions the server
 * enforces*, not the role label, and that the two irreversible actions cannot
 * fire without an explicit confirmation.
 */
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import WorkspaceSettingsPage from './page'
import { PERMISSIONS, workspaceService } from '@/lib/workspace'
import { useWorkspaceStore } from '@/store/workspaceStore'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const OWNER_PERMS = [PERMISSIONS.workspaceManage, PERMISSIONS.workspaceDelete]

const workspace = {
  id: 'w1',
  name: 'Gb Bikeas',
  slug: 'gb-bikeas',
  plan_type: 'voice-ai',
  role: 'owner',
  is_owner: true,
  permissions: OWNER_PERMS as string[],
  member_count: 3,
  owner_email: 'owner@example.com',
  created_at: '2026-07-14T10:00:00Z',
}

const summary = { ...workspace, is_current: true, joined_at: workspace.created_at }

function setStore(overrides: Partial<typeof workspace> = {}, workspaceCount = 2) {
  const current = { ...workspace, ...overrides }
  useWorkspaceStore.setState({
    current,
    workspaces: Array.from({ length: workspaceCount }, (_, i) => ({
      ...summary,
      id: `w${i + 1}`,
    })),
    isLoading: false,
    isSwitching: false,
    error: null,
  })
}

beforeEach(() => {
  vi.restoreAllMocks()
  setStore()
})

describe('general tab', () => {
  it('shows the workspace details', () => {
    render(<WorkspaceSettingsPage />)

    expect(screen.getByDisplayValue('Gb Bikeas')).toBeInTheDocument()
    expect(screen.getByText('gb-bikeas')).toBeInTheDocument()
    expect(screen.getByText('Your role').parentElement).toHaveTextContent('Owner')
    expect(screen.getByText('3 members')).toBeInTheDocument()
  })

  it('renames the workspace and refreshes the shared store', async () => {
    const user = userEvent.setup()
    const rename = vi.spyOn(workspaceService, 'rename').mockResolvedValue(workspace)
    const refresh = vi.fn().mockResolvedValue(undefined)
    const load = vi.fn().mockResolvedValue(undefined)
    useWorkspaceStore.setState({ refresh, load })
    render(<WorkspaceSettingsPage />)

    const input = screen.getByDisplayValue('Gb Bikeas')
    await user.clear(input)
    await user.type(input, 'Acme Ltd')
    await user.click(screen.getByRole('button', { name: /save changes/i }))

    await waitFor(() => expect(rename).toHaveBeenCalledWith('Acme Ltd'))
    // The name also shows in the sidebar and header, which read the store.
    expect(refresh).toHaveBeenCalled()
    expect(load).toHaveBeenCalled()
  })

  it('will not save a blank name', async () => {
    const user = userEvent.setup()
    const rename = vi.spyOn(workspaceService, 'rename')
    render(<WorkspaceSettingsPage />)

    await user.clear(screen.getByDisplayValue('Gb Bikeas'))
    await user.click(screen.getByRole('button', { name: /save changes/i }))

    expect(await screen.findByText(/enter a workspace name/i)).toBeInTheDocument()
    expect(rename).not.toHaveBeenCalled()
  })

  it('is read-only without workspace:manage', () => {
    setStore({ role: 'member', is_owner: false, permissions: [] })
    render(<WorkspaceSettingsPage />)

    expect(screen.getByDisplayValue('Gb Bikeas')).toBeDisabled()
    expect(screen.queryByRole('button', { name: /save changes/i })).not.toBeInTheDocument()
  })
})

describe('danger zone', () => {
  const openDanger = async (user: ReturnType<typeof userEvent.setup>) =>
    user.click(screen.getByRole('tab', { name: /danger zone/i }))

  it('offers delete to an owner but not leave', async () => {
    const user = userEvent.setup()
    render(<WorkspaceSettingsPage />)
    await openDanger(user)

    expect(screen.getByRole('button', { name: /delete workspace/i })).toBeInTheDocument()
    // An owner leaving would strand the workspace — they transfer first.
    expect(screen.queryByRole('button', { name: /leave workspace/i })).not.toBeInTheDocument()
  })

  it('offers leave to a member but not delete', async () => {
    const user = userEvent.setup()
    setStore({ role: 'member', is_owner: false, permissions: [] })
    render(<WorkspaceSettingsPage />)
    await openDanger(user)

    expect(screen.getByRole('button', { name: /leave workspace/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /delete workspace/i })).not.toBeInTheDocument()
  })

  it('explains why the only workspace cannot be deleted', async () => {
    const user = userEvent.setup()
    setStore({}, 1)
    render(<WorkspaceSettingsPage />)
    await openDanger(user)

    expect(screen.getByText(/only workspace/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /delete workspace/i })).not.toBeInTheDocument()
  })

  it('does not delete until the confirmation is accepted', async () => {
    const user = userEvent.setup()
    const remove = vi.spyOn(workspaceService, 'remove').mockResolvedValue(undefined)
    render(<WorkspaceSettingsPage />)
    await openDanger(user)

    await user.click(screen.getByRole('button', { name: /delete workspace/i }))
    // The dialog is up; nothing has been sent yet.
    expect(remove).not.toHaveBeenCalled()

    const dialog = screen.getByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: /^delete workspace$/i }))
    await waitFor(() => expect(remove).toHaveBeenCalled())
  })

  it('does not leave until the confirmation is accepted', async () => {
    const user = userEvent.setup()
    setStore({ role: 'member', is_owner: false, permissions: [] })
    const leave = vi.spyOn(workspaceService, 'leave').mockResolvedValue(undefined)
    render(<WorkspaceSettingsPage />)
    await openDanger(user)

    await user.click(screen.getByRole('button', { name: /leave workspace/i }))
    expect(leave).not.toHaveBeenCalled()
  })
})
