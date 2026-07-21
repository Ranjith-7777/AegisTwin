import { useState } from 'react'
import { Outlet } from 'react-router-dom'

import { AppHeader } from './AppHeader'
import { AppSidebar } from './AppSidebar'
import { SimulationBanner } from './SimulationBanner'

export function DashboardLayout() {
  const [collapsed, setCollapsed] = useState(false)
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
          setCollapsed((value) => !value)
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
        <SimulationBanner />
        <AppHeader
          onMenu={() => {
            setMobileOpen(true)
          }}
        />
        <main id="main-content" className="page-content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
