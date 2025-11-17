export interface User {
  id: string
  email: string
  full_name: string | null
  company_name: string | null
  phone_number: string | null
  avatar_url: string | null
  timezone: string
  language: string
  is_active: boolean
  is_verified: boolean
  email_verified_at: string | null
  last_login_at: string | null
  created_at: string
  updated_at: string
}

export interface Organization {
  id: string
  name: string
  slug: string
  owner_id: string
  plan_type: string
  billing_email: string | null
  is_active: boolean
  settings: Record<string, any>
  created_at: string
  updated_at: string
}

export interface Agent {
  id: string
  user_id: string
  organization_id: string
  name: string
  description: string | null
  type: 'assistant' | 'squad'
  system_prompt: string | null
  first_message: string | null
  llm_provider: string
  llm_model: string
  llm_temperature: number
  tts_provider: string
  tts_voice_id: string | null
  stt_provider: string
  stt_language: string
  is_active: boolean
  tags: string[]
  created_at: string
  updated_at: string
}

export interface Call {
  id: string
  user_id: string
  organization_id: string
  agent_id: string | null
  direction: 'inbound' | 'outbound'
  from_number: string
  to_number: string
  status: string
  started_at: string | null
  ended_at: string | null
  duration_seconds: number | null
  transcript: string | null
  sentiment_score: number | null
  sentiment_label: string | null
  cost_total: number | null
  created_at: string
}

export interface IntegrationConnector {
  id: string
  name: string
  slug: string
  category: string
  description: string | null
  logo_url: string | null
  auth_type: 'oauth2' | 'api_key' | 'basic' | 'jwt'
  supports_triggers: boolean
  supports_actions: boolean
  is_active: boolean
  is_beta: boolean
  is_premium: boolean
  created_at: string
}

export interface IntegrationConnection {
  id: string
  user_id: string
  organization_id: string
  connector_id: string
  name: string | null
  status: 'active' | 'expired' | 'error' | 'disconnected'
  last_sync_at: string | null
  created_at: string
}

export interface Workflow {
  id: string
  user_id: string
  organization_id: string
  name: string
  description: string | null
  trigger_type: string
  trigger_config: Record<string, any>
  workflow_steps: Record<string, any>
  is_active: boolean
  total_executions: number
  successful_executions: number
  failed_executions: number
  last_executed_at: string | null
  created_at: string
  updated_at: string
}

export interface WorkflowExecution {
  id: string
  workflow_id: string
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  started_at: string
  completed_at: string | null
  duration_ms: number | null
  steps_executed: number
  steps_successful: number
  steps_failed: number
  error_message: string | null
}

export interface ApiResponse<T> {
  data: T
  message?: string
  error?: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
