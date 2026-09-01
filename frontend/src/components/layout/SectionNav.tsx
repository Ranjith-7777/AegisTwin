import { NavLink, useLocation } from 'react-router-dom'

import { sectionForPath } from '../../lib/routes'
import { cn } from '../../lib/utils'

/** Sub-navigation for grouped sections, keeping every original route reachable. */
export function SectionNav() {
  const { pathname } = useLocation()
  const section = sectionForPath(pathname)
  if (!section || section.routes.length < 2) return null
  return (
    <nav className="section-nav" aria-label={`${section.label} sections`}>
      {section.routes.map((route) => (
        <NavLink
          key={route.path}
          to={route.path}
          className={({ isActive }) => cn('section-tab', isActive && 'is-active')}
        >
          <route.icon className="size-4 shrink-0" aria-hidden="true" />
          {route.label}
        </NavLink>
      ))}
    </nav>
  )
}
