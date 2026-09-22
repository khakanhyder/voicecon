/**
 * Where the Google and Apple buttons take you.
 *
 * The rule under test, for both providers alike:
 *   - a brand-new account starts the onboarding flow
 *   - an account that never finished onboarding *continues* it, even though it
 *     is no longer new
 *   - an account that finished goes straight to the dashboard, and is never
 *     sent back into onboarding
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

// `vi.mock` factories are hoisted above the file, so the spies they close over
// have to be created with `vi.hoisted` or they are not initialized yet.
const { push, googleAuth, appleAuth, signInWithApple, getStatus } = vi.hoisted(() => ({
  push: vi.fn(),
  googleAuth: vi.fn(),
  appleAuth: vi.fn(),
  signInWithApple: vi.fn(),
  getStatus: vi.fn(),
}))

vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }))
vi.mock('@/lib/auth', () => ({ authService: { googleAuth, appleAuth } }))
vi.mock('@/lib/appleAuth', () => ({
  signInWithApple,
  isAppleConfigured: () => true,
}))
vi.mock('@/lib/onboarding', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/onboarding')>()
  return { ...actual, onboardingService: { getStatus } }
})

import { useSocialAuth } from './useSocialAuth'

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

const session = (isNew: boolean) => ({
  access_token: 't',
  user: { id: 'u1', email: 'a@example.com', is_new: isNew },
})

const status = (completed: boolean, step = completed ? 'done' : 'company') => ({
  onboarding_completed: completed,
  step,
  has_company_profile: step !== 'company',
  has_subscription: completed,
  company: null,
})

/** Drive one provider's sign-in and return where it navigated. */
async function signIn(provider: 'google' | 'apple') {
  const { result } = renderHook(() => useSocialAuth(), { wrapper })
  await act(async () => {
    if (provider === 'google') result.current.onGoogleCode('auth-code')
    else result.current.signInWithApple()
  })
  await waitFor(() => expect(push).toHaveBeenCalled())
  return push.mock.calls.at(-1)?.[0]
}

beforeEach(() => {
  push.mockClear()
  googleAuth.mockReset()
  appleAuth.mockReset()
  getStatus.mockReset()
  signInWithApple.mockReset().mockResolvedValue({ id_token: 'tok', full_name: 'A B' })
})

describe.each(['google', 'apple'] as const)('%s sign-in', (provider) => {
  const authMock = () => (provider === 'google' ? googleAuth : appleAuth)

  it('sends a brand-new account into onboarding', async () => {
    authMock().mockResolvedValue(session(true))
    getStatus.mockResolvedValue(status(false))

    expect(await signIn(provider)).toBe('/onboarding/company')
  })

  it('sends a returning account that finished onboarding to the dashboard', async () => {
    authMock().mockResolvedValue(session(false))
    getStatus.mockResolvedValue(status(true))

    expect(await signIn(provider)).toBe('/dashboard')
  })

  it('resumes onboarding for a returning account that never finished it', async () => {
    // The case `is_new` alone got wrong: not a new user, but not set up either.
    authMock().mockResolvedValue(session(false))
    getStatus.mockResolvedValue(status(false, 'pricing'))

    expect(await signIn(provider)).toBe('/onboarding/pricing')
  })

  it('never re-runs onboarding for a completed account the server calls new', async () => {
    authMock().mockResolvedValue(session(true))
    getStatus.mockResolvedValue(status(true))

    expect(await signIn(provider)).toBe('/dashboard')
  })

  it('falls back to is_new when the status call fails', async () => {
    authMock().mockResolvedValue(session(true))
    getStatus.mockRejectedValue(new Error('offline'))

    expect(await signIn(provider)).toBe('/onboarding/company')
  })

  it('falls back to the dashboard for a returning user when status fails', async () => {
    authMock().mockResolvedValue(session(false))
    getStatus.mockRejectedValue(new Error('offline'))

    expect(await signIn(provider)).toBe('/dashboard')
  })
})

describe('apple sign-in specifics', () => {
  it('passes the identity token and first-authorization name to the backend', async () => {
    appleAuth.mockResolvedValue(session(true))
    getStatus.mockResolvedValue(status(false))

    await signIn('apple')

    expect(appleAuth).toHaveBeenCalledWith({ id_token: 'tok', full_name: 'A B' })
  })

  it('does not navigate when the user closes the Apple popup', async () => {
    signInWithApple.mockRejectedValue(new Error('popup_closed_by_user'))

    const { result } = renderHook(() => useSocialAuth(), { wrapper })
    await act(async () => {
      result.current.signInWithApple()
    })

    expect(push).not.toHaveBeenCalled()
    expect(appleAuth).not.toHaveBeenCalled()
  })
})
