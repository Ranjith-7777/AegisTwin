import { useState } from 'react'
import { Outlet } from 'react-router-dom'

import { AppHeader } from './AppHeader'
import { AppSidebar } from './AppSidebar'
import { SectionNav } from './SectionNav'

const COLLAPSE_KEY = 'aegisarena.sidebarCollapsed'

/** Sidebar preference is a per-browser convenience; storage may be unavailable. */
function readCollapsed(): boolean {
  try {
    return window.localStorage.getItem(COLLAPSE_KEY) === 'true'
  } catch {
    return false
  }
}

function writeCollapsed(value: boolean) {
  try {
    window.localStorage.setItem(COLLAPSE_KEY, String(value))
  } catch {
    // Private mode or blocked storage: the preference simply is not kept.
  }
}

export function DashboardLayout() {
  const [collapsed, setCollapsed] = useState(readCollapsed)
  const [mobileOpen, setMobileOpen] = useState(false)
  return (
    <div className={collapsed ? 'dashboard-shell sidebar-collapsed' : 'dashboard-shell'}>
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>
      <AppSidebar
        collapsed={collapsed}
        mobileOpen={mobileOpen}
        onCollapse={() => {
          setCollapsed((value) => {
            writeCollapsed(!value)
            return !value
          })
        }}
        onNavigate={() => {
          setMobileOpen(false)
        }}
      />
      {mobileOpen ? (
        <button
          className="sidebar-scrim"
          onClick={() => {
            setMobileOpen(false)
          }}
          aria-label="Close navigation"
        />
      ) : null}
      <div className="dashboard-main">
        <AppHeader
          onMenu={() => {
            setMobileOpen(true)
          }}
        />
        <main id="main-content" className="page-content" tabIndex={-1}>
          <SectionNav />
          <Outlet />
        </main>
      </div>
    </div>
  )
}
