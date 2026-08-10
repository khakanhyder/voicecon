/**
 * Fixture payloads shaped to match the real API responses.
 *
 * These mirror `LoginResponse` in backend/app/schemas/auth.py. If a test starts
 * failing here after a backend change, that is the mock catching contract drift
 * — update the fixture, don't loosen the assertion.
 */

export const TEST_USER = {
  id: '00000000-0000-4000-8000-000000000001',
  email: 'qa.bot@voicecon.test',
  full_name: 'QA Bot',
  is_verified: true,
} as const

export const TEST_PASSWORD = 'qa-password-123'

/** POST /api/v1/auth/login — 200 */
export function loginResponse(overrides: Record<string, unknown> = {}) {
  return {
    access_token: 'test-access-token',
    refresh_token: 'test-refresh-token',
    token_type: 'bearer',
    user: TEST_USER,
    ...overrides,
  }
}

export const VERIFICATION_TOKEN = 'test-email-verification-token'

/**
 * POST /api/v1/auth/email/send-code — 200
 *
 * `debug_code` is null by default, matching production. Passing one makes the
 * register page pre-fill the code boxes for you (register/page.tsx:88), which
 * is dev-only behaviour — leave it out unless that is what you are testing.
 */
export function sendCodeResponse(overrides: Record<string, unknown> = {}) {
  return { message: 'Code sent', expires_in_minutes: 10, debug_code: null, ...overrides }
}

/**
 * POST /api/v1/auth/email/verify-code — 200
 *
 * The page only treats the address as verified when the echoed `email` matches
 * what is in the form (register/page.tsx:45), so callers must pass their own.
 */
export function verifyCodeResponse(email: string, overrides: Record<string, unknown> = {}) {
  return {
    verified: true,
    email,
    email_verification_token: VERIFICATION_TOKEN,
    expires_in_minutes: 30,
    ...overrides,
  }
}

/** FastAPI's error envelope — every 4xx in this app uses `detail`. */
export function apiError(detail: string) {
  return { detail }
}

// ── Workspace ───────────────────────────────────────────────────────────────

export const WORKSPACE_ID = '00000000-0000-4000-8000-0000000000b1'

/**
 * Every permission the backend defines (app/core/permissions.py, mirrored in
 * frontend/src/lib/workspace.ts:38). An owner sees every control.
 */
export const ALL_PERMISSIONS = [
  'agents:read', 'agents:write', 'agents:delete',
  'calls:write', 'phone_numbers:write', 'workflows:write',
  'tools:write', 'knowledge:write', 'integrations:write',
  'team:read', 'team:manage', 'team:manage_admins',
  'billing:read', 'billing:manage',
  'api_keys:read', 'api_keys:manage',
  'workspace:manage', 'workspace:delete', 'workspace:transfer_ownership',
]

/** A read-only member: may look at agents, may not change them. */
export const VIEWER_PERMISSIONS = ['agents:read', 'team:read']

/**
 * GET /api/v1/workspaces/current — 200
 *
 * dashboard/layout.tsx loads this on mount and every page under /dashboard
 * reads `permissions` off it. Returning `{}` here (the catch-all default) makes
 * `workspace.permissions.includes(...)` throw and blanks the page, so any
 * dashboard test must stub it.
 */
export function workspaceResponse(overrides: Record<string, unknown> = {}) {
  return {
    id: WORKSPACE_ID,
    name: 'QA Workspace',
    slug: 'qa-workspace',
    plan_type: 'pro',
    role: 'owner',
    is_owner: true,
    permissions: ALL_PERMISSIONS,
    member_count: 1,
    owner_email: TEST_USER.email,
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

/** GET /api/v1/workspaces — 200 (the workspace switcher's list) */
export function workspaceListResponse() {
  return [
    {
      id: WORKSPACE_ID,
      name: 'QA Workspace',
      slug: 'qa-workspace',
      role: 'owner',
      is_owner: true,
      is_current: true,
      member_count: 1,
      joined_at: '2026-01-01T00:00:00Z',
      plan_type: 'pro',
    },
  ]
}

/**
 * GET /api/v1/billing/entitlements — 200
 *
 * Mirrors `Entitlements` in frontend/src/lib/entitlements.ts. A live, paid plan
 * by default so BillingBanner stays quiet and no upgrade dialog steals clicks.
 */
export function entitlementsResponse(overrides: Record<string, unknown> = {}) {
  return {
    status: 'active',
    plan_id: 'plan_pro',
    plan_slug: 'pro',
    plan_name: 'Pro',
    plan_tier: 2,
    source: 'stripe',
    billing_period: 'monthly',
    is_live: true,
    is_read_only: false,
    is_trial: false,
    in_grace: false,
    has_subscription: true,
    trial_end: null,
    days_remaining: null,
    trial_expiring_soon: false,
    grace_period_end: null,
    grace_days_remaining: null,
    current_period_end: '2026-12-31T00:00:00Z',
    cancel_at_period_end: false,
    features: [
      'inbound_calls', 'outbound_calls', 'workflows', 'knowledge_base',
      'analytics', 'call_recordings', 'api_access', 'crm_integrations',
    ],
    limits: { agents: 25, phone_numbers: 10, workflows: 25, team_members: 10 },
    usage: { agents: 2, phone_numbers: 1, workflows: 1, team_members: 1 },
    overage_allowed: false,
    trial_available: false,
    trial_used: true,
    ...overrides,
  }
}

// ── Agents ──────────────────────────────────────────────────────────────────

export const AGENT_ID = '00000000-0000-4000-8000-00000000a001'
export const SECOND_AGENT_ID = '00000000-0000-4000-8000-00000000a002'

/**
 * One row of GET /api/v1/agents.
 *
 * Field names match `AgentResponse` in backend/app/schemas/agent.py and the
 * `Agent` interface the list page reads (dashboard/agents/page.tsx:18).
 */
export function agent(overrides: Record<string, unknown> = {}) {
  return {
    id: AGENT_ID,
    name: 'Riley',
    description: 'Books appointments for the clinic',
    llm_provider: 'openai',
    llm_model: 'gpt-4o-mini',
    tts_provider: 'elevenlabs',
    stt_provider: 'deepgram',
    is_active: true,
    created_at: '2026-02-01T00:00:00Z',
    ...overrides,
  }
}

/** GET /api/v1/agents — 200 */
export function agentListResponse(agents = [agent()]) {
  return { agents, total: agents.length }
}

/**
 * GET /api/v1/agents/{id} — 200
 *
 * The edit page reads the nested config objects it PATCHes back, so the detail
 * shape is wider than a list row.
 */
export function agentDetail(overrides: Record<string, unknown> = {}) {
  return {
    ...agent(),
    system_prompt: 'You are Riley, a friendly clinic receptionist.',
    first_message: 'Thanks for calling Wellness Partners, this is Riley.',
    llm: { provider: 'openai', model: 'gpt-4o-mini', temperature: 0.7, max_tokens: 500 },
    voice: { provider: 'elevenlabs', voice_id: 'rachel', speed: 1, pitch: 1 },
    stt: { provider: 'deepgram', model: 'nova-2', language: 'en' },
    settings: {
      interrupt_enabled: true,
      interrupt_sensitivity: 0.5,
      silence_timeout: 2000,
      max_call_duration: 600,
    },
    advanced: {
      background_noise_reduction: true,
      sentiment_analysis_enabled: false,
      emotion_detection_enabled: false,
    },
    ...overrides,
  }
}

/**
 * GET /api/v1/agents/stats — 200
 *
 * Supplementary: the list page swallows a failure here and renders zeroes
 * (dashboard/agents/page.tsx:283), so a broken stats call must never fail a
 * test about agents.
 */
export function agentStatsResponse(stats: Record<string, unknown> = {}) {
  return {
    stats: {
      [AGENT_ID]: {
        total_calls: 12,
        completed_calls: 10,
        total_duration_seconds: 3600,
        success_rate: 0.83,
        last_call_at: '2026-02-10T12:00:00Z',
      },
      ...stats,
    },
  }
}

// ── Dashboard widgets ───────────────────────────────────────────────────────

/** GET /api/v1/calls/stats — 200 */
export function callStatsResponse(overrides: Record<string, unknown> = {}) {
  return { total_calls: 42, completed_calls: 38, failed_calls: 4, ...overrides }
}

/** GET /api/v1/workflows — 200 */
export function workflowListResponse(workflows: unknown[] = []) {
  return { workflows, total: workflows.length }
}

/** GET /api/v1/integrations/connections — 200 */
export function connectionListResponse(connections: unknown[] = []) {
  return { connections, total: connections.length }
}

/**
 * A 402 body from `require_entitlement`, captured from the live API.
 *
 * The `code` field is load-bearing: frontend/src/lib/api.ts:66 only raises the
 * upgrade dialog when it reads exactly `entitlement_required`. A plain
 * `{detail}` 402 falls through as an ordinary error, which is precisely the
 * regression this fixture guards.
 */
export function entitlementError(overrides: Record<string, unknown> = {}) {
  return {
    detail: 'Your plan allows 1 agent. Upgrade to add more.',
    code: 'entitlement_required',
    reason: 'limit_exceeded',
    limit_label: 'agent',
    status: 'trialing',
    current_plan: 'voice-ai',
    current_plan_name: 'Voice AI',
    upgrade_url: '/dashboard/settings/billing',
    ...overrides,
  }
}
