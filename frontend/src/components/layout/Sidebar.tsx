'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'
import {
  LayoutDashboard,
  Bot,
  Phone,
  Plug,
  GitBranch,
  BarChart3,
  Store,
  Settings,
  ChevronLeft,
  ChevronRight,
  X,
  Hash,
  Zap,
  LogOut,
  User,
  Wrench,
} from 'lucide-react'

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard, exact: true },
  { name: 'Agents', href: '/dashboard/agents', icon: Bot },
  { name: 'Calls', href: '/dashboard/calls', icon: Phone },
  { name: 'Phone Numbers', href: '/dashboard/phone-numbers', icon: Hash },
  { name: 'Tools', href: '/dashboard/tools', icon: Wrench },
  { name: 'Workflows', href: '/dashboard/workflows', icon: GitBranch },
  { name: 'Integrations', href: '/dashboard/integrations', icon: Plug },
  { name: 'Analytics', href: '/dashboard/analytics', icon: BarChart3 },
  { name: 'Marketplace', href: '/dashboard/marketplace', icon: Store },
]

const bottomNav = [
  { name: 'Settings', href: '/dashboard/settings', icon: Settings },
]

interface SidebarProps {
  mobileOpen: boolean
  onMobileClose: () => void
}

export function Sidebar({ mobileOpen, onMobileClose }: SidebarProps) {
  const pathname = usePathname()
  const { user, logout } = useAuth()
  const [collapsed, setCollapsed] = useState(false)

  // Close mobile sidebar on route change
  useEffect(() => {
    onMobileClose()
  }, [pathname])

  const isActive = (href: string, exact?: boolean) => {
    if (exact) return pathname === href
    return pathname === href || pathname?.startsWith(href + '/')
  }

  const NavItem = ({ item }: { item: typeof navigation[0] }) => {
    const active = isActive(item.href, item.exact)
    const Icon = item.icon
    return (
      <Link
        href={item.href}
        title={collapsed ? item.name : undefined}
        className={cn(
          'group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150',
          collapsed ? 'justify-center px-2' : '',
          active
            ? 'text-white shadow-sm'
            : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
        )}
        style={active ? {
          background: 'linear-gradient(135deg, rgba(17,104,212,0.5) 0%, rgba(26,133,255,0.35) 100%)',
          borderLeft: '2px solid #1a85ff',
          marginLeft: collapsed ? undefined : '0',
        } : {}}
      >
        <Icon className={cn('flex-shrink-0 h-5 w-5', active ? 'text-blue-300' : 'text-slate-400 group-hover:text-slate-200')} />
        {!collapsed && (
          <span className="truncate">{item.name}</span>
        )}
        {active && !collapsed && (
          <span className="ml-auto h-1.5 w-1.5 rounded-full bg-blue-400" />
        )}
        {collapsed && (
          <div className="absolute left-full ml-3 hidden rounded-md bg-slate-800 px-2.5 py-1.5 text-xs font-medium text-white shadow-lg group-hover:block whitespace-nowrap z-50 border border-slate-700">
            {item.name}
          </div>
        )}
      </Link>
    )
  }

  const sidebarContent = (
    <div className="flex h-full flex-col" style={{ background: 'hsl(222 47% 6%)' }}>
      {/* Logo */}
      <div className={cn(
        'flex h-16 items-center border-b px-4 flex-shrink-0',
        'border-white/10',
        collapsed ? 'justify-center' : 'gap-3'
      )}>
        <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg gradient-primary shadow-lg">
          <Zap className="h-4 w-4 text-white" />
        </div>
        {!collapsed && (
          <span className="text-lg font-bold text-white tracking-tight">Voicecon</span>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4 px-2 space-y-0.5">
        {navigation.map((item) => (
          <NavItem key={item.href} item={item} />
        ))}
      </nav>

      {/* Divider + Bottom nav */}
      <div className="border-t border-white/10 py-3 px-2 space-y-0.5">
        {bottomNav.map((item) => (
          <NavItem key={item.href} item={item} />
        ))}
      </div>

      {/* User profile */}
      <div className="border-t border-white/10 p-3">
        {collapsed ? (
          <button
            onClick={logout}
            title="Logout"
            className="flex w-full items-center justify-center rounded-lg p-2 text-slate-400 hover:bg-white/5 hover:text-slate-200 transition-colors"
          >
            <LogOut className="h-4 w-4" />
          </button>
        ) : (
          <div className="flex items-center gap-3 rounded-lg px-2 py-2">
            <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-white text-sm font-semibold" style={{ background: 'linear-gradient(135deg, #1168d4 0%, #1a85ff 100%)' }}>
              {user?.full_name ? user.full_name[0].toUpperCase() : <User className="h-4 w-4" />}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-white">{user?.full_name || 'User'}</p>
              <p className="truncate text-xs text-slate-400">{user?.email}</p>
            </div>
            <button
              onClick={logout}
              title="Logout"
              className="rounded-md p-1.5 text-slate-400 hover:bg-white/10 hover:text-slate-200 transition-colors"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>

      {/* Collapse toggle — desktop only */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="hidden lg:flex absolute -right-3 top-20 h-6 w-6 items-center justify-center rounded-full border border-slate-700 bg-slate-900 text-slate-400 hover:text-white shadow-md transition-colors z-10"
      >
        {collapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronLeft className="h-3 w-3" />}
      </button>
    </div>
  )

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className={cn(
          'relative hidden lg:flex flex-col flex-shrink-0 transition-all duration-300 ease-in-out',
          collapsed ? 'w-16' : 'w-60'
        )}
      >
        {sidebarContent}
      </aside>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={onMobileClose}
          />
          <aside className="absolute left-0 top-0 bottom-0 w-72 flex flex-col shadow-2xl z-50">
            <button
              onClick={onMobileClose}
              className="absolute right-3 top-3 z-10 rounded-lg p-2 text-slate-400 hover:bg-white/10 hover:text-white transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
            {sidebarContent}
          </aside>
        </div>
      )}
    </>
  )
}
