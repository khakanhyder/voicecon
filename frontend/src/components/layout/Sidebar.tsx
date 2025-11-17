'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import {
  LayoutDashboard,
  Mic,
  Phone,
  Plug,
  Workflow,
  BarChart3,
  Store,
  Settings,
} from 'lucide-react'

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Agents', href: '/dashboard/agents', icon: Mic },
  { name: 'Calls', href: '/dashboard/calls', icon: Phone },
  { name: 'Integrations', href: '/dashboard/integrations', icon: Plug },
  { name: 'Workflows', href: '/dashboard/workflows', icon: Workflow },
  { name: 'Analytics', href: '/dashboard/analytics', icon: BarChart3 },
  { name: 'Marketplace', href: '/dashboard/marketplace', icon: Store },
  { name: 'Settings', href: '/dashboard/settings', icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="flex w-64 flex-col border-r bg-background">
      {/* Logo */}
      <div className="flex h-16 items-center gap-2 border-b px-6">
        <div className="text-2xl font-bold text-primary">Voicecon</div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-4">
        {navigation.map((item) => {
          const isActive = pathname === item.href || pathname?.startsWith(item.href + '/')
          const Icon = item.icon

          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
              )}
            >
              <Icon className="h-5 w-5" />
              {item.name}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="border-t p-4">
        <div className="rounded-lg bg-muted p-3 text-sm">
          <p className="font-medium">Starter Plan</p>
          <p className="text-xs text-muted-foreground">100 minutes remaining</p>
          <Link href="/dashboard/settings/billing">
            <button className="mt-2 w-full rounded-md bg-primary px-3 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90">
              Upgrade
            </button>
          </Link>
        </div>
      </div>
    </aside>
  )
}
