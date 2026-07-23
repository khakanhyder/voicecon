export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

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
  CALL_CONTACTS: `${API_BASE}/api/v1/calls/contacts`,
  CALL_CONTACT_CALLS: (number: string) => `${API_BASE}/api/v1/calls/contacts/${encodeURIComponent(number)}/calls`,

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
  INTEGRATION_CONNECTION_ACTIONS: (id: string) => `${API_BASE}/api/v1/integrations/connections/${id}/actions`,
  INTEGRATIONS_AVAILABLE_FOR_TOOLS: `${API_BASE}/api/v1/integrations/available-for-tools`,

  // Workflows
  // Knowledge base
  KNOWLEDGE_BASES: `${API_BASE}/api/v1/knowledge/knowledge-bases`,
  KNOWLEDGE_BASE: (id: string) => `${API_BASE}/api/v1/knowledge/knowledge-bases/${id}`,
  KNOWLEDGE_BASE_DOCUMENTS: (id: string) =>
    `${API_BASE}/api/v1/knowledge/knowledge-bases/${id}/documents`,
  KNOWLEDGE_DOCUMENT: (id: string) => `${API_BASE}/api/v1/knowledge/documents/${id}`,
  KNOWLEDGE_DOCUMENTS: `${API_BASE}/api/v1/knowledge/documents`,
  KNOWLEDGE_UPLOAD: `${API_BASE}/api/v1/knowledge/documents/upload`,
  KNOWLEDGE_SEARCH: `${API_BASE}/api/v1/knowledge/search`,
  KNOWLEDGE_ASK: `${API_BASE}/api/v1/knowledge/ask`,
  AGENT_KNOWLEDGE_BASES: (agentId: string) =>
    `${API_BASE}/api/v1/knowledge/agents/${agentId}/knowledge-bases`,

  WORKFLOWS: `${API_BASE}/api/v1/workflows`,
  WORKFLOW: (id: string) => `${API_BASE}/api/v1/workflows/${id}`,
  WORKFLOW_EXECUTE: (id: string) => `${API_BASE}/api/v1/workflows/${id}/execute`,
  WORKFLOW_EXECUTIONS: (id: string) => `${API_BASE}/api/v1/workflows/${id}/executions`,
  WORKFLOW_VALIDATE: (id: string) => `${API_BASE}/api/v1/workflows/${id}/validate`,

  // Analytics
  ANALYTICS: `${API_BASE}/api/v1/analytics`,

  // Billing
  BILLING_PLANS: `${API_BASE}/api/v1/billing/plans`,
  BILLING_SUBSCRIPTION: `${API_BASE}/api/v1/billing/subscription`,
  BILLING_USAGE: `${API_BASE}/api/v1/billing/usage`,
  BILLING_INVOICES: `${API_BASE}/api/v1/billing/invoices`,
  BILLING_CONFIG: `${API_BASE}/api/v1/billing/config`,
  BILLING_TRIAL: `${API_BASE}/api/v1/billing/trial`,
  BILLING_CHECKOUT: `${API_BASE}/api/v1/billing/checkout`,

  // Onboarding
  ONBOARDING_STATUS: `${API_BASE}/api/v1/onboarding/status`,
  ONBOARDING_COMPANY: `${API_BASE}/api/v1/onboarding/company`,

  // Profile / account
  USERS_ME: `${API_BASE}/api/v1/users/me`,
  USERS_ME_PASSWORD: `${API_BASE}/api/v1/users/me/change-password`,

  // Team
  TEAM_MEMBERS: `${API_BASE}/api/v1/team/members`,
  TEAM_INVITE: `${API_BASE}/api/v1/team/invite`,
  TEAM_MEMBER: (id: string) => `${API_BASE}/api/v1/team/members/${id}`,
  TEAM_INVITATIONS: `${API_BASE}/api/v1/team/invitations`,
  TEAM_INVITATION: (id: string) => `${API_BASE}/api/v1/team/invitations/${id}`,

  // Invitations (public token-addressed)
  INVITATION: (token: string) => `${API_BASE}/api/v1/invitations/${token}`,
  INVITATION_ACCEPT: (token: string) => `${API_BASE}/api/v1/invitations/${token}/accept`,
  INVITATION_REJECT: (token: string) => `${API_BASE}/api/v1/invitations/${token}/reject`,

  // Notifications
  NOTIFICATIONS: `${API_BASE}/api/v1/notifications`,
  NOTIFICATIONS_UNREAD_COUNT: `${API_BASE}/api/v1/notifications/unread-count`,
  NOTIFICATION_READ: (id: string) => `${API_BASE}/api/v1/notifications/${id}/read`,
  NOTIFICATIONS_READ_ALL: `${API_BASE}/api/v1/notifications/read-all`,

  // API keys
  API_KEYS: `${API_BASE}/api/v1/api-keys`,
  API_KEY: (id: string) => `${API_BASE}/api/v1/api-keys/${id}`,
  API_KEY_REGENERATE: (id: string) => `${API_BASE}/api/v1/api-keys/${id}/regenerate`,

  // Tools
  TOOLS: `${API_BASE}/api/v1/tools`,
  TOOL: (id: string) => `${API_BASE}/api/v1/tools/${id}`,
  TOOL_TEST: (id: string) => `${API_BASE}/api/v1/tools/${id}/test`,
  AGENT_TOOLS: (agentId: string) => `${API_BASE}/api/v1/tools/agents/${agentId}/tools`,
  AGENT_TOOL: (agentId: string, toolId: string) => `${API_BASE}/api/v1/tools/agents/${agentId}/tools/${toolId}`,

  // Chat widget
  AGENT_WIDGET: (agentId: string) => `${API_BASE}/api/v1/chat/agents/${agentId}/widget`,
  AGENT_CHAT_SESSIONS: (agentId: string) => `${API_BASE}/api/v1/chat/agents/${agentId}/sessions`,
  CHAT_SESSION_MESSAGES: (sessionId: string) => `${API_BASE}/api/v1/chat/sessions/${sessionId}/messages`,

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
  BILLING_PLANS: ['billing', 'plans'] as const,
  ONBOARDING_STATUS: ['onboarding', 'status'] as const,
} as const
