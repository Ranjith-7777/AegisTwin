import { ChevronsLeft, ChevronsRight, Shield } from 'lucide-react'
import { NavLink } from 'react-router-dom'

import { appRoutes } from '../../lib/routes'
import { cn } from '../../lib/utils'
import { Button } from '../ui/button'

interface AppSidebarProps {
  collapsed: boolean
  mobileOpen: boolean
  onCollapse: () => void
  onNavigate: () => void
}

export function AppSidebar({ collapsed, mobileOpen, onCollapse, onNavigate }: AppSidebarProps) {
  return (
    <aside
      className={cn('app-sidebar', collapsed && 'is-collapsed', mobileOpen && 'is-mobile-open')}
      aria-label="Application sidebar"
    >
      <div className="flex h-20 items-center gap-3 border-b border-slate-800 px-4">
        <div className="brand-mark">
          <Shield className="size-5" aria-hidden="true" />
        </div>
        <div className={cn('min-w-0', collapsed && 'lg:hidden')}>
          <p className="text-base font-semibold tracking-wide text-white">AegisTwin</p>
          <p className="truncate text-[0.66rem] uppercase tracking-[0.16em] text-slate-500">
            Cyber-Resilience Twin
          </p>
        </div>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-3" aria-label="Primary navigation">
        {appRoutes.map(({ path, label, icon: Icon }) => (
          <NavLink
            key={path}
            to={path}
            end={path === '/'}
            onClick={onNavigate}
            title={collapsed ? label : undefined}
            className={({ isActive }) => cn('nav-item', isActive && 'is-active')}
          >
            <Icon className="size-[1.1rem] shrink-0" aria-hidden="true" />
            <span className={cn(collapsed && 'lg:hidden')}>{label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="hidden border-t border-slate-800 p-3 lg:block">
        <Button
          variant="ghost"
          className="w-full"
          onClick={onCollapse}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? (
            <ChevronsRight className="size-4" />
          ) : (
            <>
              <ChevronsLeft className="size-4" />
              <span>Collapse</span>
            </>
          )}
        </Button>
      </div>
    </aside>
  )
}
