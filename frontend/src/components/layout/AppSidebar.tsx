import { PanelLeftClose, PanelLeftOpen, ShieldCheck } from 'lucide-react'
import { NavLink, useLocation } from 'react-router-dom'

import { APP_NAME, APP_TAGLINE } from '../../lib/constants'
import { navGroupLabels, navSections, sectionForPath, type NavGroupId } from '../../lib/routes'
import { useSystemData } from '../../hooks/useSystemData'
import { cn } from '../../lib/utils'

interface AppSidebarProps {
  collapsed: boolean
  mobileOpen: boolean
  onCollapse: () => void
  onNavigate: () => void
}

const GROUP_ORDER: NavGroupId[] = ['operations', 'agents', 'analysis']

export function AppSidebar({ collapsed, mobileOpen, onCollapse, onNavigate }: AppSidebarProps) {
  const { pathname } = useLocation()
  const active = sectionForPath(pathname)
  const { health } = useSystemData()
  const connected = health?.status === 'healthy' && health.database === 'connected'
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
        {GROUP_ORDER.map((groupId) => (
          <div className="sidebar-group" key={groupId}>
            {!collapsed && <p className="sidebar-group-label">{navGroupLabels[groupId]}</p>}
            {navSections
              .filter((section) => section.group === groupId)
              .map((section) => (
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
          </div>
        ))}
      </nav>
      <div className="sidebar-foot">
        {!collapsed && (
          <div className="sidebar-env">
            <span
              className={cn('chip-dot', connected ? 'is-healthy' : 'is-offline')}
              aria-hidden="true"
            />
            {connected ? 'Backend Connected' : 'Backend Disconnected'}
          </div>
        )}
        {!collapsed && <div className="sidebar-env sidebar-env-muted">Demo Environment</div>}
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
