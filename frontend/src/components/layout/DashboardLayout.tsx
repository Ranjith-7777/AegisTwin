import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'

import { AppHeader } from './AppHeader'
import { AppSidebar } from './AppSidebar'
import { SectionNav } from './SectionNav'

export function DashboardLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const { pathname } = useLocation()
  const isOverview = pathname === '/'
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
        <AppHeader
          onMenu={() => {
            setMobileOpen(true)
          }}
        />
        <main
          id="main-content"
          className={isOverview ? 'page-content is-fixed' : 'page-content'}
          tabIndex={-1}
        >
          <SectionNav />
          <Outlet />
        </main>
      </div>
    </div>
  )
}
