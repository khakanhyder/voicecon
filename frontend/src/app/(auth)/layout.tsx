import Link from 'next/link'
import { VoiceconLogo } from '@/lib/icons'
import { BrandPanel } from '@/components/auth/BrandPanel'
import { MobileAccentBar } from '@/components/auth/MobileAccentBar'

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="min-h-screen lg:h-screen lg:overflow-hidden lg:p-8"
      style={{
        background: 'linear-gradient(135deg, #fdf3ec 0%, #ffffff 45%, #eef4ff 100%)',
      }}
    >
      <div className="mx-auto grid min-h-screen max-w-7xl grid-cols-1 items-stretch gap-4 bg-white md:rounded-3xl md:p-3 shadow-xl shadow-slate-200/60 lg:h-full lg:min-h-0 lg:grid-cols-2 lg:gap-2 lg:overflow-hidden">
        {/* Left — form column */}
        <div className="flex flex-col px-4 pt-10 pb-24 sm:px-8 lg:px-10 lg:py-10">
          <div className="flex flex-1 flex-col justify-center">
            <Link href="/" className="mb-3 flex items-center gap-2">
              <VoiceconLogo className="h-7 w-7" />
              <span className="text-xl font-bold text-slate-900">Voicecon</span>
            </Link>
            {children}
          </div>
        </div>

        {/* Right — brand panel */}
        <div className="hidden lg:block">
          <BrandPanel />
        </div>
      </div>

      {/* Brand accent line — small screens only */}
      <MobileAccentBar />
    </div>
  )
}
