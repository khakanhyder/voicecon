const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const API_ENDPOINTS = {
  // Auth
  AUTH_REGISTER: `${API_BASE}/api/v1/auth/register`,
  AUTH_LOGIN: `${API_BASE}/api/v1/auth/login`,
  AUTH_REFRESH: `${API_BASE}/api/v1/auth/refresh`,
  AUTH_LOGOUT: `${API_BASE}/api/v1/auth/logout`,

  // Agents
  AGENTS: `${API_BASE}/api/v1/agents`,
  AGENT: (id: string) => `${API_BASE}/api/v1/agents/${id}`,

  // Calls
  CALLS: `${API_BASE}/api/v1/calls`,
  CALL: (id: string) => `${API_BASE}/api/v1/calls/${id}`,
  CALL_STATS: `${API_BASE}/api/v1/calls/stats`,

  // Phone Numbers
  PHONE_NUMBERS: `${API_BASE}/api/v1/phone-numbers`,
  PHONE_NUMBER: (id: string) => `${API_BASE}/api/v1/phone-numbers/${id}`,
  PHONE_NUMBERS_SEARCH: `${API_BASE}/api/v1/phone-numbers/search`,
  PHONE_NUMBERS_PROVISION: `${API_BASE}/api/v1/phone-numbers/provision`,

  // Integrations
  INTEGRATIONS: `${API_BASE}/api/v1/integrations`,
  INTEGRATION: (id: string) => `${API_BASE}/api/v1/integrations/${id}`,
  INTEGRATION_CONNECTORS: `${API_BASE}/api/v1/integrations/connectors`,
  INTEGRATION_CONNECTIONS: `${API_BASE}/api/v1/integrations/connections`,
  INTEGRATION_CONNECTION: (id: string) => `${API_BASE}/api/v1/integrations/connections/${id}`,
  INTEGRATION_CONNECTION_TEST: (id: string) => `${API_BASE}/api/v1/integrations/connections/${id}/test`,

  // Workflows
  WORKFLOWS: `${API_BASE}/api/v1/workflows`,
  WORKFLOW: (id: string) => `${API_BASE}/api/v1/workflows/${id}`,

  // Analytics
  ANALYTICS: `${API_BASE}/api/v1/analytics`,

  // Billing
  BILLING_PLANS: `${API_BASE}/api/v1/billing/plans`,
  BILLING_SUBSCRIPTION: `${API_BASE}/api/v1/billing/subscription`,
  BILLING_USAGE: `${API_BASE}/api/v1/billing/usage`,
  BILLING_INVOICES: `${API_BASE}/api/v1/billing/invoices`,

  // Tools
  TOOLS: `${API_BASE}/api/v1/tools`,
  TOOL: (id: string) => `${API_BASE}/api/v1/tools/${id}`,
  TOOL_TEST: (id: string) => `${API_BASE}/api/v1/tools/${id}/test`,
  AGENT_TOOLS: (agentId: string) => `${API_BASE}/api/v1/tools/agents/${agentId}/tools`,
  AGENT_TOOL: (agentId: string, toolId: string) => `${API_BASE}/api/v1/tools/agents/${agentId}/tools/${toolId}`,

  // Health
  HEALTH: `${API_BASE}/health`,
} as const

export const QUERY_KEYS = {
  AGENTS: ['agents'] as const,
  AGENT: (id: string) => ['agents', id] as const,
  CALLS: ['calls'] as const,
  CALL: (id: string) => ['calls', id] as const,
  CALL_STATS: ['calls', 'stats'] as const,
  PHONE_NUMBERS: ['phone-numbers'] as const,
  INTEGRATIONS: ['integrations'] as const,
  INTEGRATION: (slug: string) => ['integrations', slug] as const,
  WORKFLOWS: ['workflows'] as const,
  WORKFLOW: (id: string) => ['workflows', id] as const,
  ANALYTICS: ['analytics'] as const,
  USER: ['user'] as const,
  ME: ['me'] as const,
} as const
