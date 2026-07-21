import {
  Activity,
  Bot,
  Boxes,
  FileClock,
  LayoutDashboard,
  RadioTower,
  Settings,
  ShieldAlert,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react'

export interface AppRouteDefinition {
  path: string
  label: string
  icon: LucideIcon
}

export const appRoutes: AppRouteDefinition[] = [
  { path: '/', label: 'Overview', icon: LayoutDashboard },
  { path: '/digital-twin', label: 'Digital Twin', icon: Boxes },
  { path: '/telemetry', label: 'Live Telemetry', icon: RadioTower },
  { path: '/incidents', label: 'Active Incidents', icon: ShieldAlert },
  { path: '/mitre', label: 'MITRE ATT&CK', icon: ShieldCheck },
  { path: '/response-centre', label: 'Response Centre', icon: Bot },
  { path: '/audit-trail', label: 'Audit Trail', icon: FileClock },
  { path: '/model-analytics', label: 'Model Analytics', icon: Activity },
  { path: '/settings', label: 'Settings', icon: Settings },
]
