import { Info, PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { NavLink, useLocation } from 'react-router-dom'

import { APP_NAME } from '../../lib/constants'
import { navSections, sectionForPath } from '../../lib/routes'
import { useSystemData } from '../../hooks/useSystemData'
import { useOptionalAutonomyWorkflow } from '../../hooks/useAutonomyWorkflow'
import { cn } from '../../lib/utils'
import { Tip } from '../ui/panel'
import { BrandMark } from './BrandMark'

interface AppSidebarProps {
  collapsed: boolean
  mobileOpen: boolean
  onCollapse: () => void
  onNavigate: () => void
}

/**
 * Primary navigation. On desktop it can collapse to an icon rail: labels stay
 * in the accessibility tree (visually hidden) and appear as tooltips on hover
 * and keyboard focus. The mobile drawer always shows labels.
 */
export function AppSidebar({ collapsed, mobileOpen, onCollapse, onNavigate }: AppSidebarProps) {
  const { pathname } = useLocation()
  const active = sectionForPath(pathname)
  const { health, system } = useSystemData()
  const workflow = useOptionalAutonomyWorkflow()
  const connected = health?.status === 'healthy' && health.database === 'connected'
  const awaitingApproval = workflow?.stages.some((stage) => stage.status === 'awaiting') ?? false
  const environment = health?.environment ?? system?.environment ?? null
  return (
    <aside
      className={cn('app-sidebar', collapsed && 'is-collapsed', mobileOpen && 'is-mobile-open')}
      aria-label="Application sidebar"
    >
      <div className="sidebar-brand">
        <BrandMark />
        <span className="brand-text nav-label">
          <span className="brand-name">{APP_NAME}</span>
        </span>
      </div>
      <nav className="sidebar-nav" aria-label="Primary navigation">
        <div className="sidebar-group">
          {navSections.map((section) => (
            <NavLink
              key={section.id}
              to={section.routes[0].path}
              end
              onClick={onNavigate}
              data-tip={section.label}
              aria-current={active?.id === section.id ? 'page' : undefined}
              className={cn('nav-item', active?.id === section.id && 'is-active')}
            >
              <section.icon className="shrink-0" aria-hidden="true" />
              <span className="nav-label">{section.label}</span>
              {section.id === 'workflow' && awaitingApproval ? (
                <span className="nav-badge" aria-label="Approval pending">
                  1
                </span>
              ) : null}
            </NavLink>
          ))}
        </div>
      </nav>
      <div className="sidebar-foot">
        <div className="sidebar-env nav-label" role="status">
          <span
            className={cn('chip-dot', connected ? 'is-healthy' : 'is-offline')}
            aria-hidden="true"
          />
          {connected ? 'Backend connected' : 'Backend unavailable'}
        </div>
        <div className="sidebar-card nav-label">
          <span className="sidebar-card-text">
            <strong>{APP_NAME}</strong>
            <span>
              {system?.version ? `v${system.version}` : 'version unavailable'}
              {environment ? ` · ${environment}` : ''}
            </span>
          </span>
          <Tip label="Synthetic cloud cyber range: every asset, event and action is simulated. No real system is ever targeted.">
            <Info className="size-4 text-[var(--text-faint)]" aria-label="About this range" />
          </Tip>
        </div>
        <button
          type="button"
          className="nav-item is-collapse"
          onClick={onCollapse}
          data-tip={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-expanded={!collapsed}
        >
          {collapsed ? (
            <PanelLeftOpen className="shrink-0" aria-hidden="true" />
          ) : (
            <PanelLeftClose className="shrink-0" aria-hidden="true" />
          )}
          <span className="nav-label">Collapse sidebar</span>
        </button>
      </div>
    </aside>
  )
}
