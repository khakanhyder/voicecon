'use client'

import { useEffect, useRef, useState } from 'react'
import { Bell, Check, X, CheckCheck } from 'lucide-react'
import { toast } from 'sonner'
import { useNotifications, type AppNotification } from '@/hooks/useNotifications'
import { getErrorMessage } from '@/lib/api'

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const {
    notifications,
    unreadCount,
    isLoading,
    markRead,
    markAllRead,
    acceptInvite,
    rejectInvite,
  } = useNotifications()

  // Close on outside click / Escape.
  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const isInvite = (n: AppNotification) => n.type === 'team_invitation'
  const canAct = (n: AppNotification) => isInvite(n) && !n.is_actioned && n.data?.invitation_token

  const handleAccept = async (n: AppNotification) => {
    try {
      await acceptInvite.mutateAsync(n.data.invitation_token)
      toast.success(`You've joined ${n.data.organization_name ?? 'the team'}.`)
    } catch (e) {
      toast.error(getErrorMessage(e))
    }
  }

  const handleReject = async (n: AppNotification) => {
    try {
      await rejectInvite.mutateAsync(n.data.invitation_token)
      toast.success('Invitation declined.')
    } catch (e) {
      toast.error(getErrorMessage(e))
    }
  }

  const onOpen = () => {
    setOpen((v) => !v)
  }

  const acting = acceptInvite.isPending || rejectInvite.isPending

  return (
    <div className="relative" ref={panelRef}>
      <button
        onClick={onOpen}
        aria-label="Notifications"
        className="relative flex items-center justify-center h-9 w-9 rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50 hover:text-slate-700 transition-colors"
      >
        <Bell className="h-4.5 w-4.5" />
        {unreadCount > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-blue-500 px-1 text-[10px] font-semibold text-white ring-2 ring-white">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-11 z-50 w-[360px] max-w-[calc(100vw-2rem)] rounded-xl border border-slate-200 bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <h3 className="text-sm font-semibold text-slate-900">Notifications</h3>
            {unreadCount > 0 && (
              <button
                onClick={() => markAllRead.mutate()}
                className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-700"
              >
                <CheckCheck className="h-3.5 w-3.5" />
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-[420px] overflow-y-auto">
            {isLoading ? (
              <div className="p-6 text-center text-sm text-slate-400">Loading…</div>
            ) : notifications.length === 0 ? (
              <div className="flex flex-col items-center gap-2 p-8 text-center">
                <Bell className="h-8 w-8 text-slate-300" />
                <p className="text-sm text-slate-500">You're all caught up</p>
              </div>
            ) : (
              notifications.map((n) => (
                <div
                  key={n.id}
                  className={`border-b border-slate-50 px-4 py-3 transition-colors ${
                    n.is_read ? 'bg-white' : 'bg-blue-50/40'
                  }`}
                  onMouseEnter={() => {
                    if (!n.is_read) markRead.mutate(n.id)
                  }}
                >
                  <div className="flex items-start gap-2">
                    {!n.is_read && <span className="mt-1.5 h-2 w-2 flex-shrink-0 rounded-full bg-blue-500" />}
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-slate-900">{n.title}</p>
                      {n.body && <p className="mt-0.5 text-xs text-slate-500 leading-relaxed">{n.body}</p>}
                      <p className="mt-1 text-[11px] text-slate-400">{timeAgo(n.created_at)}</p>

                      {canAct(n) && (
                        <div className="mt-2 flex gap-2">
                          <button
                            disabled={acting}
                            onClick={() => handleAccept(n)}
                            className="inline-flex items-center gap-1 rounded-md bg-blue-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
                          >
                            <Check className="h-3 w-3" />
                            Accept
                          </button>
                          <button
                            disabled={acting}
                            onClick={() => handleReject(n)}
                            className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2.5 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-60"
                          >
                            <X className="h-3 w-3" />
                            Decline
                          </button>
                        </div>
                      )}
                      {isInvite(n) && n.is_actioned && (
                        <p className="mt-1.5 text-[11px] font-medium text-slate-400">Responded</p>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
