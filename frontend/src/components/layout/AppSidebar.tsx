import { PanelLeftClose, PanelLeftOpen, ShieldCheck } from 'lucide-react'
import { NavLink, useLocation } from 'react-router-dom'

import { APP_NAME, APP_TAGLINE } from '../../lib/constants'
import { navSections, sectionForPath } from '../../lib/routes'
import { cn } from '../../lib/utils'

interface AppSidebarProps {
  collapsed: boolean
  mobileOpen: boolean
  onCollapse: () => void
  onNavigate: () => void
}

export function AppSidebar({ collapsed, mobileOpen, onCollapse, onNavigate }: AppSidebarProps) {
  const { pathname } = useLocation()
  const active = sectionForPath(pathname)
  return (
    <aside
      className={cn('app-sidebar', collapsed && 'is-collapsed', mobileOpen && 'is-mobile-open')}
      aria-label="Application sidebar"
    >
      <div className="sidebar-brand">
        <span className="brand-mark">
          <ShieldCheck className="size-[1.05rem]" aria-hidden="true" />
        </span>
        {!collapsed && (
          <span className="brand-text">
            <span className="brand-name">{APP_NAME}</span>
            <span className="brand-tagline">{APP_TAGLINE}</span>
          </span>
        )}
      </div>
      <nav className="sidebar-nav" aria-label="Primary navigation">
        {navSections.map((section) => (
          <NavLink
            key={section.id}
            to={section.routes[0].path}
            onClick={onNavigate}
            title={section.label}
            className={cn('nav-item', active?.id === section.id && 'is-active')}
          >
            <section.icon className="size-[1.05rem] shrink-0" aria-hidden="true" />
            <span className={cn(collapsed && 'lg:hidden')}>{section.label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-foot">
        {!collapsed && (
          <div className="sidebar-env">
            <span className="chip-dot" aria-hidden="true" />
            Safe Simulation
          </div>
        )}
        <button
          className="nav-item"
          onClick={onCollapse}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? (
            <PanelLeftOpen className="size-[1.05rem] shrink-0" aria-hidden="true" />
          ) : (
            <PanelLeftClose className="size-[1.05rem] shrink-0" aria-hidden="true" />
          )}
          <span className={cn(collapsed && 'lg:hidden')}>Collapse</span>
        </button>
      </div>
    </aside>
  )
}
