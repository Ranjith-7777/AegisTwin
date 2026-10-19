import {
  Activity,
  Bot,
  Boxes,
  BrainCircuit,
  Cpu,
  Database,
  FileClock,
  FileBarChart2,
  FlaskConical,
  GitBranch,
  GitCompareArrows,
  Globe,
  House,
  ListChecks,
  Network,
  RadioTower,
  Radar,
  Route,
  ScrollText,
  Settings,
  ShieldAlert,
  ShieldCheck,
  Swords,
  TriangleAlert,
  UsersRound,
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
 * Sidebar information architecture: ten top-level sections in lifecycle
 * order. Sections with more than one route render a sub-navigation strip
 * (see SectionNav), so every page stays one click away.
 */
export const navSections: NavSection[] = [
  {
    id: 'overview',
    label: 'Command Centre',
    icon: House,
    routes: [{ path: '/app', label: 'Command Centre', icon: House }],
  },
  {
    id: 'digital-twin',
    label: 'Digital Twin',
    icon: Boxes,
    routes: [
      { path: '/digital-twin', label: 'Cloud Digital Twin', icon: Boxes },
      { path: '/digital-twin/attack-paths', label: 'Attack Paths', icon: Route },
      { path: '/digital-twin/blast-radius', label: 'Blast Radius', icon: Network },
      { path: '/digital-twin/purple-team', label: 'Purple Team', icon: Swords },
    ],
  },
  {
    id: 'workflow',
    label: 'Workflow & Agents',
    icon: UsersRound,
    routes: [
      { path: '/workflow', label: 'Workflow & Agents', icon: Workflow },
      { path: '/blue-agent/overview', label: 'Blue Agent', icon: Bot },
      { path: '/blue-agent/agent-workflow', label: 'Decision Trace', icon: BrainCircuit },
      { path: '/blue-agent/response-plans', label: 'Response Plans', icon: GitBranch },
      { path: '/blue-agent/policies', label: 'Policies', icon: ListChecks },
      { path: '/blue-agent/verification', label: 'Verification', icon: ShieldCheck },
    ],
  },
  {
    id: 'red-agent',
    label: 'Red Agent',
    icon: Swords,
    routes: [{ path: '/red-agent', label: 'Red Agent', icon: Swords }],
  },
  {
    id: 'incidents',
    label: 'Incidents',
    icon: TriangleAlert,
    routes: [
      { path: '/incidents', label: 'Incidents', icon: ShieldAlert },
      { path: '/telemetry', label: 'Telemetry Replay', icon: RadioTower },
      { path: '/data-sources', label: 'Data Sources', icon: Database },
    ],
  },
  {
    id: 'intelligence',
    label: 'Threat Intelligence',
    icon: Globe,
    routes: [
      { path: '/mitre', label: 'MITRE ATT&CK', icon: ShieldCheck },
      { path: '/predictive-analytics', label: 'Attack Prediction', icon: Radar },
    ],
  },
  {
    id: 'reports',
    label: 'Reports',
    icon: FileBarChart2,
    routes: [
      { path: '/evaluation', label: 'Evaluation', icon: FlaskConical },
      { path: '/evaluation/compare', label: 'Strategy Comparison', icon: GitCompareArrows },
      { path: '/evaluation/experiments', label: 'Experiments & Reports', icon: ScrollText },
      { path: '/evaluation/aggregate', label: 'Aggregate', icon: Activity },
      { path: '/evaluation/batches', label: 'Batches', icon: Boxes },
    ],
  },
  {
    id: 'models',
    label: 'Detection Models',
    icon: Cpu,
    routes: [{ path: '/model-analytics', label: 'Detection Models', icon: Cpu }],
  },
  {
    id: 'audit',
    label: 'Audit Trail',
    icon: FileClock,
    routes: [{ path: '/audit-trail', label: 'Audit Trail', icon: FileClock }],
  },
  {
    id: 'settings',
    label: 'Settings',
    icon: Settings,
    routes: [{ path: '/settings', label: 'Settings', icon: Settings }],
  },
]

export const appRoutes: AppRouteDefinition[] = navSections.flatMap((section) => section.routes)

function matches(routePath: string, pathname: string): boolean {
  return pathname === routePath || pathname.startsWith(`${routePath}/`)
}

/** The section owning `pathname`, by longest matching route prefix. */
export function sectionForPath(pathname: string): NavSection | undefined {
  let best: { section: NavSection; length: number } | undefined
  for (const section of navSections) {
    for (const route of section.routes) {
      if (matches(route.path, pathname) && (!best || route.path.length > best.length)) {
        best = { section, length: route.path.length }
      }
    }
  }
  return best?.section
}

/** The specific route (within its section) that best matches `pathname`. */
export function routeForPath(pathname: string): AppRouteDefinition | undefined {
  let best: AppRouteDefinition | undefined
  for (const route of appRoutes) {
    if (matches(route.path, pathname) && (!best || route.path.length > best.path.length)) {
      best = route
    }
  }
  return best
}
