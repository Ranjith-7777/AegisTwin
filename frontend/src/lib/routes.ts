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
  Swords,
  Target,
  Workflow,
  type LucideIcon,
} from 'lucide-react'

export interface AppRouteDefinition {
  path: string
  label: string
  icon: LucideIcon
}

export type NavGroupId = 'operations' | 'agents' | 'analysis'

export interface NavSection {
  id: string
  label: string
  icon: LucideIcon
  group: NavGroupId
  /** The first entry is the section landing route. */
  routes: [AppRouteDefinition, ...AppRouteDefinition[]]
}

export const navGroupLabels: Record<NavGroupId, string> = {
  operations: 'Operations',
  agents: 'Agents',
  analysis: 'Analysis',
}

/**
 * Sidebar entries grouped into Operations / Agents / Analysis. Every existing
 * route is preserved and reachable through the grouped sub-navigation
 * rendered inside each section (see SectionNav).
 */
export const navSections: NavSection[] = [
  {
    id: 'overview',
    label: 'Command Centre',
    icon: LayoutDashboard,
    group: 'operations',
    routes: [{ path: '/', label: 'Command Centre', icon: LayoutDashboard }],
  },
  {
    id: 'digital-twin',
    label: 'Digital Twin',
    icon: Boxes,
    group: 'operations',
    routes: [{ path: '/digital-twin', label: 'Cloud Digital Twin', icon: Boxes }],
  },
  {
    id: 'threat-analysis',
    label: 'Threat Analysis',
    icon: Target,
    group: 'operations',
    routes: [
      { path: '/telemetry', label: 'Live Telemetry', icon: RadioTower },
      { path: '/incidents', label: 'Incidents', icon: ShieldAlert },
      { path: '/mitre', label: 'MITRE ATT&CK', icon: ShieldCheck },
      { path: '/predictive-analytics', label: 'Attack Prediction', icon: Radar },
    ],
  },
  {
    id: 'defense',
    label: 'Blue Agent',
    icon: Bot,
    group: 'agents',
    routes: [
      { path: '/blue-agent/overview', label: 'Overview', icon: Bot },
      { path: '/blue-agent/agent-workflow', label: 'Agent Workflow', icon: Workflow },
      { path: '/blue-agent/response-plans', label: 'Response Plans', icon: GitBranch },
      { path: '/blue-agent/policies', label: 'Policies', icon: ListChecks },
      { path: '/blue-agent/verification', label: 'Verification', icon: ShieldCheck },
    ],
  },
  {
    id: 'red-agent',
    label: 'Red Agent',
    icon: Swords,
    group: 'agents',
    routes: [{ path: '/red-agent', label: 'Red Agent', icon: Swords }],
  },
  {
    id: 'evaluation',
    label: 'Reports',
    icon: ListChecks,
    group: 'analysis',
    routes: [
      { path: '/evaluation/experiments', label: 'Reports', icon: ListChecks },
      { path: '/evaluation', label: 'Overview', icon: FlaskConical },
      { path: '/evaluation/compare', label: 'Compare', icon: GitBranch },
      { path: '/evaluation/aggregate', label: 'Aggregate', icon: Activity },
      { path: '/evaluation/batches', label: 'Batches', icon: Boxes },
    ],
  },
  {
    id: 'results',
    label: 'Results',
    icon: FileClock,
    group: 'analysis',
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
