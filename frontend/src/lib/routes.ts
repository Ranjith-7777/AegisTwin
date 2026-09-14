import {
  Activity,
  Bot,
  Boxes,
  FileClock,
  FlaskConical,
  GitBranch,
  LayoutDashboard,
  ListChecks,
  RadioTower,
  Radar,
  Settings,
  ShieldAlert,
  ShieldCheck,
  Target,
  Workflow,
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
    label: 'Command Centre',
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
      { path: '/blue-agent/overview', label: 'Overview', icon: Bot },
      { path: '/blue-agent/agent-workflow', label: 'Agent Workflow', icon: Workflow },
      { path: '/blue-agent/response-plans', label: 'Response Plans', icon: GitBranch },
      { path: '/blue-agent/policies', label: 'Policies', icon: ListChecks },
      { path: '/blue-agent/verification', label: 'Verification', icon: ShieldCheck },
    ],
  },
  {
    id: 'evaluation',
    label: 'Evaluation',
    icon: FlaskConical,
    routes: [
      { path: '/evaluation', label: 'Overview', icon: FlaskConical },
      { path: '/evaluation/experiments', label: 'Experiments', icon: ListChecks },
      { path: '/evaluation/compare', label: 'Compare', icon: GitBranch },
      { path: '/evaluation/aggregate', label: 'Aggregate', icon: Activity },
      { path: '/evaluation/batches', label: 'Batches', icon: Boxes },
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
