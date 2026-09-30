import type { ReactNode } from 'react'
import { VoiceconLogo } from '@/lib/icons'

/**
 * The frame around the portal's sign-in and invitation pages. Same look as the
 * customer app's auth screens, minus the brand panel: one centred card.
 */
export function AuthFrame({ children }: { children: ReactNode }) {
  return (
    <div
      className="flex min-h-screen items-center justify-center px-4 py-10"
      style={{ background: 'linear-gradient(135deg, #fdf3ec 0%, #ffffff 45%, #eef4ff 100%)' }}
    >
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-center gap-2">
          <VoiceconLogo className="h-7 w-7" />
          <span className="text-xl font-bold text-slate-900">VoiceCon</span>
          <span className="ml-1 rounded-full bg-[#243275]/10 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-[#243275]">
            Partners
          </span>
        </div>
        <div className="rounded-3xl bg-white p-6 shadow-xl shadow-slate-200/60 sm:p-8">{children}</div>
      </div>
    </div>
  )
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <div
      role="alert"
      className="mb-5 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
    >
      <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-red-100 text-xs font-bold text-red-500">
        !
      </span>
      {message}
    </div>
  )
}

export function FullScreenSpinner() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-[#243275]" />
    </div>
  )
}
