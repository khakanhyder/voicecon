import Link from 'next/link'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Page not found · Voicecon',
  robots: { index: false },
}

/** Replaces Next's unbranded default 404, which offered no way back. */
export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4 text-center">
      <p className="text-sm font-semibold uppercase tracking-wide text-[#0F6A59]">404</p>
      <h1 className="mt-2 text-2xl font-bold text-slate-900 sm:text-3xl">Page not found</h1>
      <p className="mt-3 max-w-md text-sm text-slate-600">
        The page you&apos;re looking for doesn&apos;t exist or has moved.
      </p>
      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Link
          href="/dashboard"
          className="rounded-full bg-[#0F6A59] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#0d5a4c]"
        >
          Go to dashboard
        </Link>
        <Link
          href="/"
          className="rounded-full border border-slate-200 bg-white px-5 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-100"
        >
          Home
        </Link>
      </div>
    </main>
  )
}
