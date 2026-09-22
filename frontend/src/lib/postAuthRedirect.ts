/**
 * Where to send someone the moment a session starts.
 *
 * Shared by every sign-in entry point — password login, registration, Google
 * and Apple — so all four agree: unfinished onboarding continues where it left
 * off, finished onboarding goes to the dashboard.
 */
import type { QueryClient } from '@tanstack/react-query'
import { QUERY_KEYS } from './constants'
import { onboardingRedirectPath, onboardingService } from './onboarding'

export async function resolvePostAuthPath(
  queryClient: QueryClient,
  fallback: { isNew?: boolean } = {},
): Promise<string> {
  try {
    // fetchQuery (not ensureQueryData) so the previous session's status can
    // never be reused, and the onboarding layout reads this fresh answer from
    // the cache instead of firing a second request.
    const status = await queryClient.fetchQuery({
      queryKey: QUERY_KEYS.ONBOARDING_STATUS,
      queryFn: onboardingService.getStatus,
    })
    return onboardingRedirectPath(status)
  } catch {
    return onboardingRedirectPath(null, fallback)
  }
}
