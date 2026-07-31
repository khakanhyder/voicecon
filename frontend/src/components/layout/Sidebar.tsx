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
  // Store, // Marketplace feature temporarily disabled
  Settings,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ChevronDown,
  X,
  Hash,
  Zap,
  LogOut,
  User,
  Wrench,
  BookOpen,
  Mic,
  CreditCard,
  Users,
  Key,
  Sliders,
} from 'lucide-react'

/** Sidebar palette — brand green (#0F6A59). */
const SIDEBAR = {
  bg: '#0F6A59',
  panel: 'rgba(0, 0, 0, 0.16)',
  active: 'rgba(255, 255, 255, 0.16)',
  hover: 'rgba(255, 255, 255, 0.08)',
  divider: 'rgba(0, 0, 0, 0.22)',
}

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard, exact: true },
  { name: 'Agents', href: '/dashboard/agents', icon: Bot },
  { name: 'Calls', href: '/dashboard/calls', icon: Phone },
  { name: 'Phone Numbers', href: '/dashboard/phone-numbers', icon: Hash },
  { name: 'Tools', href: '/dashboard/tools', icon: Wrench },
  { name: 'Knowledge Base', href: '/dashboard/knowledge', icon: BookOpen },
  { name: 'Workflows', href: '/dashboard/workflows', icon: GitBranch },
  { name: 'Integrations', href: '/dashboard/integrations', icon: Plug },
  { name: 'Analytics', href: '/dashboard/analytics', icon: BarChart3 },
  // Marketplace feature temporarily disabled
  // { name: 'Marketplace', href: '/dashboard/marketplace', icon: Store },
]

/** Settings renders as an expandable group, matching the design. */
const settingsNav = {
  name: 'Settings',
  href: '/dashboard/settings',
  icon: Settings,
  children: [
    { name: 'Profile', href: '/dashboard/settings/profile', icon: User },
    { name: 'Billing', href: '/dashboard/settings/billing', icon: CreditCard },
    { name: 'Team', href: '/dashboard/settings/team', icon: Users },
    { name: 'API Keys', href: '/dashboard/settings/api-keys', icon: Key },
  ],
}

interface SidebarProps {
  mobileOpen: boolean
  onMobileClose: () => void
}

export function Sidebar({ mobileOpen, onMobileClose }: SidebarProps) {
  const pathname = usePathname()
  const { user, logout } = useAuth()
  const [collapsed, setCollapsed] = useState(false)
  const [userOpen, setUserOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(
    pathname?.startsWith('/dashboard/settings') ?? false
  )

  // Close mobile sidebar on route change
  useEffect(() => {
    onMobileClose()
  }, [pathname])

  // Keep the Settings group open while browsing its sub-pages
  useEffect(() => {
    if (pathname?.startsWith('/dashboard/settings')) setSettingsOpen(true)
  }, [pathname])

  const isActive = (href: string, exact?: boolean) => {
    if (exact) return pathname === href
    return pathname === href || pathname?.startsWith(href + '/')
  }

  const firstName = user?.full_name?.trim().split(' ')[0] || 'there'

  /** Shared row styling for every top-level nav entry. */
  const rowClass = (active: boolean) =>
    cn(
      'group relative flex w-full items-center gap-3 rounded-xl px-3 py-2.5 font-poppins text-[17px] tracking-[0.25px] transition-colors duration-150',
      collapsed ? 'justify-center px-2' : '',
      active ? 'font-medium text-white' : 'text-white/80 hover:text-white'
    )

  const NavItem = ({ item }: { item: typeof navigation[0] }) => {
    const active = isActive(item.href, item.exact)
    const Icon = item.icon
    return (
      <Link
        href={item.href}
        title={collapsed ? item.name : undefined}
        className={rowClass(active)}
        style={{ background: active ? SIDEBAR.active : undefined }}
        onMouseEnter={(e) => {
          if (!active) e.currentTarget.style.background = SIDEBAR.hover
        }}
        onMouseLeave={(e) => {
          if (!active) e.currentTarget.style.background = ''
        }}
      >
        <Icon className="h-5 w-5 flex-shrink-0" strokeWidth={1.75} />
        {!collapsed && <span className="truncate">{item.name}</span>}
        {active && !collapsed && (
          <span className="ml-auto h-1.5 w-1.5 flex-shrink-0 rounded-full bg-white/80" />
        )}
        {collapsed && (
          <div className="absolute left-full ml-3 z-50 hidden whitespace-nowrap rounded-md px-2.5 py-1.5 text-xs font-medium text-white shadow-lg group-hover:block" style={{ background: '#0b5045' }}>
            {item.name}
          </div>
        )}
      </Link>
    )
  }

  const Divider = () => (
    <div
      className={cn('h-[2px] rounded-full', collapsed ? 'mx-2' : 'mx-3')}
      style={{ background: SIDEBAR.divider }}
    />
  )

  const SettingsGroup = () => {
    const active = isActive(settingsNav.href)
    const Icon = settingsNav.icon

    // Collapsed rail has no room for the sub-list — link straight to Settings.
    if (collapsed) {
      return (
        <Link
          href={settingsNav.href}
          title={settingsNav.name}
          className={rowClass(active)}
          style={{ background: active ? SIDEBAR.active : undefined }}
        >
          <Icon className="h-5 w-5 flex-shrink-0" strokeWidth={1.75} />
          <div className="absolute left-full ml-3 z-50 hidden whitespace-nowrap rounded-md px-2.5 py-1.5 text-xs font-medium text-white shadow-lg group-hover:block" style={{ background: '#0b5045' }}>
            {settingsNav.name}
          </div>
        </Link>
      )
    }

    return (
      <div>
        <button
          type="button"
          onClick={() => setSettingsOpen((open) => !open)}
          className={rowClass(active)}
          style={{ background: active && !settingsOpen ? SIDEBAR.active : undefined }}
        >
          <Icon className="h-5 w-5 flex-shrink-0" strokeWidth={1.75} />
          <span className="truncate">{settingsNav.name}</span>
          <ChevronDown
            className={cn(
              'ml-auto h-4 w-4 flex-shrink-0 transition-transform duration-200',
              settingsOpen ? '' : '-rotate-90'
            )}
          />
        </button>

        {settingsOpen && (
          <div className="mt-1 space-y-1 pl-[28px] pr-2">
            <Link
              href={settingsNav.href}
              className={cn(
                'flex items-center gap-3 truncate rounded-lg px-3 py-2 font-poppins text-[14px] tracking-[0.25px] transition-colors',
                pathname === settingsNav.href
                  ? 'bg-white/10 font-medium text-white'
                  : 'text-white/75 hover:bg-white/5 hover:text-white'
              )}
            >
              <Sliders className="h-[18px] w-[18px] flex-shrink-0" strokeWidth={2} />
              General
            </Link>
            {settingsNav.children.map((child) => {
              const childActive = isActive(child.href)
              const ChildIcon = child.icon
              return (
                <Link
                  key={child.href}
                  href={child.href}
                  className={cn(
                    'flex items-center gap-3 truncate rounded-lg px-3 py-2 font-poppins text-[14px] tracking-[0.25px] transition-colors',
                    childActive ? 'bg-white/10 font-medium text-white' : 'text-white/75 hover:bg-white/5 hover:text-white'
                  )}
                >
                  <ChildIcon className="h-[18px] w-[18px] flex-shrink-0" strokeWidth={2} />
                  {child.name}
                </Link>
              )
            })}
          </div>
        )}
      </div>
    )
  }

  const sidebarContent = (
    <div
      className="flex h-full flex-col overflow-hidden rounded-2xl"
      style={{ background: SIDEBAR.bg }}
    >
      {/* Logo */}
      <div className={cn("flex h-[72px] flex-shrink-0 items-center", collapsed ? "justify-center px-4" : "justify-start pl-6 px-4")}>
        <Link href="/dashboard" title="Voicecon" className="flex items-center gap-3">
          <Mic className="h-7 w-7 text-white flex-shrink-0" strokeWidth={2.25} />
          {!collapsed && (
            <span className="text-white font-bold text-[22px] tracking-wide font-poppins">Voicecon</span>
          )}
        </Link>
      </div>

      {/* Welcome card */}
      <div className={cn('flex-shrink-0', collapsed ? 'px-2' : 'px-3')}>
        <button
          type="button"
          onClick={() => (collapsed ? setCollapsed(false) : setUserOpen((open) => !open))}
          className={cn(
            'flex w-full items-center gap-3 rounded-xl py-2.5 text-left transition-colors',
            collapsed ? 'justify-center px-2' : 'px-3'
          )}
          style={{ background: SIDEBAR.panel }}
        >
          <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center overflow-hidden rounded-full bg-white/15 text-sm font-semibold text-white">
            {user?.avatar_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={user.avatar_url} alt="" className="h-full w-full object-cover" />
            ) : user?.full_name ? (
              user.full_name[0].toUpperCase()
            ) : (
              <User className="h-4 w-4" />
            )}
          </span>
          {!collapsed && (
            <>
              <span className="min-w-0 flex-1">
                <span className="block font-poppins text-[11px] leading-none text-white/70">
                  Welcome back,
                </span>
                <span className="mt-1 block truncate font-poppins text-[15px] font-semibold leading-tight text-white">
                  {firstName}
                </span>
              </span>
              <ChevronUp
                className={cn(
                  'h-4 w-4 flex-shrink-0 text-white/80 transition-transform duration-200',
                  userOpen ? '' : 'rotate-180'
                )}
              />
            </>
          )}
        </button>

        {/* Account panel — revealed by the chevron */}
        {userOpen && !collapsed && (
          <div className="mt-1.5 overflow-hidden rounded-xl" style={{ background: SIDEBAR.panel }}>
            <p className="truncate px-3 pt-2.5 font-poppins text-[11px] text-white/60">
              {user?.email}
            </p>
            <Link
              href="/dashboard/settings/profile"
              className="mt-1 flex items-center gap-2.5 px-3 py-2 font-poppins text-[14px] text-white/85 transition-colors hover:bg-white/10 hover:text-white"
            >
              <User className="h-4 w-4" strokeWidth={1.75} />
              Profile
            </Link>
            <button
              type="button"
              onClick={() => logout()}
              className="flex w-full items-center gap-2.5 px-3 py-2 font-poppins text-[14px] text-white/85 transition-colors hover:bg-white/10 hover:text-white"
            >
              <LogOut className="h-4 w-4" strokeWidth={1.75} />
              Sign out
            </button>
          </div>
        )}
      </div>

      <div className="pt-4">
        <Divider />
      </div>

      {/* Navigation — main items, then the Settings group directly beneath */}
      <nav className="flex-1 overflow-y-auto py-3">
        <div className={cn('space-y-1', collapsed ? 'px-2' : 'px-3')}>
          {navigation.map((item) => (
            <NavItem key={item.href} item={item} />
          ))}
        </div>

        <div className="py-3">
          <Divider />
        </div>

        <div className={collapsed ? 'px-2' : 'px-3'}>
          <SettingsGroup />
        </div>
      </nav>

    </div>
  )

  // Lives outside the clipped panel so it can overhang the rounded edge.
  const collapseToggle = (
    <button
      onClick={() => setCollapsed(!collapsed)}
      title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      className="absolute right-0 top-1/2 z-20 hidden h-6 w-6 -translate-y-1/2 items-center justify-center rounded-full text-white shadow-md ring-2 ring-white transition-transform hover:scale-105 lg:flex"
      style={{ background: '#0b5045' }}
    >
      {collapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronLeft className="h-3 w-3" />}
    </button>
  )

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className={cn(
          'relative hidden flex-shrink-0 flex-col p-3 transition-all duration-300 ease-in-out lg:flex',
          collapsed ? 'w-[92px]' : 'w-[276px]'
        )}
      >
        {sidebarContent}
        {collapseToggle}
      </aside>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={onMobileClose}
          />
          <aside className="absolute bottom-0 left-0 top-0 z-50 flex w-[288px] flex-col p-3 shadow-2xl">
            <button
              onClick={onMobileClose}
              className="absolute right-5 top-5 z-10 rounded-lg p-2 text-white/80 transition-colors hover:bg-white/10 hover:text-white"
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
