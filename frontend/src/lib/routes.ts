import {
  Activity,
  Bot,
  Boxes,
  FileClock,
  GitBranch,
  LayoutDashboard,
  RadioTower,
  Radar,
  Settings,
  ShieldAlert,
  ShieldCheck,
  Target,
  type LucideIcon,
} from 'lucide-react'

export interface AppRouteDefinition {
  path: string
  label: string
  icon: LucideIcon
}

export interface NavSection {
  id: string
  label: string
  icon: LucideIcon
  /** The first entry is the section landing route. */
  routes: [AppRouteDefinition, ...AppRouteDefinition[]]
}

/**
 * Five sidebar entries. Every existing route is preserved and reachable through
 * the grouped sub-navigation rendered inside each section.
 */
export const navSections: NavSection[] = [
  {
    id: 'overview',
    label: 'Overview',
    icon: LayoutDashboard,
    routes: [{ path: '/', label: 'Command Centre', icon: LayoutDashboard }],
  },
  {
    id: 'digital-twin',
    label: 'Digital Twin',
    icon: Boxes,
    routes: [{ path: '/digital-twin', label: 'Cloud Digital Twin', icon: Boxes }],
  },
  {
    id: 'threat-analysis',
    label: 'Threat Analysis',
    icon: Target,
    routes: [
      { path: '/telemetry', label: 'Live Telemetry', icon: RadioTower },
      { path: '/incidents', label: 'Incidents', icon: ShieldAlert },
      { path: '/mitre', label: 'MITRE ATT&CK', icon: ShieldCheck },
      { path: '/predictive-analytics', label: 'Attack Prediction', icon: Radar },
    ],
  },
  {
    id: 'defense',
    label: 'Defense',
    icon: Bot,
    routes: [
      { path: '/response-centre', label: 'Blue Agent', icon: Bot },
      { path: '/response-operations', label: 'Response Operations', icon: GitBranch },
    ],
  },
  {
    id: 'results',
    label: 'Results',
    icon: FileClock,
    routes: [
      { path: '/model-analytics', label: 'Detection Models', icon: Activity },
      { path: '/audit-trail', label: 'Audit Trail', icon: FileClock },
      { path: '/settings', label: 'Settings', icon: Settings },
    ],
  },
]

export const appRoutes: AppRouteDefinition[] = navSections.flatMap((section) => section.routes)

export function sectionForPath(pathname: string): NavSection | undefined {
  return navSections.find((section) =>
    section.routes.some((route) =>
      route.path === '/' ? pathname === '/' : pathname.startsWith(route.path),
    ),
  )
}
