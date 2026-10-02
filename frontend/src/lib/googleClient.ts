/**
 * Which Google OAuth client the sign-in popup uses.
 *
 * The backend redeems the popup's code with *its* client id and secret, and
 * Google refuses a code issued to any other client ("Google rejected the
 * sign-in"). So the browser has to use the backend's client id, not its own
 * copy: NEXT_PUBLIC_GOOGLE_CLIENT_ID is frozen at build time and went stale the
 * moment the client was changed in the admin dashboard.
 *
 * The build-time value is only a fallback, for a backend that is unreachable or
 * too old to report its client id.
 */
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api'

const BUILD_TIME_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || ''

type ProvidersResponse = {
  google?: boolean
  google_client_id?: string | null
}

/** The client id to use, given what the backend reported (if anything). */
export function resolveGoogleClientId(
  server: ProvidersResponse | undefined,
  buildTime: string = BUILD_TIME_CLIENT_ID,
): string {
  if (!server) return buildTime
  if (server.google === false) return ''
  return server.google_client_id || buildTime
}

export function useGoogleClientId(): { clientId: string; isResolving: boolean } {
  const { data, isPending } = useQuery({
    queryKey: ['auth-providers'],
    queryFn: async () => (await apiClient.get<ProvidersResponse>('/api/v1/auth/providers')).data,
    staleTime: 5 * 60 * 1000,
    retry: false,
  })
  return { clientId: resolveGoogleClientId(data), isResolving: isPending }
}
