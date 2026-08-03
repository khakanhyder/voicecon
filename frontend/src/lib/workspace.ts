import { apiClient } from './api'
import { API_ENDPOINTS } from './constants'

/** Where the active workspace id is kept so the API client can read it synchronously. */
export const ACTIVE_WORKSPACE_KEY = 'active_organization_id'

export interface WorkspaceSummary {
  id: string
  name: string
  slug: string
  role: string
  is_owner: boolean
  is_current: boolean
  member_count: number
  joined_at: string
  plan_type: string
}

export interface WorkspaceDetail {
  id: string
  name: string
  slug: string
  plan_type: string
  role: string
  is_owner: boolean
  /** The exact permission strings the backend will enforce — never re-derive these locally. */
  permissions: string[]
  member_count: number
  owner_email: string | null
  created_at: string
}

/**
 * Permission names, mirroring `app/core/permissions.py`.
 *
 * These are only for *hiding* controls. The server checks the same strings on
 * every request, so a stale or tampered client gains nothing.
 */
export const PERMISSIONS = {
  agentsRead: 'agents:read',
  agentsWrite: 'agents:write',
  agentsDelete: 'agents:delete',
  callsWrite: 'calls:write',
  phoneNumbersWrite: 'phone_numbers:write',
  workflowsWrite: 'workflows:write',
  toolsWrite: 'tools:write',
  knowledgeWrite: 'knowledge:write',
  integrationsWrite: 'integrations:write',
  teamRead: 'team:read',
  teamManage: 'team:manage',
  teamManageAdmins: 'team:manage_admins',
  billingRead: 'billing:read',
  billingManage: 'billing:manage',
  apiKeysRead: 'api_keys:read',
  apiKeysManage: 'api_keys:manage',
  workspaceManage: 'workspace:manage',
  workspaceDelete: 'workspace:delete',
  workspaceTransferOwnership: 'workspace:transfer_ownership',
} as const

export function getActiveWorkspaceId(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(ACTIVE_WORKSPACE_KEY)
}

export function setActiveWorkspaceId(id: string | null) {
  if (typeof window === 'undefined') return
  if (id) localStorage.setItem(ACTIVE_WORKSPACE_KEY, id)
  else localStorage.removeItem(ACTIVE_WORKSPACE_KEY)
}

export const workspaceService = {
  async list(): Promise<WorkspaceSummary[]> {
    const { data } = await apiClient.get<WorkspaceSummary[]>(API_ENDPOINTS.WORKSPACES)
    return data
  },

  async current(): Promise<WorkspaceDetail> {
    const { data } = await apiClient.get<WorkspaceDetail>(API_ENDPOINTS.WORKSPACE_CURRENT)
    // Pin subsequent requests to whatever the server resolved, so the client
    // and server never disagree about which workspace is active.
    setActiveWorkspaceId(data.id)
    return data
  },

  async switch(organizationId: string): Promise<WorkspaceDetail> {
    // Send the switch without the header — the target is in the path, and the
    // stored id may point at a workspace we've just been removed from.
    const { data } = await apiClient.post(
      API_ENDPOINTS.WORKSPACE_SWITCH(organizationId),
      {},
      { headers: { 'X-Skip-Workspace': '1' } }
    )
    setActiveWorkspaceId(data.workspace.id)
    return data.workspace
  },

  async create(name: string): Promise<WorkspaceDetail> {
    const { data } = await apiClient.post<WorkspaceDetail>(API_ENDPOINTS.WORKSPACES, { name })
    setActiveWorkspaceId(data.id)
    return data
  },

  async rename(name: string): Promise<WorkspaceDetail> {
    const { data } = await apiClient.patch<WorkspaceDetail>(API_ENDPOINTS.WORKSPACE_CURRENT, {
      name,
    })
    return data
  },

  async transferOwnership(userId: string): Promise<WorkspaceDetail> {
    const { data } = await apiClient.post<WorkspaceDetail>(
      API_ENDPOINTS.WORKSPACE_TRANSFER_OWNERSHIP,
      { user_id: userId }
    )
    return data
  },

  async leave(): Promise<void> {
    await apiClient.post(API_ENDPOINTS.WORKSPACE_LEAVE)
    setActiveWorkspaceId(null)
  },
}
