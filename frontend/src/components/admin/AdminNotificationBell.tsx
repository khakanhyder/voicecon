'use client'

/**
 * The admin console's bell: staff notifications such as a new affiliate request.
 *
 * Separate from the customer app's bell (`layout/NotificationBell`) on purpose.
 * It reads `/admin/notifications` with the console session, and those
 * notifications never appear in the app.
 */
import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, CheckCheck } from 'lucide-react'
import { adminApi, type AdminNotification } from '@/lib/admin'
import { RelativeTime } from '@/components/ui/relative-time'
import { cn } from '@/lib/utils'

const POLL_MS = 30_000

/** Where a notification leads. Only paths inside the console are followed. */
function target(n: AdminNotification): string | null {
  const href = n.data?.href
  return typeof href === 'string' && href.startsWith('/admin/') ? href : null
}

export function AdminNotificationBell({
  align = 'left',
  tone = 'dark',
}: {
  /** Which edge of the button the panel lines up with. */
  align?: 'left' | 'right'
  /** `dark` sits on the sidebar, `light` on the mobile header. */
  tone?: 'dark' | 'light'
}) {
  const router = useRouter()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const list = useQuery({
    queryKey: ['admin', 'notifications', 'list'],
    queryFn: adminApi.notifications,
    refetchInterval: POLL_MS,
    retry: false,
  })
  const unread = useQuery({
    queryKey: ['admin', 'notifications', 'unread'],
    queryFn: adminApi.unreadNotificationCount,
    refetchInterval: POLL_MS,
    retry: false,
  })
  const invalidate = () => qc.invalidateQueries({ queryKey: ['admin', 'notifications'] })
  const markRead = useMutation({ mutationFn: adminApi.markNotificationRead, onSuccess: invalidate })
  const markAllRead = useMutation({ mutationFn: adminApi.markAllNotificationsRead, onSuccess: invalidate })

  // Close on outside click / Escape.
  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const notifications = list.data ?? []
  const count = unread.data?.count ?? 0

  const openNotification = (n: AdminNotification) => {
    if (!n.is_read) markRead.mutate(n.id)
    const href = target(n)
    if (!href) return
    setOpen(false)
    router.push(href)
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={count > 0 ? `Notifications, ${count} unread` : 'Notifications'}
        aria-expanded={open}
        className={cn(
          'relative flex h-9 w-9 items-center justify-center rounded-lg transition-colors',
          tone === 'dark' ? 'text-slate-400 hover:bg-white/10 hover:text-white' : 'text-slate-600 hover:bg-slate-100'
        )}
      >
        <Bell className="h-[18px] w-[18px]" />
        {count > 0 && (
          <span
            className={cn(
              'absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-semibold text-white ring-2',
              tone === 'dark' ? 'ring-slate-950' : 'ring-white'
            )}
          >
            {count > 9 ? '9+' : count}
          </span>
        )}
      </button>

      {open && (
        <div
          className={cn(
            'absolute top-11 z-50 w-[360px] max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border border-slate-200 bg-white text-left shadow-xl',
            align === 'left' ? 'left-0' : 'right-0'
          )}
        >
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <h2 className="text-sm font-semibold text-slate-900">Notifications</h2>
            {count > 0 && (
              <button
                type="button"
                onClick={() => markAllRead.mutate()}
                className="flex items-center gap-1 text-xs font-medium text-brand-700 hover:text-brand-800"
              >
                <CheckCheck className="h-3.5 w-3.5" />
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-[420px] overflow-y-auto">
            {list.isLoading ? (
              <div className="p-6 text-center text-sm text-slate-400">Loading…</div>
            ) : list.isError ? (
              <div className="p-6 text-center text-sm text-rose-600">Could not load notifications.</div>
            ) : notifications.length === 0 ? (
              <div className="flex flex-col items-center gap-2 p-8 text-center">
                <Bell className="h-8 w-8 text-slate-300" />
                <p className="text-sm text-slate-500">You&apos;re all caught up</p>
              </div>
            ) : (
              notifications.map((n) => {
                const href = target(n)
                return (
                  <button
                    key={n.id}
                    type="button"
                    onClick={() => openNotification(n)}
                    className={cn(
                      'flex w-full items-start gap-2 border-b border-slate-50 px-4 py-3 text-left transition-colors hover:bg-slate-50',
                      !n.is_read && 'bg-brand-50/60'
                    )}
                  >
                    <span className={cn('mt-1.5 h-2 w-2 flex-shrink-0 rounded-full', n.is_read ? 'bg-transparent' : 'bg-brand-600')} />
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium text-slate-900">{n.title}</span>
                      {n.body && <span className="mt-0.5 block break-words text-xs leading-relaxed text-slate-500">{n.body}</span>}
                      <span className="mt-1 flex items-center gap-2 text-[11px] text-slate-400">
                        <RelativeTime value={n.created_at} />
                        {n.is_actioned ? <span>· Handled</span> : href ? <span className="font-medium text-brand-700">· Review</span> : null}
                      </span>
                    </span>
                  </button>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}
