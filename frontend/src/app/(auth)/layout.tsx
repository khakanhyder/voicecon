import Link from 'next/link'
import { Zap } from 'lucide-react'

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Left panel — branding */}
      <div className="hidden lg:flex lg:w-[45%] xl:w-[40%] flex-col relative overflow-hidden" style={{ background: 'hsl(222 47% 8%)' }}>
        {/* Background decoration */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute -top-40 -left-40 h-96 w-96 rounded-full bg-blue-500/10 blur-3xl" />
          <div className="absolute top-1/2 -right-20 h-72 w-72 rounded-full bg-violet-500/10 blur-3xl" />
          <div className="absolute -bottom-20 left-1/3 h-64 w-64 rounded-full bg-indigo-400/10 blur-3xl" />
          {/* Grid */}
          <div
            className="absolute inset-0 opacity-5"
            style={{
              backgroundImage: 'linear-gradient(rgba(255,255,255,0.15) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.15) 1px, transparent 1px)',
              backgroundSize: '40px 40px',
            }}
          />
        </div>

        <div className="relative flex flex-col h-full p-10">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl gradient-primary shadow-lg shadow-indigo-500/30">
              <Zap className="h-5 w-5 text-white" />
            </div>
            <span className="text-xl font-bold text-white">Voicecon</span>
          </Link>

          {/* Hero content */}
          <div className="flex-1 flex flex-col justify-center py-16">
            <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-blue-500/10 px-4 py-1.5 text-sm text-indigo-300 font-medium mb-6 w-fit">
              <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-pulse" />
              Voice AI Platform
            </div>
            <h2 className="text-4xl xl:text-5xl font-bold text-white leading-tight">
              Build smarter<br />
              <span className="text-gradient">voice AI agents</span><br />
              in minutes.
            </h2>
            <p className="mt-5 text-lg text-slate-400 max-w-sm leading-relaxed">
              Deploy AI-powered voice agents, automate workflows, and connect your entire business stack.
            </p>

            {/* Stats */}
            <div className="mt-10 grid grid-cols-3 gap-4">
              {[
                { value: '10M+', label: 'Calls handled' },
                { value: '99.9%', label: 'Uptime SLA' },
                { value: '< 500ms', label: 'Response time' },
              ].map((stat) => (
                <div key={stat.label} className="rounded-xl border border-white/10 bg-white/5 p-4">
                  <div className="text-xl font-bold text-white">{stat.value}</div>
                  <div className="text-xs text-slate-400 mt-0.5">{stat.label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Testimonial */}
          <div className="rounded-xl border border-white/10 bg-white/5 p-5">
            <p className="text-sm text-slate-300 leading-relaxed">
              &ldquo;Voicecon reduced our customer support call handling time by 68% while improving satisfaction scores.&rdquo;
            </p>
            <div className="mt-3 flex items-center gap-3">
              <div className="h-8 w-8 rounded-full bg-blue-500 flex items-center justify-center text-white text-sm font-bold">S</div>
              <div>
                <div className="text-sm font-medium text-white">Sarah Chen</div>
                <div className="text-xs text-slate-400">CTO at TechCorp</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right panel — auth form */}
      <div className="flex flex-1 flex-col items-center justify-center px-6 py-12">
        {/* Mobile logo */}
        <Link href="/" className="flex lg:hidden items-center gap-2 mb-10">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg gradient-primary">
            <Zap className="h-4 w-4 text-white" />
          </div>
          <span className="text-lg font-bold text-slate-900">Voicecon</span>
        </Link>

        {children}
      </div>
    </div>
  )
}
