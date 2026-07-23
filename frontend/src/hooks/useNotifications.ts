'use client'

/**
 * Notifications hook backing the header bell.
 *
 * Polls the unread count and the list on an interval (light, professional
 * near-real-time), and exposes mutations to mark read and to Accept/Reject a
 * team invitation directly from a notification (via its carried token).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { useAuthStore } from '@/store/authStore'

export interface AppNotification {
  id: string
  type: string
  title: string
  body: string
  data: Record<string, any>
  is_read: boolean
  is_actioned: boolean
  created_at: string
}

const POLL_MS = 30_000

export function useNotifications() {
  const qc = useQueryClient()
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)

  const listQuery = useQuery({
    queryKey: ['notifications', 'list'],
    queryFn: async () =>
      (await apiClient.get<AppNotification[]>(API_ENDPOINTS.NOTIFICATIONS)).data,
    enabled: isAuthenticated,
    refetchInterval: POLL_MS,
    retry: false,
  })

  const unreadQuery = useQuery({
    queryKey: ['notifications', 'unread'],
    queryFn: async () =>
      (await apiClient.get<{ count: number }>(API_ENDPOINTS.NOTIFICATIONS_UNREAD_COUNT)).data.count,
    enabled: isAuthenticated,
    refetchInterval: POLL_MS,
    retry: false,
  })

  const invalidate = () => qc.invalidateQueries({ queryKey: ['notifications'] })

  const markRead = useMutation({
    mutationFn: (id: string) => apiClient.post(API_ENDPOINTS.NOTIFICATION_READ(id)),
    onSuccess: invalidate,
  })

  const markAllRead = useMutation({
    mutationFn: () => apiClient.post(API_ENDPOINTS.NOTIFICATIONS_READ_ALL),
    onSuccess: invalidate,
  })

  const acceptInvite = useMutation({
    mutationFn: (token: string) => apiClient.post(API_ENDPOINTS.INVITATION_ACCEPT(token)),
    onSuccess: () => {
      invalidate()
      qc.invalidateQueries({ queryKey: ['team'] })
    },
  })

  const rejectInvite = useMutation({
    mutationFn: (token: string) => apiClient.post(API_ENDPOINTS.INVITATION_REJECT(token)),
    onSuccess: invalidate,
  })

  return {
    notifications: listQuery.data ?? [],
    unreadCount: unreadQuery.data ?? 0,
    isLoading: listQuery.isLoading,
    markRead,
    markAllRead,
    acceptInvite,
    rejectInvite,
    refetch: invalidate,
  }
}
